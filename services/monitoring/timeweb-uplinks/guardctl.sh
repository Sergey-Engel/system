#!/usr/bin/env bash
# Exact-manifest IPv4 guards. No route edits, flushing, or VPN restarts.
set -Eeuo pipefail
umask 077
manifest=$(readlink -f "${1:?manifest required}")
action=${2:?action required}
shift 2
test "$(id -u)" = 0
test "$(stat -c %u "$manifest")" = 0
test "$((8#$(stat -c %a "$manifest") & 022))" = 0
jq -e '.version==1 and (.rules|length)==22 and (.expected_rules|length)==22' "$manifest" >/dev/null
state_dir=${GUARD_STATE_DIR:-/var/lib/vpn-uplink-guards}
mkdir -p "$state_dir"
test "$(stat -c %u "$state_dir")" = 0
test "$((8#$(stat -c %a "$state_dir") & 022))" = 0
exec 8>"$state_dir/lock"
flock -n 8
digest=$(sha256sum "$manifest" | awk '{print $1}')
kind=$(jq -r .target.kind "$manifest")
die() { printf 'REFUSED %s\n' "$*" >&2; exit 2; }
identity() {
    if [ "$kind" = lab ]; then
        test "${UPLINK_GUARD_LAB:-}" = yes || return 1
        test "$(readlink /proc/self/ns/net)" != "$(readlink /proc/1/ns/net)" || return 1
        test "$(readlink /proc/self/ns/net)" = "$(jq -r .target.namespace "$manifest")"
    else
        test "$kind" = production || return 1
        local live pid
        live=$(docker inspect wg-relay | jq '.[0]|{Id,State:{Pid:.State.Pid,StartedAt:.State.StartedAt,Running:.State.Running}}') || return 1
        test "$(jq -cS . <<< "$live")" = "$(jq -cS .target.container "$manifest")" || return 1
        pid=$(jq -r .State.Pid <<< "$live")
        test "$pid" -gt 1 || return 1
        test "$(cat /proc/sys/kernel/random/boot_id)" = "$(jq -r .target.boot "$manifest")" || return 1
        test "$(readlink /proc/$pid/ns/net)" = "$(jq -r .target.namespace "$manifest")" || return 1
        test "$(awk '{print $22}' /proc/$pid/stat)" = "$(jq -r .target.start "$manifest")"
    fi
}
identity || die namespace_generation_changed
if [ "$kind" = lab ]; then
    exec 9</proc/self/ns/net
else
    pid=$(jq -r .target.container.State.Pid "$manifest")
    exec 9<"/proc/$pid/ns/net"
