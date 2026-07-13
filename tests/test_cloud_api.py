import sys
from datetime import datetime, timedelta
from pathlib import Path
from types import SimpleNamespace

import numpy as np
from fastapi.testclient import TestClient


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "core"))
sys.path.insert(0, str(ROOT / "generated"))

import cloud_api  # noqa: E402


client = TestClient(cloud_api.app)
AUTH = {"X-API-Key": "test-cloud-secret"}


def _series(count=30, anomaly=False):
    start = datetime(2024, 1, 1)
    values = 50 + np.sin(np.arange(count) / 2)
    if anomaly:
        values[-5] = 150
    return [
        {"date": (start + timedelta(days=index)).isoformat(), "value": float(value)}
        for index, value in enumerate(values)
    ]


def test_health_is_public_but_capabilities_require_auth(monkeypatch):
    monkeypatch.setenv("QLIK_CLOUD_API_KEY", "test-cloud-secret")
    assert client.get("/healthz").json()["status"] == "ok"
    assert client.get("/v1/capabilities").status_code == 401
    response = client.get("/v1/capabilities", headers=AUTH)
    assert response.status_code == 200
    assert "forecast" in response.json()["endpoints"]


def test_cloud_forecast_correlation_and_anomalies(monkeypatch):
    monkeypatch.setenv("QLIK_CLOUD_API_KEY", "test-cloud-secret")
    forecast = client.post(
        "/v1/forecast",
        headers=AUTH,
        json={"series": _series(), "model": "AutoARIMA", "freq": "D", "periods": 3, "level": 90},
    )
    assert forecast.status_code == 200, forecast.text
    assert len(forecast.json()["rows"]) == 3
    assert set(forecast.json()["rows"][0]) == {"date", "forecast", "lower", "upper"}

    correlation = client.post(
        "/v1/correlation", headers=AUTH, json={"x": [1, 2, 3], "y": [2, 4, 6], "method": "pearson"}
    )
    assert correlation.status_code == 200
    assert correlation.json()["value"] == 1.0

    anomalies = client.post(
        "/v1/anomalies",
        headers=AUTH,
        json={"series": _series(40, anomaly=True), "model": "AutoARIMA", "freq": "D", "level": 95},
    )
    assert anomalies.status_code == 200, anomalies.text
    assert any(row["is_anomaly"] == 1 for row in anomalies.json()["rows"])


def test_cloud_responses_supports_structured_output(monkeypatch):
    monkeypatch.setenv("QLIK_CLOUD_API_KEY", "test-cloud-secret")
    calls = []

    class Responses:
        def create(self, **kwargs):
            calls.append(kwargs)
            return SimpleNamespace(output_text='{"risk":"low"}', id="resp-test")

    monkeypatch.setattr(
        cloud_api,
        "_responses_client",
        lambda: SimpleNamespace(responses=Responses()),
    )
    response = client.post(
        "/v1/responses",
        headers=AUTH,
        json={
            "prompts": ["Classify this account"],
            "instructions": "Return the risk",
            "json_schema": {
                "type": "object",
                "properties": {"risk": {"type": "string"}},
                "required": ["risk"],
                "additionalProperties": False,
            },
        },
    )
    assert response.status_code == 200, response.text
    assert response.json()["rows"][0]["response_id"] == "resp-test"
    assert calls[0]["text"]["format"]["strict"] is True
