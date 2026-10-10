#!/bin/bash
set -euo pipefail
base=/opt/timeweb-reality/bth-recovery
case "${1:-}" in
apply)
  test ! -e /etc/systemd/system/bth-recovery.service
  test ! -e /etc/systemd/system/bth-recovery.timer
  bash "$base/bth_recover.sh" --check
  systemd-analyze verify "$base/bth-recovery.service" "$base/bth-recovery.timer"
  trap 'systemctl disable --now bth-recovery.timer 2>/dev/null || true' ERR
  install -m644 "$base/bth-recovery.service" /etc/systemd/system/bth-recovery.service
  install -m644 "$base/bth-recovery.timer" /etc/systemd/system/bth-recovery.timer
  systemctl daemon-reload
  systemctl start bth-recovery.service
  systemctl enable --now bth-recovery.timer
  systemctl is-active --quiet bth-recovery.timer
  trap - ERR
  echo BTH_RECOVERY_ENABLED;;
rollback)
  cmp "$base/bth-recovery.service" /etc/systemd/system/bth-recovery.service
  cmp "$base/bth-recovery.timer" /etc/systemd/system/bth-recovery.timer
  systemctl disable --now bth-recovery.timer
  systemctl stop bth-recovery.service
  echo 'Recovery disabled; files retained; peer remains runtime-only';;
*) exit 2;;
esac
