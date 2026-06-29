# Qlik SSE Tools Documentation

This folder is the Markdown reference set for the Qlik Python Tools Server-Side Extension.

Use these documents together with the top-level `README.md`, `USAGE.md`, `TESTING.md`, and `core/functions.json`.

## What The SSE Provides

The service exposes Python analytics through Qlik Sense Client-Managed analytic connections. Qlik sends expression or load-script data over gRPC, the SSE runs the configured Python capability, and Qlik receives scalar values or tabular results.

The function catalog currently includes:

| Area | Main docs | Function families |
| --- | --- | --- |
| Forecasting | `Prophet.md`, `StatsForecast.md`, `Keras.md` | `Prophet`, `Prophet_Holidays`, `Prophet_Multivariate`, `StatsForecast`, sequence prediction |
| Machine learning | `scikit-learn.md`, `Pretrained.md` | `sklearn_*`, `Predict`, `Bulk_Predict`, model metrics and feature expressions |
| Natural language | `NER.md` | `spaCy_Get_Entities`, `spaCy_Get_Entities_From_Model`, `spaCy_Retrain` |
| Association and correlation | `Association-Rules.md`, `Correlation.md` | `Association_Rules`, `Correlation`, `Pearson` |
| Clustering | `Clustering.md` | `Cluster`, `Cluster_by_Dim`, `Cluster_Geo` |
| LLM integrations | `LLM.md` | `LLM_Chat`, `LLM_Chat_Bulk`, `LLM_Claude_Chat`, `LLM_Claude_Chat_Bulk` |
| Web and document extraction | `Firecrawl.md` | `Firecrawl_Scrape`, `Firecrawl_Extract`, `Firecrawl_Search`, `Firecrawl_Agent` |

## How An AI Agent Should Read These Docs

1. Start with this file to identify the capability family.
2. Open the family-specific Markdown file.
3. Check the function signatures and whether the function is intended for a chart expression or a load script.
4. Use `core/functions.json` when an exact function id, parameter order, or Qlik SSE type is needed.
5. Use `TESTING.md` for the verification command and expected standalone test coverage.

## Qlik Connection Pattern

Create an analytic connection in Qlik Sense Client-Managed. The connection name becomes the prefix used in expressions. In examples below, replace `<AAI>` with the configured connection name.

Chart expression shape:

```qlik
<AAI>.FunctionName(Parameter1, Parameter2, 'key=value|key=value')
```

Load script shape:

```qlik
Extension <AAI>.FunctionName(InputTable{Field1, Field2, Args});
```

Most optional arguments use a single string column. Pipe-delimited kwargs are preferred:

```text
key=value|key=value|debug=true
```

Some legacy functions also accept comma-delimited kwargs. Prefer pipe delimiters when values may contain commas.

## Runtime And Operations

- Default gRPC port: `50055`.
- Runtime folder after initialization: `qlik-py-env`.
- Runtime logs are written under `qlik-py-env/core/logs` when running from the installed environment.
- Python runtime target: Python `3.13+`.
- The Windows service helper uses Servy and runs `qlik-py-env/core/__main__.py`. Servy is not bundled in the SSE zip; install it system-wide or place the Servy x64 installer beside `Qlik-Py-Service-Install.bat`.
- Prophet/CmdStanPy temp files use a persistent runtime temp folder by default: `qlik-py-env/tmp`.
- Set `QLIK_PY_TOOLS_TEMP_DIR` in `.env` only when an operator needs to force a different persistent temp location.

## Environment Variables

Only configure credentials for integrations that will be used.

| Variable | Used by |
| --- | --- |
| `AZURE_OPENAI_API_KEY` | Azure OpenAI chat functions |
| `AZURE_OPENAI_ENDPOINT` | Azure OpenAI chat functions |
| `AZURE_OPENAI_DEPLOYMENT` | Azure OpenAI chat functions |
| `AZURE_OPENAI_API_VERSION` | Azure OpenAI chat functions |
| `AZURE_FOUNDRY_API_KEY` | Azure AI Foundry Claude functions |
| `AZURE_FOUNDRY_API_VERSION` | Azure AI Foundry Claude functions |
| `AZURE_CLAUDE_HAIKU` | Claude model alias |
| `AZURE_CLAUDE_OPUS` | Claude model alias |
| `AZURE_CLAUDE_SONNET` | Claude model alias |
| `AZURE_FOUNDRY_CLAUDE_API_ENDPOINT` | Azure AI Foundry Claude functions |
| `FIRECRAWL_API_KEY` | Firecrawl web scrape/search/extract/agent functions |
| `QLIK_PY_TOOLS_TEMP_DIR` | Optional persistent temp override |

## Model State

Several machine-learning functions create files under the runtime model folder. Treat that folder as service state:

- Back it up before replacing the runtime.
- Keep it on a persistent disk for Windows service deployments.
- Avoid sharing the same model folder between unrelated customer environments.
- Do not package trained customer models into a public download artifact.

## Documentation Boundary

The old sample applications, sample data, images, notebooks, and workshop files have been removed from `/docs`. The docs now describe capability usage directly and should remain portable across customer environments.
