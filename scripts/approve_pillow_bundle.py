"""Issue an operator-local approval only after authenticated live GitHub proof.

Uses the operator's existing gh authentication without reading/exporting tokens.
No target operation and no public release publication. A failed/incomplete CI run,
foreign head/tree, expired artifact or changed transport bytes cannot be approved.
"""

import argparse
import json
import subprocess
import threading
from pathlib import Path

import pillow_bundle as bundle


def github(resource):
    command = ["gh", "api", "--hostname", "github.com", f"repos/{bundle.REPOSITORY}/{resource}"]
    process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
    timer = threading.Timer(30, process.kill)
    timer.start()
    try:
        data = process.stdout.read(2 * 1024 * 1024 + 1)
        bundle.require(len(data) <= 2 * 1024 * 1024, "GitHub proof exceeds metadata budget")
        bundle.require(process.wait(timeout=5) == 0, "Authenticated GitHub proof lookup failed: " + resource.split("?")[0])
        return json.loads(data)
    finally:
        timer.cancel()
        if process.poll() is None:
            process.kill()
        process.wait()
        process.stdout.close()


def qualify_evidence(run, artifact, jobs, producer_commit, consumer_commit, producer_tree, consumer_tree, expected_source):
    bundle.require(run.get("status") == "completed" and run.get("conclusion") == "success"
                   and run.get("path") == bundle.WORKFLOW and run.get("event") in ("push", "pull_request", "workflow_dispatch", "schedule")
                   and run.get("repository", {}).get("id") == bundle.REPOSITORY_ID
                   and run.get("head_repository", {}).get("id") == bundle.REPOSITORY_ID,
                   "Native approval requires successful same-repository CI")
    bundle.require(producer_commit["sha"] == run["head_sha"] and consumer_commit["sha"] == expected_source
                   and producer_commit["tree"]["sha"] == consumer_commit["tree"]["sha"]
                   and producer_tree["sha"] == consumer_tree["sha"] == producer_commit["tree"]["sha"],
                   "Qualified producer/consumer source trees differ")
    required = ("frozen-locks", "deep-learning", "security", "optional-extras", "verify (windows-latest)",
                "verify (macos-latest)", "verify (ubuntu-latest,", "native-security (windows-latest)",
                "native-security (macos-latest)", "native-security (ubuntu-latest,")
    for name in required:
        matches = [j for j in jobs if j["name"] == name or (name.endswith(",") and j["name"].startswith(name))]
        bundle.require(len(matches) == 1 and matches[0].get("conclusion") == "success", "Required native/source/consumer CI job is not successful")
    windows = next(j for j in jobs if j["name"] == "native-security (windows-latest)")
    bundle.require(any(s["name"] == "Qualify explicit Windows native bundle" and s.get("conclusion") == "success"
                       for s in windows.get("steps", [])), "Actual compiler-free consumer CI proof missing")
    bundle.require(artifact.get("expired") is False and artifact.get("workflow_run", {}).get("id") == run["id"]
                   and artifact["workflow_run"].get("head_sha") == run["head_sha"]
                   and artifact["workflow_run"].get("head_repository_id") == bundle.REPOSITORY_ID
                   and artifact.get("digest", "").startswith("sha256:")
                   and bundle.is_digest(artifact["digest"][7:]), "Immutable GitHub artifact proof differs")


