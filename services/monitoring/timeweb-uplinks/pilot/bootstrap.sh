#!/bin/bash
set -euo pipefail
export DEBIAN_FRONTEND=noninteractive
sources=$(mktemp /tmp/uplink-pilot-sources.XXXXXX.list)
trap 'rm -f "$sources"' EXIT
printf '%s\n' \
  'deb [signed-by=/usr/share/keyrings/ubuntu-archive-keyring.gpg] https://archive.ubuntu.com/ubuntu noble main universe' \
  'deb [signed-by=/usr/share/keyrings/ubuntu-archive-keyring.gpg] https://archive.ubuntu.com/ubuntu noble-updates main universe' \
  'deb [signed-by=/usr/share/keyrings/ubuntu-archive-keyring.gpg] https://security.ubuntu.com/ubuntu noble-security main universe' > "$sources"
opts=(-o "Dir::Etc::sourcelist=$sources" -o 'Dir::Etc::sourceparts=-'
      -o DPkg::Lock::Timeout=15 -o Acquire::Retries=0 -o Acquire::https::Timeout=10)
timeout --kill-after=5s 90s apt-get "${opts[@]}" update
timeout --kill-after=5s 90s apt-get "${opts[@]}" install -y --no-install-recommends python3-venv
install -d -m 700 /opt/vpn-monitoring/pilot /var/lib/vpn-uplink-pilot
python3 -m venv /opt/vpn-monitoring/pilot/.venv
