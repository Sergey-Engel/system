set -Eeuo pipefail
umask 077
dest=/opt/vpn-monitoring/guards
stage=/root/uplink-guards-stage-20260911
pid=$(docker inspect -f '{{.State.Pid}}' wg-relay)
bash "$dest/guardctl.sh" "$dest/guard-manifest.json" check
test ! -e "$stage/probes.capture"
filter=$(jq -r '[.targets[].ip|"host "+.]|join(" or ")' "$dest/probe-targets.json")
nsenter -t "$pid" -n tcpdump -p -n -l -i any -s 96 \
 "tcp and (host 10.20.0.1 or host 10.40.40.2) and ($filter)" > "$stage/probes.capture" 2> "$stage/probes.capture.stderr" &
probe_capture=$!
nsenter -t "$pid" -n tcpdump -p -n -l -i any -s 96 -c 2000 \
 'tcp and (net 10.50.50.0/24 or net 10.10.10.0/24)' > "$stage/clients.capture" 2> "$stage/clients.capture.stderr" &
client_capture=$!
cleanup() {
    kill -INT "$probe_capture" "$client_capture" 2>/dev/null || true
    wait "$probe_capture" || true
    wait "$client_capture" || true
}
trap cleanup EXIT
for attempt in $(seq 1 40); do
    if grep -q 'listening on' "$stage/probes.capture.stderr" && grep -q 'listening on' "$stage/clients.capture.stderr"; then break; fi
    sleep 0.05
done
grep -q 'listening on' "$stage/probes.capture.stderr"
grep -q 'listening on' "$stage/clients.capture.stderr"
printf 'CAPTURE_START %s\n' "$(date -u +%FT%TZ)"
for uplink in fornex cenuta; do
    for target in gstatic cloudflare ipify; do
        printf 'PROBE upstream=%s target=%s\n' "$uplink" "$target"
        bash "$dest/guardctl.sh" "$dest/guard-manifest.json" probe "$uplink" "$dest/probe-targets.json" "$target"
    done
done
sleep 3
kill -0 "$probe_capture"
cleanup
trap - EXIT
printf 'CAPTURE_END %s\n' "$(date -u +%FT%TZ)"
printf 'PROBE_WAN_DIRECT_COUNT='
grep -cE 'eth0 +Out' "$stage/probes.capture" || true
printf 'PROBE_WG_FORNEX_OUT='
grep -cE 'wg1 +Out' "$stage/probes.capture" || true
printf 'PROBE_WG_CENUTA_OUT='
grep -cE 'wg-up-cenuta +Out' "$stage/probes.capture" || true
printf 'CLIENT_SELECTOR_IN='
grep -cE 'wg-clients +In' "$stage/clients.capture" || true
printf 'CLIENT_SELECTOR_OUT='
grep -cE 'wg-clients +Out' "$stage/clients.capture" || true
printf 'CLIENT_LEGACY_IN='
grep -cE 'wg0 +In' "$stage/clients.capture" || true
printf 'CLIENT_LEGACY_OUT='
grep -cE 'wg0 +Out' "$stage/clients.capture" || true
cat "$stage/probes.capture.stderr" "$stage/clients.capture.stderr"
test "$(grep -cE 'eth0 +Out' "$stage/probes.capture" || true)" -eq 0
bash "$dest/guardctl.sh" "$dest/guard-manifest.json" check
