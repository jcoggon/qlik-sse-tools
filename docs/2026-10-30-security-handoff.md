# Canonical SSE security repair and Gateway integration handoff

## Ownership and observed baseline

The canonical repository is [jcoggon/qlik-sse-tools](https://github.com/jcoggon/qlik-sse-tools).
Its default `master` was freshly fetched at
`8bb3a2767d9a72513840f4f0e683ae72c093eb1c`. The existing dependency PR
[#15](https://github.com/jcoggon/qlik-sse-tools/pull/15) proposes 31 broader updates
without updating `uv.lock`; this change does not adopt that unrelated refresh.
The two existing local project chats were `notLoaded`, with no overlapping
active executor observed. Original untracked `.DS_Store` and `graphify-out/`
were preserved. The existing Graphify query was verified against owning files.

Gateway's latest comments on [#623](https://github.com/jcoggon/raptor-gateway/issues/623),
[#624](https://github.com/jcoggon/raptor-gateway/issues/624),
[#628](https://github.com/jcoggon/raptor-gateway/issues/628),
[#629](https://github.com/jcoggon/raptor-gateway/issues/629) and
[#630](https://github.com/jcoggon/raptor-gateway/issues/630) report completed
source/build remediation in merged [#632](https://github.com/jcoggon/raptor-gateway/pull/632),
retained in merged [#646](https://github.com/jcoggon/raptor-gateway/pull/646),
and released as **2026.10.30.1** from
`54d1af2dc26f165e038b3735df125d54b0f4658e`. Those comments retain independent
installation/model-trust acceptance. This work changes no Gateway checkout,
builder, hosted service, customer runtime or published download.

The exact-source [Gateway remediation record](https://github.com/jcoggon/raptor-gateway/blob/54d1af2dc26f165e038b3735df125d54b0f4658e/docs/security/2026-10-29-gateway-remediation.md)
and owning source were read. Gateway still imports SSE application revision
`23ae07d3a9afbb103b0ea0a789e37b9e57299174`, with reviewed dependency overrides.
At that Gateway revision, `source.json` records source archive SHA-256
`d8b3f2aa70bba0c899b8d63ec452ee5fd9937e23db1b49a4e409d2f67e1ad305`,
runtime lock SHA-256
`eb5585b04b81cc8df7bcbb58bd874c9e61c579fa0d22fce78e7b275f1d5f38a2`,
and build lock SHA-256
`4f83d9cafd3046ed2b9b874a11ae061771e8848505bbdf14cf35c26958b1d2aa`.
These are historical downstream input identities, not hashes for this change.

## Source changes and dependency decisions

| Component | Canonical source before | Reviewed upstream coordinate | Scope/primary evidence |
| --- | --- | --- | --- |
| certifi | uv lock 2026.6.17 | 2026.10.19 | [Maintainer advisory](https://github.com/certifi/python-certifi/security/advisories/GHSA-6q48-6c7w-9gw2) names 2026.10.18 as fixed. Audit PYSEC metadata instead recommends 2026.10.19, restoring unaffected roots. Use the later [maintainer release](https://github.com/certifi/python-certifi/releases/tag/2026.10.19), retain an actual compromised ECC G3 root-absence check, and record the metadata disagreement. |
| urllib3 | uv lock 2.7.0 | 2.8.0 | [Chunk line](https://github.com/urllib3/urllib3/security/advisories/GHSA-vxq7-64xx-v4gw): >=1.10.3,<2.8.0. [Deflate progress](https://github.com/urllib3/urllib3/security/advisories/GHSA-gh4c-6fx4-qh6g): >=2.6.2,<2.8.0. Configured Requests model endpoints are an owned path; attacker control is unproven. |
| Keras | canonical 3.15.0; old Gateway lock 3.13.2 | 3.15.0, unchanged | [Maintainer release](https://github.com/keras-team/keras/releases/tag/v3.15.0), [HDF5 validation fix](https://github.com/keras-team/keras/commit/d5a88bdb137c0d3039b8f4bbbe8c7099925cc10c), [shape validation fix](https://github.com/keras-team/keras/commit/4933ea4a5b3fcc24ceacdc276f5bb5dfbd06756c). GHSA-26c4 includes a fixed 3.12.3 backport and affected >=3.13.0,<3.15.0 branch; GHSA-74m6 fixes <3.15.0. All three owned loaders enforce the baseline and safe mode; trusted models remain required. |
| Pillow | uv lock 12.3.0 | 13.0.0 plus separate native repair | [MIC](https://github.com/python-pillow/Pillow/security/advisories/GHSA-22hg-r758-rrw9): 7.2.0–12.3.0, optional olefile and n_frames. [Multi-frame](https://github.com/python-pillow/Pillow/security/advisories/GHSA-v9pv-5gc8-w2m6): >=11.0.0,<=12.3.0, mode-transition decoder path. [FPX JPEG](https://github.com/python-pillow/Pillow/security/advisories/GHSA-5x8w-8jj5-q52h): separate decoder/olefile prerequisite. No owned PIL image-open sink or installed olefile established. No product RCE claimed. |
| Brotli inside Pillow | reviewed Linux and macOS wheels 1.2.0 | 1.2.1 | [Vendor release](https://github.com/google/brotli/releases/tag/v1.2.1); checksum-pinned source, exact wheel preimages, runtime version/bytes/RECORD and codec/font gates. Updating a Python Brotli package, Node or a system library would not replace this copy. |
| aiohttp | uv lock 3.14.1 | 3.14.4 | [Resource bounds](https://github.com/aio-libs/aiohttp/security/advisories/GHSA-2g87-pp6c-29x5): <=3.14.3, fixed3.14.4; [C parser](https://github.com/aio-libs/aiohttp/security/advisories/GHSA-cq5v-8q36-5273): <=3.14.2, fixed3.14.3. Maintainer metadata governs. No owned aiohttp service path established. |
| AnyIO | uv lock already 4.14.2 | 4.14.2 | [Process-pool stderr](https://github.com/agronholm/anyio/security/advisories/GHSA-5p39-cfhj-2xmp) and [IDNA TLS](https://github.com/agronholm/anyio/security/advisories/GHSA-82r6-8w77-94w6): <=4.14.1. [Supplementary groups](https://github.com/agronholm/anyio/security/advisories/GHSA-3w57-8xmc-8v26) lists only4.14.0; do not label4.14.1 affected by that separate finding. Specific feature exposure unproven. |
| multidict | uv lock 6.7.1 | 6.9.1 | [Items-view reference leak](https://github.com/aio-libs/multidict/security/advisories/GHSA-54p9-h82j-f925): >=6.7.0,<=6.9.0 C extension; items-view reflected union/subtraction. |
| yarl | uv lock 1.24.2 | 1.25.1 | Required compatibility baseline for aiohttp3.14.4, reused from the real Gateway lock resolution. |
| cryptography | uv lock 49.0.0 | 50.0.0 | Strict audit surfaced [PKCS#7 oracle](https://github.com/pyca/cryptography/security/advisories/GHSA-g6cj-pr64-35w5). Requires adaptive untrusted EnvelopedData decryption; no owned route established. Vendor notes OpenSSL backend differences and separate inherent unauthenticated CBC limitations. |
| setuptools | uv lock 83.0.0 | 84.2.1 | Strict audit surfaced [legacy Windows wheel path escape](https://github.com/pypa/setuptools/security/advisories/GHSA-xmj3-9gf7-h52w), >=38.2.2,<84.1.0. No claim that ordinary pip wheel installation uses that legacy API. Build-system and bootstrap pins align. |
| Dev-only filelock / msgpack / pytest | 3.29.7 /1.2.1 /9.0.2 | 4.2.1 /1.2.3 /9.0.3 | Full dev audit additionally required these updates. They remain outside the core runtime. Primary range and feature notes below; no advisory is ignored. |
| Python / pip | installers accepted any3.13 / unpinned tool uplift | Python>=3.13.18,<3.14 / pip26.2.2 | Reuse the maintained baseline of closed Gateway#625/#627 for SSE-owned standalone setup; do not reopen or redo the official builder repair. |

Dev-only filelock primary records were reviewed individually: SQLite
[path/side files](https://github.com/tox-dev/filelock/security/advisories/GHSA-v4x8-3wr5-3wq8),
[Windows side files](https://github.com/tox-dev/filelock/security/advisories/GHSA-9vhv-jxww-xfm5)
and [schema resource use](https://github.com/tox-dev/filelock/security/advisories/GHSA-cwqr-hh33-gh44)
cover >=3.20.4,<=4.2.0; the earlier [SQLite symlink](https://github.com/tox-dev/filelock/security/advisories/GHSA-j8f7-rjxc-mr56)
covers >=3.20.4,<=4.0.8 and fixes4.0.9. Windows
[oplocks](https://github.com/tox-dev/filelock/security/advisories/GHSA-567q-5qvw-pf92),
soft-lock [forged PID](https://github.com/tox-dev/filelock/security/advisories/GHSA-rfpc-qcw5-3pc4)
and [inode reuse](https://github.com/tox-dev/filelock/security/advisories/GHSA-fq56-3cx3-fjxp)
cover >=3.22.0,<=4.2.0. Windows
[inherited ACL](https://github.com/tox-dev/filelock/security/advisories/GHSA-8mx5-7m5m-r77g)
covers >=3.10.0,<=4.2.0; Unix
[rename/hard-link truncation](https://github.com/tox-dev/filelock/security/advisories/GHSA-69hj-f68j-2879)
covers <=4.2.0. All except the earlier SQLite fix select4.2.1. These require
specific local directory/lock/ACL conditions; owned SSE code uses its own model
lock mechanism, not these APIs.

The [msgpack maintainer record](https://github.com/msgpack/msgpack-python/security/advisories/GHSA-j586-36cw-2gc2)
lists reproduced1.2.2, fixed1.2.3, and explicitly leaves the earliest affected
release unresolved despite a broader report narrative. Audit labels locked1.2.1
affected; this change selects1.2.3 without asserting that disputed earlier range.
The C-extension leak requires strict-map-key validation failures; no owned SSE
msgpack sink was established. Pytest's [9.0.3 release](https://github.com/pytest-dev/pytest/releases/tag/9.0.3)
and [maintainer changelog](https://docs.pytest.org/en/stable/changelog.html) support
the temporary-directory security correction. None of these dev-tool updates is
evidence of an exploited product service.

The source adds decoded response limits/timeouts/redirect rejection, local model
name containment and optional mandatory digest provenance. Details, defaults,
trust limits, frozen generation commands and native platform holds are documented
in [Security.md](Security.md). Qlik function IDs and argument contracts are unchanged.

## Platform evidence and distribution hold

The downloaded Pillow CPython3.13 wheel hashes were independently checked against
PyPI metadata: Linux AMD64
`5f56499c1a74d2b862beb0c33b8016f99d095858455df9d21583bbbc1c15b582`,
macOS ARM64
`f11a3c1358bb3c68012a7b1f41b223c3db9f7bfde90b481df028cfe1c3363313`,
Windows AMD64
`9dda0788a9932776a75d8bcc020076edc308ce2508b51f6739a45e3158b3fc42`.
Linux policy exactly reuses Gateway's accepted original library names/hashes.
macOS's original decoder was actually loaded and reported `0x1002000`.

The local macOS ARM64 repair passed all12 available upstream Brotli CTest cases,
decoder1.2.1 readback, bounded decompression, PNG/JPEG/TIFF/WebP/AVIF/JPEG2000
round trips, FreeType use and repaired installed-RECORD checks. Resulting local
decoder SHA-256 was
`786c272c623420f659c39b94e9c7df027c3b53633066efe1491bbc257832c772`;
common-library SHA-256 was
`8a5577aeed2a3c0f6dd5ebecfe66b46edcde36753c078cc0054e75292aea629e`.
Build output hashes are toolchain-specific receipts, not portable wheel hashes.

Windows statically incorporates Brotli into its FreeType extension according to
the primary [Pillow build recipe](https://github.com/python-pillow/Pillow/blob/13.0.0/winbuild/build_prepare.py)
and [dependency manifest](https://github.com/python-pillow/Pillow/blob/13.0.0/.github/dependencies.json).
Its native repair is **not implemented/qualified**; setup fails explicitly there.
Other architectures are likewise unqualified. Do not distribute this change as
a complete Windows security update. Keep the PR draft until the required native
build and platform acceptance are resolved or scope is explicitly accepted.

Local analytics/protocol/scikeras checks encountered a pre-existing macOS27
loader rejection in the pinned SciPy1.15.3 `_spropack` Mach-O wheel. The fixed
StatsForecast2.0.3 dependency constraint requires scipy<1.16, so this task does not
silently replace the analytics stack or count those checks as passing. Real
trusted `.keras` and HDF5 round trips passed independently. Cross-platform CI and
the complete frozen install must be read back on the final PR revision.

## Downstream integration ownership matrix

| Stage | SSE repository owns | Gateway follow-up / acceptance |
| --- | --- | --- |
| Canonical source | Reviewed final commit, pyproject/requirements/uv exports, installer/native repair, regression tests. | Select the final merged SSE commit, not the old23ae07d3 ref or a dirty checkout. Re-fetch current Gateway main before integration. |
| Dependency import | Hash-locked core/cloud/deep-learning/dev bundles and bootstrap inputs. | Reconcile `resources/supply-chain/qlik-sse-tools/{upstream-requirements.txt,runtime-requirements.in,build-requirements.in,requirements-linux-x86_64-py313.lock,build-requirements-linux-x86_64-py313.lock,security-overrides.json}` with the new source. Existing Gateway Click8.3.1 override conflicts with canonical Click8.4.2; resolve deliberately. Include required optional coordinates without forcing them into standalone core. Do not retain old overrides blindly or remove native repair. |
| Exact source/hash/member policy | Stable source ZIP contents including locks and repair tools. | With a clean checkout at the final full SSE SHA, regenerate the source archive SHA, source requirements SHA, both lock hashes, source marker and Dockerfile pins using `npm run governed:sse:refresh -- --write --source-root=... --source-commit=...`. Review `source.json`, Dockerfile and `scripts/security/governed-sse-package-policy.json` together, including changed command helpers and new members. Run the non-write pin check. Never bypass existing member/hash gates. |
| Builder/native integration | Exact Linux/macOS wheel custody and source-pinned repair contract. | Retain the already completed Python3.13.18/pip26.2.2 and Linux Pillow/Brotli repair, reconciling receipt format/repair sequencing if adopting the upstream helper. Rebuild a source-derived candidate and read back the interpreter, every reviewed package, actual decoder version/hash, linkage and RECORD in the final runtime prefix. Run TLS/HTTP/model/native/standalone and combined packaging/security checks. |
| Released downloads | No publication in this task. | Dedicated Gateway builder owns authorized publication. Inspect actual ZIP members/hashes and normal download-byte evidence. Source completion and a passing builder are distinct from publication. |
| Independent installations | Setup enforces supported frozen/native gates but does not update existing installations automatically. | Separately authorized inventory, backup/rollback, platform-specific installation, installed version/native readback and relevant model/HTTP/feature acceptance. No service restart, customer update or fleet action is authorized by this handoff. |

Cross-repository references are **Refs**, never automatic closing references.
Retain all five Gateway issues' residual independent-installation and trust
acceptance. No issue transfer, deletion or bulk churn is part of this work.

## Working storage / resume location

At Jason's direction, active work moved to
`/Volumes/Steam Library/CodexData/qlik-sse-security-20261030` on verified mounted
HFS+ volume UUID `B13D3E7E-13F5-3B36-822A-D69317F8C5DF`.
The original project checkout and unrelated untracked files remain intact.
Task environments, wheel downloads, outputs, temporary work and cache directories
are beneath `.task/` on that volume. Source `.task/environment.sh` for later
commands; do not use the app's stale original cwd. Migration source hashes and
local test logs are retained under `.task/evidence/` and excluded from Git.
