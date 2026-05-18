# Keras Sequence Prediction

This page documents the Keras and sequence-prediction SSE functions exposed to Qlik. It is written for AI agents and automation flows that need to create Qlik load-script calls or chart expressions from the current runtime capabilities.

Keras support is built on the same model lifecycle used by the scikit-learn functions: setup, feature definition, optional Keras architecture definition, fit, metrics, and prediction. TensorFlow/Keras are loaded on demand so the base SSE can start without importing the deep learning stack.

## Supported Workflow

1. Create a model with `sklearn_Setup` or `sklearn_Setup_Adv`.
2. Register model features with `sklearn_Set_Features`.
3. Register the neural network architecture with `Keras_Set_Layers`.
4. Train the model with `sklearn_Fit`.
5. Evaluate held-out sequential rows with `sklearn_Calculate_Metrics_Sequence`.
6. Inspect training history with `Keras_Get_History`.
7. Score sequences with `sklearn_Predict_Sequence`, `sklearn_Bulk_Predict_Sequence`, `sklearn_Predict_Proba_Sequence`, or `sklearn_Bulk_Predict_Proba_Sequence`.

Use `KerasRegressor` for regression models and `KerasClassifier` for classification models.

## Functions

| Function | Qlik call type | Purpose |
| --- | --- | --- |
| `Keras_Set_Layers(model_name, sort_order, layer_type, args, kwargs)` | Load script tensor | Persist a Keras Sequential architecture for an existing model. |
| `Keras_Get_History(model_name)` | Load script tensor | Return training history columns such as iteration, epoch, loss, and metrics. |
| `sklearn_Predict_Sequence(model_name, key, feature1, ...)` | Tensor | Return sequence predictions keyed by row. |
| `sklearn_Bulk_Predict_Sequence(model_name, key, feature1, ...)` | Load script tensor | Bulk sequence prediction during reload. |
| `sklearn_Predict_Proba_Sequence(model_name, key, feature1, ...)` | Tensor | Return class probabilities for sequence classifiers. |
| `sklearn_Bulk_Predict_Proba_Sequence(model_name, key, feature1, ...)` | Load script tensor | Bulk probability prediction during reload. |
| `sklearn_Calculate_Metrics_Sequence(model_name, key, feature1, ...)` | Load script tensor | Calculate metrics for ordered sequential test data. |

The sequence prediction and metrics functions take `model_name`, a row key, and then the feature values in the same order as the registered feature definitions.

## Model Setup

Create the model before setting layers. The setup table must provide `model_name`, estimator args, scaler args, and execution args.

```qlik
ModelSetup:
LOAD * INLINE [
model_name, estimator_args, scaler_args, execution_args
demand_lstm, estimator=KerasRegressor,epochs=150|int,batch_size=32|int, scaler=StandardScaler, test_size=0,lags=30,lag_target=true,scale_target=false,current_sample_as_input=false,prediction_periods=7,overwrite=true
];

SetupResult:
LOAD model_name, result, timestamp
EXTENSION <AAI>.sklearn_Setup(ModelSetup{model_name, estimator_args, scaler_args, execution_args});
```

Important execution args for sequence models:

| Argument | Values | Notes |
| --- | --- | --- |
| `test_size` | Decimal | Set to `0` when evaluating sequence models separately with `sklearn_Calculate_Metrics_Sequence`. |
| `time_series_split` | Integer | Enables ordered cross-validation using time series splits. |
| `max_train_size` | Integer | Optional rolling training window for time series splits. |
| `lags` | Integer | Number of previous rows to add to each model input. |
| `lag_target` | `true`, `false` | Adds previous target values as lagged input features. |
| `scale_target` | `true`, `false` | Scales the target during fitting and reverses scaling for predictions. |
| `scale_lag_target` | `true`, `false` | Scales lagged target features even when `scale_target=false`. |
| `make_stationary` | `log`, `difference` | Transforms the target and reverses the transform for predictions. |
| `stationarity_lags` | Typed list | Lags used when `make_stationary=difference`, for example `1;12|list|int`. |
| `current_sample_as_input` | `true`, `false` | Controls whether the current row's features are included with lagged observations. |
| `prediction_periods` | Integer | Number of future steps expected from the model. Must match the output layer. |
| `random_state` | Integer | Seed for repeatable splitting and related operations. |
| `retain_data` | `true`, `false` | Stores training/test data in the model artifact. |
| `debug` | `true`, `false` | Writes execution details to logs. |

