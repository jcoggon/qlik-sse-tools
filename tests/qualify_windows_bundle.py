"""CI fixture qualification, never an operator approval issuer or target installer.

The CI run is still in progress here. Test-only approval derives from workflow
context and immutable upload outputs; production approval requires the completed
successful run and authenticated live GitHub proof in approve_pillow_bundle.py.
"""

import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import pillow_bundle as bundle
import pillow_windows
import provision


def forbidden(*args, **kwargs):
    raise AssertionError("Explicit native mode invoked compiler discovery/build")


def main():
    bundle.target_profile()
    artifact = Path(os.environ["NATIVE_DOWNLOADED"])
    assert {p.name for p in artifact.iterdir()} == {"windows-native-bundle.zip", "producer-receipt.json"}
    native_zip = artifact / "windows-native-bundle.zip"
    data = bundle.read_file(native_zip, bundle.MAX_BUNDLE, os.environ["NATIVE_BUNDLE_SHA256"])
    manifest, native, members = bundle.inspect_bundle(data)
    producer = manifest["producer"]
    assert producer["run_id"] == int(os.environ["GITHUB_RUN_ID"])
    assert producer["run_attempt"] == int(os.environ["GITHUB_RUN_ATTEMPT"])
    receipt = bundle.decode_json(bundle.read_file(artifact / "producer-receipt.json", bundle.MAX_JSON))
    assert receipt == {"schema": "qlik.sse.native-producer-receipt/v1", "bundle_sha256": bundle.sha(data),
        "manifest_sha256": bundle.sha(members["manifest.json"]), "producer": producer,
        "profile": bundle.PROFILE, "toolchain": native["toolchain"], "artifact_name": bundle.artifact_name(producer)}
    approval = {"schema": "qlik.sse.approved-native-delivery/v1", "bundle_sha256": bundle.sha(data),
        "manifest_sha256": bundle.sha(members["manifest.json"]), "manifest": manifest, "native_receipt": native,
        "github": {"artifact_id": int(os.environ["NATIVE_ARTIFACT_ID"]), "artifact_name": bundle.artifact_name(producer),
                   "artifact_digest": os.environ["NATIVE_ARTIFACT_DIGEST"].removeprefix("sha256:"),
                   "run_id": producer["run_id"], "run_attempt": producer["run_attempt"],
                   "producer_commit": producer["source_commit"], "consumer_commit": producer["source_commit"],
                   "producer_tree": producer["source_tree"], "consumer_tree": producer["source_tree"],
                   "workflow": bundle.WORKFLOW, "repository": bundle.REPOSITORY}}
    bundle.validate_approval(approval)
    approved_data = bundle.json_bytes(approval)
    approval_file = artifact.parent / "CI-TEST-ONLY-native-approval.json"
    approval_file.write_bytes(approved_data)
    pillow_windows.preflight = pillow_windows.build = forbidden
    provision.install("core", str(native_zip), bundle.sha(data), str(approval_file), bundle.sha(approved_data))
    # Idempotent readback must preserve custody and execute the same fresh probe.
    bundle.apply_bundle(native_zip, bundle.sha(data), approval_file, bundle.sha(approved_data))
    print(json.dumps({"qualification": "CI test fixture only; not operator approval", "profile": bundle.PROFILE,
                      "bundle_sha256": bundle.sha(data), "producer": producer, "toolchain": native["toolchain"]}))


if __name__ == "__main__":
    main()
