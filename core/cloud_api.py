"""Authenticated REST façade for Qlik Cloud and other HTTPS clients."""

from __future__ import annotations

import hmac
import os
from datetime import datetime
from typing import Any, Literal

import numpy as np
import pandas as pd
from fastapi import Depends, FastAPI, Header, HTTPException, status
from openai import OpenAI
from pydantic import BaseModel, ConfigDict, Field, field_validator
from dotenv import load_dotenv
from statsforecast import StatsForecast

try:
    from ._statsforecast import MODEL_MAP, build_statsforecast_model
    from ._version import __version__
except ImportError:  # Support the launch scripts' top-level module mode.
    from _statsforecast import MODEL_MAP, build_statsforecast_model
    from _version import __version__

load_dotenv()


app = FastAPI(
    title="Qlik Python Tools Cloud API",
    version=__version__,
    docs_url="/docs" if os.environ.get("QLIK_CLOUD_ENABLE_DOCS", "false").lower() == "true" else None,
    redoc_url=None,
)


def _max_rows() -> int:
    return int(os.environ.get("QLIK_CLOUD_MAX_ROWS", "10000"))


def require_api_key(
    authorization: str | None = Header(default=None),
    x_api_key: str | None = Header(default=None),
):
    expected = os.environ.get("QLIK_CLOUD_API_KEY")
    allow_insecure = os.environ.get("QLIK_CLOUD_ALLOW_INSECURE", "false").lower() == "true"
    if not expected:
        if allow_insecure:
            return
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="QLIK_CLOUD_API_KEY is not configured",
        )
    bearer = None
    if authorization and authorization.lower().startswith("bearer "):
        bearer = authorization[7:].strip()
    supplied = x_api_key or bearer or ""
    if not hmac.compare_digest(supplied, expected):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid API key")


class SeriesPoint(BaseModel):
    date: datetime
    value: float


class ForecastRequest(BaseModel):
    series: list[SeriesPoint]
    model: str = "AutoARIMA"
    freq: str = "D"
    periods: int = Field(default=12, ge=1, le=10000)
    level: int = Field(default=95, gt=0, lt=100)
    season_length: int | None = Field(default=None, ge=1)
    model_kwargs: dict[str, Any] = Field(default_factory=dict)

    @field_validator("series")
    @classmethod
    def validate_series(cls, value):
        if len(value) < 2:
            raise ValueError("At least two observations are required")
        if len(value) > _max_rows():
            raise ValueError(f"Series exceeds QLIK_CLOUD_MAX_ROWS={_max_rows()}")
        return value


class AnomalyRequest(BaseModel):
    series: list[SeriesPoint]
    model: str = "AutoARIMA"
    freq: str = "D"
    level: int = Field(default=95, gt=0, lt=100)
    season_length: int | None = Field(default=None, ge=1)
    model_kwargs: dict[str, Any] = Field(default_factory=dict)

    @field_validator("series")
    @classmethod
    def validate_series(cls, value):
        if len(value) < 8:
            raise ValueError("At least eight observations are required")
        if len(value) > _max_rows():
            raise ValueError(f"Series exceeds QLIK_CLOUD_MAX_ROWS={_max_rows()}")
        return value


class CorrelationRequest(BaseModel):
    x: list[float]
    y: list[float]
    method: Literal["pearson", "spearman", "kendall"] = "pearson"

    @field_validator("y")
    @classmethod
    def validate_lengths(cls, value, info):
        x = info.data.get("x", [])
        if len(value) != len(x):
            raise ValueError("x and y must contain the same number of values")
        if len(value) < 2:
            raise ValueError("At least two paired values are required")
        if len(value) > _max_rows():
            raise ValueError(f"Input exceeds QLIK_CLOUD_MAX_ROWS={_max_rows()}")
        return value


class ResponsesRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    prompts: list[str]
    model: str | None = None
    instructions: str | None = None
    max_output_tokens: int = Field(default=2048, ge=1, le=100000)
    store: bool = False
    previous_response_id: str | None = None
    json_schema: dict[str, Any] | None = None
    json_schema_name: str = "qlik_response"

    @field_validator("prompts")
    @classmethod
    def validate_prompts(cls, value):
        if not value or any(not prompt.strip() for prompt in value):
            raise ValueError("At least one non-empty prompt is required")
        if len(value) > min(_max_rows(), 1000):
            raise ValueError("Too many prompts")
        return value


