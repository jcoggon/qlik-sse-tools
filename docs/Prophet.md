# Prophet Forecasting

This page documents the Prophet server-side extension (SSE) functions exposed to Qlik. It is written for AI agents and automation flows that need to build Qlik expressions or load-script calls from the current runtime capabilities.

Prophet is used for time series forecasting, uncertainty bands, trend and seasonality components, holiday effects, and forecasts with additional numeric regressors.

## Functions

| Function | Qlik call type | Purpose |
| --- | --- | --- |
| `Prophet(date, value, args)` | Scalar chart expression or load script | Standard univariate forecast. |
| `Prophet_Basic(date, value)` | Scalar chart expression | Standard forecast with default settings. |
| `Prophet_Holidays(date, value, holiday_name, args)` | Scalar chart expression or load script | Forecast with named holiday effects. |
| `Prophet_Seasonality(season_value, time_series, holidays, args)` | Scalar chart expression or load script | Return a seasonality component on a requested output scale. |
| `Prophet_Multivariate(date, value, holiday_name, regressors, regressor_args, args)` | Scalar chart expression or load script | Forecast with one or more additional numeric regressors. |
| `Prophet_Seasonality_Multivariate(season_value, time_series, holidays, regressors, regressor_args, args)` | Scalar chart expression or load script | Return seasonality components for a multivariate Prophet model. |

Use the analytic connection name configured in Qlik in place of `<AAI>`.

## Standard Forecast

```qlik
<AAI>.Prophet(DateField, Sum(ValueField), 'freq=MS, return=yhat')
```

The first argument must be a Qlik date or timestamp. Internally Qlik serial dates are converted to pandas datetimes.

The second argument is the measure to forecast. Historical rows must contain numeric values. Future rows must exist in the chart or load table with null values so the SSE can count the requested forecast periods.

The third argument is a string of keyword arguments. Both comma-separated and pipe-separated formats are accepted by the current implementation:

```qlik
'freq=MS, return=yhat, interval_width=0.9'
'freq=MS|return=yhat|interval_width=0.9'
```

For chart expressions, the returned vector has the same row count and row order as the request. For load-script calls, pass `load_script=true` and use `LOAD ... EXTENSION`.

```qlik
ForecastInput:
LOAD
    MonthStart(OrderDate) as ds,
    Sum(Sales) as y,
    'freq=MS, return=all, load_script=true' as args
RESIDENT SalesByMonth
GROUP BY MonthStart(OrderDate);

Forecast:
LOAD *
EXTENSION <AAI>.Prophet(ForecastInput{ds, y, args});
```

## Return Values

Set `return=<column>` in the args string.

Common values:

| Return value | Meaning |
| --- | --- |
| `yhat` | Forecasted value. Default. |
| `yhat_lower` | Lower uncertainty bound. |
| `yhat_upper` | Upper uncertainty bound. |
| `y_then_yhat` | Historical actuals followed by forecast values for future rows. |
| `y_then_yhat_lower` | Null historical values followed by lower forecast bound. |
| `y_then_yhat_upper` | Null historical values followed by upper forecast bound. |
| `trend`, `trend_lower`, `trend_upper` | Trend component. |
| `additive_terms`, `multiplicative_terms` | Combined component effects when present. |
| `weekly`, `yearly`, `daily`, or a custom seasonality name | Specific seasonality component when present. |
| `holidays` or a normalized holiday name | Holiday effect. Holiday names are lowercased, spaces become underscores, and apostrophes are removed. |
| `residual` | Historical actual minus `yhat`; future rows are null. |
| `all` | All Prophet output columns. Use only with `load_script=true`. |

## Key Parameters

