# Pretrained Models

This page documents the common pretrained-model inference functions exposed by
the Qlik Python SSE. It is intended as an operational reference for agents
configuring model metadata, building feature expressions, or calling inference
from Qlik.

## Capability

The common prediction layer calls existing models from Qlik. Supported model
types are:

- Pickled scikit-learn compatible models.
- Keras models saved in HDF5-compatible format.
- REST endpoints called with HTTP POST.

The model is described by a YAML file in the SSE models directory. The model
name passed from Qlik is the YAML filename without `.yaml`.

## Functions

```qlik
PythonSSE.Predict(model_name, features, args)
PythonSSE.Bulk_Predict(model_name, key, features, args)
PythonSSE.Get_Features_Expression(model_name)
```

Inputs:

| Parameter | Type | Meaning |
| --- | --- | --- |
| `model_name` | string | YAML model definition name without extension. |
| `key` | string | Record identifier returned by `Bulk_Predict`. |
| `features` | string | Feature values concatenated with `|` in the order defined by YAML. |
| `args` | string | Optional keyword arguments for prediction behavior. |

Outputs:

| Function | Return |
| --- | --- |
| `Predict` | Scalar prediction for chart expressions. |
| `Bulk_Predict` | Table with `model_name`, `key`, and `prediction`. |
| `Get_Features_Expression` | Table with one `result` value containing a Qlik expression that concatenates the YAML-defined features. |

## YAML Model Definition

Required fields:

```yaml
type: sklearn
path: ../models/customer_churn.pkl
features:
  Age: numeric
  TenureMonths: numeric
  PlanType: string
```

Supported top-level fields:

| Field | Applies To | Meaning |
| --- | --- | --- |
| `type` | all | `sklearn`, `scikit-learn`, `keras`, `rest`, or `restful`. |
| `path` | all | Model file path or REST endpoint URL. |
| `features` | all | Ordered mapping of feature names to data types. The order defines Qlik feature concatenation. |
| `preprocessor` | sklearn, keras | Pickled object with a `transform` method applied before prediction. |
| `response_section` | REST | Optional response key to read from the JSON response. |
| `user` | REST | User or endpoint key for basic auth. |
| `password` | REST | Password or secret for basic auth. |
| `payload_header` | REST | Optional JSON wrapper key for POST payloads. |

REST example:

```yaml
type: rest
path: https://model.example.net/predict
user: endpoint-user
password: endpoint-secret
response_section: prediction
features:
  Age: numeric
  TenureMonths: numeric
  PlanType: string
```

The SSE does not encrypt YAML files. Treat model definition files as sensitive
when they include endpoints or credentials.

## Feature Expression Pattern

The feature string must match the YAML feature order and use `|` as the
delimiter. Agents can either build it manually or request it from the SSE:

```qlik
FeatureExpression:
LOAD
    model_name
INLINE [
model_name
customer_churn
];

FeatureExpressionResult:
LOAD
    result
EXTENSION PythonSSE.Get_Features_Expression(FeatureExpression{model_name});

LET vCustomerChurnFeatures = Peek('result', 0, 'FeatureExpressionResult');
DROP TABLE FeatureExpressionResult;
DROP TABLE FeatureExpression;
```

The resulting expression is suitable for use where Qlik can evaluate the listed
field names.

Manual form:

```qlik
Num(Age) & '|' & Num(TenureMonths) & '|' & PlanType
```

## Chart Prediction Pattern

```qlik
PythonSSE.Predict(
    'customer_churn',
    $(vCustomerChurnFeatures),
    ''
)
```

Use chart predictions only when the chart grain equals the model's expected
sample grain.

## Load-Script Prediction Pattern

```qlik
PredictInput:
LOAD
    'customer_churn' as model_name,
    CustomerId as key,
    Num(Age) & '|' & Num(TenureMonths) & '|' & PlanType as features,
    '' as args
RESIDENT Customers;

Predictions:
LOAD
    model_name,
    key,
    prediction
EXTENSION PythonSSE.Bulk_Predict(PredictInput{model_name, key, features, args});
```

## Prediction Arguments

Arguments are passed as a single string:

```text
return=predict_proba, identifier=CustomerId, exclude_identifier=true
```

Supported arguments:

| Argument | Notes |
| --- | --- |
| `return` | Model method to call. Defaults to `predict`. Use values such as `predict_proba` only when the underlying model supports them. |
| `identifier` | Feature column used to sort input before prediction. Useful for sequence-sensitive models. |
| `exclude_identifier` | Set `true` to remove the identifier column before calling the model. |
| `debug` | Enables detailed logs. |
| `load_script` | Managed by the function path; use `Bulk_Predict` for table output. |

## Operational Notes

- For sklearn and Keras files, runtime library versions must be compatible with
  the environment that created the model.
- For REST models, the SSE posts each row as JSON and reads the configured
  response. Validate endpoint latency before using chart expressions.
- Feature names in YAML should match Qlik fields if using
  `Get_Features_Expression`.
- Keep feature ordering stable. Changing YAML feature order changes inference
  input order.
- Place preprocessing that must always happen before inference in the YAML
  `preprocessor`, not in ad hoc chart expressions.
- Use `Bulk_Predict` for reload-time scoring and repeatable app behavior; use
  `Predict` for interactive scenarios where selection-aware inference is
  intentional.
