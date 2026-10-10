#!/usr/bin/env bash
set -euo pipefail
for attempt in {1..60}; do
  if docker exec wg-relay ip link show wg-clients >/dev/null 2>&1; then
    break
  fi
  sleep 1
done
python3 /root/restore_runtime_20260927.py
for device in macbook iphone12 macmini; do
  /usr/local/sbin/timeweb-flex-macbook --device "$device" reconcile
done
bash /opt/timeweb-reality/bth-recovery/bth_recover.sh
python3 /root/rebind_after_reboot_20260927.py --image sha256:d3e46bc7a1510142afb30b4f5375c7d4470c75ed89483e798813c1acd6e7c1cb --apply
rm /var/lib/os-maintenance-recovery-20260927.pending
