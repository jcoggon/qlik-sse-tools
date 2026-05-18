# Named Entity Recognition

This page documents the spaCy NER functions exposed by the Qlik Python SSE.
It is intended as an operational reference for agents extracting entities,
training a custom recognizer, or checking load-script integration.

## Capability

The SSE can:

- Extract named entities with the default spaCy model.
- Extract named entities with a named spaCy model stored under the SSE model
  directory.
- Retrain a spaCy NER model from labelled text supplied by Qlik.

The default model name in the server is `en_core_web_sm`.

## Functions

```qlik
PythonSSE.spaCy_Get_Entities(key, text, args)
PythonSSE.spaCy_Get_Entities_From_Model(key, text, model_name, args)
PythonSSE.spaCy_Retrain(text, entity, entity_type, model_name, args)
```

Entity extraction input:

| Parameter | Type | Meaning |
| --- | --- | --- |
| `key` | string | Record identifier returned with each entity. |
| `text` | string | Text to send to spaCy. |
| `model_name` | string | Named model to load for `spaCy_Get_Entities_From_Model`. |
| `args` | string | Optional keyword arguments. Use an empty string when no options are needed. |

Entity extraction output:

| Field | Type | Meaning |
| --- | --- | --- |
| `key` | string | Input key. |
| `entity` | string | Entity text. |
| `start` | numeric | Start character offset. |
| `end` | numeric | End character offset. |
| `type` | string | Entity label. |
| `description` | string | spaCy explanation for the label when available. |

Retraining input:

| Parameter | Type | Meaning |
| --- | --- | --- |
| `text` | string | Full text sample. |
| `entity` | string | Labelled entity text to find within `text`. |
| `entity_type` | string | Entity label to train. |
| `model_name` | string | Output model name. Must not be `en_core_web_sm`. |
| `args` | string | Training arguments. |

Retraining output:

| Field | Type | Meaning |
| --- | --- | --- |
| `model_name` | string | Model trained or evaluated. |
| `subset` | string | `train` or validation/test subset. |
| `metric` | string | Metric or loss name. |
| `value` | numeric | Metric value. |

## Argument Format

Arguments are passed as a single string:

```text
debug=true, custom=true, epochs=20, test=0.2
```

Supported arguments:

| Argument | Applies To | Notes |
| --- | --- | --- |
| `debug` | all functions | Writes request, parameters, and response details to logs. |
| `custom` | extraction, retraining | Set `custom=true` when loading a model from the SSE spaCy model directory rather than a built-in spaCy model name. |
| `base_model` | retraining | Existing model to update. Defaults to `en_core_web_sm`. Can point to a custom model when `custom=true`. |
| `blank` | retraining | Set `blank=true` to create a blank spaCy language pipeline instead of updating an existing model. |
| `epochs` | retraining | Training epochs. |
| `batch_size` | retraining | Integer batch size or typed batch-size schedule supported by the server parser. |
| `drop` | retraining | Dropout rate. |
| `test` | retraining | Validation split ratio. |

## Extraction Pattern

```qlik
EntityInput:
LOAD
    ArticleId as key,
    BodyText as text,
    '' as args
RESIDENT Articles;

Entities:
LOAD
    key,
    entity,
    start,
    end,
    type,
    description
EXTENSION PythonSSE.spaCy_Get_Entities(EntityInput{key, text, args});
```

Use a custom model:

```qlik
CustomEntityInput:
LOAD
    ArticleId as key,
    BodyText as text,
    'domain_ner_v1' as model_name,
    'custom=true' as args
RESIDENT Articles;

Entities:
LOAD
    key,
    entity,
    start,
    end,
    type,
    description
EXTENSION PythonSSE.spaCy_Get_Entities_From_Model(CustomEntityInput{key, text, model_name, args});
```

## Retraining Pattern

Training data should contain repeated text rows when a single text has multiple
entities. The server groups each text, finds labelled entity occurrences, drops
overlapping spans, trains the NER component, saves the model, and returns
metrics.

```qlik
TrainingInput:
LOAD
    Text as text,
    EntityValue as entity,
    EntityLabel as entity_type,
    'domain_ner_v1' as model_name,
    'epochs=20, test=0.2, drop=0.2' as args
RESIDENT LabelledEntities;

NERMetrics:
LOAD
    model_name,
    subset,
    metric,
    value
EXTENSION PythonSSE.spaCy_Retrain(TrainingInput{text, entity, entity_type, model_name, args});
```

## Operational Notes

- The retraining function saves models under the SSE spaCy model directory,
  which defaults in code to `../models/spaCy/`.
- A lock file is used while saving a retrained model. If a stale lock remains
  after an interrupted run, the server error will identify the file.
- Entity labels can be spaCy defaults or domain-specific labels. Keep labels
  consistent across all training rows.
- The training preprocessor searches entity text inside the full text. Ensure
  labelled entity strings match the exact text form that appears in the sample.
- Provide enough varied labelled examples for each label. Very small training
  sets can produce low loss but poor generalisation.
- Use `debug=true` for diagnosing empty entity output, mismatched labels, or
  unexpected retraining results.
