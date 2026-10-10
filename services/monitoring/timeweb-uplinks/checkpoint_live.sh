set -Eeuo pipefail
umask 077
dest=/opt/vpn-monitoring/guards
bash "$dest/guardctl.sh" "$dest/guard-manifest.json" check
stamp=$(date -u +%Y%m%dT%H%M%SZ)
dir="/root/uplink-guards-stage-20260911/checkpoint-$stamp"
mkdir "$dir"
cp "$dest/guardctl.sh" "$dest/guard-manifest.json" "$dest/probe-targets.json" "$dir/"
cp /var/lib/vpn-uplink-guards/state.json "$dir/"
pid=$(docker inspect -f '{{.State.Pid}}' wg-relay)
nsenter -t "$pid" -n ip -j -4 rule show > "$dir/rules.json"
nsenter -t "$pid" -n ip -j -4 route show table all > "$dir/routes.json"
date -u +%FT%TZ > "$dir/time.txt"
cd "$dir"
sha256sum guardctl.sh guard-manifest.json probe-targets.json state.json rules.json routes.json time.txt > SHA256SUMS
sha256sum -c SHA256SUMS
tar -czf "$dir.tar.gz" guardctl.sh guard-manifest.json probe-targets.json state.json rules.json routes.json time.txt SHA256SUMS
sha256sum "$dir.tar.gz"
printf 'CHECKPOINT=%s.tar.gz\n' "$dir"
printf 'STATE\n'
cat state.json
printf 'UPLINK_HANDSHAKES\n'
nsenter -t "$pid" -n wg show wg1 latest-handshakes
nsenter -t "$pid" -n wg show wg-up-cenuta latest-handshakes
printf 'RESOURCES\n'
free -m
df -h /
printf 'WATCHERS\n'
ps -eo pid,ppid,args | grep -E '(ip -ts monitor|guards_lab.sh)' | grep -v grep || true
printf 'TIMERS\n'
systemctl list-timers --all --no-pager | grep uplink-guards || true
printf 'TEMP_LAB_DIRS\n'
find /tmp -maxdepth 1 -type d -name 'uplink-netns-lab.*'
bash "$dest/guardctl.sh" "$dest/guard-manifest.json" check
