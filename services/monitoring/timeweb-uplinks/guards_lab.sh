#!/usr/bin/env bash
set -Eeuo pipefail
stage=/root/uplink-guards-stage-20260911
export UPLINK_LAB_AUTHORIZED=yes
# Reuse the reviewed isolated TLS/WG fixture, not its test runner.
source <(awk '/^start_capture\(\)/ {exit} {print}' "$stage/uplink_namespace_lab.sh" | sed 's/unshare --net sleep 150/unshare --net sleep 300/')
source <(awk '/^start_capture\(\)/ {on=1} /^https_case direct_control/ {exit} on {print}' "$stage/uplink_namespace_lab.sh" | sed 's/wg-lab/wg1/g')
cleanup_with_state() {
    if test -d "$lab/state"; then
        find "$lab/state" -type f -delete
        find "$lab/state" -depth -type d -empty -delete
    fi
    cleanup
}
trap cleanup_with_state EXIT
ip link set wg-lab name wg1
ip address del 10.200.0.1/30 dev wg1
ip address add 10.20.0.1/24 dev wg1
peer ip address del 10.200.0.2/30 dev wg-lab
peer ip address add 10.20.0.2/24 dev wg-lab
peer wg set wg-lab peer "$probe_public" allowed-ips 10.20.0.1/32
ip route replace table 100 default via 10.20.0.2 dev wg1
ip link add wg-up-cenuta type wireguard
peer ip link add wg-cenuta type wireguard
wg set wg-up-cenuta private-key "$lab/probe.key" listen-port 51893 peer "$peer_public" allowed-ips 0.0.0.0/0 endpoint 198.18.0.2:51894
peer wg set wg-cenuta private-key "$lab/peer.key" listen-port 51894 peer "$probe_public" allowed-ips 10.40.40.2/32 endpoint 198.18.0.1:51893
ip address add 10.40.40.2/32 dev wg-up-cenuta
peer ip address add 10.40.40.1/24 dev wg-cenuta
ip link set wg-up-cenuta up
peer ip link set wg-cenuta up
ip route add table 200 default dev wg-up-cenuta
for pair in wg-home:10.30.30.1 wg-clients:10.50.50.1 wg0:10.10.10.1; do
    name=${pair%:*}
    address=${pair#*:}
    ip link add "$name" type dummy
    ip address add "$address/24" dev "$name"
    ip link set "$name" up
done
ip route add 172.19.0.0/16 via 198.18.2.2 dev direct0
ip route add table 300 default dev wg-home
ip rule add priority 180 to 10.50.50.0/24 lookup main
ip rule add priority 181 to 10.10.10.0/24 lookup main
ip rule add priority 190 fwmark 0x30 lookup 300
ip rule add priority 219 from 10.10.10.0/24 lookup 100
ip rule add priority 220 from 10.50.50.20/32 lookup 200
ip rule add priority 227 from 10.50.50.27/32 lookup 100
ip rule add priority 300 iif wg-home lookup 300

baseline=$(jq -cn \
 --argjson rules "$(ip -j -4 rule show)" --argjson routes "$(ip -j -4 route show table all)" \
 --argjson links "$(ip -j -4 address show | jq '[.[]|{ifindex,ifname,flags,mtu,addr_info:[.addr_info[]|{local,prefixlen}]}]')" \
 --arg f "$(wg show wg1 allowed-ips)" --arg c "$(wg show wg-up-cenuta allowed-ips)" \
 --arg filter "$(iptables -S)" --arg nat "$(iptables -t nat -S)" --arg mangle "$(iptables -t mangle -S)" \
 '{rules:$rules,routes:$routes,links:$links,peers:{fornex:$f,cenuta:$c},filter:$filter,nat:$nat,mangle:$mangle}')
for i in $(seq 0 21); do
    mapfile -t args < <(jq -r --argjson n "$i" '.rules[$n].argv[]' "$stage/guard-manifest.json")
    ip -4 rule add "${args[@]}"
done
expected=$(ip -j -4 rule show | jq '[.[]|select(.priority>=31000 and .priority<=31021)]')
printf 'EXPECTED_RULES=%s\n' "$(jq -c . <<< "$expected")"
for i in $(seq 21 -1 0); do
    mapfile -t args < <(jq -r --argjson n "$i" '.rules[$n].argv[]' "$stage/guard-manifest.json")
    ip -4 rule del "${args[@]}"
done
jq --argjson base "$baseline" --argjson expected "$expected" --arg ns "$(readlink /proc/self/ns/net)" \
 '.target={kind:"lab",namespace:$ns}|.baseline=$base|.expected_rules=$expected' "$stage/guard-manifest.json" > "$lab/manifest.json"
jq -n --arg ca "$lab/tls.crt" --argjson expiry "$(( $(date +%s)+600 ))" \
 '{expires_unix:$expiry,ca_file:$ca,targets:{fixture:{url:"https://probe.test:8443/",host:"probe.test",ip:"203.0.113.10",port:8443}}}' > "$lab/targets.json"
export GUARD_STATE_DIR="$lab/state" UPLINK_GUARD_LAB=yes
ctl() { bash "$stage/guardctl.sh" "$lab/manifest.json" "$@"; }
expected_rc() {
    local expected=$1 label=$2
    shift 2
    local rc=0
    "$@" > "$lab/$label.result" 2>&1 || rc=$?
    cat "$lab/$label.result"
    check "$label rc=$expected" test "$rc" -eq "$expected"
}
matrix() {
    ip route get 203.0.113.10 from 10.50.50.20 iif wg-clients
    ip route get 203.0.113.10 from 10.50.50.27 iif wg-clients
    ip route get 203.0.113.10 from 10.10.10.7 iif wg0
    ip route get 203.0.113.10 from 10.50.50.20 iif wg-clients mark 0x30
    for src in 10.20.0.1 10.40.40.2; do
        for dst in 10.50.50.20 10.10.10.7 10.30.30.2 172.19.0.1 10.20.0.2; do
            ip route get "$dst" from "$src"
        done
    done
}
matrix > "$lab/matrix.before"
expected_rc 0 apply ctl apply
expected_rc 0 idempotent ctl apply
check 'idempotent no duplicate rules' test "$(ip -j rule show | jq '[.[]|select(.priority>=31000 and .priority<=31021)]|length')" -eq 22
matrix > "$lab/matrix.after"
check 'forwarded and local service route regression' cmp -s "$lab/matrix.before" "$lab/matrix.after"
for upstream in fornex cenuta; do
    start_capture "probe-$upstream"
    expected_rc 0 "probe-$upstream" ctl probe "$upstream" "$lab/targets.json" fixture
    stop_capture
    check "$upstream HTTPS 200" grep -q 'http=200' "$lab/probe-$upstream.result"
    check "$upstream no direct TCP" test "$(count_packets "probe-$upstream" 'direct0 +Out')" -eq 0
done

# Verify late kernel replies against the final 22-rule inventory.
peer tc qdisc add dev wg-lab root netem delay 100ms
https_case final_guards_late_rst wg1 0.25 timeout
check 'final guards late RST through WG' test "$wg_rst" -gt 0
check 'final guards late RST no direct TCP' test "$direct_count" -eq 0
peer tc qdisc del dev wg-lab root

# Delete and restore the route while the request is in progress (ABA).
peer tc qdisc add dev wg-lab root netem delay 100ms
(
    timeout 12 tcpdump --immediate-mode -l -p -n -i wg1 -c 1 'tcp and dst host 203.0.113.10 and dst port 8443 and tcp[13] & 0x12 = 0x02' >"$lab/aba.syn" 2>"$lab/aba.capture-ready"
    printf 'ABA_DELETE %s\n' "$(date -u +%FT%T.%NZ)"
    ip route del table 100 default
    sleep 0.05
    ip route add table 100 default via 10.20.0.2 dev wg1
    printf 'ABA_RESTORED %s\n' "$(date -u +%FT%T.%NZ)"
) &
route_job=$!
ready=no
for attempt in $(seq 1 100); do
    if grep -q listening "$lab/aba.capture-ready" 2>/dev/null; then ready=yes; break; fi
    kill -0 "$route_job"
    sleep 0.02
done
test "$ready" = yes
printf 'ABA_HELPER_START %s\n' "$(date -u +%FT%T.%NZ)"
expected_rc 90 aba ctl probe fornex "$lab/targets.json" fixture
wait "$route_job"
route_job=
cat "$lab/aba.syn"
check 'ABA detected despite restored manifest' grep -q 'generation_or_manifest_changed' "$lab/aba.result"
peer tc qdisc del dev wg-lab root
expected_rc 0 recovered ctl probe fornex "$lab/targets.json" fixture

ip route del table 200 default
expected_rc 90 missing_route ctl probe cenuta "$lab/targets.json" fixture
check 'missing route no request' grep -q request_not_started "$lab/missing_route.result"
ip route add table 200 default dev wg-up-cenuta
expected_rc 0 rollback ctl rollback
expected_rc 0 rollback_again ctl rollback
check 'rollback restores exact rules' test "$(ip -j -4 rule show | jq -cS .)" = "$(jq -cS .rules <<< "$baseline")"
ip rule add priority 31000 from 198.51.100.0/24 lookup main
expected_rc 2 conflict ctl apply
check 'conflicting rule retained' test "$(ip -j rule show | jq '[.[]|select(.priority==31000)]|length')" -eq 1
ip rule del priority 31000 from 198.51.100.0/24 lookup main
jq '.target.namespace="net:[0]"' "$lab/manifest.json" > "$lab/stale.json"
expected_rc 2 stale_generation bash "$stage/guardctl.sh" "$lab/stale.json" apply
expected_rc 0 second_apply ctl apply
expected_rc 0 second_rollback ctl rollback
printf 'SUMMARY failures=%s ended=%s\n' "$failures" "$(date -u +%FT%TZ)"
test "$failures" -eq 0