The feature definitions must include one `identifier` field for sequence models. Use a numeric field that preserves the sequence order, such as `Num(DateField)`.

## Feature Definitions

Register one row per input column.

```qlik
Features:
LOAD * INLINE [
model_name, feature_name, variable_type, data_type, feature_strategy, strategy_args
demand_lstm, date_key, identifier, float, none,
demand_lstm, sales, target, float, scaling,
demand_lstm, price, feature, float, scaling,
demand_lstm, promotion_flag, feature, int, none,
demand_lstm, channel, feature, str, one hot encoding,
];

FeatureResult:
LOAD model_name, result, timestamp
EXTENSION <AAI>.sklearn_Set_Features(Features{
    model_name, feature_name, variable_type, data_type, feature_strategy, strategy_args
});
```

Feature fields:

| Field | Values | Notes |
| --- | --- | --- |
| `feature_name` | String | Must match the order used in fit and prediction calls. |
| `variable_type` | `feature`, `target`, `excluded`, `identifier` | Sequence models require an `identifier`. |
| `data_type` | `bool`, `int`, `float`, `str` | Used to coerce values received from Qlik. |
| `feature_strategy` | `one hot encoding`, `hashing`, `count_vectorizing`, `tf_idf`, `text_similarity`, `scaling`, `none` | Converts raw Qlik values into model-ready numeric features. |
| `strategy_args` | String | Strategy-specific arguments, such as hash width or vectorizer kwargs. |

## Keras Architecture

`Keras_Set_Layers` accepts one row per layer and a final `Compilation` row. The model must already exist from `sklearn_Setup`.

```qlik
Architecture:
LOAD * INLINE [
model_name, sort_order, layer_type, args, kwargs
demand_lstm, 1, LSTM, 64|int, input_shape=30;None|tuple|int, activation=relu|str
demand_lstm, 2, Dense, 7|int, activation=linear|str
demand_lstm, 3, Compilation, , loss=mse|str, optimizer=adam|str, metrics=mae|list|str
];

LayerResult:
LOAD model_name, result, timestamp
EXTENSION <AAI>.Keras_Set_Layers(Architecture{
    model_name, sort_order, layer_type, args, kwargs
});
```

Architecture fields:

| Field | Notes |
| --- | --- |
| `model_name` | Existing model name. |
| `sort_order` | Numeric layer order. |
| `layer_type` | Keras layer name, optimizer name, `Compilation`, or wrapper plus layer such as `TimeDistributed Dense`. |
| `args` | Positional args in typed format, for example `64|int`. |
| `kwargs` | Keyword args in typed format, for example `activation=relu|str, input_shape=30;None|tuple|int`. |

Typed argument syntax:

| Shape | Example |
| --- | --- |
| Scalar positional arg | `64|int` |
| Keyword scalar | `activation=relu|str` |
| Tuple | `input_shape=30;None|tuple|int` |
| List | `metrics=mae|list|str` |
| Dictionary | `some_arg=a:1;b:2|dict|str|int` |

The implementation calculates the final feature count after preprocessing. Use `None` as the placeholder for the feature dimension in `input_shape`. Do not use Keras `input_dim`; use `input_shape`.

For convolutional or recurrent sequence models:

- `lags=30,current_sample_as_input=false` usually maps to `input_shape=30;None|tuple|int`.
- `lags=29,current_sample_as_input=true` also maps to 30 time steps because the current sample is included.
- `lag_target=true` adds another feature but does not change the time-step count.
- Multi-step regression requires the final output layer width to equal `prediction_periods`.