def approve(transport, run_id, artifact_id, source_commit, output):
    bundle.require(bundle.is_digest(source_commit, 40) and run_id > 0 and artifact_id > 0, "Explicit source/run/artifact identity required")
    def git(*args):
        return subprocess.check_output(["git", *args], cwd=bundle.ROOT, text=True).strip()
    bundle.require(Path(git("rev-parse", "--show-toplevel")).resolve() == bundle.ROOT
                   and git("rev-parse", "HEAD") == source_commit and not git("status", "--porcelain", "--untracked-files=no"),
                   "Issue approval from the clean reviewed consumer-source checkout")
    run = github(f"actions/runs/{run_id}")
    artifact = github(f"actions/artifacts/{artifact_id}")
    bundle.require(run.get("id") == run_id and artifact.get("id") == artifact_id, "GitHub run/artifact lookup identity differs")
    jobs = github(f"actions/runs/{run_id}/jobs?filter=latest&per_page=100")["jobs"]
    producer_commit = github("git/commits/" + run["head_sha"])
    consumer_commit = github("git/commits/" + source_commit)
    producer_tree = github("git/trees/" + producer_commit["tree"]["sha"] + "?recursive=1")
    consumer_tree = github("git/trees/" + consumer_commit["tree"]["sha"] + "?recursive=1")
    qualify_evidence(run, artifact, jobs, producer_commit, consumer_commit, producer_tree, consumer_tree, source_commit)
    bundle.require(not producer_tree.get("truncated") and not consumer_tree.get("truncated"), "Incomplete GitHub source tree")
    bundle.require(git("rev-parse", "HEAD^{tree}") == consumer_commit["tree"]["sha"], "Local reviewed source tree differs")
    transport_data = bundle.read_file(transport, bundle.MAX_BUNDLE, artifact["digest"][7:])
    outer = bundle.read_zip(transport_data, ("windows-native-bundle.zip", "producer-receipt.json"))
    manifest, native, members = bundle.inspect_bundle(outer["windows-native-bundle.zip"])
    producer = manifest["producer"]
    bundle.require(producer["run_id"] == run["id"] and producer["run_attempt"] == run["run_attempt"]
                   and producer["source_commit"] == run["head_sha"] and producer["source_tree"] == producer_commit["tree"]["sha"]
                   and artifact["name"] == bundle.artifact_name(producer), "Artifact source/attempt/name differs")
    paths = {item["path"]: item for item in producer_tree["tree"]}
    for name, identity in manifest["source_files"].items():
        bundle.require(paths.get(name, {}).get("type") == "blob" and paths[name]["sha"] == identity["git_blob"],
                       "Native source bytes do not match authenticated GitHub tree")
    transport_receipt = bundle.decode_json(outer["producer-receipt.json"])
    bundle.require(transport_receipt == {"schema": "qlik.sse.native-producer-receipt/v1",
        "bundle_sha256": bundle.sha(outer["windows-native-bundle.zip"]), "manifest_sha256": bundle.sha(members["manifest.json"]),
        "producer": producer, "profile": bundle.PROFILE, "toolchain": native["toolchain"], "artifact_name": artifact["name"]},
        "Producer transport receipt differs")
    approval = {"schema": "qlik.sse.approved-native-delivery/v1", "bundle_sha256": transport_receipt["bundle_sha256"],
        "manifest_sha256": transport_receipt["manifest_sha256"], "manifest": manifest, "native_receipt": native,
        "github": {"artifact_id": artifact["id"], "artifact_name": artifact["name"], "artifact_digest": artifact["digest"][7:],
                   "run_id": run["id"], "run_attempt": run["run_attempt"], "producer_commit": run["head_sha"],
                   "consumer_commit": source_commit, "producer_tree": producer["source_tree"], "consumer_tree": consumer_commit["tree"]["sha"],
                   "workflow": bundle.WORKFLOW, "repository": bundle.REPOSITORY}}
    bundle.validate_approval(approval)
    output = Path(output)
    output.mkdir(exist_ok=False)
    (output / "windows-native-bundle.zip").write_bytes(outer["windows-native-bundle.zip"])
    approved_data = bundle.json_bytes(approval)
    (output / "native-approval.json").write_bytes(approved_data)
    print(json.dumps({"bundle_sha256": approval["bundle_sha256"], "approval_sha256": bundle.sha(approved_data),
                      "source_commit": source_commit, "source_tree": producer["source_tree"], "run_id": run_id, "artifact_id": artifact_id,
                      "artifact_transport_sha256": artifact["digest"][7:]}))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--transport", required=True)
    parser.add_argument("--run-id", type=int, required=True)
    parser.add_argument("--artifact-id", type=int, required=True)
    parser.add_argument("--source-commit", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    approve(args.transport, args.run_id, args.artifact_id, args.source_commit, args.output)
