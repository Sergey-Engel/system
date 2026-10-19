#!/usr/bin/env bash
# Configuration backup only: never changes services, peers, routes or firewall.
set -euo pipefail
export LC_ALL=C
# Bash ulimit -f uses KiB unless POSIXLY_CORRECT is set.
unset POSIXLY_CORRECT
MAX_OUTPUT_BYTES=$((256 * 1024 * 1024))
DISK_MARGIN_BYTES=$((256 * 1024 * 1024))
MAX_ROOTS=64
MAX_CONTAINERS=16
MAX_MEMBERS=12000
MAX_INVENTORY_BYTES=$((8 * 1024 * 1024))
TAR_HEADER_BYTES=16384
CAPTURE_BYTES=$((1024 * 1024))
MAX_CAPTURES=96
FIXED_OVERHEAD_BYTES=$((8 * 1024 * 1024))
RUNTIME_ESTIMATE_BYTES=$((16 * 1024 * 1024))

fail() { printf '%s\n' "$*" >&2; exit 4; }

# Common GNU/BusyBox stat format. No dereferencing of links or opening device nodes.
# Internal TSV: path, type, octal mode, uid, gid, size, link, major-hex, minor-hex.
read -r -d '' MEMBER_PROGRAM <<'SH' || :
set -eu
fail() { printf 'SCAN_ERROR\n'; exit 4; }
tab=$(printf '\t')
cr=$(printf '\r')
nl='
'
for p in "$@"; do
    case "$p" in *"$tab"*|*"$cr"*|*"$nl"*) fail ;; esac
    [ ${#p} -le 4096 ] || fail
    values=$(stat -c '%f %a %u %g %s %t %T' "$p") || fail
    set -- $values
    [ "$#" -eq 7 ] || fail
    kind=$((0x$1 & 61440))
    case "$kind" in
        32768) type=f ;; 16384) type=d ;; 40960) type=l ;;
        8192) type=c ;; 24576) type=b ;; 4096) type=p ;; 49152) type=s ;;
        *) fail ;;
    esac
    link=
    if [ "$type" = l ]; then
        # Suppress the utility's delimiter; retain all bytes of the target.
        link=$(readlink -n "$p" && printf '.') || fail
        link=${link%.}
        case "$link" in *"$tab"*|*"$cr"*|*"$nl"*) fail ;; esac
        [ ${#link} -le 4096 ] || fail
    fi
    printf '%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\n' "$p" "$type" "$2" "$3" "$4" "$5" "$link" "$6" "$7"
done
SH

read -r -d '' SCAN_PROGRAM <<'SH' || :
set -eu
cd /
member_program=$1
shift
find "$@" \( -path opt/wg-router/backups -o -path opt/wg-router/logs \) -prune -o \
    -exec sh -c "$member_program" sh {} +
SH

read -r -d '' HASH_PROGRAM <<'SH' || :
set -eu
cd /
while IFS= read -r p; do
    [ -f "$p" ] && [ ! -L "$p" ] || exit 4
    sha256sum "$p"
done
SH

validate_inventory() {
    awk -F '\t' -v max="$MAX_MEMBERS" -v bytes="$MAX_INVENTORY_BYTES" \
        -v payload="$MAX_OUTPUT_BYTES" '
        NF != 9 || $2 !~ /^[fdlcbps]$/ || $3 !~ /^[0-7]+$/ ||
        $4 !~ /^[0-9]+$/ || $5 !~ /^[0-9]+$/ || $6 !~ /^[0-9]+$/ ||
        $8 !~ /^[0-9a-fA-F]+$/ || $9 !~ /^[0-9a-fA-F]+$/ { bad=1; exit 4 }
        { n++; size+=length($0)+1; if ($2=="f") data+=$6;
          if (n>max || size>bytes || data>payload) { bad=1; exit 4 }
          print }
        END { if (bad || !n) exit 4 }' | sort
}

scan_source() {
    local container=$1
    shift
    (( $# > 0 && $# <= MAX_ROOTS )) || fail 'Source root count exceeds limit'
    if [[ $container == host ]]; then
        timeout -k 5 60 sh -c "$SCAN_PROGRAM" sh "$MEMBER_PROGRAM" "$@"
    else
        timeout -k 5 60 docker exec "$container" sh -c "$SCAN_PROGRAM" sh "$MEMBER_PROGRAM" "$@"
    fi | validate_inventory
}

metadata_nul() {
    # Exact host contract: type, mode-octal, uid, gid, path, link-target, then NUL.
    awk -F '\t' '{printf "%s\t%s\t%s\t%s\t%s\t%s%c", $2,$3,$4,$5,$1,$7,0}' | sort -z
}

hash_inventory() {
    local container=$1 inventory=$2
    printf '%s\n' "$inventory" | awk -F '\t' '$2=="f" {print $1}' |
        if [[ $container == host ]]; then
            timeout -k 5 60 sh -c "$HASH_PROGRAM"
        else
            timeout -k 5 60 docker exec -i "$container" sh -c "$HASH_PROGRAM"
        fi | sort
}

host_roots() {
    local p
    for p in etc/wireguard etc/nftables.conf etc/iptables etc/ufw etc/default/ufw etc/iproute2 etc/sysctl.conf etc/sysctl.d etc/netplan etc/network etc/docker etc/systemd/system etc/ssh etc/passwd etc/group etc/subuid etc/subgid etc/sudoers etc/sudoers.d etc/cron.d etc/cron.daily etc/crontab var/spool/cron/crontabs root/.ssh/authorized_keys home/ubuntu/.ssh/authorized_keys; do
        if [[ -e /$p || -L /$p ]]; then printf '%s\n' "$p"; fi
    done
    if [[ $host != cenuta ]]; then printf '%s\n' opt/wg; fi
    if [[ $host == timeweb ]]; then
        printf '%s\n' opt/wg-router usr/local/bin/wg-status usr/local/sbin/wg-client-config \
            etc/wstunnel usr/local/lib/wstunnel usr/local/sbin/wstunnel-timeweb-fornex-wg-fallback \
            usr/local/sbin/timeweb-fornex-wg-transport usr/local/sbin/wstunnel-timeweb-cenuta-wg-fallback \
            usr/local/sbin/timeweb-cenuta-wg-transport
        if [[ -d /opt/timeweb-reality ]]; then printf '%s\n' opt/timeweb-reality; fi
        if [[ -d /opt/vpn-s2s ]]; then
            printf '%s\n' opt/vpn-s2s etc/vpn-s2s var/lib/vpn-s2s usr/local/sbin/timeweb-s2s
        fi
        if [[ -d /opt/vpn-runtime-recovery ]]; then
            printf '%s\n' opt/vpn-runtime-recovery var/lib/vpn-runtime-recovery \
                opt/vpn-monitoring/guards var/lib/vpn-uplink-guards/state.json \
                opt/vpn-monitoring/pilot/candidate/guardctl-batch.sh \
                opt/vpn-monitoring/pilot/config.json \
                opt/vpn-monitoring/pilot/collector/uplink_monitor/console.py \
                var/lib/vpn-uplink-pilot/transport-state.json \
                usr/local/sbin/timeweb-flex-macbook usr/local/sbin/timeweb-flex-fleet \
                etc/tmpfiles.d/timeweb-console-locks.conf
            for p in /var/lib/vpn-uplink-pilot/flex*.json; do
                [[ ! -f $p ]] || printf '%s\n' "${p#/}"
            done
        fi
    fi
    if [[ $host == fornex ]]; then
        printf '%s\n' opt/amnezia opt/fornex-awg31 etc/wstunnel usr/local/lib/wstunnel
    fi
    if [[ $host == cenuta ]]; then printf '%s\n' etc/reality-c3 etc/wstunnel usr/local/lib/wstunnel; fi
}

container_roots() {
    timeout -k 5 20 docker exec "$1" sh -c '
        cd /
        for p in opt/amnezia opt/fornex-awg31 opt/unbound/etc etc/unbound etc/wireguard etc/amnezia etc/ipsec.conf etc/ipsec.secrets etc/ipsec.d etc/strongswan.conf etc/strongswan.d etc/swanctl etc/xl2tpd etc/ppp etc/dnsmasq.conf etc/dnsmasq.d etc/bind etc/openvpn; do
            if [ -e "$p" ] || [ -L "$p" ]; then printf "%s\n" "$p"; fi
        done' | sort
}

container_inventory() {
    timeout -k 5 20 docker ps -a --format '{{.Names}}' |
        awk -v max="$MAX_CONTAINERS" '
            !/^[A-Za-z0-9][A-Za-z0-9_.-]*$/ || ++n>max { bad=1; exit 4 }
            { print }
            END { if (bad || !n) exit 4 }' | sort
}

check_disk() {
    local used=0 free remaining
    if [[ -d $dest ]]; then used=$(( $(du -sk "$dest" | awk '{print $1}') * 1024 )); fi
    # Reserve both the remaining raw bundle and its compressed copy, plus free margin.
    remaining=$((2 * planned_bytes - used))
    (( remaining > 0 )) || remaining=0
    free=$(( $(df -Pk "$base" | awk 'NR==2 {print $4}') * 1024 ))
    (( free >= remaining + DISK_MARGIN_BYTES )) || fail 'Insufficient remaining backup disk budget'
}

working_bytes() { find "$dest" -type f -printf '%s\n' | awk '{n+=$1} END {printf "%.0f\n",n}'; }

check_output_budget() {
    local next=$1 used needed
    used=$(working_bytes)
    # Charge actual captures, keeping space for uncaptured sources and packaging.
    needed=$((used + next + remaining_archive_bytes + metadata_reserve + FIXED_OVERHEAD_BYTES))
    (( needed <= MAX_OUTPUT_BYTES - 1048576 )) || fail 'Backup output exceeds admitted budget'
    if (( needed > planned_bytes )); then planned_bytes=$(( (needed + 1023) / 1024 * 1024 )); fi
    check_disk
}

limited_archive() (
    local limit=$1 output=$2
    shift 2
    ulimit -f "$((limit / 1024))"
    "$@" > "$output"
)

capture() {
    local dir=$1 name=$2 rc=0
    shift 2
    captures=$((captures + 1))
    (( captures <= MAX_CAPTURES )) || fail 'Runtime capture count exceeds limit'
    check_output_budget "$((2 * CAPTURE_BYTES))"
    (ulimit -f "$((CAPTURE_BYTES / 1024))"; timeout -k 5 20 "$@") > "$dir/$name" 2> "$dir/$name.stderr" || rc=$?
    printf '%s\t%s\n' "$name" "$rc" >> "$dir/commands.tsv"
    if (( rc != 0 )); then errors=$((errors + 1)); fi
}

snapshot() {
    local dir=$1 c pid
    capture "$dir" identity.txt sh -c 'hostname; date -u +%FT%TZ; uname -a; uptime; cat /proc/sys/kernel/random/boot_id'
    capture "$dir" boot-id.txt cat /proc/sys/kernel/random/boot_id
    capture "$dir" resources.txt sh -c 'free -m; df -h /; cat /proc/loadavg'
    capture "$dir" listeners.txt ss -lntup
    capture "$dir" host-addresses.json ip -j address show
    capture "$dir" host-routes4.json ip -j -4 route show table all
    capture "$dir" host-routes6.json ip -j -6 route show table all
    capture "$dir" host-rules4.json ip -j -4 rule show
    capture "$dir" host-rules6.json ip -j -6 rule show
    capture "$dir" host-nft.json nft -j -a list ruleset
    capture "$dir" host-nft.txt nft -a list ruleset
    capture "$dir" host-iptables.txt iptables-save
    capture "$dir" host-ip6tables.txt ip6tables-save
    capture "$dir" services.txt systemctl list-units --all --no-pager
    capture "$dir" unit-files.txt systemctl list-unit-files --no-pager
    capture "$dir" failed.txt systemctl --failed --no-pager
    capture "$dir" sysctl.txt sysctl net.ipv4.ip_forward net.ipv4.conf.all.rp_filter net.ipv4.conf.default.rp_filter net.ipv6.conf.all.forwarding
    capture "$dir" resolv.conf cat /etc/resolv.conf
    capture "$dir" accounts.txt getent passwd
    capture "$dir" groups.txt getent group
    if [[ $host == cenuta ]]; then
        capture "$dir" wg-public.txt wg show all
        capture "$dir" wg-runtime.conf wg showconf wg-cenuta
        capture "$dir" wg-unit.txt systemctl show wg-quick@wg-cenuta nftables -p Id -p ActiveState -p SubState -p ActiveEnterTimestamp -p FragmentPath
        return
    fi
    capture "$dir" docker-ps.json docker ps -a --format '{{json .}}'
    capture "$dir" docker-images.json docker image ls --digests --no-trunc --format '{{json .}}'
    capture "$dir" docker-networks.json sh -c 'docker network inspect $(docker network ls -q)'
    capture "$dir" docker-inspect.json sh -c 'docker inspect $(docker ps -aq)'
    capture "$dir" docker-stats.json docker stats --no-stream --format '{{json .}}'
    if [[ $host == timeweb ]]; then
        if [[ -f /etc/wireguard/wg-s2s.conf ]]; then
            capture "$dir" host-s2s-runtime.conf wg showconf wg-s2s
            capture "$dir" host-s2s-guard.txt python3 /etc/wireguard/s2s-pilot/guard.py check
        fi
        capture "$dir" xray-unit.txt systemctl show xray-timeweb-reality.service -p Id -p ActiveState -p SubState -p MainPID -p ActiveEnterTimestamp -p FragmentPath
        # --check does not alter peers/guards, but the existing helper uses /run
        # scratch files and its recovery lock. This is the explicit ephemeral exception.
        capture "$dir" bth-contract.txt bash /opt/timeweb-reality/bth-recovery/bth_recover.sh --check
        capture "$dir" bth-units.txt systemctl show bth-recovery.service bth-recovery.timer -p Id -p UnitFileState -p ActiveState -p Result
    else
        capture "$dir" awg-runtime.conf docker exec fornex-awg31 awg showconf awg0
        capture "$dir" awg-firewall.txt docker exec fornex-awg31 iptables-save
    fi
    if [[ $host == timeweb ]]; then c=wg-relay; else c=wg-exit; fi
    pid=$(docker inspect -f '{{.State.Pid}}' "$c")
    [[ $pid =~ ^[0-9]+$ && $pid -gt 0 ]]
    printf '%s\n' "$pid" > "$dir/wg-container-pid.txt"
    readlink "/proc/$pid/ns/net" > "$dir/wg-netns.txt"
    capture "$dir" wg-public.txt docker exec "$c" wg show all
    capture "$dir" wg-runtime.conf docker exec "$c" sh -c 'for i in $(wg show interfaces); do printf "# interface: %s\n" "$i"; wg showconf "$i"; done'
    capture "$dir" wg-addresses.json nsenter -t "$pid" -n ip -j address show
    capture "$dir" wg-routes4.json nsenter -t "$pid" -n ip -j -4 route show table all
    capture "$dir" wg-routes6.json nsenter -t "$pid" -n ip -j -6 route show table all
    capture "$dir" wg-rules4.json nsenter -t "$pid" -n ip -j -4 rule show
    capture "$dir" wg-rules6.json nsenter -t "$pid" -n ip -j -6 rule show
    capture "$dir" wg-nft.json nsenter -t "$pid" -n nft -j -a list ruleset
    capture "$dir" wg-nft.txt nsenter -t "$pid" -n nft -a list ruleset
    capture "$dir" wg-iptables.txt docker exec "$c" iptables-save
    capture "$dir" wg-ip6tables.txt docker exec "$c" ip6tables-save
    capture "$dir" wg-forwarding.txt nsenter -t "$pid" -n sysctl net.ipv4.ip_forward net.ipv4.conf.all.rp_filter net.ipv4.conf.default.rp_filter
}

set_roots() {
    local p
    roots=()
    while IFS= read -r p; do
        [[ $p =~ ^[A-Za-z0-9_./-]+$ && $p != /* && /$p/ != *'/../'* ]] || fail 'Invalid fixed source root'
        roots+=("$p")
        (( ${#roots[@]} <= MAX_ROOTS )) || fail 'Source root count exceeds limit'
    done <<< "$1"
}

admit_source() {
    local source=$1 root_list=$2 inventory entries payload hash_bytes estimate
    set_roots "$root_list"
    inventory=$(scan_source "$source" "${roots[@]}")
    read -r entries payload hash_bytes <<< "$(printf '%s\n' "$inventory" | awk -F '\t' '
        {n++; if ($2=="f") {bytes+=$6; hashes+=2*length($1)+68}}
        END {printf "%d %.0f %.0f\n",n,bytes,hashes}')"
    total_members=$((total_members + entries))
    (( total_members <= MAX_MEMBERS )) || fail 'Total source member count exceeds limit'
    # Count hardlinked file data more than once deliberately. Header allowance covers
    # padding, long names, ACL/xattr PAX records; the per-tar cap catches excess xattrs.
    estimate=$(( (payload + entries * TAR_HEADER_BYTES + 10240 + 1023) / 1024 * 1024 ))
    remaining_archive_bytes=$((remaining_archive_bytes + estimate))
    metadata_reserve=$((metadata_reserve + 4 * (${#inventory} + 1) + 3 * hash_bytes))
    planned_bytes=$((RUNTIME_ESTIMATE_BYTES + FIXED_OVERHEAD_BYTES + remaining_archive_bytes + metadata_reserve))
    (( planned_bytes <= MAX_OUTPUT_BYTES - 1048576 )) || fail 'Source and evidence estimates exceed 256 MiB output budget'
    sources+=("$source")
    source_roots+=("$root_list")
    initial_inventory+=("$inventory")
    archive_limits+=("$estimate")
}

source_phase() {
    local i=$1 phase=$2 source root_list inventory meta hashes meta_before hash_before root_file
    source=${sources[$i]}
    if [[ $source == host ]]; then
        root_list=$(host_roots)
        meta="$dest/host-metadata-$phase.nul"
        hashes="$dest/host-source-$phase.sha256"
        meta_before="$dest/host-metadata-before.nul"
        hash_before="$dest/host-source-before.sha256"
        root_file="$dest/host-roots-$phase.txt"
    else
        root_list=$(container_roots "$source")
        meta="$dest/containers/$source.metadata-$phase.nul"
        hashes="$dest/containers/$source.$phase.sha256"
        meta_before="$dest/containers/$source.metadata-before.nul"
        hash_before="$dest/containers/$source.before.sha256"
        root_file="$dest/containers/$source.roots-$phase.txt"
    fi
    [[ $root_list == "${source_roots[$i]}" ]] || fail "Source roots changed: $source"
    set_roots "$root_list"
    inventory=$(scan_source "$source" "${roots[@]}")
    # Includes size and inventory additions/removals, not just previously known files.
    [[ $inventory == "${initial_inventory[$i]}" ]] || fail "Source inventory or metadata changed: $source/$phase"
    check_output_budget "$((2 * (${#inventory} + 1)))"
    printf '%s\n' "$root_list" > "$root_file"
    printf '%s\n' "$inventory" | metadata_nul > "$meta"
    hash_inventory "$source" "$inventory" > "$hashes"
    if [[ $phase != before ]]; then
        cmp -s "$meta_before" "$meta" || fail "Source metadata changed: $source/$phase"
        cmp -s "$hash_before" "$hashes" || fail "Source content changed: $source/$phase"
    fi
}

main() {
    umask 077
    host=${1:?host required}
    run=${2:?run required}
    [[ $host =~ ^(timeweb|fornex|cenuta)$ ]]
    [[ $run =~ ^[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{6}Z_current-config$ ]]
    [[ $(id -u) == 0 ]]
    ulimit -c 0
    ulimit -f "$((MAX_OUTPUT_BYTES / 1024))"
    base=/var/backups/timeweb-reality
    dest=$base/$run
    install -d -m 700 "$base"
    exec 8>"$base/.backup.lock"
    flock -n 8 || fail 'Another configuration backup is running'
    [[ ! -e $dest && ! -L $dest && ! -e $dest.tar.gz && ! -L $dest.tar.gz ]]
    cd /
    local started c i inventory final_estimate
    started=$(date -u +%FT%TZ)
    errors=0
    captures=0
    sources=() source_roots=() initial_inventory=() archive_limits=()
    total_members=0
    remaining_archive_bytes=0
    metadata_reserve=0
    planned_bytes=$((RUNTIME_ESTIMATE_BYTES + FIXED_OVERHEAD_BYTES))
    # Admission happens in memory before creating the run directory or writing tar data.
    admit_source host "$(host_roots)"
    inventory=
    if [[ $host != cenuta ]]; then
        inventory=$(container_inventory)
        while IFS= read -r c; do
            # These mounted WG files are covered by the host's opt/wg archive.
            if [[ $c == wg-relay || $c == wg-exit ]]; then continue; fi
            [[ $(timeout -k 5 20 docker inspect -f '{{.State.Running}}' "$c") == true ]] || fail "Cannot capture stopped container: $c"
            admit_source "$c" "$(container_roots "$c")"
        done <<< "$inventory"
    fi
    planned_bytes=$(( (planned_bytes + 1023) / 1024 * 1024 ))
    check_disk
    mkdir -m 700 "$dest"
    mkdir -m 700 "$dest/state-before" "$dest/state-after" "$dest/containers"
    printf '%s\n' "$started" > "$dest/started_utc.txt"
    printf '3\n' > "$dest/schema-version.txt"
    printf '%s\n' "$host" > "$dest/host.txt"
    printf 'limit_bytes\t%d\nplanned_bytes\t%d\ndisk_margin_bytes\t%d\nsource_members\t%d\n' \
        "$MAX_OUTPUT_BYTES" "$planned_bytes" "$DISK_MARGIN_BYTES" "$total_members" > "$dest/budget.tsv"
    printf '%s\n' 'BTH --check preserves peers/guards but uses ephemeral /run scratch files and the existing recovery lock.' > "$dest/read-only-scope.txt"
    printf '%s\n' "${source_roots[0]}" > "$dest/host-roots.txt"
    printf '%s\n' opt/wg-router/backups opt/wg-router/logs > "$dest/excluded.txt"
    if [[ $host != cenuta ]]; then printf '%s\n' "$inventory" > "$dest/container-inventory.txt"; fi
    snapshot "$dest/state-before"
    # Establish every baseline before any tar is captured.
    for ((i=0; i<${#sources[@]}; i++)); do source_phase "$i" before; done
    for ((i=0; i<${#sources[@]}; i++)); do
        c=${sources[$i]}
        set_roots "${source_roots[$i]}"
        remaining_archive_bytes=$((remaining_archive_bytes - archive_limits[i]))
        check_output_budget "${archive_limits[$i]}"
        if [[ $c == host ]]; then
            limited_archive "${archive_limits[$i]}" "$dest/host-files.tar" \
                timeout -k 5 45 nice -n 10 tar --acls --xattrs --numeric-owner \
                --exclude-from="$dest/excluded.txt" -cf - "${roots[@]}"
            tar -tf "$dest/host-files.tar" > "$dest/host-tar-members.txt"
        else
            printf '%s\n' "${source_roots[$i]}" > "$dest/containers/$c.roots.txt"
            limited_archive "${archive_limits[$i]}" "$dest/containers/$c.tar" \
                timeout -k 5 30 docker exec -i "$c" tar -cf - -C / -T - < "$dest/containers/$c.roots.txt"
            tar -tf "$dest/containers/$c.tar" > "$dest/containers/$c.members.txt"
        fi
        source_phase "$i" after
    done
    snapshot "$dest/state-after"
    if [[ $host != cenuta ]]; then
        container_inventory > "$dest/container-inventory-final.txt"
        cmp -s "$dest/container-inventory.txt" "$dest/container-inventory-final.txt" || fail 'Container inventory changed'
    fi
    # Revisit all containers after all captures; the host check is deliberately last.
    for ((i=1; i<${#sources[@]}; i++)); do source_phase "$i" final; done
    source_phase 0 final
    date -u +%FT%TZ > "$dest/completed_utc.txt"
    printf '%s\n' "$errors" > "$dest/capture-errors.txt"
    check_output_budget 0
    cd "$dest"
    find . -type f ! -name SHA256SUMS -print0 | sort -z | xargs -0 -r sha256sum > SHA256SUMS
    sha256sum -c SHA256SUMS > /dev/null
    final_estimate=$(find . -printf '%s\t%y\n' | awk -F '\t' -v header="$TAR_HEADER_BYTES" '
        {n++; if ($2=="f") bytes+=$1} END {printf "%.0f\n",bytes+n*header+10240+1048576}')
    (( final_estimate <= MAX_OUTPUT_BYTES )) || fail 'Final bundle exceeds output budget before compression'
    if (( final_estimate > planned_bytes )); then planned_bytes=$final_estimate; fi
    check_disk
    cd "$base"
    limited_archive "$MAX_OUTPUT_BYTES" "$dest.tar.gz" timeout -k 5 45 bash -o pipefail -c \
        'nice -n 10 tar -cf - "$1" | gzip -1' bash "$run"
    gzip -t "$dest.tar.gz"
    chmod 600 "$dest.tar.gz"
    printf 'BACKUP_HOST=%s\nCAPTURE_ERRORS=%s\n' "$host" "$errors"
    sha256sum "$dest.tar.gz"
    du -h "$dest.tar.gz"
    if (( errors != 0 )); then return 3; fi
}

if [[ ${BASH_SOURCE[0]:-$0} == "$0" ]]; then main "$@"; fi
