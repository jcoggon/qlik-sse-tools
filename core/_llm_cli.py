"""Run the provider's signed-in CLI for a single text-generation request."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import tempfile
from functools import cache
from pathlib import Path
from threading import BoundedSemaphore


class LLMError(RuntimeError):
    """An error safe to return to Qlik callers."""


# A provider must access its OS profile and TLS configuration. Give it no SSE
# credentials, proxy headers, or API-key overrides from the service environment.
_CLI_ENV = frozenset({
    "APPDATA", "COMMONPROGRAMFILES", "COMSPEC", "HOME", "HOMEDRIVE", "HOMEPATH",
    "LANG", "LC_ALL", "LC_CTYPE", "LOCALAPPDATA", "LOGNAME", "PATH", "PATHEXT",
    "PROGRAMDATA", "PROGRAMFILES", "PROGRAMFILES(X86)", "SYSTEMDRIVE", "SYSTEMROOT",
    "USER", "USERNAME", "USERPROFILE", "WINDIR", "XDG_CONFIG_HOME", "XDG_RUNTIME_DIR",
    "DBUS_SESSION_BUS_ADDRESS", "SSL_CERT_FILE", "SSL_CERT_DIR", "NODE_EXTRA_CA_CERTS",
    "HTTPS_PROXY", "HTTP_PROXY", "NO_PROXY",
})


def _limit(name: str, default: int, maximum: int) -> int:
    try:
        value = int(os.environ.get(name, str(default)))
    except ValueError as exc:
        raise LLMError(f"{name} must be an integer.") from exc
    if not 1 <= value <= maximum:
        raise LLMError(f"{name} must be between 1 and {maximum}.")
    return value


def cli_row_limit() -> int:
    return _limit("QLIK_LLM_CLI_MAX_ROWS", 8, 100)


@cache
def _slots(limit: int) -> BoundedSemaphore:
    return BoundedSemaphore(limit)


def _resolve_binary(provider: str) -> str:
    name = f"QLIK_LLM_{provider.upper()}_BIN"
    configured = os.environ.get(name)
    path = Path(configured) if configured else None
    if path is not None and not path.is_absolute():
        raise LLMError(f"{name} must be an absolute executable path.")
    binary = shutil.which(str(path) if path else provider)
    if not binary or (os.name == "nt" and Path(binary).suffix.lower() != ".exe"):
        raise LLMError(f"{provider} executable unavailable. Set {name} to the native binary.")
    return str(Path(binary).resolve())


def _environment(provider: str, workdir: Path) -> dict[str, str]:
    env = {key: value for key, value in os.environ.items() if key.upper() in _CLI_ENV}
    env.update({name: str(workdir) for name in ("TEMP", "TMP", "TMPDIR")})
    profile_var = "CODEX_HOME" if provider == "codex" else "CLAUDE_CONFIG_DIR"
    profile = os.environ.get(f"QLIK_LLM_{profile_var}") or os.environ.get(profile_var)
    if profile:
        if not Path(profile).is_absolute():
            raise LLMError(f"{profile_var} must be an absolute path.")
        env[profile_var] = profile
    return env


def _subprocess_error(provider: str, stderr: str, stdout: str) -> LLMError:
    # Use the CLI's diagnostics for classification only. They can contain prompt
    # content, local paths, or authentication URLs.
    detail = (stderr + "\n" + stdout).lower()
    if any(word in detail for word in ("usage limit", "usage_limit", "rate limit", "rate_limit", "quota", "429")):
        return LLMError(f"{provider} usage limit reached for the shared account.")
    if any(word in detail for word in ("not logged in", "unauthorized", "authentication", "sign in", "login", "401")):
        return LLMError(f"{provider} authentication failed. Sign in as the SSE service account.")
    return LLMError(f"{provider} CLI request failed. Check the executable, login, and configured model on the SSE host.")


def _codex_command(binary: str, workdir: Path, model: str | None, schema: dict | None) -> list[str]:
    command = [
        binary, "-a", "never", "exec", "--ephemeral", "--ignore-user-config", "--ignore-rules",
        "--skip-git-repo-check", "--sandbox", "read-only", "--json",
        "--disable", "shell_tool", "--disable", "unified_exec", "--disable", "plugins",
        "--disable", "hooks", "--disable", "memories", "--disable", "image_generation",
        "--disable", "multi_agent", "--disable", "multi_agent_v2", "--disable", "request_permissions_tool",
        "-c", 'web_search="disabled"', "-c", "mcp_servers={}",
        "-c", "project_doc_max_bytes=0", "-c", 'forced_login_method="chatgpt"',
        "-c", f"log_dir={json.dumps(str(workdir))}",
        "--output-last-message", str(workdir / "response.txt"),
    ]
    # A fresh SQLite directory triggers a history backfill from CODEX_HOME on
    # every call. Keep the CLI's state in the dedicated profile or on a service volume.
    if state_dir := os.environ.get("QLIK_LLM_CODEX_STATE_DIR"):
        if not Path(state_dir).is_absolute():
            raise LLMError("QLIK_LLM_CODEX_STATE_DIR must be an absolute path.")
        command += ["-c", f"sqlite_home={json.dumps(state_dir)}"]
    if model:
        command += ["--model", model]
    if schema is not None:
        schema_path = workdir / "schema.json"
        schema_path.write_text(json.dumps(schema), encoding="utf-8")
        command += ["--output-schema", str(schema_path)]
    return command + ["-"]


def _claude_command(binary: str, model: str | None, schema: dict | None) -> list[str]:
    command = [
        binary, "-p", "--output-format", "json", "--tools", "", "--disable-slash-commands",
        "--no-session-persistence", "--strict-mcp-config", "--setting-sources", "",
        "--settings", '{"disableAllHooks":true}', "--permission-mode", "dontAsk",
        "--max-turns", "1",
    ]
    if model:
        command += ["--model", model]
    if schema is not None:
        command += ["--json-schema", json.dumps(schema)]
    return command


def cli_text(
    provider: str, prompt: str, *, model: str | None = None, instructions: str | None = None,
    schema: dict | None = None, max_tokens: int | None = None,
) -> str:
    binary = _resolve_binary(provider)
    timeout = _limit("QLIK_LLM_CLI_TIMEOUT_SECONDS", 90, 600)
    slots = _slots(_limit("QLIK_LLM_CLI_CONCURRENCY", 1, 8))
    if not slots.acquire(blocking=False):
        raise LLMError("The shared CLI backend is busy. Retry later.")
    try:
        with tempfile.TemporaryDirectory(prefix="qlik-llm-") as tempdir:
            workdir = Path(tempdir)
            # Use separate boundaries for administrator/user instructions and row data.
            task = {"instructions": instructions, "input": prompt}
            if max_tokens is not None:
                task["suggested_max_output_tokens"] = max_tokens
            payload = (
                "Complete the text generation task described in this JSON. Use only the supplied data. "
                "Return the answer directly.\n" + json.dumps(task, ensure_ascii=False)
            )
            if provider == "codex":
                command = _codex_command(binary, workdir, model, schema)
            else:
                command = _claude_command(binary, model, schema)
            result = subprocess.run(
                command, cwd=workdir, env=_environment(provider, workdir), input=payload,
                capture_output=True, encoding="utf-8", errors="replace", timeout=timeout, check=False,
            )
            if result.returncode:
                raise _subprocess_error(provider, result.stderr, result.stdout)
            if provider == "codex":
                output_file = workdir / "response.txt"
                output = output_file.read_text(encoding="utf-8").strip() if output_file.is_file() else ""
            else:
                envelope = json.loads(result.stdout)
                if envelope.get("is_error") or envelope.get("subtype") != "success":
                    raise _subprocess_error(provider, result.stderr, result.stdout)
                output = envelope.get("result", "") if schema is None else json.dumps(
                    envelope["structured_output"], ensure_ascii=False,
                )
            if not isinstance(output, str) or not output.strip():
                raise LLMError(f"{provider} CLI returned no text.")
            if schema is not None:
                json.loads(output)
            return output
    except subprocess.TimeoutExpired:
        raise LLMError(f"{provider} CLI timed out after {timeout} seconds.") from None
    except (OSError, ValueError, KeyError, AttributeError):
        raise LLMError(f"{provider} CLI returned an unreadable result.") from None
    finally:
        slots.release()
