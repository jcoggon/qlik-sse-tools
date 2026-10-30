#!/bin/sh
# Reuse the already qualified Gateway CPython image's fixed Debian snapshots.
# This changes only disposable CI containers, never a workstation or service.
set -eu
rm -f /etc/apt/sources.list /etc/apt/sources.list.d/debian.sources
cat > /etc/apt/sources.list <<'EOF'
deb [check-valid-until=no] http://snapshot.debian.org/archive/debian/20261028T204034Z bookworm main
deb [check-valid-until=no] http://snapshot.debian.org/archive/debian-security/20261028T214216Z bookworm-security main
EOF
apt-get update
apt-get install -y --no-install-recommends build-essential=12.9 git=1:2.39.5-0+deb12u3 libgomp1=12.2.0-14+deb12u1
rm -rf /var/lib/apt/lists/*
