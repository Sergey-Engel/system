set -Eeuo pipefail
dest=/opt/vpn-monitoring/guards
bash "$dest/guardctl.sh" "$dest/guard-manifest.json" check
systemctl stop timeweb-uplink-guards-live-rollback-20260911.timer
printf 'GUARD_LAYER_RETAINED %s; application acceptance remains partial\n' "$(date -u +%FT%TZ)"
sha256sum "$dest/guardctl.sh" "$dest/guard-manifest.json" "$dest/probe-targets.json"
cat /var/lib/vpn-uplink-guards/state.json
printf 'WATCHERS\n'
ps -eo pid,ppid,args | grep -E '(ip -ts monitor|guards_lab.sh)' | grep -v grep || true
printf 'TIMERS\n'
systemctl list-timers --all --no-pager | grep uplink-guards || true
printf 'TEMP_LAB_DIRS\n'
find /tmp -maxdepth 1 -type d -name 'uplink-netns-lab.*'