fi
ns() { nsenter --net=/proc/self/fd/9 "$@"; }
rules_now() { ns ip -j -4 rule show; }
snapshot() {
    jq -cn \
      --argjson rules "$(rules_now)" \
      --argjson routes "$(ns ip -j -4 route show table all)" \
      --argjson links "$(ns ip -j -4 address show | jq '[.[]|{ifindex,ifname,flags,mtu,addr_info:[.addr_info[]|{local,prefixlen}]}]')" \
      --arg f "$(ns wg show wg1 allowed-ips)" --arg c "$(ns wg show wg-up-cenuta allowed-ips)" \
      --arg filter "$(ns iptables -S)" --arg nat "$(ns iptables -t nat -S)" --arg mangle "$(ns iptables -t mangle -S)" \
      '{rules:$rules,routes:$routes,links:$links,peers:{fornex:$f,cenuta:$c},filter:$filter,nat:$nat,mangle:$mangle}'
}
baseline_valid() {
    identity || return 1
    local live
    live=$(snapshot) || return 1
    # FLEX tables may change independently; only the two reviewed defaults are allowed.
    local flex_route='. as $root | all(["410","412","414"][]; . as $table |
      [$root.routes[] | select(.table==$table)] as $routes |
      $routes == [{"dst":"default","gateway":"10.20.0.2","dev":"wg1","table":$table,"flags":[]}] or
      $routes == [{"dst":"default","dev":"wg-up-cenuta","table":$table,"scope":"link","flags":[]}])'
    jq -e "$flex_route" <<< "$live" >/dev/null || return 1
    jq -e ".baseline | $flex_route" "$manifest" >/dev/null || return 1
    test "$(jq -cS 'del(.rules) | .routes |= (map(select(.table!="410" and .table!="412" and .table!="414")) | sort)' <<< "$live")" = \
         "$(jq -cS '.baseline | del(.rules) | .routes |= (map(select(.table!="410" and .table!="412" and .table!="414")) | sort)' "$manifest")" || return 1
    test "$(jq -cS '.rules|map(select(.priority<31000 or .priority>31021))' <<< "$live")" = "$(jq -cS .baseline.rules "$manifest")"
}
full_valid() {
    baseline_valid || return 1
    test "$(rules_now | jq -cS '[.[]|select(.priority>=31000 and .priority<=31021)]')" = "$(jq -cS .expected_rules "$manifest")"
}
argv_at() { mapfile -t argv < <(jq -r --argjson n "$1" '.rules[$n].argv[]' "$manifest"); }
current_at() { rules_now | jq -cS --argjson p "$1" '[.[]|select(.priority==$p)]'; }
expected_at() { jq -cS --argjson p "$1" '[.expected_rules[]|select(.priority==$p)]' "$manifest"; }
owned_state() { test -f "$state_dir/state.json" && test "$(jq -r .manifest_sha256 "$state_dir/state.json")" = "$digest"; }
advance() {
    local generation=0
    if test -f "$state_dir/state.json"; then generation=$(jq -r .generation "$state_dir/state.json"); fi
    jq -n --arg digest "$digest" --arg status "$1" --argjson generation "$((generation + 1))" \
      '{manifest_sha256:$digest,generation:$generation,status:$status}' > "$state_dir/state.tmp"
    mv "$state_dir/state.tmp" "$state_dir/state.json"
}
rollback() {
    owned_state || die missing_ownership_state
    identity || die namespace_generation_changed
    local i priority current
    # Validate the entire inventory before deleting even one rule.
    for i in $(seq 0 21); do
        priority=$((31000+i))
        current=$(current_at "$priority")
        if [ "$current" != '[]' ] && [ "$current" != "$(expected_at "$priority")" ]; then die "foreign_or_duplicate_rule_$priority"; fi
    done
    for i in $(seq 21 -1 0); do
        identity || die namespace_generation_changed
        priority=$((31000+i))
        if [ "$(current_at "$priority")" != '[]' ]; then
            argv_at "$i"
            ns ip -4 rule del "${argv[@]}"
        fi
    done
    advance rolled_back
    printf 'ROLLBACK own_rules_removed=22_or_already_absent\n'
}
case "$action" in
check)
    owned_state || die missing_ownership_state
    full_valid || die manifest_invalid
    printf 'VALID generation=%s\n' "$(jq -r .generation "$state_dir/state.json")"
    ;;
apply)
    baseline_valid || die baseline_drift
    occupied=$(rules_now | jq '[.[]|select(.priority>=31000 and .priority<=31021)]|length')
    if [ "$occupied" -ne 0 ]; then
        owned_state || die priorities_occupied_without_ownership
        full_valid || die partial_or_conflicting_rules
        printf 'NOOP already_applied\n'
        exit 0
    fi
    if test -f "$state_dir/state.json"; then owned_state || die different_manifest_owner; fi
    advance applying
    trap 'rc=$?; if [ "$rc" -ne 0 ]; then rollback || true; fi; exit "$rc"' EXIT
    for i in $(seq 0 21); do
        identity || die namespace_generation_changed
        test "$(current_at "$((31000+i))")" = '[]' || die priority_became_occupied
        argv_at "$i"
        ns ip -4 rule add "${argv[@]}"
    done
    full_valid || die post_apply_invalid
    advance applied
    trap - EXIT
    printf 'APPLIED own_rules=22\n'
    ;;
