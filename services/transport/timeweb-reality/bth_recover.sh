#!/bin/bash
# Restore only the BTH peer after validating a fresh, pinned namespace.
set -Eeuo pipefail
export PATH=/usr/sbin:/usr/bin:/sbin:/bin
export LC_ALL=C
umask 077
cd /opt/timeweb-reality/bth-recovery
if [ "${BTH_RECOVERY_LOCK_HELD:-}" != "1" ]; then
    exec 9>/run/lock/reality-stage9.lock
    flock -w 5 9
fi
key=$(cat peer.public)
ns_path=
tmp=$(mktemp -d /run/bth-recover.XXXXXXXX)
restored=false
check_only=false
if [ "${1:-}" = --check ]; then check_only=true; fi
ns() { nsenter --net="$ns_path" -- "$@"; }
finish() {
    rc=$?
    trap - EXIT
    if [ "$rc" != 0 ]; then
        if [ -n "$ns_path" ] && [ "$check_only" = false ]; then ns wg set wg-home peer "$key" remove 2>/dev/null || true; fi
        echo 'BTH REFUSED: contract or readiness check failed; foreign exits unchanged' >&2
    fi
    rm -rf -- "$tmp"
    exit "$rc"
}
trap finish EXIT
hash() { sha256sum "$1" | cut -d ' ' -f 1; }
need_hash() { [ "$(hash "$2")" = "$(jq -r --arg k "$1" '.hashes[$k]' contract.json)" ]; }
xray_contract_valid() {
    local config=/opt/timeweb-reality/config.json
    local tag native backup actual
    for tag in wg-fornex wg-cenuta; do
        native=$(jq -er --arg tag "$tag" '.xray_endpoints[$tag].native' contract.json) || return 1
        backup=$(jq -er --arg tag "$tag" '.xray_endpoints[$tag].backup' contract.json) || return 1
        actual=$(jq -er --arg tag "$tag" '
            [.outbounds[] | select(.tag == $tag) | .settings.peers[] | .endpoint]
            | if length == 1 then .[0] else error("unexpected peer count") end
        ' "$config") || return 1
        [ "$actual" = "$native" ] || [ "$actual" = "$backup" ] || return 1
    done
    [ "$(jq -S '
        (.outbounds[] | select(.tag == "wg-fornex") | .settings.peers[0].endpoint) = "<fornex-endpoint>"
        | (.outbounds[] | select(.tag == "wg-cenuta") | .settings.peers[0].endpoint) = "<cenuta-endpoint>"
    ' "$config" | sha256sum | cut -d ' ' -f 1)" = "$(jq -r '.hashes.xray_normalized' contract.json)" ]
}
wg_allowed_contract_valid() {
    local wg_hash allowed_hash
    wg_hash=$(hash "$1")
    allowed_hash=$(hash "$2")
    if jq -e '.wg_allowed_states? | type == "array" and length > 0' contract.json >/dev/null; then
        jq -e --arg wg "$wg_hash" --arg allowed "$allowed_hash" \
            '.wg_allowed_states | any(.wg == $wg and .allowed == $allowed)' contract.json >/dev/null
    else
        [ "$wg_hash" = "$(jq -r '.hashes.wg' contract.json)" ] &&
            [ "$allowed_hash" = "$(jq -r '.hashes.allowed' contract.json)" ]
    fi
}
rules_contract_valid() {
    need_hash rules rules.baseline || return 1
    if jq -e '.hashes | has("rules_with_monitoring")' contract.json >/dev/null; then
        need_hash rules_with_monitoring rules.monitoring.baseline || return 1
        # Accept two complete reviewed inventories, never ignore a priority range.
        need_hash rules "$1" || need_hash rules_with_monitoring "$1"
    else
        need_hash rules "$1"
    fi
}
inspect() { docker inspect wg-relay >"$tmp/inspect.json"; }
inspect
pid=$(jq -er '.[0].State | select(.Running == true) | .Pid | select(. > 1)' "$tmp/inspect.json")
cid=$(jq -r '.[0].Id' "$tmp/inspect.json")
exec 3<"/proc/$pid/ns/net"
ns_path="/proc/$$/fd/3"
inode=$(readlink "$ns_path")
contract_check() {
    inspect
    [ "$(jq -r '.[0].Id' "$tmp/inspect.json")" = "$cid" ]
    [ "$(jq -r '.[0].State.Pid' "$tmp/inspect.json")" = "$pid" ]
    [ "$(readlink "/proc/$pid/ns/net")" = "$inode" ]
    [ "$(jq -r '.[0].Image' "$tmp/inspect.json")" = "$(jq -r .image contract.json)" ]
    jq -e '.[0].Mounts | any(.Source == "/opt/wg/config" and .Destination == "/config" and .RW == true)' "$tmp/inspect.json" >/dev/null
    jq -e '.[0].NetworkSettings.Networks | any(.IPAddress == "172.19.0.2")' "$tmp/inspect.json" >/dev/null
    xray_contract_valid
    need_hash guard relay.nft
    need_hash expected relay.expected
    need_hash public peer.public
    need_hash psk peer.psk
    [ "$(ns wg show wg-home public-key)" = "$(jq -r .wg_public contract.json)" ]
    [ "$(ns wg show wg-home listen-port)" = 51830 ]
    ns ip -j -4 address show dev eth0 | jq -e '.[0].addr_info | any(.local == "172.19.0.2")' >/dev/null
    ns ip -j -4 address show dev wg-home | jq -e '.[0].addr_info | any(.local == "10.30.30.1" and .prefixlen == 24)' >/dev/null
    ns ip -j rule show | jq -S . >"$tmp/rules"
    rules_contract_valid "$tmp/rules"
    ns ip -j route show table 300 | jq -S . >"$tmp/routes"
    need_hash routes "$tmp/routes"
    ns ip -j route get 1.1.1.1 from 10.30.30.5 iif wg-home | jq -e '.[0] | .dev == "wg-home" and (.table == 300 or .table == "300")' >/dev/null
    ns wg show wg-home allowed-ips | awk -v k="$key" '$1 != k' | sort >"$tmp/allowed"
    wg_allowed_contract_valid /opt/wg/config/wg_confs/wg-home.conf "$tmp/allowed"
    nft -s list table inet reality_fornex >"$tmp/hostguard"
    need_hash hostguard "$tmp/hostguard"
}
contract_check
if ns nft list table inet reality_b5 >/dev/null 2>&1; then
    ns nft -s list table inet reality_b5 >"$tmp/guard"
    cmp -s relay.expected "$tmp/guard"
else
    # A peer must never remain enabled while its forwarding guard is absent.
    [ "$check_only" = false ]
    ns wg set wg-home peer "$key" remove
    ns nft -f relay.nft
    ns nft -s list table inet reality_b5 >"$tmp/guard"
    cmp -s relay.expected "$tmp/guard"
    restored=true
fi
existing=$(ns wg show wg-home allowed-ips | awk -v k="$key" '$1 == k {print $2}')
if [ -z "$existing" ]; then
    [ "$check_only" = false ]
    contract_check
    ns wg set wg-home peer "$key" preshared-key peer.psk allowed-ips 10.30.30.5/32
    restored=true
else
    [ "$existing" = 10.30.30.5/32 ]
    actual_psk=$(ns wg show wg-home preshared-keys | awk -v k="$key" '$1 == k {print $2}')
    [ "$actual_psk" = "$(cat peer.psk)" ]
fi
contract_check
ns nft -s list table inet reality_b5 >"$tmp/guard"
cmp -s relay.expected "$tmp/guard"
if [ "$check_only" = true ]; then echo BTH_CONTRACT_VALID; exit 0; fi
jq -n --arg cid "$cid" --arg ns "$inode" --argjson pid "$pid" --argjson restored "$restored" \
    '{container:$cid,namespace:$ns,pid:$pid,restored:$restored,checked_unix:now}' >"$tmp/state"
install -m600 "$tmp/state" /run/bth-recovery-state.json
if [ "$restored" = true ]; then echo "BTH RESTORED namespace=$inode pid=$pid"; fi
