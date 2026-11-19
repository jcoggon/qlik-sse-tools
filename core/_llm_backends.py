"""Server-configured model clients shared by SSE, REST and document extraction."""

from __future__ import annotations

import os
import re
from dataclasses import dataclass

try:
    from ._llm_cli import LLMError
except ImportError:  # The standalone SSE launcher imports modules directly.
    from _llm_cli import LLMError


@dataclass(frozen=True)
class Generation:
    prompt: str
    instructions: str | None = None
    max_tokens: int = 2048
    temperature: float | None = None
    schema: dict | None = None
    schema_name: str = "qlik_response"
    store: bool = False
    previous_response_id: str | None = None


def _required(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        raise LLMError(f"Set {name} on the SSE host.")
    return value


def responses_backend() -> str:
    return os.environ.get("QLIK_LLM_RESPONSES_BACKEND", "azure_openai").strip().lower()


def openai_model(backend: str) -> str:
    if backend == "openai":
        return _required("OPENAI_MODEL")
    if backend == "azure_openai":
        return os.environ.get("AZURE_OPENAI_DEPLOYMENT", "gpt-4o")
    raise LLMError("The OpenAI API backend must be azure_openai or openai.")


def openai_client(backend: str, *, responses: bool = True):
    from openai import AzureOpenAI, OpenAI

    if backend == "openai":
        return OpenAI(api_key=_required("OPENAI_API_KEY"), base_url="https://api.openai.com/v1", timeout=60, max_retries=1)
    if backend != "azure_openai":
        raise LLMError("The OpenAI API backend must be azure_openai or openai.")
    key = _required("AZURE_OPENAI_API_KEY")
    if responses:
        base_url = os.environ.get("AZURE_OPENAI_RESPONSES_BASE_URL")
        if not base_url:
            base_url = _required("AZURE_OPENAI_ENDPOINT").rstrip("/") + "/openai/v1/"
        return OpenAI(api_key=key, base_url=base_url, timeout=60, max_retries=1)
    return AzureOpenAI(
        api_key=key, azure_endpoint=_required("AZURE_OPENAI_ENDPOINT"),
        api_version=os.environ.get("AZURE_OPENAI_API_VERSION", "2025-11-01-preview"),
        timeout=60, max_retries=1,
    )


def api_response(client, model: str, request: Generation) -> tuple[str, str | None]:
    options = {
        "model": model, "input": request.prompt, "max_output_tokens": request.max_tokens, "store": request.store,
    }
    if request.instructions:
        options["instructions"] = request.instructions
    if request.previous_response_id:
        options["previous_response_id"] = request.previous_response_id
    if request.temperature is not None:
        options["temperature"] = request.temperature
    if request.schema is not None:
        options["text"] = {"format": {
            "type": "json_schema", "name": request.schema_name, "schema": request.schema, "strict": True,
        }}
    response = client.responses.create(**options)
    status = getattr(response, "status", None)
    if status and status != "completed":
        raise LLMError(f"Responses API returned status {status}.")
    if not response.output_text:
        raise LLMError("Responses API returned no text or declined the request.")
    return response.output_text, getattr(response, "id", None)


def claude_backend() -> str:
    return os.environ.get("QLIK_LLM_CLAUDE_BACKEND", "foundry").strip().lower()


def claude_model(backend: str, model: str | None = None) -> str:
    name = model or "sonnet"
    family = name.casefold()
    if family not in {"haiku", "sonnet", "opus"}:
        return name
    if backend == "claude_cli":
        return name if model else os.environ.get("QLIK_LLM_CLAUDE_MODEL", "sonnet")
    if backend == "anthropic":
        defaults = {"haiku": "claude-haiku-5-5", "sonnet": "claude-sonnet-5-5", "opus": "claude-opus-5-5"}
        return os.environ.get(f"ANTHROPIC_{family.upper()}_MODEL", defaults[family])
    if backend == "foundry":
        # Existing installations can use custom Foundry deployment names.
        return os.environ.get(f"AZURE_CLAUDE_{family.upper()}", name)
    raise LLMError("QLIK_LLM_CLAUDE_BACKEND must be foundry, anthropic or claude_cli.")


def claude_client(backend: str):
    import anthropic

    if backend == "anthropic":
        return anthropic.Anthropic(
            api_key=_required("ANTHROPIC_API_KEY"), base_url="https://api.anthropic.com", timeout=60, max_retries=1,
        )
    if backend == "foundry":
        return anthropic.AnthropicFoundry(
            api_key=_required("AZURE_FOUNDRY_API_KEY"),
            base_url=_required("AZURE_FOUNDRY_CLAUDE_API_ENDPOINT"),
            default_headers={"anthropic-version": "2023-06-01"},
            timeout=60, max_retries=1,
        )
    raise LLMError("QLIK_LLM_CLAUDE_BACKEND must be foundry, anthropic or claude_cli.")


def claude_api_text(client, backend: str, model: str, request: Generation) -> str:
    options = {
        "model": model, "messages": [{"role": "user", "content": request.prompt}], "max_tokens": request.max_tokens,
    }
    if request.instructions:
        options["system"] = request.instructions
    # New Claude models reject sampling parameters. Foundry deployment names
    # can obscure the model version, so support a server-level override there.
    unsupported_sampling = re.match(r"claude-(?:haiku|sonnet|opus|fable|mythos)-5(?:-|$)", model.casefold())
    unsupported_sampling = unsupported_sampling or model.casefold().startswith(("claude-opus-4-7", "claude-opus-4-8"))
    if (request.temperature is not None and not unsupported_sampling
            and os.environ.get("QLIK_LLM_CLAUDE_SAMPLING", "true").lower() == "true"):
        options["extra_body"] = {"temperature": request.temperature}
    if backend == "foundry":
        options["extra_headers"] = {"api-version": os.environ.get("AZURE_FOUNDRY_API_VERSION", "2024-05-01-preview")}
    response = client.messages.create(**options)
    text = "".join(block.text for block in response.content if block.type == "text")
    if not text or response.stop_reason in {"max_tokens", "refusal"}:
        raise LLMError("Claude returned no complete text response.")
    return text


def gemini_text(request: Generation) -> str:
    model = _required("GEMINI_MODEL")
    if not re.fullmatch(r"[a-zA-Z0-9_.-]+", model):
        raise LLMError("GEMINI_MODEL must be a model ID, without a URL or models/ prefix.")
    config = {"maxOutputTokens": request.max_tokens}
    if request.temperature is not None:
        config["temperature"] = request.temperature
    if request.schema is not None:
        config.update(responseMimeType="application/json", responseJsonSchema=request.schema)
    body = {"contents": [{"role": "user", "parts": [{"text": request.prompt}]}], "generationConfig": config}
    if request.instructions:
        body["systemInstruction"] = {"parts": [{"text": request.instructions}]}
    data = _post_json(
        "Gemini", f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent",
        body, {"x-goog-api-key": _required("GEMINI_API_KEY")},
    )
    candidate = next(iter(data.get("candidates", [])), {})
    text = "".join(part.get("text", "") for part in candidate.get("content", {}).get("parts", []) if not part.get("thought"))
    if not text or candidate.get("finishReason") not in {None, "STOP"}:
        raise LLMError("Gemini returned no complete text response.")
    return text


def ollama_text(request: Generation) -> str:
    base_url = os.environ.get("OLLAMA_BASE_URL", "http://127.0.0.1:11434").rstrip("/")
    messages = [{"role": "system", "content": request.instructions}] if request.instructions else []
    messages.append({"role": "user", "content": request.prompt})
    options = {"num_predict": request.max_tokens}
    if request.temperature is not None:
        options["temperature"] = request.temperature
    body = {"model": _required("OLLAMA_MODEL"), "messages": messages, "options": options, "stream": False}
    if request.schema is not None:
        body["format"] = request.schema
    data = _post_json("Ollama", base_url + "/api/chat", body)
    text = data.get("message", {}).get("content")
    if not text or data.get("done_reason") == "length":
        raise LLMError("Ollama returned no complete text response.")
    return text


def _post_json(provider: str, url: str, body: dict, headers: dict | None = None) -> dict:
    import requests

    try:
        response = requests.post(url, json=body, headers=headers, timeout=(5, 60), allow_redirects=False)
        if not response.ok or response.is_redirect:
            raise LLMError(f"{provider} API returned HTTP {response.status_code}.")
        return response.json()
    except (requests.RequestException, ValueError):
        raise LLMError(f"{provider} API request failed.") from None