| Parameter | Typical values | Notes |
| --- | --- | --- |
| `freq` | `D`, `MS`, `M`, `H`, `T`, `S` | Pandas date frequency used for future rows. Always set this explicitly. |
| `load_script` | `true`, `false` | Return a Qlik load-script table instead of a chart vector. |
| `debug` | `true`, `false` | Writes execution detail to stdout and `logs/Prophet Log <n>.txt`. |
| `take_log` | `true`, `false` | Fits on log-transformed values and returns values on the original scale. |
| `cap` | Numeric | Enables logistic growth with a saturating maximum. |
| `floor` | Numeric | Optional logistic floor. Requires `cap`. |
| `changepoint_prior_scale` | `0.01` to `0.5` | Lower values smooth trend changes; higher values make trend more flexible. |
| `n_changepoints` | Integer | Number of potential trend changepoints. |
| `changepoint_range` | Decimal below `1` | Fraction of history used for changepoint selection. |
| `interval_width` | `0.8`, `0.9`, `0.95` | Width of uncertainty intervals. |
| `uncertainty_samples` | Integer | Simulated draws for uncertainty intervals. |
| `mcmc_samples` | Integer | Use full Bayesian inference when greater than zero. |
| `random_seed` | Integer | Seeds NumPy and is passed to Prophet fit when MCMC is used. |
| `seasonality_mode` | `additive`, `multiplicative` | Global seasonality mode. |
| `add_seasonality` | Name | Adds a custom seasonality. Pair with period and Fourier order. |
| `add_seasonality_mode` | `additive`, `multiplicative` | Mode for the added seasonality. |
| `seasonality_period` | Numeric days | Period for the added seasonality. |
| `seasonality_fourier` | Integer | Fourier order for the added seasonality. |
| `seasonality_prior_scale` | Numeric | Smooths seasonality effects. |
| `holidays_prior_scale` | Numeric | Smooths holiday effects. |
| `lower_window` | Negative integer | Extends holiday effect before the holiday date. |
| `upper_window` | Positive integer | Extends holiday effect after the holiday date. |
| `seasonality` | `yearly`, `weekly`, custom name | Used by seasonality requests. |
| `is_seasonality_request` | `true`, `false` | Forces load-script seasonality output with different cardinality. |
| `weekly_start` | Integer | Offset for weekly seasonality output. |
| `yearly_start` | Integer | Offset for yearly seasonality output. |

## Holidays

Use `Prophet_Holidays` when each date can carry a holiday name.

```qlik
<AAI>.Prophet_Holidays(
    DateField,
    Sum(ValueField),
    HolidayName,
    'freq=D, return=holidays, lower_window=-1, upper_window=1'
)
```

Rows without a holiday should send an empty string or null holiday name. Holiday dates should be included for both historical and future rows when the forecast horizon contains known holidays.

Holiday names are normalized before being passed to Prophet. If an agent wants a specific holiday component back, normalize the requested return value the same way: lower case, replace spaces with underscores, remove apostrophes.

## Additional Regressors

Use `Prophet_Multivariate` when one or more known future numeric variables should influence the forecast.

```qlik
<AAI>.Prophet_Multivariate(
    DateField,
    Sum(ValueField),
    HolidayName,
    Temperature & '|' & CampaignFlag,
    'prior_scale=10, mode=additive|prior_scale=5, mode=multiplicative',
    'freq=D, return=yhat'
)
```

Regressor rules:

- Send all regressors as a single pipe-delimited string in the fourth argument.
- Regressor values must be numeric.
- Regressor values must be available for historical rows and future forecast rows.
- The fifth argument can be empty, one argument set applied to every regressor, or one pipe-delimited argument set per regressor.

Regressor argument keys:

| Key | Values | Notes |
| --- | --- | --- |
| `prior_scale` | Numeric | Strength of the regressor effect. |
| `standardize` | `auto`, `true`, `false` | Whether Prophet should standardize the regressor. |
| `mode` | `additive`, `multiplicative` | Regressor mode. Defaults to the model seasonality mode. |

## Seasonality Outputs

For a normal forecast, agents can request seasonality columns directly when they exist:

```qlik
<AAI>.Prophet(DateField, Sum(ValueField), 'freq=D, return=yearly')
```

Use `Prophet_Seasonality` when the output needs a different row count or a more natural seasonality scale, such as seven rows for weekly seasonality or 365 rows for yearly seasonality.

```qlik
<AAI>.Prophet_Seasonality(
    SeasonValue,
    'QlikDateNumber1:Value1;QlikDateNumber2:Value2',
    'QlikDateNumber1:HolidayName;QlikDateNumber2:HolidayName',
    'freq=D, seasonality=weekly, return=weekly'
)
```

The `time_series` argument is a semicolon-delimited list of `date_number:value` pairs. Use Qlik numeric date values, not formatted date strings. The `holidays` argument uses the same structure with holiday names. Pass an empty string when there are no holidays.

For load-script seasonality output, call `Prophet` or `Prophet_Multivariate` with:

```qlik
'freq=D, load_script=true, is_seasonality_request=true, seasonality=yearly'
```

## Operational Notes

- The current implementation requires at least two non-null historical observations; otherwise it returns null values rather than a forecast.
- Future forecast periods are inferred from trailing null measure values sent by Qlik.
- Duplicate dates may be deduplicated by Prophet internally; the SSE merges results back to the original request dates.
- `return=all` and seasonality requests can produce multiple columns or different cardinality, so use them from the load script.
- Prophet and CmdStanPy use a persistent runtime temp directory. By default this is `qlik-py-env/tmp`; it can be overridden with `QLIK_PY_TOOLS_TEMP_DIR`.
- Use `debug=true` only while building or diagnosing a call because it writes request, input, future, and forecast frames to logs.
- For production reloads, prefer explicit `freq`, explicit return fields, and stable `random_seed` when uncertainty repeatability matters.
