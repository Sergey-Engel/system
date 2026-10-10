#!/usr/bin/env bash
# Run only inside a fresh Linux network namespace; no production network access.
set -Eeuo pipefail
umask 077

test "${UPLINK_LAB_AUTHORIZED:-}" = yes
test "$(uname -s)" = Linux
test "$(readlink /proc/self/ns/net)" != "$(readlink /proc/1/ns/net)"
test "$(ip -o link show | wc -l)" -eq 1
test "$(ip -o link show | awk -F': ' '{print $2}')" = lo

lab=$(mktemp -d /tmp/uplink-netns-lab.XXXXXXXX)
peer_pid=
server_pid=
capture_pid=
route_job=
failures=0
cleanup() {
    for child in "$route_job" "$capture_pid" "$server_pid" "$peer_pid"; do
        if [ -n "$child" ]; then
            kill "$child" 2>/dev/null || true
            wait "$child" 2>/dev/null || true
        fi
    done
    case "$lab" in
        /tmp/uplink-netns-lab.*)
            find "$lab" -maxdepth 1 -type f -delete
            rmdir "$lab"
            ;;
    esac
    printf 'CLEANUP complete: test processes and temporary files removed\n'
}
trap cleanup EXIT
trap 'exit 130' INT TERM HUP

peer() { nsenter -t "$peer_pid" -n "$@"; }
check() {
    local label=$1
    shift
    if "$@"; then
        printf 'PASS %s\n' "$label"
    else
        printf 'FAIL %s\n' "$label"
        failures=$((failures + 1))
    fi
}

printf 'START %s\n' "$(date -u +%FT%TZ)"
printf 'probe_namespace=%s\n' "$(readlink /proc/self/ns/net)"
unshare --net sleep 150 &
peer_pid=$!
for attempt in $(seq 1 40); do
    if [ "$(readlink /proc/"$peer_pid"/ns/net)" != "$(readlink /proc/self/ns/net)" ]; then
        break
    fi
    sleep 0.05
done
test "$(readlink /proc/"$peer_pid"/ns/net)" != "$(readlink /proc/self/ns/net)"
printf 'peer_namespace=%s pid=%s\n' "$(readlink /proc/"$peer_pid"/ns/net)" "$peer_pid"

# Both veth pairs are entirely inside disposable namespaces.
ip link set lo up
peer ip link set lo up
ip link add underlay0 type veth peer name underlay1
ip link set underlay1 netns "$peer_pid"
ip address add 198.18.0.1/30 dev underlay0
peer ip address add 198.18.0.2/30 dev underlay1
ip link set underlay0 up
peer ip link set underlay1 up
ip link add direct0 type veth peer name direct1
ip link set direct1 netns "$peer_pid"
ip address add 198.18.2.1/30 dev direct0
peer ip address add 198.18.2.2/30 dev direct1
ip link set direct0 up
peer ip link set direct1 up
ip route add default via 198.18.2.2 dev direct0
peer ip address add 203.0.113.10/32 dev lo

wg genkey > "$lab/probe.key"
wg genkey > "$lab/peer.key"
probe_public=$(wg pubkey < "$lab/probe.key")
peer_public=$(wg pubkey < "$lab/peer.key")
ip link add wg-lab type wireguard
peer ip link add wg-lab type wireguard
wg set wg-lab private-key "$lab/probe.key" listen-port 51891 peer "$peer_public" allowed-ips 0.0.0.0/0 endpoint 198.18.0.2:51892
peer wg set wg-lab private-key "$lab/peer.key" listen-port 51892 peer "$probe_public" allowed-ips 10.200.0.1/32 endpoint 198.18.0.1:51891
ip address add 10.200.0.1/30 dev wg-lab
peer ip address add 10.200.0.2/30 dev wg-lab
ip link set wg-lab mtu 1420 up
peer ip link set wg-lab mtu 1420 up
ip route add table 100 default dev wg-lab
expected_route=$(ip -4 route show table 100 exact 0.0.0.0/0)
test -n "$expected_route"
sysctl -qw net.ipv4.ip_forward=1 net.ipv4.conf.all.rp_filter=0 net.ipv4.conf.wg-lab.rp_filter=0
peer sysctl -qw net.ipv4.conf.all.rp_filter=0 net.ipv4.conf.wg-lab.rp_filter=0