An optimizer row can be placed before `Compilation` when optimizer parameters are required:

```qlik
demand_lstm, 3, Adam, , learning_rate=0.001|float
demand_lstm, 4, Compilation, , loss=mse|str, metrics=mae|list|str
```

## Training

Training uses `sklearn_Fit`. The input table must send `model_name`, a feature count field, and then the feature values in the same order as the feature definitions. The exact feature count convention is shared with the scikit-learn functions in this SSE.

```qlik
TrainRows:
LOAD
    'demand_lstm' as model_name,
    5 as n_features,
    Num(DateField) as date_key,
    Sales as sales,
    Price as price,
    PromotionFlag as promotion_flag,
    Channel as channel
RESIDENT TrainingData;

FitResult:
LOAD model_name, result, time_stamp, score_result, score
EXTENSION <AAI>.sklearn_Fit(TrainRows{
    model_name, n_features, date_key, sales, price, promotion_flag, channel
});
```

Operational rules:

- Send fields in the registered feature-definition order.
- Include the target while fitting.
- Include a numeric identifier so the SSE can sort the sequence before adding lags.
- For sequence forecasting, hold out test rows yourself or use ordered split settings rather than random k-fold validation.

## Metrics

Use `sklearn_Calculate_Metrics_Sequence` for ordered sequence test data.

```qlik
Metrics:
LOAD *
EXTENSION <AAI>.sklearn_Calculate_Metrics_Sequence(TestRows{
    model_name, key, n_features, date_key, sales, price, promotion_flag, channel
});
```

Regression metric output includes columns such as `r2_score`, `mean_squared_error`, `mean_absolute_error`, `median_absolute_error`, and `explained_variance_score`.

Classifier metric output includes class-level precision, recall, f-score, support, and accuracy. For multi-step classifiers, confusion-matrix output can include a `step` field.

## Training History

Use `Keras_Get_History` after fitting a Keras model.

```qlik
HistoryInput:
LOAD 'demand_lstm' as model_name AUTOGENERATE 1;

History:
LOAD *
EXTENSION <AAI>.Keras_Get_History(HistoryInput{model_name});
```

The response includes `model_name` followed by Keras history columns. Common columns are `iteration`, `epoch`, `loss`, and any metrics configured in the `Compilation` row.

## Predictions

Use bulk prediction from the load script when precomputing output rows.

```qlik
Predictions:
LOAD model_name, key, prediction
EXTENSION <AAI>.sklearn_Bulk_Predict_Sequence(PredictRows{
    model_name, key, n_features, date_key, price, promotion_flag, channel
});
```

Use probability functions only for classifiers:

```qlik
ClassProbabilities:
LOAD *
EXTENSION <AAI>.sklearn_Bulk_Predict_Proba_Sequence(PredictRows{
    model_name, key, n_features, date_key, price, promotion_flag, channel
});
```

Prediction rules:

- Use the same feature order as setup.
- Do not include the target unless the model call expects it as part of the feature set for the chosen workflow.
- Provide enough prior rows for the configured `lags`.
- Provide future-known feature values for every row being predicted.
- For multi-step models, expect one prediction vector per keyed sequence input.

## Operational Notes

- Keras and TensorFlow are lazy-loaded. First Keras use may take longer than later calls.
- Trained Keras models are saved separately as `.h5` files while the SSE persists the surrounding pipeline metadata.
- The runtime clears and reloads Keras sessions around persisted models to avoid stale TensorFlow state.
- Keras history is available only after a successful fit.
- `sklearn_Explain_Importances` is not supported for Keras models.
- Use `debug=true` only while building or diagnosing a model because it increases log output.
- Keep model names stable and unique. Use `overwrite=true` intentionally when replacing a model artifact.
- Validate TensorFlow, Keras, and scikeras availability in the runtime before relying on these functions in production reload schedules.
