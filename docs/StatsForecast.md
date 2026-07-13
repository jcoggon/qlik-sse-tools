# StatsForecast

`StatsForecast` exposes Nixtla statistical forecasting models through Qlik. Use it when the series needs a fast statistical forecast and does not require Prophet-specific holiday or regressor handling.

## Function

| Function | Qlik use | Parameters |
| --- | --- | --- |
| `StatsForecast` | Chart expression | date, value, kwargs |
| `StatsForecast_Intervals` | Load script | date, value, kwargs |
| `StatsForecast_Anomalies` | Load script | date, value, kwargs |

Example:

```qlik
<AAI>.StatsForecast(Date, Sum(Sales), 'model=AutoARIMA|freq=MS|periods=12|season_length=12|return=yhat')
```

The date argument must be a Qlik numeric date. The value argument must be numeric. Add future placeholder rows in the Qlik chart or load-script context when the expression should return forecast values for future periods.

## Supported Models

Model names are case-insensitive.

| Model | Typical use |
| --- | --- |
| `AutoARIMA` | General univariate forecasting with automatic ARIMA selection |
| `AutoETS` | Exponential smoothing model selection |
| `AutoTheta` | Theta-method forecasting |
| `AutoCES` | Complex exponential smoothing |
| `MSTL` | Multiple seasonal decomposition; requires `season_length` |
| `Naive` | Last observed value baseline |
| `SeasonalNaive` | Seasonal baseline; requires `season_length` |
| `HistoricAverage` | Historical mean baseline |
| `WindowAverage` | Rolling average baseline |
| `SeasonalWindowAverage` | Seasonal rolling average; requires `season_length` |
| `ADIDA` | Intermittent demand |
| `CrostonClassic` | Intermittent demand |
| `CrostonOptimized` | Intermittent demand |
| `CrostonSBA` | Intermittent demand with bias adjustment |
| `IMAPA` | Intermittent demand |
| `TSB` | Intermittent demand |

## Keyword Arguments

| Argument | Default | Notes |
| --- | --- | --- |
| `model` | `AutoARIMA` | Forecasting model name |
| `freq` | `MS` | Pandas frequency string, such as `D`, `W`, `MS`, `M`, `Q`, or `Y` |
| `periods` | `12` | Number of future rows to forecast |
| `return` | `yhat` | Output type |
| `level` | `95` | Prediction interval level; use semicolon-separated values for multiple levels |
| `season_length` | none | Required by seasonal models such as `MSTL`, `SeasonalNaive`, and `SeasonalWindowAverage` |
| `take_log` | `false` | Log-transform input values before fitting |
| `n_jobs` | `1` | Parallel jobs passed to StatsForecast |
| `debug` | `false` | Writes additional logs |

Additional kwargs are passed to the selected model when supported.

## Return Values

| Return value | Meaning |
| --- | --- |
| `yhat` or `forecast` | Forecast value for future periods |
| `yhat_upper`, `upper`, `hi` | Upper prediction interval |
| `yhat_lower`, `lower`, `lo` | Lower prediction interval |
| `y_then_yhat` | Actuals for historical rows, forecasts for future rows |
| explicit StatsForecast column name | Return a specific column if present |

Historical rows return null for plain forecast outputs and preserve actuals when using `y_then_*` return modes.

## Interval And Anomaly Tables

`StatsForecast_Intervals` returns `date`, `forecast`, `lower`, and `upper` for the requested future periods:

```qlik
ForecastBands:
Extension <AAI>.StatsForecast_Intervals(ForecastInput{Date, Value, Args});
```

`StatsForecast_Anomalies` fits the historical series and returns `date`, `actual`, `expected`, `lower`, `upper`, and numeric `is_anomaly`. An observation is flagged when it falls outside the requested fitted interval.

```qlik
AnomalyRows:
Extension <AAI>.StatsForecast_Anomalies(HistoryInput{Date, Value, Args});
```

## Agent Notes

- Prefer `StatsForecast` for fast demand, inventory, or operational forecasts.
- Prefer `Prophet` when holiday effects, custom seasonalities, or external regressors are central.
- Always set `freq` to match the date grain sent by Qlik.
- Use `season_length=12` for monthly annual seasonality and `season_length=7` for daily weekly seasonality.
- Intermittent-demand models are useful when many historical periods have zero demand.
