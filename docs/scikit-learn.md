# scikit-learn Machine Learning

This page documents the scikit-learn functions exposed by the Qlik Python SSE.
It is intended as an operational reference for agents creating or inspecting
Qlik load script, model setup tables, training flows, prediction calls, and
model diagnostics.

## Capability

The SSE can configure, train, persist, score, and inspect machine-learning
pipelines from Qlik. The implementation builds a persistent model object, stores
feature metadata, preprocesses Qlik data, fits a scikit-learn compatible
pipeline, and saves the model under the SSE model directory.

Supported estimator families include scikit-learn classifiers, regressors,
decomposers, and clusterers, plus optional XGBoost, LightGBM, and Keras wrapper
estimators when those dependencies are installed in the runtime.

## Core Workflow

A supervised training flow normally has four load-script steps:

1. Create a model with `sklearn_Setup` or `sklearn_Setup_Adv`.
2. Add feature definitions with `sklearn_Set_Features`.
3. Train the model with `sklearn_Fit`.
4. Retrieve metrics, predictions, feature expressions, or diagnostics with the
   relevant functions.

All feature values supplied to training and prediction functions are passed as
a single `|`-delimited string. The feature order must match the stored feature
definitions.

## Function Reference

Model setup:

| Function | Use | Output |
| --- | --- | --- |
| `sklearn_Setup(model_name, estimator_args, scaler_args, execution_args)` | Create a persistent model with estimator, scaler, and execution settings. | `model_name`, `result`, `timestamp`. |
| `sklearn_Setup_Adv(model_name, estimator_args, scaler_args, metric_args, dim_reduction_args, execution_args)` | Create a model with additional metric and dimensionality-reduction settings. | `model_name`, `result`, `timestamp`. |
| `sklearn_Set_Param_Grid(model_name, estimator_args, grid_search_args)` | Attach a grid-search parameter grid to an existing model. | `model_name`, `result`, `timestamp`. |
| `sklearn_Get_Best_Params(model_name)` | Return best parameters after grid search has been fitted. | `model_name`, `best_params`. |
| `sklearn_List_Models(search_pattern)` | List saved models whose filenames match a pattern. | Scalar/text response. |

Feature definitions:

| Function | Use | Output |
| --- | --- | --- |
| `sklearn_Set_Features(model_name, feature_name, var_type, data_type, strategy, strategy_args)` | Persist ordered feature definitions. | `model_name`, `result`, `timestamp`. |
| `sklearn_Get_Features(model_name)` | Return stored feature definitions. | `model_name`, `sort_order`, `feature`, `var_type`, `data_type`, `strategy`, `strategy_args`. |
| `sklearn_Get_Features_Expression(model_name)` | Return a Qlik expression that concatenates non-excluded input features in the correct order. | `result`. |

Training and scoring:

| Function | Use | Output |
| --- | --- | --- |
| `sklearn_Fit(model_name, features)` | Fit the configured supervised model. Feature rows include target and input values according to feature definitions. | `model_name`, `result`, `time_stamp`, `score_result`, `score`. |
| `sklearn_Calculate_Metrics(model_name, features)` | Calculate metrics from supplied evaluation data. | Metric table. |
| `sklearn_Get_Metrics(model_name)` | Return metrics saved during fitting or external metric calculation. | Classifier or regressor metric table. |
| `sklearn_Get_Confusion_Matrix(model_name)` | Return confusion matrix for classifier models when available. | Label/count table or multilabel table. |
| `sklearn_Explain_Importances(model_name)` | Return permutation feature importances when enabled. | `model_name`, `feature_name`, `importance`. |

Prediction:

| Function | Use | Output |
| --- | --- | --- |
| `sklearn_Predict(model_name, features)` | Chart-expression prediction. | Scalar prediction. |
| `sklearn_Bulk_Predict(model_name, key, features)` | Load-script prediction. | `model_name`, `key`, `prediction`. |
| `sklearn_Predict_Proba(model_name, features)` | Chart-expression class probabilities. | Scalar/string probability result. |
| `sklearn_Bulk_Predict_Proba(model_name, key, features)` | Load-script class probabilities. | `model_name`, `key`, `prediction`. |

Sequence prediction:

| Function | Use |
| --- | --- |
| `sklearn_Predict_Sequence(model_name, key, features)` | Chart-expression sequence prediction with ordered data. |
| `sklearn_Bulk_Predict_Sequence(model_name, key, features)` | Load-script sequence prediction. |
| `sklearn_Predict_Proba_Sequence(model_name, key, features)` | Chart-expression sequence probability prediction. |
| `sklearn_Bulk_Predict_Proba_Sequence(model_name, key, features)` | Load-script sequence probability prediction. |
| `sklearn_Calculate_Metrics_Sequence(model_name, key, features)` | Ordered metrics for sequence data. |

