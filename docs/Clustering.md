# Clustering

This page documents the HDBSCAN clustering functions exposed by the Qlik Python
SSE. It is intended as an operational reference for agents writing Qlik
expressions or load script.

## Capability

The clustering functions assign records to density-based clusters with
HDBSCAN. They support ordinary feature vectors, feature pivoting by a second
dimension, and geospatial clustering from latitude/longitude.

Cluster labels start at `0`. HDBSCAN marks noise as `-1`.

## Functions

```qlik
PythonSSE.Cluster(key, features, args)
PythonSSE.Cluster_by_Dim(key, feature_dimension, measure, args)
PythonSSE.Cluster_Geo(key, latitude, longitude, args)
```

Inputs:

| Function | Inputs | Use |
| --- | --- | --- |
| `Cluster` | key, semicolon-delimited feature string, args | Cluster rows that already have a feature vector. Can be used in charts or load script. |
| `Cluster_by_Dim` | key, second dimension, numeric measure, args | Pivot the second dimension into features before clustering. Load-script only. |
| `Cluster_Geo` | key, latitude, longitude, args | Cluster geographic points. Uses haversine distance by default. |

Load-script output:

| Field | Type | Meaning |
| --- | --- | --- |
| `key` | string | The first input dimension. |
| `label`, `probabilities`, `cluster_persistence`, or `outlier_scores` | numeric | The selected return value. The field name depends on the `return` argument. |

Chart-expression output:

| Function | Return |
| --- | --- |
| `Cluster` | One numeric result per input row. |
| `Cluster_Geo` | One numeric result per input row. |

`Cluster_by_Dim` is load-script only because pivoting changes the input and
output shape.

## Argument Format

Arguments are passed as one string:

```text
load_script=true, scaler=robust, min_cluster_size=5, min_samples=3
```

The clustering parser also accepts `|` as a delimiter when needed:

```text
load_script=true|scaler=quantile|min_cluster_size=10
```

SSE arguments:

| Argument | Values | Notes |
| --- | --- | --- |
| `load_script` | `true`, `false` | Set to `true` when calling `Cluster` or `Cluster_Geo` from the load script. `Cluster_by_Dim` behaves as load-script output by default. |
| `return` | `labels`, `probabilities`, `cluster_persistence`, `outlier_scores` | Selects the numeric output. Defaults to labels. |
| `missing` | `zeros`, `mean`, `median`, `mode` | Missing-value strategy before scaling. |
| `scaler` | `standard`, `minmax`, `maxabs`, `robust`, `quantile`, `none` | Defaults to `robust` for ordinary clustering and `none` for geospatial clustering. |
| `debug` | `true`, `false` | Writes request, parameters, and response details to logs. |

HDBSCAN arguments:

| Argument | Notes |
| --- | --- |
| `algorithm` | HDBSCAN algorithm selection such as `best`, `generic`, `prims_kdtree`, or `boruvka_kdtree`. |
| `metric` | Distance metric. Defaults to ordinary HDBSCAN behavior for `Cluster` and `Cluster_by_Dim`; defaults to `haversine` for `Cluster_Geo`. |
| `min_cluster_size` | Minimum cluster size. Larger values produce fewer, denser clusters. |
| `min_samples` | Core-point neighborhood size. Larger values produce more noise. |
| `p` | Minkowski metric parameter. |
| `alpha` | Robust single-linkage distance scaling. |
| `cluster_selection_method` | `eom` or `leaf`. |
| `allow_single_cluster` | Allows HDBSCAN to return one cluster when set to `true`. |
| `match_reference_implementation` | Matches the reference implementation with a performance cost. |

Scaler-specific arguments follow the scikit-learn scaler names used by the
server code, for example `with_mean`, `with_std`, `feature_range`,
`with_centering`, `with_scaling`, `quantile_range`, `n_quantiles`,
`output_distribution`, `ignore_implicit_zeros`, `subsample`, and
`random_state`.

## Script Patterns

Cluster prebuilt feature vectors:

```qlik
ClusterInput:
LOAD
    CustomerId as key,
    Num(Spend) & ';' & Num(Visits) & ';' & Num(Margin) as features,
    'load_script=true, scaler=robust, min_cluster_size=10' as args
RESIDENT CustomerFeatures;

CustomerClusters:
LOAD
    key,
    label
EXTENSION PythonSSE.Cluster(ClusterInput{key, features, args});
```

Cluster by pivoting a second dimension:

```qlik
ClusterByDimInput:
LOAD
    CustomerId as key,
    ProductCategory as feature_dimension,
    Sum(Sales) as measure,
    'scaler=quantile, min_cluster_size=10' as args
RESIDENT Sales
GROUP BY CustomerId, ProductCategory;

CustomerClusters:
LOAD
    key,
    label
EXTENSION PythonSSE.Cluster_by_Dim(ClusterByDimInput{key, feature_dimension, measure, args});
```

Cluster geospatial points:

```qlik
GeoClusterInput:
LOAD
    LocationId as key,
    Latitude as latitude,
    Longitude as longitude,
    'load_script=true, min_cluster_size=5' as args
RESIDENT Locations;

GeoClusters:
LOAD
    key,
    label
EXTENSION PythonSSE.Cluster_Geo(GeoClusterInput{key, latitude, longitude, args});
```

## Operational Notes

- Use numeric, comparable feature scales. Select a scaler deliberately rather
  than relying on raw mixed-unit values.
- For `Cluster_Geo`, pass decimal latitude and longitude. The server converts
  coordinates for haversine distance.
- When the result is mostly `-1`, reduce `min_cluster_size` or `min_samples`, or
  inspect whether the selected features are too sparse.
- When using chart expressions, remember that clusters are recalculated in the
  current selection context.
- For repeatable app behavior and large inputs, prefer load-script clustering
  and store the cluster result in the data model.
