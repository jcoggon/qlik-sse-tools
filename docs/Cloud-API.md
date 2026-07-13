# Qlik Cloud REST API

The optional Cloud API exposes the maintained analytics stack over authenticated HTTP for Qlik Cloud REST connections, application automations, and other HTTPS clients.

## Install And Start

```bash
./Qlik-Py-Extras.sh qlik_cloud
export QLIK_CLOUD_API_KEY="replace-with-a-long-random-secret"
./Qlik-Py-Cloud-Start.sh
```

Windows operators can use `Qlik-Py-Cloud-Start.bat` or `Qlik-Py-Cloud-Start.ps1`.

The service binds to `127.0.0.1:8080` by default. Keep that private bind and place IIS, Caddy, nginx, or another approved HTTPS ingress in front of it. If the process must bind to another interface, set `QLIK_CLOUD_HOST` deliberately.

## Authentication

All `/v1/*` routes require either:

- `X-API-Key: <QLIK_CLOUD_API_KEY>`
- `Authorization: Bearer <QLIK_CLOUD_API_KEY>`

`/healthz` is intentionally unauthenticated and returns only status and version. The API refuses protected requests when no key is configured. `QLIK_CLOUD_ALLOW_INSECURE=true` exists only for isolated local development.

## Endpoints

| Route | Purpose |
| --- | --- |
| `GET /healthz` | Load balancer health check |
| `GET /v1/capabilities` | Models, endpoints, and row limit |
| `POST /v1/forecast` | Point forecasts and prediction intervals |
| `POST /v1/anomalies` | Fitted expectations, intervals, and anomaly flags |
| `POST /v1/correlation` | Pearson, Spearman, or Kendall correlation |
| `POST /v1/responses` | Azure/OpenAI Responses API, including strict JSON schemas |

Example forecast body:

```json
{
  "series": [
    {"date": "2026-01-01T00:00:00Z", "value": 120.0},
    {"date": "2026-01-02T00:00:00Z", "value": 126.0}
  ],
  "model": "AutoARIMA",
  "freq": "D",
  "periods": 7,
  "level": 95
}
```

The response contains a `rows` array designed for Qlik REST Connector selection. Use POST, add the API key as an encrypted request header, and enable HTTPS-only operation in the Qlik connection.

## Qlik Cloud REST Connection

Create a REST connection in a personal or shared space with these settings:

1. Use the public HTTPS reverse-proxy URL for the required `/v1/*` route.
2. Select `POST` for forecast, anomaly, correlation, and Responses requests.
3. Add `X-API-Key` as an encrypted request header. Never place the key in a load script.
4. Set the request content type to `application/json` and provide the JSON body in the connection.
5. Test the connection, then select fields from the returned `rows` array.

Keep separate REST connections for materially different request bodies. Qlik stores the request configuration with the connection, which makes a dedicated forecast connection easier to govern and reuse than dynamically rewriting one connection.

For a forecast response, the useful fields under `rows` are `date`, `forecast`, `lower`, and `upper`; the top-level `model` and `level` values can be loaded as metadata. Validate a new deployment with a small fixed series before connecting production data.

## Limits And Safety

- `QLIK_CLOUD_MAX_ROWS` defaults to `10000`.
- Interactive OpenAPI docs are disabled unless `QLIK_CLOUD_ENABLE_DOCS=true`.
- No permissive CORS middleware is enabled.
- Do not expose Uvicorn directly to the public internet.
- Keep model/API credentials in the process environment or approved secret store, not in Qlik scripts.