rollback) rollback ;;
probe)
    # One-shot measurement, not a collector. RTNL events invalidate even ABA changes.
    uplink=${1:?uplink required}
    owned_state || die missing_ownership_state
    targets=${2:?targets JSON required}
    target=${3:?target name required}
    test "$(stat -c %u "$targets")" = 0
    test "$((8#$(stat -c %a "$targets") & 022))" = 0
    interface=$(jq -er --arg u "$uplink" '.uplinks[$u].interface' "$manifest")
    url=$(jq -er --arg t "$target" '.targets[$t].url' "$targets")
    host=$(jq -er --arg t "$target" '.targets[$t].host' "$targets")
    ip=$(jq -er --arg t "$target" '.targets[$t].ip' "$targets")
    port=$(jq -er --arg t "$target" '.targets[$t].port' "$targets")
    expiry=$(jq -er .expires_unix "$targets")
    test "$(date +%s)" -lt "$expiry" || die targets_expired
    work=$(mktemp -d "$state_dir/probe.XXXXXXXX")
    monitor=
    cleanup_probe() {
        if [ -n "$monitor" ]; then kill "$monitor" 2>/dev/null || true; wait "$monitor" 2>/dev/null || true; fi
        find "$work" -maxdepth 1 -type f -delete
        rmdir "$work"
    }
    trap cleanup_probe EXIT
    nsenter --net=/proc/self/fd/9 stdbuf -oL -eL ip -ts monitor link address route rule 8>&- > "$work/events" 2> "$work/errors" &
    monitor=$!
    monitor_inode=
    monitor_ready() {
        local fd link inode row groups queue drops
        for fd in /proc/"$monitor"/fd/*; do
            link=$(readlink "$fd") || continue
            if [[ "$link" =~ ^socket:\[([0-9]+)\]$ ]]; then
                inode=${BASH_REMATCH[1]}
                row=$(awk -v inode="$inode" '$2==0 && $10==inode {print $4,$5,$9}' "/proc/$monitor/net/netlink")
                test -n "$row" || continue
                read -r groups queue drops <<< "$row"
                if (( (16#$groups & 0xd1) == 0xd1 )) && [ "$drops" = 0 ]; then
                    monitor_inode=$inode
                    return 0
                fi
            fi
        done
        return 1
    }
    monitor_healthy() {
        test -n "$monitor_inode" || return 1
        awk -v inode="$monitor_inode" '$2==0 && $10==inode && $5==0 && $9==0 {ok=1} END {exit !ok}' "/proc/$monitor/net/netlink"
    }
    ready=no
    for attempt in $(seq 1 50); do
        if monitor_ready; then ready=yes; break; fi
        kill -0 "$monitor" || die monitor_failed
        sleep 0.02
    done
    test "$ready" = yes || die monitor_not_ready
    sleep 0.05
    if ! full_valid; then printf 'UNKNOWN reason=pre_manifest_invalid request_not_started\n'; exit 90; fi
    before=$(cat "$state_dir/state.json")
    args=()
    if [ "$kind" = lab ]; then args=(--cacert "$(jq -er .ca_file "$targets")"); fi
    set +e
    ns curl -q -4 --noproxy '*' --interface "if!$interface" --resolve "$host:$port:$ip" \
      "${args[@]}" --connect-timeout 3 --max-time 5 -sS -o /dev/null \
      -w 'http=%{http_code} local=%{local_ip} remote=%{remote_ip} seconds=%{time_total}\n' "$url" > "$work/curl" 2>&1
    rc=$?
    set -e
    sleep 0.2
    valid=yes
    full_valid || valid=no
    kill -0 "$monitor" 2>/dev/null || valid=no
    monitor_healthy || valid=no
    test ! -s "$work/events" || valid=no
    test ! -s "$work/errors" || valid=no
    test "$before" = "$(cat "$state_dir/state.json")" || valid=no
    cat "$work/curl"
    if [ "$valid" != yes ]; then printf 'UNKNOWN reason=generation_or_manifest_changed result_discarded\n'; exit 90; fi
    printf 'VALID_OBSERVATION curl_exit=%s generation=%s\n' "$rc" "$(jq -r .generation "$state_dir/state.json")"
    # Exit 0 means the observation is valid, NOT that the uplink is UP.
    ;;
*) die 'action must be apply/check/rollback/probe' ;;
esac
