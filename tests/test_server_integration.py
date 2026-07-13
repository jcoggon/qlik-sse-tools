import json
import os
import signal
import socket
import subprocess
import sys
from pathlib import Path

import grpc
from grpc_health.v1 import health_pb2, health_pb2_grpc


ROOT = Path(__file__).resolve().parents[1]
CORE = ROOT / "core"
GENERATED = ROOT / "generated"
sys.path.insert(0, str(GENERATED))

import ServerSideExtension_pb2 as SSE  # noqa: E402
import ServerSideExtension_pb2_grpc as SSE_grpc  # noqa: E402


def _free_port():
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def _server_env():
    env = os.environ.copy()
    env["PYTHONPATH"] = os.pathsep.join([str(CORE), str(GENERATED), env.get("PYTHONPATH", "")])
    return env


def _start_server(port):
    process = subprocess.Popen(
        [sys.executable, "-u", "__main__.py", "--port", str(port), "--workers", "2"],
        cwd=CORE,
        env=_server_env(),
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )
    channel = grpc.insecure_channel(f"127.0.0.1:{port}")
    try:
        grpc.channel_ready_future(channel).result(timeout=30)
    except Exception:
        process.terminate()
        output = process.communicate(timeout=10)[0]
        raise AssertionError(f"SSE server did not become ready:\n{output}")
    return process, channel


def _stop_server(process):
    if process.poll() is not None:
        return
    if os.name == "nt":
        process.terminate()
    else:
        process.send_signal(signal.SIGINT)
    try:
        process.communicate(timeout=10)
    except subprocess.TimeoutExpired:
        process.kill()
        process.communicate(timeout=5)


def test_diagnostics_command_reports_runtime_state():
    result = subprocess.run(
        [sys.executable, "__main__.py", "--check"],
        cwd=CORE,
        env=_server_env(),
        check=True,
        capture_output=True,
        text=True,
        timeout=60,
    )
    payload = json.loads(result.stdout.strip().splitlines()[-1])
    assert payload["status"] == "ok"
    assert payload["version"] == "3.1.0"
    assert payload["function_count"] >= 59
    assert all(payload["modules"].values())


def test_grpc_health_capabilities_and_function_execution():
    port = _free_port()
    process, channel = _start_server(port)
    try:
        health_stub = health_pb2_grpc.HealthStub(channel)
        health_response = health_stub.Check(
            health_pb2.HealthCheckRequest(service="qlik.sse.Connector"), timeout=5
        )
        assert health_response.status == health_pb2.HealthCheckResponse.SERVING

        stub = SSE_grpc.ConnectorStub(channel)
        capabilities = stub.GetCapabilities(SSE.Empty(), timeout=5)
        assert capabilities.pluginIdentifier == "Qlik Python Tools"
        assert capabilities.pluginVersion == "v3.1.0"
        assert len(capabilities.functions) >= 59

        function_header = SSE.FunctionRequestHeader(functionId=4, version="1")
        common_header = SSE.CommonRequestHeader(
            appId="integration-test",
            userId="UserDirectory=LOCAL; UserId=ci",
            cardinality=1,
        )
        request = SSE.BundledRows(
            rows=[SSE.Row(duals=[SSE.Dual(strData="1;2;3;4"), SSE.Dual(strData="2;4;6;8")])]
        )
        response = list(
            stub.ExecuteFunction(
                iter([request]),
                metadata=[
                    ("qlik-functionrequestheader-bin", function_header.SerializeToString()),
                    ("qlik-commonrequestheader-bin", common_header.SerializeToString()),
                ],
                timeout=5,
            )
        )
        values = [dual.numData for bundle in response for row in bundle.rows for dual in row.duals]
        assert values == [1.0]
    finally:
        channel.close()
        _stop_server(process)
