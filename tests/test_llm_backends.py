import json
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "core"), str(ROOT / "generated")]

import _llm_backends as backends  # noqa: E402
import _llm_cli as cli  # noqa: E402
from _firecrawl import FirecrawlForQlik  # noqa: E402


SCHEMA = {
    "type": "object",
    "properties": {"label": {"type": "string"}},
    "required": ["label"],
    "additionalProperties": False,
}


def test_codex_uses_stdin_clean_environment_and_temporary_directory(monkeypatch, tmp_path):
    monkeypatch.setattr(cli, "_resolve_binary", lambda provider: "codex")
    monkeypatch.setenv("OPENAI_API_KEY", "test-api-key")
    monkeypatch.setenv("QLIK_CLOUD_API_KEY", "test-sse-key")
    state = tmp_path / "persistent-state"
    monkeypatch.setenv("QLIK_LLM_CODEX_STATE_DIR", str(state))
    observed = []

    def run(command, **options):
        temp = options["cwd"]
        observed.append(temp)
        assert "sample prompt" not in command
        assert json.loads(options["input"].splitlines()[-1])["input"] == "sample prompt"
        assert "OPENAI_API_KEY" not in options["env"]
        assert "QLIK_CLOUD_API_KEY" not in options["env"]
        assert command[-1] == "-"
        assert "--ignore-user-config" in command and "--ephemeral" in command
        assert "shell_tool" in command and "mcp_servers={}" in command
        assert f"sqlite_home={json.dumps(str(state))}" in command
        assert json.loads((temp / "schema.json").read_text()) == SCHEMA
        (temp / "response.txt").write_text('{"label":"test"}', encoding="utf-8")
        return subprocess.CompletedProcess(command, 0, "event noise", "")

    monkeypatch.setattr(cli.subprocess, "run", run)
    assert json.loads(cli.cli_text("codex", "sample prompt", schema=SCHEMA)) == {"label": "test"}
    assert not observed[0].exists()


def test_cli_failure_and_timeout_are_redacted_and_release_capacity(monkeypatch):
    monkeypatch.setattr(cli, "_resolve_binary", lambda provider: "codex")
    monkeypatch.setenv("QLIK_LLM_CLI_CONCURRENCY", "1")
    monkeypatch.setenv("QLIK_LLM_CLI_TIMEOUT_SECONDS", "1")
    run = Mock(side_effect=[
        subprocess.TimeoutExpired("codex", 1, stderr="private diagnostic"),
        subprocess.CompletedProcess("codex", 1, "", "401 private diagnostic"),
        subprocess.CompletedProcess("codex", 1, "", "usage_limit_reached private diagnostic"),
    ])
    monkeypatch.setattr(cli.subprocess, "run", run)
    for expected in ("timed out", "authentication failed", "usage limit reached"):
        with pytest.raises(cli.LLMError, match=expected) as error:
            cli.cli_text("codex", "sample prompt")
        assert "private diagnostic" not in str(error.value)


def test_claude_cli_parses_structured_output_without_tools(monkeypatch):
    monkeypatch.setattr(cli, "_resolve_binary", lambda provider: "claude")

    def run(command, **options):
        assert command[command.index("--tools") + 1] == ""
        assert "--strict-mcp-config" in command and "--no-session-persistence" in command
        assert "CLAUDE_CODE_ENTRYPOINT" not in options["env"]
        return subprocess.CompletedProcess(command, 0, json.dumps({
            "type": "result", "subtype": "success", "structured_output": {"label": "test"},
        }), "")

    monkeypatch.setattr(cli.subprocess, "run", run)
    assert json.loads(cli.cli_text("claude", "sample prompt", schema=SCHEMA)) == {"label": "test"}


def test_claude_messages_uses_text_blocks_and_modern_sampling_rules(monkeypatch):
    monkeypatch.delenv("QLIK_LLM_CLAUDE_SAMPLING", raising=False)
    create = Mock(return_value=SimpleNamespace(content=[
        SimpleNamespace(type="thinking"), SimpleNamespace(type="text", text="hello"),
        SimpleNamespace(type="text", text=" world"),
    ], stop_reason="end_turn"))
    client = SimpleNamespace(messages=SimpleNamespace(create=create))
    request = backends.Generation("hi", instructions="system instruction", temperature=0.1)
    assert backends.claude_api_text(client, "anthropic", "claude-sonnet-5-5", request) == "hello world"
    assert "extra_body" not in create.call_args.kwargs
    backends.claude_api_text(client, "anthropic", "claude-sonnet-4-6", request)
    assert create.call_args.kwargs["extra_body"]["temperature"] == 0.1
    assert create.call_args.kwargs["system"] == "system instruction"


def test_gemini_and_ollama_request_native_structured_output(monkeypatch):
    monkeypatch.setenv("GEMINI_MODEL", "gemini-selected")
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")
    monkeypatch.setenv("OLLAMA_MODEL", "local-selected")
    monkeypatch.delenv("OLLAMA_BASE_URL", raising=False)
    options = backends.Generation("sample", instructions="summarize", schema=SCHEMA, max_tokens=123)
    post = Mock(side_effect=[
        {"candidates": [{"finishReason": "STOP", "content": {"parts": [{"text": '{"label":"test"}'}]}}]},
        {"done_reason": "stop", "message": {"content": '{"label":"local"}'}},
    ])
    monkeypatch.setattr(backends, "_post_json", post)
    assert json.loads(backends.gemini_text(options)) == {"label": "test"}
    _, url, body, headers = post.call_args.args
    assert url.endswith("/gemini-selected:generateContent")
    assert headers == {"x-goog-api-key": "test-key"}
    assert body["generationConfig"] == {
        "maxOutputTokens": 123, "responseMimeType": "application/json", "responseJsonSchema": SCHEMA,
    }
    assert json.loads(backends.ollama_text(options)) == {"label": "local"}
    _, url, body = post.call_args.args
    assert url == "http://127.0.0.1:11434/api/chat"
    assert body["options"] == {"num_predict": 123}
    assert body["format"] == SCHEMA


def test_firecrawl_extract_routes_without_legacy_fallback(monkeypatch):
    monkeypatch.delenv("FIRECRAWL_EXTRACT_MAX_CREDITS", raising=False)
    service = FirecrawlForQlik([], None)
    service.client = SimpleNamespace(
        scrape=Mock(return_value=SimpleNamespace(json={})),
        agent=Mock(return_value={"data": {"label": "from agent"}, "status": "completed", "success": True}),
    )
    service.schema = SCHEMA
    service.enable_web_search = False
    service.only_main_content = service.timeout = service.pdf_mode = service.pdf_max_pages = None
    service.max_credits = service.agent_model = None
    assert json.loads(service._extract_from_url("https://example.com", "prompt")) == {}
    service.client.agent.assert_not_called()
    service.client.scrape.return_value = SimpleNamespace(json=None)
    with pytest.raises(RuntimeError, match="did not return extracted JSON"):
        service._extract_from_url("https://example.com", "prompt")
    service.client.agent.assert_not_called()

    assert "from agent" in service._extract_from_url("https://example.com/a; https://example.com/b", "prompt")
    assert service.client.agent.call_args.kwargs["strict_constrain_to_urls"] is True
    service.enable_web_search = True
    service._extract_from_url("https://example.com", "prompt")
    assert "strict_constrain_to_urls" not in service.client.agent.call_args.kwargs
    assert service.client.agent.call_args.kwargs["max_credits"] == 100
