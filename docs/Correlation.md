# Correlation

This page documents the correlation functions exposed by the Qlik Python SSE.
It is intended as an operational reference for agents building Qlik chart
expressions or load-script calls.

## Capability

The SSE calculates correlation between two numeric series passed as delimited
strings. It supports Pearson, Spearman rank, and Kendall Tau correlation.

Use native Qlik correlation functions when they already satisfy the use case.
Use the SSE when an agent needs a consistent Python implementation or needs to
switch correlation methods dynamically.

## Functions

```qlik
PythonSSE.Pearson(series1, series2)
PythonSSE.Correlation(series1, series2, corr_type)
```

Inputs:

| Parameter | Type | Meaning |
| --- | --- | --- |
| `series1` | string | First numeric series. Values are separated with semicolons. |
| `series2` | string | Second numeric series. Values are separated with semicolons. |
| `corr_type` | string | `pearson`, `spearman`, or `kendall`. Missing or unknown values default to Pearson behavior in the server code path. |

Output:

| Function | Return |
| --- | --- |
| `Pearson` | Numeric correlation as a scalar result. |
| `Correlation` | Numeric correlation as a scalar result. |

## Input Pattern

Pass each series as a semicolon-delimited string. Build the string in Qlik with
a deterministic sort so both series align row by row.

```qlik
PythonSSE.Correlation(
    Concat(Aggr(Sum(ValueA), SortKey), ';'),
    Concat(Aggr(Sum(ValueB), SortKey), ';'),
    'spearman'
)
```

For dynamic series comparisons, include the same sort key in both `Aggr`
expressions and avoid selection states that produce mismatched series lengths.

## Data Handling

- The server attempts to coerce values to numeric data before calculating the
  correlation matrix.
- Empty, nonnumeric, or placeholder values should be removed or normalised in
  Qlik before concatenation when possible.
- Series order matters. The first value in `series1` is compared to the first
  value in `series2`, and so on.
- The function is most useful for chart-expression calculations. For large
  repeated calculations, consider materialising the input series in the load
  script and caching the result in the app model.

## Operational Notes

- `Pearson` is a convenience function for the most common linear correlation
  case.
- `Correlation` is the general function when the method needs to be selected by
  expression or variable.
- Use `pearson` for linear relationships, `spearman` for monotonic rank
  relationships, and `kendall` for rank association that is less sensitive to
  outliers in small samples.
- Debug output for this module is written to the SSE logs when enabled by the
  server code path.
