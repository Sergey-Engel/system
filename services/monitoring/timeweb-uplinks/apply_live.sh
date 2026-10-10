set -Eeuo pipefail
dest=/opt/vpn-monitoring/guards
unit=timeweb-uplink-guards-live-rollback-20260911
systemd-run --unit="$unit" --on-active=10m --timer-property=AccuracySec=1s \
 /bin/bash "$dest/guardctl.sh" "$dest/guard-manifest.json" rollback
bash "$dest/guardctl.sh" "$dest/guard-manifest.json" apply
bash "$dest/guardctl.sh" "$dest/guard-manifest.json" check
printf 'LIVE_GUARDS_APPLIED %s rollback_timer=%s\n' "$(date -u +%FT%TZ)" "$unit"
