"""Exercise real frozen SDK serialization and parsing without paid network calls."""

import json
import sys
from pathlib import Path
from urllib.parse import urlsplit

import anthropic
import httpx2 as httpx
import openai
import pytest
import requests
from firecrawl import Firecrawl

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "core"), str(ROOT / "generated")]
import _firecrawl  # noqa: E402
import _llm  # noqa: E402
import ServerSideExtension_pb2 as SSE  # noqa: E402


def request(*values):
    return [SSE.BundledRows(rows=[SSE.Row(duals=[SSE.Dual(strData=v) for v in values])])]


@pytest.mark.parametrize("method", ["chat", "response"])
def test_azure_openai_real_sdk_contract(monkeypatch, method):
    seen = []

    def respond(req):
        seen.append(req)
        if method == "chat":
            data = {"id": "chat_1", "object": "chat.completion", "created": 1, "model": "deployment",
                    "choices": [{"index": 0, "message": {"role": "assistant", "content": "qualified"}, "finish_reason": "stop"}]}
        else:
            data = {"id": "resp_1", "object": "response", "created_at": 1, "status": "completed",
                    "output": [{"type": "message", "id": "msg_1", "role": "assistant", "status": "completed",
                                "content": [{"type": "output_text", "text": "qualified", "annotations": []}]}]}
        return httpx.Response(200, json=data)

    with httpx.Client(transport=httpx.MockTransport(respond)) as http:
        monkeypatch.setenv("AZURE_OPENAI_API_KEY", "offline-test-key")
        monkeypatch.setenv("AZURE_OPENAI_ENDPOINT", "https://azure.example.invalid")
        monkeypatch.setenv("AZURE_OPENAI_DEPLOYMENT", "deployment")
        monkeypatch.setattr(_llm, "AzureOpenAI", lambda **kw: openai.AzureOpenAI(**kw, http_client=http, max_retries=0))
        monkeypatch.setattr(_llm, "OpenAI", lambda **kw: openai.OpenAI(**kw, http_client=http, max_retries=0))
        tool = _llm.LLMForQlik(request("Synthetic prompt", "max_tokens=123,system_prompt=Be concise"), None)
        assert getattr(tool, method)().tolist() == ["qualified"]
    req = seen[0]
    body = json.loads(req.content)
    assert body["model"] == "deployment"
    if method == "chat":
        assert req.url.path == "/openai/deployments/deployment/chat/completions"
        assert req.url.params["api-version"]
        assert body["max_completion_tokens"] == 123
    else:
        assert req.url.path == "/openai/v1/responses"
        assert body["max_output_tokens"] == 123
        assert body["instructions"] == "Be concise"
        assert body["store"] is False


@pytest.mark.parametrize("temperature", [None, "0.2"])
def test_foundry_anthropic_real_sdk_contract(monkeypatch, temperature):
    seen = []

    def respond(req):
        seen.append(req)
        return httpx.Response(200, json={"id": "msg_1", "type": "message", "role": "assistant", "model": "deployment",
                                        "content": [{"type": "thinking", "thinking": "synthetic", "signature": "offline"},
                                                    {"type": "text", "text": "quali"}, {"type": "text", "text": "fied"}], "stop_reason": "end_turn",
                                        "usage": {"input_tokens": 1, "output_tokens": 1}})

    original = anthropic.Anthropic
    with httpx.Client(transport=httpx.MockTransport(respond)) as http:
        monkeypatch.setenv("AZURE_FOUNDRY_API_KEY", "offline-test-key")
        monkeypatch.setenv("AZURE_FOUNDRY_CLAUDE_API_ENDPOINT", "https://foundry.example.invalid/anthropic/")
        monkeypatch.setenv("AZURE_CLAUDE_SONNET", "deployment")
        monkeypatch.setattr(anthropic, "Anthropic", lambda **kw: original(**kw, http_client=http, max_retries=0))
        args = "max_tokens=123,system_prompt=Be concise"
        if temperature is not None:
            args += ",temperature=" + temperature
        tool = _llm.ClaudeForQlik(request("Synthetic prompt", args), None)
        assert tool.chat().tolist() == ["qualified"]
    assert seen[0].url.path == "/anthropic/v1/messages"
    assert seen[0].headers["api-version"] == "2024-05-01-preview"
    assert seen[0].headers["anthropic-version"] == "2023-06-01"
    assert json.loads(seen[0].content)["temperature"] == (0.7 if temperature is None else float(temperature))
    assert json.loads(seen[0].content)["max_tokens"] == 123


