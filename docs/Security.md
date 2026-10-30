# SSE security and standalone provisioning

Qlik SSE is owned by `jcoggon/qlik-sse-tools`. Raptor Gateway imports and packages
this source through its separately governed builder. A source ZIP contains no
virtual environment. Neither a new ZIP nor a patched Gateway builder upgrades an
independently installed SSE runtime.

## Frozen installation

Use maintained CPython **3.13.18 or later in the 3.13 series**. The init scripts
create `qlik-py-env`, then call `scripts/provision.py core`. Cloud and deep-learning
extras call that same provisioner with their own bundle. It installs hash-locked
bootstrap tools and the complete bundle using `--require-hashes`, wheels only,
and no build isolation, runs `pip check`, then repairs/qualifies Pillow's decoder.
A missing wheel is a qualification failure; setup does not silently fall back to
an unpinned native source build. An existing importable optional package is still
upgraded to the reviewed bundle when explicitly selected.

`requirements*.txt` and `pyproject.toml` are reviewed inputs; `uv.lock` owns the
resolved dependency graph. `locks/{core,cloud,deep-learning,dev}.lock` are pip
exports of that graph, including hashes and platform markers. The dev bundle
includes cloud, while core excludes TensorFlow/Keras. Other optional extensions
(Jupyter, extra spaCy models, Plotly) retain the graph's constraints; their extra
packages are not represented as a fully frozen supported runtime bundle.

After changing inputs, with uv **0.10.12**:

```sh
uv lock --refresh-package raptor-qlik-sse-tools
python scripts/export_locks.py
uv pip compile --universal --python-version 3.13 --generate-hashes --no-header --no-annotate requirements-bootstrap.in -o locks/bootstrap.lock
python scripts/export_locks.py --check
```

Do not edit resolved hashes manually. Strict audit remains required for every
complete exported bundle. Auditing with `--no-deps --disable-pip` uses the complete
resolved inputs without creating a second resolver environment; it does not
ignore advisories. Native components require separate checks.

## Pillow's independent Brotli decoder

Pillow **13.0.0 alone is insufficient**. Its reviewed CPython 3.13 Linux AMD64
wheel bundles Brotli 1.2.0 under `pillow.libs`; the macOS ARM64 wheel bundles it
under `PIL/.dylibs`. `scripts/pillow_native.py --repair` accepts only the exact
reviewed preimage library hashes. It builds checksum-pinned Brotli **1.2.1** source
commit `db24a98aed38a16de78cc05ca15cdd8dc2a0d92d`, runs all available upstream
CTest cases, repairs linkage, and updates installed `RECORD` and a provenance
receipt. A separate process reads back the decoder version, exercises bounded
decompression, six image codecs and FreeType. Failure rolls back replaced bytes.
Reinstalling Pillow requires repeating the repair; running the script without
`--repair` verifies the installed bytes and receipt without changing them.

A C compiler/toolchain is required. Bootstrap locks supply CMake and Linux
patchelf. macOS uses Xcode's `install_name_tool` and ad hoc `codesign`. No compiler,
system package, system trust store or service is changed automatically by this
repair. In an isolated build with mismatched Command Line Tools, explicitly set
`SDKROOT` to the matching Xcode SDK for that build only.

**Platform qualification boundary:** Linux AMD64 policy reuses the exact Gateway
repair inputs. macOS ARM64 has a separately reviewed wheel policy. Windows AMD64
Pillow statically incorporates Brotli into its FreeType extension (upstream
`winbuild/build_prepare.py` and `.github/dependencies.json` pin 1.2.0); no safe DLL
swap is available. Windows, macOS Intel, Linux ARM and other wheels are currently
unqualified by this upstream repair and provisioning explicitly stops there.
This is a distribution hold for those platforms, not a claim that their native
decoder was fixed. A separately reviewed fixed Windows wheel build, with frozen
native inputs, component provenance and codec/font qualification, remains needed.
Existing functionality must be retained when that build is qualified.

Installing this project directly with pip or uv installs the dependency baseline
but does not execute native repair hooks. Such environments require the same
explicit repair/readback before security acceptance. The source ZIP includes the
locks and repair script; it contains no prepatched native binaries.

## Models are executable trusted inputs

Only trusted operators may write model directories, YAML definitions, Python
custom objects or model artifacts. Do not expose these directories as untrusted
upload destinations. Pickle/joblib can execute Python during deserialization.
Keras safe mode is not a sandbox and does not cover all HDF5 behavior. Patched
Keras **3.15.0**, TensorFlow **2.21.0**, scikeras **0.13.0** and h5py **3.14.0** are
retained as the tested deep-learning coordinates; loading remains lazy.

All three Keras load paths enforce the patched baseline and `safe_mode=True`.
Qlik-supplied model names cannot traverse directories. Local serialized files
must be regular files within the configured size budget (default 1 GiB,
`QLIK_MODEL_MAX_BYTES`). YAML may supply `sha256` and `preprocessor_sha256` for
operator-reviewed pretrained artifacts.

For mandatory provenance, set `QLIK_MODEL_MANIFEST` to an operator-owned JSON file
mapping canonical absolute artifact paths to approved SHA-256 digests. Once set,
every loaded pickle/joblib/Keras artifact must appear with matching bytes. Include
both a persistent pipeline's `.joblib` and `.h5` artifacts. Newly trained or
replaced artifacts require approval of their new hashes before loading. Without
a manifest, the historical operator-managed local-file trust boundary remains.
Checks do not replace filesystem ACLs, prevent a privileged operator changing
files between checks and use, or authorize hostile models.

## REST prediction responses

Configured endpoints retain Requests' TLS certificate and hostname checks.
Requests use connect/read timeouts of 5/30 seconds, stream decoded JSON up to
8 MiB by default, and enforce a 60-second elapsed deadline between chunks.
Operators can set `QLIK_REST_MAX_RESPONSE_BYTES` and
`QLIK_REST_RESPONSE_SECONDS` (positive; deadline at most 3600 seconds). Redirects
require updating the explicit endpoint configuration. Non-success status codes,
oversized responses and elapsed deadlines fail the prediction call and close the
response. The elapsed check is not a hard process/CPU deadline: patched urllib3
remains independently required for chunk parser/deflate progress guarantees.

The owned service is gRPC; its optional cloud façade is FastAPI/Uvicorn. No owned
aiohttp server or AnyIO process-pool route has been established. Their presence
through SDK/transitive dependencies is not evidence of exploitation. SDK-level
HTTP paths and document/image features still require deployment-specific input,
network and resource-boundary review.
