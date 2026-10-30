"""Listener input admission and IPv6 formatting, without analytics imports."""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "core"))
from _server_bind import bind_address, parse_bind_host  # noqa: E402


@pytest.mark.parametrize("value,expected", [
    ("localhost", "127.0.0.1"), ("127.0.0.1", "127.0.0.1"),
    ("0.0.0.0", "0.0.0.0"), ("192.0.2.10", "192.0.2.10"),
    ("::", "::"), ("::1", "::1"), ("[::1]", "::1"),
    ("2001:db8::1", "2001:db8::1"),
])
def test_bind_host_admits_only_explicit_addresses(value, expected):
    assert parse_bind_host(value) == expected


@pytest.mark.parametrize("value", [
    "", None, " 127.0.0.1", "127.0.0.1 ", "localhost:50055",
    "127.0.0.1:50055", "[::1]:50055", "[127.0.0.1]", "[::1", "::1]",
    "dns:///example.com", "unix:/tmp/server.sock", "example.com", "*",
    "127.0.0.1,0.0.0.0", "fe80::1%eth0", "127.0.0.1\n",
])
def test_bind_host_rejects_ports_resolver_targets_and_ambiguous_input(value):
    with pytest.raises(ValueError):
        parse_bind_host(value)


@pytest.mark.parametrize("host,expected", [
    ("127.0.0.1", "127.0.0.1:50055"), ("::1", "[::1]:50055"),
    ("[::]", "[::]:50055"),
])
def test_listener_endpoint_keeps_host_and_port_separate(host, expected):
    assert bind_address(host, "50055") == expected


@pytest.mark.parametrize("port", [None, -1, 65536, "50055/extra", "50055:1", "5.5", "٥٠٠٥٥", True])
def test_listener_endpoint_rejects_invalid_port(port):
    with pytest.raises(ValueError):
        bind_address("127.0.0.1", port)
