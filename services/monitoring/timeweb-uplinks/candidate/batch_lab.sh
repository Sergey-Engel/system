#!/usr/bin/env bash
set -Eeuo pipefail
candidate=$(dirname "$(readlink -f "$0")")
source <(awk '/^matrix > / {exit} {print}' /root/uplink-guards-stage-20260911/guards_lab.sh)
ctl apply
sleep 3
jq '.targets={gstatic:.targets.fixture,cloudflare:.targets.fixture}' "$lab/targets.json" > "$lab/batch-targets.json"
batch() { bash "$candidate/guardctl-batch.sh" "$lab/manifest.json" batch "$lab/batch-targets.json"; }
if [ "${CANCEL_ONLY:-}" = yes ]; then
    peer iptables -I INPUT -p tcp --dport 8443 -j DROP
    timeout --verbose --kill-after=2s 1s env BATCH_BOUNDED=yes bash -x "$candidate/guardctl-batch.sh" "$lab/manifest.json" batch "$lab/batch-targets.json" > "$lab/cancel-debug" 2>&1 || true
    sleep 2
    tail -n 100 "$lab/cancel-debug"
    find "$lab/state" -mindepth 1
    exit 0
fi
expected_rc 0 batch_healthy batch
check 'six records' jq -e '(.records|length)==6 and (.records|all(.curl_exit==0)) and .universal_generation==false' "$lab/batch_healthy.result"
check 'batch workdirs cleaned' test "$(find "$lab/state" -mindepth 1 -type d | wc -l)" -eq 0

ip route del table 200 default
expected_rc 2 batch_missing_route batch
ip route add table 200 default dev wg-up-cenuta

peer tc qdisc add dev wg-lab root netem delay 100ms
(
    timeout 8 tcpdump --immediate-mode -l -p -n -i wg1 -c 1 'tcp and dst host 203.0.113.10 and dst port 8443' > "$lab/batch-aba.syn" 2> "$lab/batch-aba.ready"
    ip route del table 100 default
    sleep 0.05
    ip route add table 100 default via 10.20.0.2 dev wg1
) &
route_job=$!
for attempt in $(seq 1 100); do
    if grep -q listening "$lab/batch-aba.ready" 2>/dev/null; then break; fi
    sleep 0.02
done
expected_rc 2 batch_rtnl_aba batch
wait "$route_job"
route_job=
peer tc qdisc del dev wg-lab root

# Out-of-band WG and iptables ABA has no RTNL event guarantee. Record, do not hide.
peer tc qdisc add dev wg-lab root netem delay 100ms
(
    sleep 1
    wg set wg1 peer "$peer_public" allowed-ips 203.0.113.10/32
    wg set wg1 peer "$peer_public" allowed-ips 0.0.0.0/0
    iptables -I OUTPUT -d 192.0.2.123 -j DROP
    iptables -D OUTPUT -d 192.0.2.123 -j DROP
) &
route_job=$!
expected_rc 0 batch_known_aba_blindspot batch
wait "$route_job"
route_job=
check 'blind spot explicitly reported' jq -e '.universal_generation==false' "$lab/batch_known_aba_blindspot.result"
peer tc qdisc del dev wg-lab root

# Late SYN-ACK after the bound socket has timed out must not cause a direct RST.
peer tc qdisc add dev wg-lab root netem delay 3500ms
start_capture batch_late_rst
expected_rc 0 batch_late_rst batch
stop_capture
check 'late RST exists inside WG' test "$(count_packets batch_late_rst 'wg1 +Out.*Flags \[R')" -gt 0
check 'late WG-source RST never direct' test "$(count_packets batch_late_rst 'direct0 +Out.*10\.20\.0\.1.*Flags \[R')" -eq 0
peer tc qdisc del dev wg-lab root

# Six HTTPS failures must fit in one batch budget, with at most two concurrent curl.
peer iptables -I INPUT -p tcp --dport 8443 -j DROP
expected_rc 0 batch_timeouts batch
check 'timeouts are observations, not success' jq -e '(.records|all(.curl_exit==28)) and (.finished_unix-.started_unix<43)' "$lab/batch_timeouts.result"
peer iptables -D INPUT -p tcp --dport 8443 -j DROP
# Accept TCP in the kernel but stop TLS setup (curl's connect timeout includes TLS).
kill -STOP "$server_pid"
expected_rc 0 batch_tls_timeouts batch
kill -CONT "$server_pid"
check 'full TLS timeout batch stays bounded' jq -e '(.records|all(.curl_exit==28)) and (.finished_unix-.started_unix<43)' "$lab/batch_tls_timeouts.result"
# Force an outer deadline while curl jobs are active; cleanup must release the lock.
peer iptables -I INPUT -p tcp --dport 8443 -j DROP
expected_rc 124 batch_cancel timeout --kill-after=2s 1s bash "$candidate/guardctl-batch.sh" "$lab/manifest.json" batch "$lab/batch-targets.json"
for attempt in $(seq 1 100); do
    if test "$(find "$lab/state" -mindepth 1 -type d | wc -l)" -eq 0; then break; fi
    sleep 0.02
done
find "$lab/state" -mindepth 1 -type d
check 'cancel removed batch workdirs' test "$(find "$lab/state" -mindepth 1 -type d | wc -l)" -eq 0
expected_rc 0 lock_released ctl check
peer iptables -D INPUT -p tcp --dport 8443 -j DROP
jq '.expires_unix=0' "$lab/batch-targets.json" > "$lab/expired.json"
expected_rc 2 batch_expired bash "$candidate/guardctl-batch.sh" "$lab/manifest.json" batch "$lab/expired.json"
expected_rc 0 rollback ctl rollback
printf 'SUMMARY failures=%s\n' "$failures"
test "$failures" -eq 0
