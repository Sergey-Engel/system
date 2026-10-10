#!/bin/zsh
set -e
root=$(CDPATH='' cd -- "$(dirname "$0")/../../../.." && pwd)
exec "$root/.venv/bin/python" -B "$root/services/monitoring/vpn-connectivity/probe/host_probe.py"
