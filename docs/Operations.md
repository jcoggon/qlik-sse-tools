# Operations And Hardening

## Diagnostics

Run a non-listening startup check from the runtime core folder:

```bash
python __main__.py --check
```

The final JSON line reports version, Python, module status, function count, configured
host/bind address, TLS configuration, worker count, and message limit. This check
does not open a socket. Normal startup logs show the actual chosen address and
bound port, including an allocated port when `--port 0` is used.

## Health

The SSE implements the standard `grpc.health.v1.Health` service. Both the overall service (`""`) and `qlik.sse.Connector` report `SERVING` after the socket has started and transition during graceful shutdown.

## Configuration

| Variable | Default |
| --- | --- |
| `QLIK_SSE_HOST` | `127.0.0.1` |
| `QLIK_SSE_PORT` | `50055` |
| `QLIK_SSE_WORKERS` | `10` |
| `QLIK_SSE_MAX_MESSAGE_MB` | `10` |
| `QLIK_SSE_SHUTDOWN_GRACE_SECONDS` | `5` |

Command-line arguments override these defaults.

`--host` accepts literal IPv4/IPv6 addresses and the `localhost` alias for
`127.0.0.1`. IPv6 is formatted correctly for gRPC; `::1` selects IPv6 loopback,
and `0.0.0.0`/`::` explicitly select wildcard listeners. DNS names, resolver URLs,
embedded ports, whitespace and scoped IPv6 are rejected. Keep the port separate.

### Listener migration

Earlier releases bound both secure and insecure listeners to `[::]` implicitly.
The new default is IPv4 loopback. Same-host Qlik connections should use
`127.0.0.1:50055`, or explicitly select `--host ::1` with a matching IPv6 client.
Remote installations must opt into the intended interface or wildcard and retain
the existing mutual-TLS setup described below. A QMC client connection pointing
at loopback does not establish how the Python server is bound.

The bind option controls reachability; selecting a non-loopback address alone
does not enable TLS or authenticate clients. Preserve network access policy and
certificate identities when changing an existing remote service configuration.

## Windows Scheduled Tasks

The package includes restart-loop wrappers for unattended Windows deployments:

- `scripts/run-sse-service.ps1` starts the gRPC SSE and writes wrapper/process logs under the installation's `logs` folder.
- `scripts/run-cloud-service.ps1` starts the optional REST façade with the same restart and logging pattern.

Create scheduled tasks that run these scripts as the chosen service identity, start whether or not that user is logged on, and restart after host boot. Keep the task working directory at the installation root. The SSE process reads `QLIK_SSE_HOST` from its environment/runtime `.env`; the
wrapper forwards additional arguments, including `--host`, `--pem_dir` and
`--require_tls`. The wrappers also use `QLIK_SSE_PORT`, `QLIK_CLOUD_HOST`, and
`QLIK_CLOUD_PORT` when configured and otherwise use the documented defaults.

Before switching an existing deployment, export its task definitions and keep the previous installation directory intact. Validate the replacement with `scripts/smoke_sse.py`, `/healthz`, and an authenticated capabilities request before removing the rollback copy.

## Mutual TLS

Production deployments can require mutual TLS:

```bash
python __main__.py --host 0.0.0.0 --port 50055 --pem_dir /secure/cert-folder --require_tls
```

The folder must contain `sse_server_key.pem`, `sse_server_cert.pem`, and `root_cert.pem`. Configure the matching certificate path in the Qlik analytic connection. Store private keys outside the downloadable package and restrict filesystem permissions to the service identity.

That example deliberately exposes IPv4 interfaces with mutual TLS. Use an
assigned literal interface IP instead of `0.0.0.0` to narrow the bind, or `::`
for an explicit IPv6 wildcard. The server certificate must match the client's
connection identity, and clients must present a certificate trusted by
`root_cert.pem`; server-side client-certificate verification remains required.

## Service Identity

Run the process as a dedicated non-administrator account with write access only to its logs, runtime temp directory, and approved model directory. Do not grant the service broad access merely to support document parsing or model files.
