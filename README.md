# Qlik SSE Tools

Modern Python Server-Side Extension (SSE) tooling for Qlik Sense Client-Managed.

This repository exposes analytics, machine learning, forecasting, NLP, LLM, and web/document extraction workflows to Qlik through a gRPC-based SSE service. It is not just a mirror of the older upstream project: the current codebase has been substantially rebuilt for modern Python and current library versions, with new integrations and a cleaner operational workflow.

> The top-level README documents the current project. The `docs/` folder now contains lean Markdown reference pages for humans and AI agents; legacy sample apps, data files, notebooks, and screenshots have been removed.

## Recommended companion: Raptor MCP

This SSE can be used directly from Qlik Sense Client-Managed, but it also pairs with Raptor MCP as the recommended AI-assisted workflow for setup, troubleshooting, script generation, and customer-server operations.

Raptor MCP is the current product surface for the AI assistant runtime and downloadable client packages. Use it when you want an MCP-capable assistant to help inspect Qlik apps, reason about SSE usage, generate load-script patterns, or package this SSE for customer environments.

To learn more about Raptor MCP and the broader platform around it, visit [raptorbi.ai](https://raptorbi.ai/).

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

- Standardized on Python `3.13` while the native analytics stack completes Python 3.14 wheel support.
- Refreshed the dependency stack for modern NumPy, Pandas, scikit-learn, Prophet, spaCy, OpenAI, Anthropic, and Firecrawl releases.
- Added Azure OpenAI chat functions and Azure-hosted Claude chat functions.
- Added Firecrawl-based web scraping, extraction, search, and agent functions.
- Added Nixtla StatsForecast support alongside Prophet.
- Added a standalone verification suite in [`TESTING.md`](TESTING.md).
- Added optional package bundles via `Qlik-Py-Extras.*`.
- Improved startup scripts so source changes sync into the runtime venv before launch.
- Added Windows service install/uninstall scripts using Servy.
- Added a persistent runtime temp directory for Prophet/CmdStanPy so long-running Windows services do not depend on the user temp folder.
- Kept heavyweight components like TensorFlow/Keras lazily loaded so the core SSE can start more reliably.
- Added locked project metadata, security scanning, cross-platform CI, gRPC health checks, and real protocol tests.
- Added an authenticated REST façade for Qlik Cloud deployments.
- Added Azure/OpenAI Responses API functions, forecast interval tables, and anomaly detection.

## Feature areas

| Area | What is included |
| --- | --- |
| Core analytics | HDBSCAN clustering, geographic clustering, Pearson/correlation utilities, association rules |
| Forecasting | Prophet, multivariate Prophet, StatsForecast point forecasts, interval tables, and anomaly detection |
| Machine learning | End-to-end model setup, feature definition, fit, partial fit, predict, predict_proba, bulk prediction, cross-validation, grid search, confusion matrix, feature importances |
| Deep learning | Keras layer definition, training history, sequence prediction support, lazy TensorFlow/Keras loading |
| Text and NLP | spaCy entity extraction, model-based extraction, retraining workflows |
| Pretrained inference | YAML-defined sklearn, Keras, or REST prediction endpoints callable from Qlik |
| LLM integrations | Azure OpenAI chat, Responses API with strict JSON schemas, and Azure AI Foundry Claude |
| Document and web intelligence | Firecrawl scrape, extract, search, agent modes, plus local PDF/Word/Excel/CSV parsing |

The current SSE registry exposes `63` functions across these areas.

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

Prophet uses CmdStanPy, which writes temporary model data while fitting. The SSE now stores those files in a persistent runtime folder by default: `qlik-py-env/tmp`. If a customer needs a specific location, set `QLIK_PY_TOOLS_TEMP_DIR` in `.env`.

### 2. Initialize the runtime

Use maintained Python **3.13.18+ within the 3.13 series**. Setup installs the
hash-locked core bundle and verifies Pillow's independent native decoder.
Native repair supports reviewed Linux AMD64, macOS ARM64 and Windows AMD64
wheels (Windows requires installed MSVC C++ Build Tools and Windows SDK);
setup stops explicitly on unsupported architectures. See [Security.md](docs/Security.md)
for model trust, platform prerequisites and independently installed runtimes.

macOS or Linux:

```bash
./Qlik-Py-Init.sh
```

Windows:

```bat
Qlik-Py-Init.bat
```

This creates `qlik-py-env/`, copies the source into the runtime location, installs dependencies, and downloads the default spaCy English model.

## Build a download package

After changes are tested, create a clean customer download zip with:

```bash
./qlik-py-env/bin/python scripts/package_sse.py
```

By default this runs the standalone verification suite and writes
`dist/raptor-qlik-sse-tools.zip`, including frozen pip locks and native verification
scripts. Raptor Gateway's dedicated governed builder owns distribution. Import a
reviewed SSE source commit through that repository's source/lock/hash workflow;
local artifact copying is not a Raptor publication procedure.

### 3. Start the SSE

macOS or Linux:

```bash
./Qlik-Py-Start.sh
```

Windows:

```bat
Qlik-Py-Start.bat
```

The server listens on **`127.0.0.1:50055`** by default. Set `QLIK_SSE_HOST`
or pass `--host` to select another literal IPv4/IPv6 address. Start scripts
forward command-line options, for example `./Qlik-Py-Start.sh --host ::1`.
`localhost` explicitly selects IPv4 loopback; DNS names and resolver URLs are
not accepted as listener addresses.

**Existing remote clients:** earlier releases implicitly listened on `[::]`.
Before upgrading a remote deployment, select the intended interface with
`--host`/`QLIK_SSE_HOST` and retain its mutual-TLS certificate configuration.
See [Operations](docs/Operations.md#mutual-tls) for explicit remote examples.
Changing the Qlik connection host does not restrict the Python listener.

Run a non-listening diagnostic check with `cd core && ../qlik-py-env/bin/python __main__.py --check`. The configured bind address is included in diagnostics. Host, port, worker count, message size, and shutdown grace are configurable through `.env`.

### 4. Configure the analytic connection in Qlik

Use these defaults unless you intentionally change them:

| Setting | Value |
| --- | --- |
| Name | `PythonSSE` |
| Host | `127.0.0.1` |
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
| Qlik Cloud REST API | `QLIK_CLOUD_API_KEY`; bind and port are optional |

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

Available extras include larger spaCy models, Jupyter, Plotly, deep learning, and the Qlik Cloud API. TensorFlow/Keras are no longer forced into every core installation.

### Qlik Cloud REST façade

```bash
./Qlik-Py-Extras.sh qlik_cloud
export QLIK_CLOUD_API_KEY="$(python -c 'import secrets; print(secrets.token_urlsafe(32))')"
./Qlik-Py-Cloud-Start.sh
```

The default bind is `127.0.0.1:8080`. Put it behind an HTTPS reverse proxy before exposing it beyond the host. See [`docs/Cloud-API.md`](docs/Cloud-API.md).

## Validation

- [`USAGE.md`](USAGE.md): full SSE function reference and calling patterns
- [`TESTING.md`](TESTING.md): setup, verification flow, and troubleshooting
- [`CHANGELOG.md`](CHANGELOG.md): release history and upgrade highlights
- [`tests/test_all_tools.py`](tests/test_all_tools.py): standalone smoke and compatibility suite
- `tests/test_server_integration.py`: real health, capability, and function execution over gRPC
- `tests/test_cloud_api.py`: authenticated REST forecast, anomaly, correlation, and Responses API checks
- `.github/workflows/ci.yml`: Python 3.13 verification on Windows, Linux, and macOS

## Windows deployment

For customer-server style Windows deployments, this repo includes:

- `Qlik-Py-Init.bat` for environment setup
- `Qlik-Py-Start.bat` for foreground execution
- `Qlik-Py-Service-Install.bat` and `Qlik-Py-Service-Uninstall.bat` for Servy-backed Windows service management.

The SSE download package does not bundle Servy. Before running the service installer, install Servy system-wide or download the Servy x64 installer from <https://github.com/aelassas/servy/releases> and place `servy-8.5-x64-installer.exe` beside `Qlik-Py-Service-Install.bat`.

## Repository layout

| Path | Purpose |
| --- | --- |
| `core/` | Main SSE implementation and feature modules |
| `generated/` | Generated protobuf and gRPC bindings |
| `tests/` | Standalone verification suite |
| `docs/` | Markdown-only capability reference for humans and AI agents |
| `qlik-py-env/` | Runtime virtual environment created by the init scripts |

## Notes on documentation

The authoritative public entry points for the rebuilt project are this README, [`USAGE.md`](USAGE.md), [`TESTING.md`](TESTING.md), and the Markdown-only capability references under `docs/`.

## Attribution

This project builds on the original [`qlik-py-tools`](https://github.com/nabeel-oz/qlik-py-tools) work by Nabeel Asif. The current repository has diverged significantly through modernization, dependency upgrades, new integrations, and workflow changes, but it still acknowledges that original foundation.

## License

This repository remains MIT licensed. The upstream MIT license has been restored in [`LICENSE`](LICENSE).
