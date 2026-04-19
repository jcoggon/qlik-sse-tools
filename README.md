# Qlik SSE Tools

Modern Python Server-Side Extension (SSE) tooling for Qlik Sense Client-Managed.

This repository exposes analytics, machine learning, forecasting, NLP, LLM, and web/document extraction workflows to Qlik through a gRPC-based SSE service. It is not just a mirror of the older upstream project: the current codebase has been substantially rebuilt for modern Python and current library versions, with new integrations and a cleaner operational workflow.

> The top-level README documents the current project. Older material under `docs/` is still useful for sample apps and reference assets, but parts of that folder predate the rebuild.

## What this project can do

- Train and score scikit-learn, XGBoost, LightGBM, and optional Keras models from Qlik.
- Run clustering, correlation analysis, association rules, and feature importance workflows.
- Forecast time series with Prophet and StatsForecast, including multivariate Prophet and intermittent-demand models.
- Handle sequence and lag-based prediction workflows for time series style use cases.
- Extract entities with spaCy and retrain NER models from Qlik-loaded data.
- Score pretrained models defined in YAML, including local scikit-learn, Keras, and REST-backed models.
- Call Azure OpenAI and Azure AI Foundry Claude models directly from Qlik expressions or load scripts.
- Scrape, search, extract, and agentically research content with Firecrawl.
- Parse local PDF, Word, Excel, CSV, and text files for document-driven workflows.

## Rebuild highlights

- Upgraded to Python `3.13+`.
- Refreshed the dependency stack for modern NumPy, Pandas, scikit-learn, Prophet, spaCy, OpenAI, Anthropic, and Firecrawl releases.
- Added Azure OpenAI chat functions and Azure-hosted Claude chat functions.
- Added Firecrawl-based web scraping, extraction, search, and agent functions.
- Added Nixtla StatsForecast support alongside Prophet.
- Added a standalone verification suite in [`TESTING.md`](TESTING.md).
- Added optional package bundles via `Qlik-Py-Extras.*`.
- Improved startup scripts so source changes sync into the runtime venv before launch.
- Added Windows service install/uninstall scripts using NSSM.
- Kept heavyweight components like TensorFlow/Keras lazily loaded so the core SSE can start more reliably.

## Feature areas

| Area | What is included |
| --- | --- |
| Core analytics | HDBSCAN clustering, geographic clustering, Pearson/correlation utilities, association rules |
| Forecasting | Prophet, holiday-aware Prophet, multivariate Prophet, seasonality outputs, StatsForecast (`AutoARIMA`, `AutoETS`, `AutoTheta`, `MSTL`, Croston-family models, and more) |
| Machine learning | End-to-end model setup, feature definition, fit, partial fit, predict, predict_proba, bulk prediction, cross-validation, grid search, confusion matrix, feature importances |
| Deep learning | Keras layer definition, training history, sequence prediction support, lazy TensorFlow/Keras loading |
| Text and NLP | spaCy entity extraction, model-based extraction, retraining workflows |
| Pretrained inference | YAML-defined sklearn, Keras, or REST prediction endpoints callable from Qlik |
| LLM integrations | Azure OpenAI chat and bulk chat, Azure AI Foundry Claude chat and bulk chat |
| Document and web intelligence | Firecrawl scrape, extract, search, agent modes, plus local PDF/Word/Excel/CSV parsing |

The current SSE registry exposes `59` functions across these areas.

## Quick start

### 1. Create your environment file

```bash
cp .env.example .env
```

On Windows:

```bat
copy .env.example .env
```

Populate the values you need for your deployment. Only the integrations you plan to use need credentials.

### 2. Initialize the runtime

macOS or Linux:

```bash
./Qlik-Py-Init.sh
```

Windows:

```bat
Qlik-Py-Init.bat
```

This creates `qlik-py-env/`, copies the source into the runtime location, installs dependencies, and downloads the default spaCy English model.

### 3. Start the SSE

macOS or Linux:

```bash
./Qlik-Py-Start.sh
```

Windows:

```bat
Qlik-Py-Start.bat
```

The server listens on port `50055` by default.

### 4. Configure the analytic connection in Qlik

Use these defaults unless you intentionally change them:

| Setting | Value |
| --- | --- |
| Name | `PythonSSE` |
| Host | `localhost` |
| Port | `50055` |

Example usage from Qlik:

```qlik
PythonSSE.LLM_Chat('Summarize this sales trend', 'system_prompt=You are a retail analyst')
```

```qlik
LOAD * EXTENSION PythonSSE.sklearn_Setup(MySetupTable{model_name, estimator_args, scaler_args, execution_args});
```

## Environment variables

The included [`.env.example`](.env.example) covers the currently supported external integrations:

| Integration | Required variables |
| --- | --- |
| Azure OpenAI | `AZURE_OPENAI_API_KEY`, `AZURE_OPENAI_ENDPOINT`, `AZURE_OPENAI_DEPLOYMENT`, optional `AZURE_OPENAI_API_VERSION` |
| Azure AI Foundry Claude | `AZURE_FOUNDRY_API_KEY`, `AZURE_FOUNDRY_CLAUDE_API_ENDPOINT`, `AZURE_FOUNDRY_API_VERSION`, Claude deployment names |
| Firecrawl | `FIRECRAWL_API_KEY` |

If you only want classical ML, forecasting, clustering, or spaCy-based functions, you can leave the LLM and Firecrawl credentials unset.

## Optional packages

After initialization, you can install extra capabilities with:

```bash
./Qlik-Py-Extras.sh --list
```

or on Windows:

```bat
Qlik-Py-Extras.bat --list
```

Available extras include larger spaCy models, Jupyter, Plotly, Excel support, and deep-learning bundles.

## Validation

- [`USAGE.md`](USAGE.md): full SSE function reference and calling patterns
- [`TESTING.md`](TESTING.md): setup, verification flow, and troubleshooting
- [`tests/test_all_tools.py`](tests/test_all_tools.py): standalone smoke and compatibility suite

## Windows deployment

For customer-server style Windows deployments, this repo includes:

- `Qlik-Py-Init.bat` for environment setup
- `Qlik-Py-Start.bat` for foreground execution
- `Qlik-Py-Service-Install.bat` and `Qlik-Py-Service-Uninstall.bat` for NSSM-backed Windows service management

## Repository layout

| Path | Purpose |
| --- | --- |
| `core/` | Main SSE implementation and feature modules |
| `generated/` | Generated protobuf and gRPC bindings |
| `tests/` | Standalone verification suite |
| `docs/` | Sample apps, sample data, legacy reference docs, and assets |
| `qlik-py-env/` | Runtime virtual environment created by the init scripts |

## Notes on legacy material

This repository still includes legacy sample apps and documentation assets because they are useful for testing and Qlik-side examples. The authoritative public entry points for the rebuilt project are this README, [`USAGE.md`](USAGE.md), and [`TESTING.md`](TESTING.md).

## Attribution

This project builds on the original [`qlik-py-tools`](https://github.com/nabeel-oz/qlik-py-tools) work by Nabeel Asif. The current repository has diverged significantly through modernization, dependency upgrades, new integrations, and workflow changes, but it still acknowledges that original foundation.

## License

This repository remains MIT licensed. The upstream MIT license has been restored in [`LICENSE`](LICENSE).