@pytest.mark.parametrize("operation", ["scrape", "search", "extract", "agent", "failure"])
def test_firecrawl_real_sdk_contract(monkeypatch, operation):
    seen = []

    def send(session, req, **kwargs):
        seen.append(req)
        path = urlsplit(req.url).path
        response = requests.Response()
        response.status_code = 200
        if operation == "failure":
            response.status_code = 401
            data = {"success": False, "error": "Invalid synthetic key"}
        elif path == "/v2/scrape":
            data = {"success": True, "data": {"markdown": "qualified"}}
        elif path == "/v2/search":
            data = {"success": True, "data": {"web": [{"url": "https://example.invalid", "title": "qualified"}]}}
        elif req.method == "POST":
            data = {"success": True, "id": "offline-job"}
        else:
            data = {"success": True, "id": "offline-job", "status": "completed", "data": {"result": "qualified"}}
        response._content = json.dumps(data).encode()
        response.headers["Content-Type"] = "application/json"
        response.request = req
        response.url = req.url
        return response

    monkeypatch.setattr(requests.Session, "send", send)
    tool = _firecrawl.FirecrawlForQlik([], None)
    tool.client = Firecrawl(api_key="offline-test-key", api_url="https://firecrawl.example.invalid", max_retries=0)
    tool.request_df = _firecrawl.pd.DataFrame({"source": ["https://example.invalid"], "kwargs": [""]})
    tool._set_params("format=markdown,pdf_mode=ocr,pdf_max_pages=2,limit=3,max_credits=10,model=spark-2")
    if operation == "failure":
        with pytest.raises(Exception, match="synthetic key"):
            tool._scrape_url("https://example.invalid")
    elif operation == "scrape":
        assert tool._scrape_url("https://example.invalid") == "qualified"
        assert json.loads(seen[0].body)["parsers"] == [{"type": "pdf", "mode": "ocr", "maxPages": 2}]
    elif operation == "search":
        assert json.loads(tool._search_web("synthetic query"))["web"][0]["title"] == "qualified"
        assert json.loads(seen[0].body)["limit"] == 3
    elif operation == "extract":
        assert json.loads(tool._extract_from_url("https://example.invalid", "Extract result")) == {"result": "qualified"}
        assert any(urlsplit(req.url).path == "/v2/extract" for req in seen)
    else:
        assert json.loads(tool._run_agent("https://example.invalid", "Extract result"))["data"] == {"result": "qualified"}
        assert json.loads(seen[0].body)["maxCredits"] == 10
    assert seen
    assert all(urlsplit(req.url).hostname == "firecrawl.example.invalid" for req in seen)


@pytest.mark.parametrize("provider", ["openai", "claude"])
def test_local_document_extraction_uses_real_sdk_contract(monkeypatch, provider):
    seen = []

    def respond(req):
        seen.append(req)
        if provider == "openai":
            data = {"id": "chat_1", "object": "chat.completion", "created": 1, "model": "deployment",
                    "choices": [{"index": 0, "message": {"role": "assistant", "content": '{"value":1}'}, "finish_reason": "stop"}]}
        else:
            data = {"id": "msg_1", "type": "message", "role": "assistant", "model": "deployment",
                    "content": [{"type": "text", "text": '{"value":1}'}], "stop_reason": "end_turn",
                    "usage": {"input_tokens": 1, "output_tokens": 1}}
        return httpx.Response(200, json=data)

    azure, claude = openai.AzureOpenAI, anthropic.Anthropic
    with httpx.Client(transport=httpx.MockTransport(respond)) as http:
        monkeypatch.setenv("AZURE_OPENAI_API_KEY", "offline-test-key")
        monkeypatch.setenv("AZURE_OPENAI_ENDPOINT", "https://azure.example.invalid")
        monkeypatch.setenv("AZURE_FOUNDRY_API_KEY", "offline-test-key")
        monkeypatch.setenv("AZURE_FOUNDRY_CLAUDE_API_ENDPOINT", "https://foundry.example.invalid/anthropic/")
        monkeypatch.setattr(openai, "AzureOpenAI", lambda **kw: azure(**kw, http_client=http, max_retries=0))
        monkeypatch.setattr(anthropic, "Anthropic", lambda **kw: claude(**kw, http_client=http, max_retries=0))
        tool = _firecrawl.FirecrawlForQlik([], None)
        call = tool._call_openai_for_extraction if provider == "openai" else tool._call_claude_for_extraction
        assert json.loads(call("Extract JSON", "Synthetic content")) == {"value": 1}
    body = json.loads(seen[0].content)
    if provider == "openai":
        assert body["max_completion_tokens"] == 4096
    else:
        assert seen[0].headers["anthropic-version"] == "2023-06-01"
        assert body["temperature"] == 0.1
