import base64
import json
import sys
from pathlib import Path
from types import SimpleNamespace


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "core"))
sys.path.insert(0, str(ROOT / "generated"))

import ServerSideExtension_pb2 as SSE  # noqa: E402
import _llm  # noqa: E402


class Context:
    def send_initial_metadata(self, metadata):
        self.metadata = metadata


class FakeResponses:
    def __init__(self):
        self.kwargs = None

    def create(self, **kwargs):
        self.kwargs = kwargs
        return SimpleNamespace(output_text='{"risk":"low"}')


def test_responses_api_supports_strict_json_schema(monkeypatch):
    fake_responses = FakeResponses()
    fake_client = SimpleNamespace(responses=fake_responses)
    monkeypatch.setattr(_llm, "AzureOpenAI", lambda **kwargs: SimpleNamespace())
    monkeypatch.setattr(_llm, "OpenAI", lambda **kwargs: fake_client)
    monkeypatch.setenv("AZURE_OPENAI_API_KEY", "test-key")
    monkeypatch.setenv("AZURE_OPENAI_ENDPOINT", "https://example.openai.azure.com")

    schema = {
        "type": "object",
        "properties": {"risk": {"type": "string", "enum": ["low", "high"]}},
        "required": ["risk"],
        "additionalProperties": False,
    }
    encoded = base64.urlsafe_b64encode(json.dumps(schema).encode()).decode().rstrip("=")
    kwargs = (
        "system_prompt=Classify risk,max_tokens=100,store=true,"
        f"json_schema_name=risk_result,json_schema_b64={encoded}"
    )
    request = [
        SSE.BundledRows(
            rows=[SSE.Row(duals=[SSE.Dual(strData="A stable account"), SSE.Dual(strData=kwargs)])]
        )
    ]

    result = _llm.LLMForQlik(request, Context()).response()

    assert result.tolist() == ['{"risk":"low"}']
    assert fake_responses.kwargs["instructions"] == "Classify risk"
    assert fake_responses.kwargs["max_output_tokens"] == 100
    assert fake_responses.kwargs["store"] is True
    assert fake_responses.kwargs["text"]["format"]["schema"] == schema
    assert "temperature" not in fake_responses.kwargs