def _series_frame(points: list[SeriesPoint]) -> pd.DataFrame:
    frame = pd.DataFrame({"ds": [p.date for p in points], "y": [p.value for p in points]})
    frame = frame.sort_values("ds").drop_duplicates("ds", keep="last")
    frame.insert(0, "unique_id", "series_1")
    return frame


def _records(frame: pd.DataFrame) -> list[dict[str, Any]]:
    records = []
    for raw in frame.to_dict(orient="records"):
        record = {}
        for key, value in raw.items():
            if isinstance(value, (pd.Timestamp, datetime)):
                value = value.isoformat()
            elif isinstance(value, np.generic):
                value = value.item()
            if isinstance(value, float) and not np.isfinite(value):
                value = None
            record[key] = value
        records.append(record)
    return records


def _responses_client() -> OpenAI:
    base_url = os.environ.get("AZURE_OPENAI_RESPONSES_BASE_URL")
    if not base_url:
        endpoint = os.environ.get("AZURE_OPENAI_ENDPOINT", "").rstrip("/")
        base_url = f"{endpoint}/openai/v1/" if endpoint else None
    if not base_url or not os.environ.get("AZURE_OPENAI_API_KEY"):
        raise HTTPException(status_code=503, detail="Azure/OpenAI Responses API is not configured")
    return OpenAI(api_key=os.environ["AZURE_OPENAI_API_KEY"], base_url=base_url)


@app.get("/healthz")
def healthz():
    return {"status": "ok", "version": __version__}


@app.get("/v1/capabilities", dependencies=[Depends(require_api_key)])
def capabilities():
    return {
        "version": __version__,
        "endpoints": ["forecast", "anomalies", "correlation", "responses"],
        "forecast_models": sorted(MODEL_MAP),
        "max_rows": _max_rows(),
    }


@app.post("/v1/forecast", dependencies=[Depends(require_api_key)])
def forecast(request: ForecastRequest):
    frame = _series_frame(request.series)
    model = build_statsforecast_model(request.model, request.season_length, request.model_kwargs)
    engine = StatsForecast(models=[model], freq=request.freq, n_jobs=1)
    result = engine.forecast(df=frame, h=request.periods, level=[request.level])
    model_name = type(model).__name__
    result = result[["ds", model_name, f"{model_name}-lo-{request.level}", f"{model_name}-hi-{request.level}"]]
    result.columns = ["date", "forecast", "lower", "upper"]
    return {"model": model_name, "level": request.level, "rows": _records(result)}


@app.post("/v1/anomalies", dependencies=[Depends(require_api_key)])
def anomalies(request: AnomalyRequest):
    frame = _series_frame(request.series)
    model = build_statsforecast_model(request.model, request.season_length, request.model_kwargs)
    engine = StatsForecast(models=[model], freq=request.freq, n_jobs=1)
    engine.forecast(df=frame, h=1, level=[request.level], fitted=True)
    result = engine.forecast_fitted_values()
    model_name = type(model).__name__
    lo = f"{model_name}-lo-{request.level}"
    hi = f"{model_name}-hi-{request.level}"
    result = result[["ds", "y", model_name, lo, hi]].copy()
    result.columns = ["date", "actual", "expected", "lower", "upper"]
    result["is_anomaly"] = (
        (result["actual"] < result["lower"]) | (result["actual"] > result["upper"])
    ).astype(int)
    return {"model": model_name, "level": request.level, "rows": _records(result)}


@app.post("/v1/correlation", dependencies=[Depends(require_api_key)])
def correlation(request: CorrelationRequest):
    value = pd.Series(request.x).corr(pd.Series(request.y), method=request.method)
    return {"method": request.method, "value": None if pd.isna(value) else float(value)}


@app.post("/v1/responses", dependencies=[Depends(require_api_key)])
def responses(request: ResponsesRequest):
    client = _responses_client()
    model = request.model or os.environ.get("AZURE_OPENAI_DEPLOYMENT", "gpt-4o")
    results = []
    for prompt in request.prompts:
        kwargs: dict[str, Any] = {
            "model": model,
            "input": prompt,
            "max_output_tokens": request.max_output_tokens,
            "store": request.store,
        }
        if request.instructions:
            kwargs["instructions"] = request.instructions
        if request.previous_response_id:
            kwargs["previous_response_id"] = request.previous_response_id
        if request.json_schema:
            kwargs["text"] = {
                "format": {
                    "type": "json_schema",
                    "name": request.json_schema_name,
                    "schema": request.json_schema,
                    "strict": True,
                }
            }
        response = client.responses.create(**kwargs)
        results.append({"prompt": prompt, "response": response.output_text, "response_id": response.id})
    return {"model": model, "rows": results}