openssl req -x509 -newkey ec -pkeyopt ec_paramgen_curve:prime256v1 -nodes -days 1 -subj /CN=probe.test -addext subjectAltName=DNS:probe.test -keyout "$lab/tls.key" -out "$lab/tls.crt" > "$lab/cert.log" 2>&1
nsenter -t "$peer_pid" -n openssl s_server -accept 203.0.113.10:8443 -cert "$lab/tls.crt" -key "$lab/tls.key" -www -quiet > "$lab/server.log" 2>&1 &
server_pid=$!
for attempt in $(seq 1 40); do
    if peer ss -lnt | grep -q '203.0.113.10:8443'; then break; fi
    sleep 0.05
done
peer ss -lnt | grep -q '203.0.113.10:8443'

start_capture() {
    local label=$1
    tcpdump -p -n -l -i any -s 96 'tcp and host 203.0.113.10' > "$lab/$label.capture" 2> "$lab/$label.stderr" &
    capture_pid=$!
    for attempt in $(seq 1 40); do
        if grep -q 'listening on' "$lab/$label.stderr"; then return; fi
        sleep 0.05
    done
    printf 'Capture failed to start\n' >&2
    exit 1
}
stop_capture() {
    sleep 0.8
    kill -INT "$capture_pid"
    wait "$capture_pid" || true
    capture_pid=
}
count_packets() {
    local label=$1 pattern=$2
    grep -cE "$pattern" "$lab/$label.capture" || true
}
valid_probe_route() {
    test "$(ip -4 route show table 100 exact 0.0.0.0/0)" = "$expected_route"
}
https_case() {
    local label=$1 interface=$2 deadline=$3 expected=$4 gated=${5:-no}
    local args=()
    if [ "$interface" != direct ]; then args=(--interface "if!$interface"); fi
    start_capture "$label"
    if [ "$gated" = yes ] && ! valid_probe_route; then
        printf 'state=UNKNOWN reason=probe_path_unverified request_not_started\n' > "$lab/$label.curl"
        rc=90
    else
        set +e
        curl -q -4 --noproxy '*' "${args[@]}" --cacert "$lab/tls.crt" --resolve probe.test:8443:203.0.113.10 --connect-timeout 1 --max-time "$deadline" -sS -o /dev/null -w 'http=%{http_code} local=%{local_ip}:%{local_port} seconds=%{time_total}\n' https://probe.test:8443/ > "$lab/$label.curl" 2>&1
        rc=$?
        set -e
        if [ "$gated" = yes ] && ! valid_probe_route; then
            printf 'state=UNKNOWN reason=probe_path_changed result_discarded\n' >> "$lab/$label.curl"
            rc=90
        fi
    fi
    printf '\nCASE %s result_rc=%s ended=%s\n' "$label" "$rc" "$(date -u +%T.%N)"
    cat "$lab/$label.curl"
    stop_capture
    direct_count=$(count_packets "$label" 'direct0 +Out')
    direct_rst=$(count_packets "$label" 'direct0 +Out.*Flags \[R')
    wg_rst=$(count_packets "$label" 'wg-lab +Out.*Flags \[R')
    printf 'packets direct_out=%s direct_rst=%s wg_rst=%s\n' "$direct_count" "$direct_rst" "$wg_rst"
    grep -E 'Flags \[R|Flags \[F' "$lab/$label.capture" | head -n 6 || true
    case "$expected" in
        success) check "$label HTTPS200" grep -q 'http=200' "$lab/$label.curl"; check "$label exit0" test "$rc" -eq 0 ;;
        timeout) check "$label timeout28" test "$rc" -eq 28 ;;
        failure) check "$label fail_closed" test "$rc" -ne 0; check "$label no_direct" test "$direct_count" -eq 0 ;;
        absent) check "$label missing_interface45" test "$rc" -eq 45; check "$label no_direct" test "$direct_count" -eq 0 ;;
        unknown) check "$label UNKNOWN90" test "$rc" -eq 90; check "$label no_direct" test "$direct_count" -eq 0 ;;
    esac
}
rst_case() {
    local label=$1 expected_direct=$2
    start_capture "$label"
    peer nc -n -z -w 1 -s 203.0.113.10 10.200.0.1 45678 > "$lab/$label.nc" 2>&1 || true
    stop_capture
    local direct_rst wg_rst
    direct_rst=$(count_packets "$label" 'direct0 +Out.*Flags \[R')
    wg_rst=$(count_packets "$label" 'wg-lab +Out.*Flags \[R')
    printf '\nCASE %s closed_port direct_rst=%s wg_rst=%s\n' "$label" "$direct_rst" "$wg_rst"
    grep -E 'Flags \[R' "$lab/$label.capture" | head -n 3 || true
    if [ "$expected_direct" = yes ]; then
        check "$label reproduced_leak" test "$direct_rst" -gt 0
    elif [ "$expected_direct" = blocked ]; then
        check "$label no_direct_rst" test "$direct_rst" -eq 0
        check "$label no_wg_rst_without_route" test "$wg_rst" -eq 0
    else
        check "$label no_direct_rst" test "$direct_rst" -eq 0
        check "$label reply_through_wg" test "$wg_rst" -gt 0
    fi
}

