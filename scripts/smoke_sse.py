#!/usr/bin/env python3
"""Run a live health, capability, and Pearson smoke test against a Qlik SSE."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import grpc
from grpc_health.v1 import health_pb2, health_pb2_grpc


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "generated"))

import ServerSideExtension_pb2 as SSE  # noqa: E402
import ServerSideExtension_pb2_grpc as SSE_grpc  # noqa: E402


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=50055)
    parser.add_argument("--timeout", type=float, default=20)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    target = f"{args.host}:{args.port}"
    channel = grpc.insecure_channel(target)
    grpc.channel_ready_future(channel).result(timeout=args.timeout)

    health = health_pb2_grpc.HealthStub(channel).Check(
        health_pb2.HealthCheckRequest(service="qlik.sse.Connector"),
        timeout=args.timeout,
    )
    if health.status != health_pb2.HealthCheckResponse.SERVING:
        raise RuntimeError(f"SSE health is not SERVING: {health.status}")

    stub = SSE_grpc.ConnectorStub(channel)
    capabilities = stub.GetCapabilities(SSE.Empty(), timeout=args.timeout)

    function_header = SSE.FunctionRequestHeader(functionId=4, version="1")
    common_header = SSE.CommonRequestHeader(
        appId="smoke-test",
        userId="UserDirectory=LOCAL; UserId=smoke",
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
            timeout=args.timeout,
        )
    )
    values = [dual.numData for bundle in response for row in bundle.rows for dual in row.duals]
    if values != [1.0]:
        raise RuntimeError(f"Pearson smoke returned {values!r}, expected [1.0]")

    print(
        json.dumps(
            {
                "target": target,
                "health": "SERVING",
                "plugin": capabilities.pluginIdentifier,
                "version": capabilities.pluginVersion,
                "function_count": len(capabilities.functions),
                "pearson": values[0],
            },
            sort_keys=True,
        )
    )
    channel.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
