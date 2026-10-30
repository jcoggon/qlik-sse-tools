"""Validate literal gRPC listener addresses without DNS or resolver targets."""

import ipaddress

DEFAULT_BIND_HOST = "127.0.0.1"


def parse_bind_host(value):
    if value == "localhost":
        return DEFAULT_BIND_HOST
    if not isinstance(value, str) or not value or value != value.strip() or "%" in value:
        raise ValueError("Use an IPv4/IPv6 address or localhost, without a port or scope ID")
    if value.startswith("[") and value.endswith("]") and ":" in value:
        value = value[1:-1]
    try:
        return str(ipaddress.ip_address(value))
    except ValueError as error:
        raise ValueError("Use an IPv4/IPv6 address or localhost, without a port or resolver scheme") from error


def bind_address(host, port):
    host = parse_bind_host(host)
    if not str(port).isascii() or not str(port).isdigit() or not 0 <= int(port) <= 65535:
        raise ValueError("SSE port must be an integer from 0 to 65535")
    return f"[{host}]:{int(port)}" if ":" in host else f"{host}:{int(port)}"
