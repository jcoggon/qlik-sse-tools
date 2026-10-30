# Changelog

## Unreleased

- Default the gRPC listener to IPv4 loopback and add validated `--host`/`QLIK_SSE_HOST` selection for plaintext and mutual-TLS modes. Existing remote clients must explicitly select their interface/wildcard and retain TLS configuration. Start wrappers forward these options; startup/diagnostics show the selected address.

- Refresh the supported analytics, scraping, LLM, cloud and developer dependency graph, including Firecrawl 4.54, OpenAI 3.41, Anthropic 2.3, StatsForecast 2.1 and SciPy 1.18.
- Freeze notebook, Plotly and curated transformer extras with complete hashed exports; update and pin CI actions and uv.
- Repair Pillow's independent Brotli decoder to 1.2.1 on reviewed Windows AMD64, Linux AMD64 and macOS ARM64 wheels, retaining native provenance and codec/font checks.
- Bound REST model responses, constrain local model names and enforce patched Keras safe loading with optional artifact digest admission.
- Regenerate Python gRPC bindings with current tools while preserving the SSE protocol and function registry.
- Retain pandas 2.3.3, h5py 3.14.0 and curated transformers 0.3.1 where current upstream dependency constraints require them. Pretrained model assets remain separate downloads.

## 3.1.0 - 2026-07-13

### Added

- Authenticated Qlik Cloud REST façade for forecasting, anomaly detection, correlation, and Responses API workloads.
- StatsForecast prediction-interval and anomaly table functions.
- Azure/OpenAI Responses API functions with structured JSON output support.
- Standard gRPC health reporting, startup diagnostics, configurable runtime limits, and graceful shutdown.
- Cross-platform CI, dependency auditing, protocol integration tests, and reproducible dependency locking.
- Windows scheduled-task runners and a live SSE smoke-test utility.

### Changed

- Standardized the supported runtime on Python 3.13 and refreshed the maintained analytics stack.
- Split deep-learning and Qlik Cloud dependencies into optional bundles so the core SSE remains lighter.
- Expanded the public registry from 59 to 63 functions.
- Hardened initialization, packaging, temporary storage, and service-operation behavior.

### Upgrade notes

- Install into a new directory and preserve the previous deployment until gRPC and Qlik reload tests pass.
- Recreate the Python 3.13 virtual environment; do not reuse an environment from an older Python release.
- Run `Qlik-Py-Extras` for optional deep-learning or Qlik Cloud dependencies.
- Configure a new random `QLIK_CLOUD_API_KEY` and an HTTPS reverse proxy before exposing the REST façade.