Unsupervised learning:

| Function | Use | Output |
| --- | --- | --- |
| `sklearn_Fit_Transform(model_name, key, features)` | Fit a decomposer and return transformed dimensions. | `model_name`, `key`, `dim_1...dim_n`. |
| `sklearn_Fit_Predict(model_name, features)` | Chart-expression clustering label from a configured clusterer. | Scalar label. |
| `sklearn_Bulk_Fit_Predict(model_name, key, features)` | Load-script clustering labels. | `model_name`, `key`, `label`. |

## Setup Arguments

Arguments are passed as strings of `keyword=value` pairs. Values that need type
conversion use the repository parser convention:

```text
estimator=RandomForestClassifier, n_estimators=200|int, max_depth=8|int
```

Estimator arguments:

| Argument | Notes |
| --- | --- |
| `estimator` | Required. Class name known to the server, for example `RandomForestClassifier`, `LogisticRegression`, `LinearRegression`, `KMeans`, or `PCA`. |
| estimator kwargs | Any supported keyword for the selected estimator, with type markers when needed. |

Scaler arguments:

| Argument | Notes |
| --- | --- |
| `scaler` | Required when scaler args are supplied. Common values include `StandardScaler`, `MinMaxScaler`, `MaxAbsScaler`, `RobustScaler`, and `QuantileTransformer`. |
| `missing` | Missing-value strategy used by preprocessing. Defaults to `zeros`. |
| `scale_hashed` | Whether hashed categorical features are scaled. Defaults to `true`. |
| `scale_vectors` | Whether vector features are scaled. Defaults to `true`. |
| scaler kwargs | Any supported keyword for the selected scaler. |

Execution arguments:

| Argument | Default | Notes |
| --- | --- | --- |
| `overwrite` | `true` | Whether an existing model file can be replaced. |
| `test_size` | `0.33` | Hold-out validation split. Set to `0` for external validation only. |
| `cv` | `0` | K-fold count. When greater than zero, K-fold validation is used instead of hold-out. |
| `time_series_split` | `0` | Enables ordered `TimeSeriesSplit` validation. Requires an identifier feature. |
| `max_train_size` | empty | Optional rolling-window training size for time-series split. |
| `random_state` | `42` | Seed for splits and model operations that use it. |
| `compress` | `3` | Joblib compression level for saved models. |
| `retain_data` | `false` | Store training/test data inside the model object. |
| `calculate_importances` | `false` | Calculate permutation importances during fit. |
| `importances_n_repeats` | `30` | Repeats for permutation importance. |
| `debug` | `false` | Write detailed setup, fit, and response logs. |

Sequence and target transformation arguments:

| Argument | Notes |
| --- | --- |
| `lags` | Adds prior observations to the feature matrix. |
| `lag_target` | Adds previous target values as features. |
| `scale_target` | Scales the target during fitting and reverses scaling on prediction. |
| `scale_lag_target` | Scales lagged target features. |
| `make_stationary` | `log` or `difference`; reversed before returning predictions. |
| `stationarity_lags` | Typed list of differencing lags, for example `stationarity_lags=1;12|list|int`. |
| `current_sample_as_input` | Include current row features with lag features. |
| `prediction_periods` | Multi-step prediction output count for compatible Keras models. |

Advanced setup arguments:

| Argument Group | Notes |
| --- | --- |
| `metric_args` | Extra metric keyword arguments for metric calculation. |
| `dim_reduction_args` | Include `reduction=<ClassName>` plus kwargs, for example `reduction=PCA, n_components=3|int`. |

## Feature Definitions

Feature definitions are stored in order and drive preprocessing, training,
prediction, and generated Qlik expressions.

```qlik
Features:
LOAD * INLINE [
model_name, feature_name, var_type, data_type, strategy, strategy_args
churn_v1, CustomerId, identifier, string, none, ''
churn_v1, Churned, target, numeric, none, ''
churn_v1, Age, feature, numeric, none, ''
churn_v1, PlanType, feature, string, hash, ''
];

LOAD *
EXTENSION PythonSSE.sklearn_Set_Features(Features{model_name, feature_name, var_type, data_type, strategy, strategy_args});
```

Common `var_type` values:

| Value | Meaning |
| --- | --- |
| `feature` | Input feature used for model training and prediction. |
| `target` | Supervised target value. Excluded from prediction expressions unless target lagging requires it. |
| `identifier` | Sort/order key for sequence or time-series operations. Only one identifier is allowed. |
| `excluded` | Stored in metadata but excluded from training and prediction input expressions. |

The exact preprocessing behavior depends on the repository's `Preprocessor`
implementation and the selected strategy. Agents should preserve existing
strategy values when modifying a model unless the requested change is
explicitly about feature engineering.

