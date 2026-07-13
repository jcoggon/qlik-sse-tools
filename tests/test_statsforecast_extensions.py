import sys
from pathlib import Path

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "core"))
sys.path.insert(0, str(ROOT / "generated"))

import ServerSideExtension_pb2 as SSE  # noqa: E402
from _statsforecast import StatsForecastForQlik  # noqa: E402


class Context:
    def send_initial_metadata(self, metadata):
        self.metadata = metadata


def _qlik_date(value):
    return (pd.Timestamp(value) - pd.Timestamp("1899-12-30")).days


def _request(values, kwargs):
    rows = [
        SSE.Row(
            duals=[
                SSE.Dual(numData=float(_qlik_date(date))),
                SSE.Dual(numData=float(value)),
                SSE.Dual(strData=kwargs),
            ]
        )
        for date, value in values
    ]
    return [SSE.BundledRows(rows=rows)]


def test_forecast_intervals_return_a_typed_future_table():
    dates = pd.date_range("2023-01-01", periods=24, freq="MS")
    values = [(date, 100 + index * 2 + np.sin(index)) for index, date in enumerate(dates)]
    values.extend((dates[-1] + pd.DateOffset(months=index), 0) for index in range(1, 4))
    context = Context()
    predictor = StatsForecastForQlik(
        _request(values, "model=AutoARIMA|freq=MS|periods=3|level=90"), context
    )

    result = predictor.forecast_table()

    assert list(result.columns) == ["date", "forecast", "lower", "upper"]
    assert len(result) == 3
    assert (result["lower"] <= result["forecast"]).all()
    assert (result["forecast"] <= result["upper"]).all()
    assert context.metadata


def test_anomaly_detection_returns_fitted_bounds_and_flags():
    dates = pd.date_range("2024-01-01", periods=40, freq="D")
    series = 50 + np.sin(np.arange(40) / 2)
    series[30] = 150
    context = Context()
    predictor = StatsForecastForQlik(
        _request(zip(dates, series), "model=AutoARIMA|freq=D|level=95"), context
    )

    result = predictor.anomaly_table()

    assert list(result.columns) == ["date", "actual", "expected", "lower", "upper", "is_anomaly"]
    assert len(result) == 40
    assert set(result["is_anomaly"].unique()).issubset({0.0, 1.0})
    assert result["is_anomaly"].sum() >= 1
    assert context.metadata