https_case direct_control direct 2 success
check 'direct_control uses direct0' test "$direct_count" -gt 0
https_case baseline_https wg-lab 2 success
rst_case baseline_rst yes
peer tc qdisc add dev wg-lab root netem delay 100ms
https_case baseline_late_https wg-lab 0.25 timeout
check 'baseline late reply produces direct RST' test "$direct_rst" -gt 0
peer tc qdisc del dev wg-lab root

forward_before=$(ip -4 route get 203.0.113.10 from 198.51.100.20 iif underlay0)

# oif catches live bound sockets; local-source catches unbound kernel replies.
ip rule add priority 100 iif lo oif wg-lab lookup 100
ip rule add priority 101 iif lo oif wg-lab prohibit
ip rule add priority 102 iif lo from 10.200.0.1/32 lookup 100
ip rule add priority 103 iif lo from 10.200.0.1/32 prohibit
printf '\nLAB GUARD RULES\n'
ip rule show
https_case guarded_https wg-lab 2 success
check 'guarded HTTPS no direct packets' test "$direct_count" -eq 0
rst_case guarded_rst no
peer tc qdisc add dev wg-lab root netem delay 100ms
https_case guarded_late_https wg-lab 0.25 timeout
check 'guarded late reply no direct packets' test "$direct_count" -eq 0
check 'guarded late reply RST through WG' test "$wg_rst" -gt 0
peer tc qdisc del dev wg-lab root

printf '\nFORWARDED LOOKUP (must not match iif lo)\n'
forward_route=$(ip -4 route get 203.0.113.10 from 198.51.100.20 iif underlay0)
printf '%s\n' "$forward_route"
check 'forwarded route unchanged' test "$forward_route" = "$forward_before"

ip route del table 100 default dev wg-lab
https_case missing_table_route_raw wg-lab 1 success
check 'raw bound socket still stays in WG' test "$direct_count" -eq 0
https_case missing_table_route_gated wg-lab 1 unknown yes
check 'missing manifest prevents request start' grep -q request_not_started "$lab/missing_table_route_gated.curl"
rst_case missing_table_route_rst blocked
https_case direct_still_works direct 2 success
check 'direct control still uses direct0' test "$direct_count" -gt 0
ip route add table 100 default dev wg-lab
https_case route_recovered wg-lab 2 success yes
check 'route recovery stays in WG' test "$direct_count" -eq 0
peer tc qdisc add dev wg-lab root netem delay 100ms
(
    sleep 0.2
    ip route del table 100 default dev wg-lab
) &
route_job=$!
https_case route_changed_mid_request wg-lab 2 unknown yes
wait "$route_job"
route_job=
check 'mid-request route change discards result' grep -q result_discarded "$lab/route_changed_mid_request.curl"
peer tc qdisc del dev wg-lab root
ip route add table 100 default dev wg-lab
ip link set wg-lab down
https_case interface_down wg-lab 1 failure
ip link set wg-lab up
https_case interface_recovered wg-lab 2 success
check 'interface recovery stays in WG' test "$direct_count" -eq 0
ip link del wg-lab
https_case interface_deleted wg-lab 1 absent

printf '\nRESULT failures=%s finished=%s\n' "$failures" "$(date -u +%FT%TZ)"
test "$failures" -eq 0