## Supervised Training Pattern

```qlik
Setup:
LOAD * INLINE [
model_name, estimator_args, scaler_args, execution_args
churn_v1, 'estimator=RandomForestClassifier, n_estimators=200|int', 'scaler=StandardScaler, missing=zeros', 'test_size=0.25, random_state=42'
];

LOAD *
EXTENSION PythonSSE.sklearn_Setup(Setup{model_name, estimator_args, scaler_args, execution_args});

TrainingRows:
LOAD
    'churn_v1' as model_name,
    CustomerId & '|' & Churned & '|' & Age & '|' & PlanType as features
RESIDENT Customers;

FitResult:
LOAD
    model_name,
    result,
    time_stamp,
    score_result,
    score
EXTENSION PythonSSE.sklearn_Fit(TrainingRows{model_name, features});
```

Use `sklearn_Setup_Adv` instead of `sklearn_Setup` when metric arguments or
dimensionality reduction must be part of the pipeline.

## Prediction Pattern

Retrieve the feature expression, then use it for chart or load-script
prediction:

```qlik
FeatureExpression:
LOAD * INLINE [
model_name
churn_v1
];

FeatureExpressionResult:
LOAD result
EXTENSION PythonSSE.sklearn_Get_Features_Expression(FeatureExpression{model_name});

LET vChurnFeatures = Peek('result', 0, 'FeatureExpressionResult');
DROP TABLE FeatureExpressionResult;
DROP TABLE FeatureExpression;
```

Chart expression:

```qlik
PythonSSE.sklearn_Predict('churn_v1', $(vChurnFeatures))
```

Load-script scoring:

```qlik
ScoreInput:
LOAD
    'churn_v1' as model_name,
    CustomerId as key,
    CustomerId & '|' & Age & '|' & PlanType as features
RESIDENT CustomersToScore;

Scores:
LOAD
    model_name,
    key,
    prediction
EXTENSION PythonSSE.sklearn_Bulk_Predict(ScoreInput{model_name, key, features});
```

For classifiers, use `sklearn_Predict_Proba` or
`sklearn_Bulk_Predict_Proba` only when the fitted estimator supports
probability prediction.

## Metrics and Diagnostics

After fitting, agents can request:

```qlik
ModelLookup:
LOAD * INLINE [
model_name
churn_v1
];

LOAD * EXTENSION PythonSSE.sklearn_Get_Metrics(ModelLookup{model_name});
LOAD * EXTENSION PythonSSE.sklearn_Get_Confusion_Matrix(ModelLookup{model_name});
LOAD * EXTENSION PythonSSE.sklearn_Explain_Importances(ModelLookup{model_name});
LOAD * EXTENSION PythonSSE.sklearn_Get_Best_Params(ModelLookup{model_name});
```

Notes:

- `sklearn_Get_Metrics` requires metrics created during fitting or via
  `sklearn_Calculate_Metrics`.
- `sklearn_Get_Confusion_Matrix` applies to classifier models.
- `sklearn_Explain_Importances` requires `calculate_importances=true` and a
  validation or external metrics path that provides evaluation data.
- Grid-search best parameters are available after a model with a parameter grid
  has been fitted.

## Unsupervised Patterns

Dimensionality reduction:

```qlik
ReduceInput:
LOAD
    'pca_v1' as model_name,
    RowId as key,
    FeatureA & '|' & FeatureB & '|' & FeatureC as features
RESIDENT SourceRows;

Reduced:
LOAD
    model_name,
    key,
    dim_1,
    dim_2
EXTENSION PythonSSE.sklearn_Fit_Transform(ReduceInput{model_name, key, features});
```

Clustering with scikit-learn clusterers:

```qlik
ClusterInput:
LOAD
    'kmeans_v1' as model_name,
    RowId as key,
    FeatureA & '|' & FeatureB & '|' & FeatureC as features
RESIDENT SourceRows;

Clusters:
LOAD
    model_name,
    key,
    label
EXTENSION PythonSSE.sklearn_Bulk_Fit_Predict(ClusterInput{model_name, key, features});
```

## Operational Notes

- Keep feature order stable. Stored feature definitions and feature strings must
  match exactly.
- Use load-script training and scoring for repeatable results. Use chart
  prediction only when selection-aware scoring is intentional and the chart
  grain matches the model grain.
- Persisted models are cached by the SSE after loading. Restart the SSE if
  direct filesystem changes are made outside the extension.
- Use `debug=true` during model build or troubleshooting to write detailed logs
  under the server log directory.
- Cross-validation, grid search, permutation importance, and large ensemble
  models can be expensive during Qlik reload. Start with bounded test data and
  conservative parameter grids.
- For ordered sequence workflows, define a single `identifier` feature and use
  the `_Sequence` functions for prediction and metric calculation.
