# Optional local Windows native delivery

The default standalone provisioning route still requires existing MSVC C++ Build
Tools and a Windows SDK. It compiles the pinned Pillow font extension locally and
fails if prerequisites or any native checks fail. There is no automatic fallback.

An operator may instead explicitly deliver a reviewed Windows native test artifact
from this repository's successful CI. This narrow route accepts only ordinary
GIL CPython 3.13.18 AMD64 from the exact full python-build-standalone supplier in
`scripts/windows-native-python.json`, in a private virtual environment, with the
exact original Pillow 13.0.0 Windows wheel. It does not accept arbitrary compatible
Python builds, later patch versions, ARM64, debug/free-threaded builds or copied
extensions. It does not change models, service/task configuration or the host.
The initial route is operator-local; it is not a public binary release channel.

## Producer and qualification

1. Windows CI stages one size/SHA-verified full runtime archive, safely validates
   its fixed tar layout, verifies base Python/DLL hashes, then reads back the
   actual 3.13.18 AMD64 runtime. The cached setup-python interpreter only downloads
   this archive; it is not the qualification interpreter. Runtime staging changes
   only scoped CI step PATH, with no registry/system launcher changes.
2. CI verifies the complete original vendor wheel and installed RECORD, performs
   the existing pinned source build and 14 Brotli CTests, and executes the real
   decoder 1.2.1/bounded decompression/WOFF2/six-codec/default-font/text-feature
   checks. Compiler/SDK identities and tool binary hashes are read back inside
   the same build environment used for the extension.
3. Only after these pass, CI exports `windows-native-bundle.zip` and an external
   `producer-receipt.json` to one immutable artifact. The inner ZIP contains one
   extension, one pinned WOFF2 fixture, six licenses, manifest and native receipt.
   Dedicated bounds are 16 MiB compressed, 32 MiB expanded, 16 MiB extension and
   128 KiB per other member. All inventories are exact; aliases, links, unknown
   members, encryption and unsupported compression fail. No executable goes in
   the governed Gateway source ZIP and no general archive limit changes.
4. CI downloads the artifact by immutable ID and applies it in a fresh original
   wheel environment with compiler discovery/build replaced by failing sentinels.
   It uses a clearly marked CI fixture approval from trusted workflow/upload
   outputs, because the run is not complete yet. This is not production approval.
   Real fresh-process native checks and idempotent readback must pass. Separate
   regressions reject digest/source/ABI/runtime/preimage/RECORD/member/alias/
   custody drift, incomplete GitHub proof, and test rollback and concurrent change.

The workflow checks out the actual PR head, rather than its synthetic merge.
Manifest provenance records actual git HEAD/tree, raw source/recipe/input/lock/
workflow/test bytes plus Git blob IDs, producer run/attempt and all postimages.
LF attributes keep these trusted bytes identical in Windows checkouts and source
archives. No normalization or user-supplied recipe/source override is accepted.
Prior native CI used a cached older Windows 3.13 interpreter: those results prove
ABI/native behavior, not Windows 3.13.18 execution. New CI explicitly qualifies
both producer and consumer on the exact maintained supplier.

## Complete-source boundary

Approval, application and later native verification require the complete clean
canonical checkout at the qualified consumer commit, including the reviewed
workflow, tests, lock files and installation helpers in `source_files()`. The
standalone source ZIP and Gateway's pruned runtime companion do not contain that
complete checkout and cannot independently perform this contract. Retain the
pinned full checkout in operator-controlled storage for these operations. Gateway
may quarantine producer/bootstrap/approval tools from its runtime companion; no
missing-file exception or relaxed source check is added to fit that companion.
Gateway's owner controls its separate member policy and candidate provisioning.

## Independent operator approval

Use an existing authenticated `gh` session on the source/review host. Download the
raw GitHub artifact ZIP by the selected immutable artifact ID to private operator
storage. Preserve its original transport bytes. From a clean reviewed checkout:

```text
python scripts/approve_pillow_bundle.py --transport /private/transport.zip \
  --run-id RUN_ID --artifact-id ARTIFACT_ID --source-commit CONSUMER_COMMIT \
  --output /private/approved-native
```

The issuer queries the real completed successful CI run, all ten required jobs,
actual consumer execution proof, artifact API ID/name/digest/expiry, repository
identity, producer/consumer Git commits/trees and critical source blobs. Consumer
execution requires authenticated bounded GitHub job logs with the exact reviewed
command, two actual successful post-apply native probe receipts and the final
matching source/bundle/runtime/compiler result. Any available step metadata must
also show success; empty step arrays are not treated as a passed step. The issuer
reports the explicit authenticated job-log method, job ID and complete log SHA.
Missing or differing logs/results fail approval. Producer
and consumer commits may differ only when their complete trees are identical
(for example, a reviewed squash merge). It hashes the raw transport before
opening it, then verifies the exact outer inventory, inner bundle, receipts and
current trusted source. Failed/incomplete runs and stale/foreign bytes cannot
produce an approval. The issuer exports only the inner ZIP, separate approval
record and their SHA256 values. It neither reads nor exports authentication tokens.

**Trust boundary:** the target is offline for approval verification. The operator
must independently review the issuer's GitHub evidence and supply both digests
through the trusted deployment process. The approval is not signed; its fields
and the embedded manifest cannot authenticate themselves. Supplying an arbitrary
approval file and its own calculated hash is not independent approval. Compromise
of the operator, reviewed source, GitHub workflow or CI runner is outside this
mechanism's proof. The installer owner must review source/tree/artifact identity
before any target apply; a green producer job alone is insufficient.

## Explicit consumer

In a new private environment using the exact qualified runtime, pass all four
local inputs; do not derive the approved digest from the arriving file:

```text
python scripts/provision.py core \
  --native-bundle /private/approved-native/windows-native-bundle.zip \
  --native-bundle-sha256 INDEPENDENTLY_APPROVED_BUNDLE_SHA256 \
  --native-approval /private/approved-native/native-approval.json \
  --native-approval-sha256 INDEPENDENTLY_APPROVED_APPROVAL_SHA256
```

This explicit route checks runtime, digests and source provenance before pip
runs, then installs the unchanged frozen bootstrap/core requirements, verifies
the complete vendor wheel payload and RECORD before importing any Pillow code,
and snapshots original optional text features in a fresh process. Only legitimate
pip metadata and mutable CPython 3.13 caches are permitted; isolated probes use a
fresh cache prefix and never load those existing caches. An existing different
repair or package drift fails closed; use a fresh environment rather than mutate
an unqualified installation. Other bundles may be selected with the same flags.

Application stages files privately, rechecks the preimage immediately before
replacement, writes exact payload/approval/native receipt and installed RECORD,
then runs the full native probes in fresh processes. Stored approval and payload
hashes are verified on every later native probe before loading the extension.
Probe failure restores original bytes and RECORD only while this transaction
still owns them. If another writer changes custody, application fails and retains
backups for operator recovery without overwriting that writer's changes.

The default init/extras scripts retain source-build behavior. This opt-in path
must be invoked explicitly by the authorized operator; it does not install a
compiler, download an unapproved native bundle or bypass native acceptance.
Gateway packaging/installation/publication and Qlik Demo testing remain separate
owned stages tracked by Gateway issue #654. No source CI result proves installed
customer/Demo behavior or hostile-model safety.
