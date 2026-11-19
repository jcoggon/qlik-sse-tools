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
    import openai

    fake_responses = FakeResponses()
    fake_client = SimpleNamespace(responses=fake_responses)
    monkeypatch.setattr(openai, "OpenAI", lambda **kwargs: fake_client)
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


def _bundle(rows):
    return [SSE.BundledRows(rows=[SSE.Row(duals=[SSE.Dual(strData=value) for value in row]) for row in rows])]


def test_codex_bulk_uses_shared_backend_without_azure(monkeypatch):
    monkeypatch.setenv("QLIK_LLM_RESPONSES_BACKEND", "codex_cli")
    monkeypatch.setenv("QLIK_LLM_CODEX_MODEL", "configured-model")
    monkeypatch.delenv("AZURE_OPENAI_API_KEY", raising=False)
    calls = []

    def generate(provider, prompt, **options):
        calls.append((provider, prompt, options))
        return prompt.upper()

    monkeypatch.setattr(_llm, "cli_text", generate)
    context = Context()
    result = _llm.LLMForQlik(_bundle([
        ("a", "one", "system_prompt=Use upper case,debug=true"), ("b", "two", ""),
    ]), context).response(load_script=True)

    assert result.values.tolist() == [["a", "one", "ONE"], ["b", "two", "TWO"]]
    assert [call[:2] for call in calls] == [("codex", "one"), ("codex", "two")]
    assert calls[0][2]["model"] == "configured-model"
    assert calls[0][2]["instructions"] == "Use upper case"
    description = SSE.TableDescription.FromString(context.metadata[0][1])
    assert [field.name for field in description.fields] == ["key", "prompt", "response"]


def test_codex_rejects_state_and_large_bundles_before_launch(monkeypatch):
    monkeypatch.setenv("QLIK_LLM_RESPONSES_BACKEND", "codex_cli")
    monkeypatch.setenv("QLIK_LLM_CLI_MAX_ROWS", "1")

    def unexpected(*args, **kwargs):
        raise AssertionError("CLI must not launch")

    monkeypatch.setattr(_llm, "cli_text", unexpected)
    too_many = _llm.LLMForQlik(_bundle([("one", ""), ("two", "")]), Context()).response()
    assert all("at most 1 rows" in row for row in too_many)
    stateful = _llm.LLMForQlik(_bundle([("one", "store=true")]), Context()).response()
    assert "stateless" in stateful.iloc[0]


def test_native_openai_responses_uses_public_endpoint(monkeypatch):
    import openai

    monkeypatch.setenv("QLIK_LLM_RESPONSES_BACKEND", "openai")
    monkeypatch.setenv("OPENAI_API_KEY", "unit-test-only")
    monkeypatch.setenv("OPENAI_MODEL", "selected-model")
    fake = FakeResponses()

    def new_client(**options):
        assert options["base_url"] == "https://api.openai.com/v1"
        return SimpleNamespace(responses=fake)

    monkeypatch.setattr(openai, "OpenAI", new_client)
    result = _llm.LLMForQlik(_bundle([("sample", "")]), Context()).response()
    assert result.tolist() == ['{"risk":"low"}']
    assert fake.kwargs["model"] == "selected-model"
