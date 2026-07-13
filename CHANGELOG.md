# Changelog

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
