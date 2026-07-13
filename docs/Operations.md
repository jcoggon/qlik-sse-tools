# Operations And Hardening

## Diagnostics

Run a non-listening startup check from the runtime core folder:

```bash
python __main__.py --check
```

The final JSON line reports version, Python, module status, function count, TLS configuration, worker count, and message limit.

## Health

The SSE implements the standard `grpc.health.v1.Health` service. Both the overall service (`""`) and `qlik.sse.Connector` report `SERVING` after the socket has started and transition during graceful shutdown.

## Configuration

| Variable | Default |
| --- | --- |
| `QLIK_SSE_PORT` | `50055` |
| `QLIK_SSE_WORKERS` | `10` |
| `QLIK_SSE_MAX_MESSAGE_MB` | `10` |
| `QLIK_SSE_SHUTDOWN_GRACE_SECONDS` | `5` |

Command-line arguments override these defaults.

## Windows Scheduled Tasks

The package includes restart-loop wrappers for unattended Windows deployments:

- `scripts/run-sse-service.ps1` starts the gRPC SSE and writes wrapper/process logs under the installation's `logs` folder.
- `scripts/run-cloud-service.ps1` starts the optional REST façade with the same restart and logging pattern.

Create scheduled tasks that run these scripts as the chosen service identity, start whether or not that user is logged on, and restart after host boot. Keep the task working directory at the installation root. The wrappers use `QLIK_SSE_PORT`, `QLIK_CLOUD_HOST`, and `QLIK_CLOUD_PORT` when configured and otherwise use the documented defaults.

Before switching an existing deployment, export its task definitions and keep the previous installation directory intact. Validate the replacement with `scripts/smoke_sse.py`, `/healthz`, and an authenticated capabilities request before removing the rollback copy.

## Mutual TLS

Production deployments can require mutual TLS:

```bash
python __main__.py --pem_dir /secure/cert-folder --require_tls
```

The folder must contain `sse_server_key.pem`, `sse_server_cert.pem`, and `root_cert.pem`. Configure the matching certificate path in the Qlik analytic connection. Store private keys outside the downloadable package and restrict filesystem permissions to the service identity.

## Service Identity

Run the process as a dedicated non-administrator account with write access only to its logs, runtime temp directory, and approved model directory. Do not grant the service broad access merely to support document parsing or model files.
