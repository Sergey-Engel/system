#!/usr/bin/env bash
# Sourced only by the candidate helper, under its ownership lock and pinned ns FD.
batch_probe() {
    # EXIT after a signal may run after Bash has unwound function-local variables.
    # Resource ownership must outlive the function frame.
    work= monitor= jobs=()
    local targets=$1 before cache_hash started ended generation ready=no
    local monitor_inode= monitor_start= up target i dev args ca=()
    owned_state || die missing_ownership_state
    test "$(stat -c %u "$targets")" = 0 || die targets_owner
    test "$((8#$(stat -c %a "$targets") & 022))" = 0 || die targets_permissions
    test "$(stat -c %s "$targets")" -le 65536 || die targets_size
    jq -e '.expires_unix|numbers' "$targets" >/dev/null || die targets_format
    if [ "$kind" = production ]; then
        jq -e '(.targets|keys)==["cloudflare","gstatic"] and
          .targets.gstatic.host=="www.gstatic.com" and
          .targets.gstatic.url=="https://www.gstatic.com/generate_204" and
          .targets.cloudflare.host=="www.cloudflare.com" and
          .targets.cloudflare.url=="https://www.cloudflare.com/cdn-cgi/trace" and
          ([.targets[].port]|all(.==443))' "$targets" >/dev/null || die targets_policy
    else
        ca=(--cacert "$(jq -er .ca_file "$targets")")
    fi
    started=$(date +%s.%N)
    jq -e --argjson now "$started" '$now<.expires_unix' "$targets" >/dev/null || die targets_expired
    cleanup_batch() {
        trap - EXIT
        trap '' TERM INT HUP
        local job
        for job in "${jobs[@]}"; do kill -KILL -- "-$job" 2>/dev/null || true; wait "$job" 2>/dev/null || true; done
        if [ -n "$monitor" ]; then kill -KILL "$monitor" 2>/dev/null || true; wait "$monitor" 2>/dev/null || true; fi
        if [ -n "${work:-}" ] && [ -d "$work" ]; then
            find "$work" -maxdepth 1 -type f -delete
            rmdir "$work"
        fi
    }
    trap cleanup_batch EXIT
    trap 'exit 90' TERM INT HUP
    work=$(mktemp -d "$state_dir/batch.XXXXXXXX")
    cp "$targets" "$work/targets.json"
    cache_hash=$(sha256sum "$work/targets.json" | awk '{print $1}')
    test "$cache_hash" = "$(sha256sum "$targets" | awk '{print $1}')" || die cache_changed
    nsenter --net=/proc/self/fd/9 stdbuf -oL -eL ip -ts monitor link address route rule 8>&- > "$work/events" 2> "$work/errors" &
    monitor=$!
    monitor_start=$(awk '{print $22}' /proc/"$monitor"/stat)
    batch_watcher_healthy() {
        local fd link inode row groups queue drops found=no
        kill -0 "$monitor" 2>/dev/null || return 1
        test "$monitor_start" = "$(awk '{print $22}' /proc/"$monitor"/stat)" || return 1
        test "$(readlink /proc/"$monitor"/ns/net)" = "$(readlink /proc/self/fd/9)" || return 1
        for fd in /proc/"$monitor"/fd/*; do
            link=$(readlink "$fd") || continue
            if [[ "$link" =~ ^socket:\[([0-9]+)\]$ ]]; then
                inode=${BASH_REMATCH[1]}
                if [ -n "$monitor_inode" ] && [ "$inode" != "$monitor_inode" ]; then continue; fi
                row=$(awk -v inode="$inode" '$2==0 && $10==inode {print $4,$5,$9}' /proc/"$monitor"/net/netlink)
                test -n "$row" || continue
                read -r groups queue drops <<< "$row"
                if (( (16#$groups & 0xd1) == 0xd1 )) && [ "$drops" = 0 ] && [ "$queue" = 0 ]; then
                    monitor_inode=$inode; found=yes
                fi
            fi
        done
        test "$found" = yes
    }
    for i in $(seq 1 50); do
        if batch_watcher_healthy; then ready=yes; break; fi
        sleep 0.02
    done
    test "$ready" = yes || die watcher_not_ready
    full_valid || die pre_manifest_invalid
    before=$(cat "$state_dir/state.json")
    generation=$(jq -er .generation <<< "$before")
    # Capture counters around the bound HTTPS probes. A raw counter alone is
    # not a failure signal: WireGuard keepalives also contribute bytes.
    # The collector uses these deltas only as corroboration for a failed probe.
    wg_transfer_snapshot() {
        local interface output lines peer received sent extra
        interface=$1
        output=$(ns timeout 2 wg show "$interface" transfer 2>/dev/null) || return 1
        lines=$(printf '%s\n' "$output" | sed '/^$/d' | wc -l)
        test "$lines" = 1 || return 1
        read -r peer received sent extra <<< "$output"
        [[ "$peer" =~ ^[A-Za-z0-9+/]{40,48}={0,2}$ ]] || return 1
        [[ "$received" =~ ^[0-9]+$ && "$sent" =~ ^[0-9]+$ ]] || return 1
        test -z "${extra:-}" || return 1
        jq -cn --argjson received "$received" --argjson sent "$sent" \
            '{received_bytes:$received,sent_bytes:$sent}'
    }
    for up in fornex cenuta; do
        if [ "$up" = fornex ]; then dev=wg1; else dev=wg-up-cenuta; fi
        wg_transfer_snapshot "$dev" > "$work/$up-transfer-pre.json" 2>/dev/null || true
    done
    # Snapshot coverage is intentionally NOT advertised as universal WG/firewall ABA.
    snapshot > "$work/pre.json"
    for up in fornex cenuta direct; do
        jobs=()
        for target in $(jq -r '.targets|keys[]' "$work/targets.json"); do
            local host ip port url
            host=$(jq -er --arg t "$target" '.targets[$t].host' "$work/targets.json")
            ip=$(jq -er --arg t "$target" '.targets[$t].ip' "$work/targets.json")
            port=$(jq -er --arg t "$target" '.targets[$t].port' "$work/targets.json")
            url=$(jq -er --arg t "$target" '.targets[$t].url' "$work/targets.json")
            [[ "$target" =~ ^[a-z_]{1,32}$ ]] || die target_name
            args=()
            if [ "$up" != direct ]; then
                dev=$(jq -er --arg u "$up" '.uplinks[$u].interface' "$manifest")
                args=(nsenter --net=/proc/self/fd/9)
            elif [ "$kind" = lab ]; then
                args=(nsenter --net=/proc/self/fd/9)
            fi
            # Each process group is individually owned and killed on every exit path.
            local bind=()
            if [ "$up" != direct ]; then bind=(--interface "if!$dev"); fi
            setsid "${args[@]}" curl -q -4 --noproxy '*' --proto '=https' \
                "${bind[@]}" "${ca[@]}" --resolve "$host:$port:$ip" \
                --connect-timeout 3 --max-time 5 -sS -o /dev/null \
                -w 'http=%{http_code} local=%{local_ip} remote=%{remote_ip} seconds=%{time_total} connect=%{time_connect} tls=%{time_appconnect}\n' \
                "$url" 8>&- > "$work/$up-$target.output" 2>&1 &
            jobs+=("$!")
        done
        i=0
        for target in $(jq -r '.targets|keys[]' "$work/targets.json"); do
            local rc=0
            wait "${jobs[$i]}" || rc=$?
            printf '%s' "$rc" > "$work/$up-$target.rc"
            i=$((i+1))
        done
        jobs=()
    done
    printf '{}' > "$work/diagnostics.json"
    for up in fornex cenuta; do
        local src peer stamp age result observed mode dnsok
        if [ "$up" = fornex ]; then dev=wg1; src=10.20.0.1; peer=10.20.0.2;
        else dev=wg-up-cenuta; src=10.40.40.2; peer=10.40.40.1; fi
        printf '{}' > "$work/signals.json"
        result=0
        ns timeout 2 ping -n -I "$dev" -c 1 -W 1 "$peer" > "$work/ping" 2>&1 || result=$?
        observed=$(date +%s.%N)
        if [ "$result" -le 1 ]; then
            jq --argjson now "$observed" --argjson rc "$result" \
                '.peer_icmp={value:($rc==0),observed_unix:$now}' "$work/signals.json" > "$work/signals.tmp"
            mv "$work/signals.tmp" "$work/signals.json"
        fi
        stamp=$(ns timeout 2 wg show "$dev" latest-handshakes | awk 'NR==1 {stamp=$2} END {if(NR==1) print stamp}')
        if [[ "$stamp" =~ ^[0-9]+$ ]]; then
            age=$(( $(date +%s) - stamp ))
            jq --argjson now "$observed" --argjson age "$age" \
                '.handshake_age={value:$age,observed_unix:$now}' "$work/signals.json" > "$work/signals.tmp"
            mv "$work/signals.tmp" "$work/signals.json"
        fi
        # The after value shares the same protected batch as the HTTPS probes.
        # Drop the observation on a peer reset instead of publishing a negative delta.
        if [ -s "$work/$up-transfer-pre.json" ] && wg_transfer_snapshot "$dev" > "$work/$up-transfer-post.json" 2>/dev/null; then
            if jq -n -e --slurpfile pre "$work/$up-transfer-pre.json" --slurpfile post "$work/$up-transfer-post.json" \
                '$post[0].received_bytes >= $pre[0].received_bytes and $post[0].sent_bytes >= $pre[0].sent_bytes' >/dev/null; then
                jq --slurpfile pre "$work/$up-transfer-pre.json" --slurpfile post "$work/$up-transfer-post.json" \
                    --argjson now "$observed" \
                    '.wg_transfer={value:($post[0] + {
                        received_delta_bytes:($post[0].received_bytes - $pre[0].received_bytes),
                        sent_delta_bytes:($post[0].sent_bytes - $pre[0].sent_bytes)
                    }),observed_unix:$now}' "$work/signals.json" > "$work/signals.tmp"
                mv "$work/signals.tmp" "$work/signals.json"
            fi
        fi
        if [ "$kind" = production ]; then
            for mode in udp tcp; do
                local tcp=()
                if [ "$mode" = tcp ]; then tcp=(+tcp); fi
                result=0
                ns timeout 2 dig -4 -b "$src" @1.1.1.1 www.gstatic.com A \
                    +time=1 +tries=1 +noall +comments +answer "${tcp[@]}" > "$work/dns" 2>&1 || result=$?
                if [ "$result" = 0 ] || [ "$result" = 9 ]; then
                    dnsok=false
                    if [ "$result" = 0 ] && grep -q 'status: NOERROR' "$work/dns" && grep -qE '[[:space:]]IN[[:space:]]+A[[:space:]]' "$work/dns"; then dnsok=true; fi
                    jq --arg key "dns_$mode" --argjson now "$(date +%s.%N)" --argjson ok "$dnsok" \
                        '.[$key]={value:$ok,observed_unix:$now}' "$work/signals.json" > "$work/signals.tmp"
                    mv "$work/signals.tmp" "$work/signals.json"
                fi
            done
        fi
        jq --arg up "$up" --slurpfile signals "$work/signals.json" \
            '.[$up]=$signals[0]' "$work/diagnostics.json" > "$work/diagnostics.tmp"
        mv "$work/diagnostics.tmp" "$work/diagnostics.json"
    done
    sleep 0.2
    full_valid || die post_manifest_invalid
    snapshot > "$work/post.json"
    cmp -s "$work/pre.json" "$work/post.json" || die snapshot_changed
    test "$before" = "$(cat "$state_dir/state.json")" || die guard_generation_changed
    test "$cache_hash" = "$(sha256sum "$targets" | awk '{print $1}')" || die cache_changed
    ended=$(date +%s.%N)
    # A target snapshot is admitted only at batch start and copied to this
    # private directory. Later cycles must resolve again; this batch remains
    # bounded by its independent 43-second deadline.
    jq -e --argjson end "$ended" --argjson start "$started" \
        '$end>= $start and ($end-$start)<43 and $start<.expires_unix' "$work/targets.json" >/dev/null || die deadline_or_start_expiry
    batch_watcher_healthy || die watcher_unhealthy
    if [ -s "$work/events" ] || [ -s "$work/errors" ]; then
        sed -n '1,10p' "$work/events" >&2
        sed -n '1,10p' "$work/errors" >&2
        die rtnl_event
    fi
    printf '[]' > "$work/records.json"
    for up in fornex cenuta direct; do
        for target in $(jq -r '.targets|keys[]' "$work/targets.json"); do
            test "$(stat -c %s "$work/$up-$target.output")" -le 4096 || die output_limit
            jq --arg up "$up" --arg target "$target" --rawfile output "$work/$up-$target.output" \
                --argjson rc "$(cat "$work/$up-$target.rc")" \
                '.+[{upstream:$up,target:$target,curl_exit:$rc,output:$output}]' \
                "$work/records.json" > "$work/records.tmp"
            mv "$work/records.tmp" "$work/records.json"
        done
    done
    jq -n --argjson started "$started" --argjson ended "$ended" --argjson generation "$generation" \
        --arg cache "$cache_hash" --arg manifest "$digest" --slurpfile records "$work/records.json" \
        --slurpfile diagnostics "$work/diagnostics.json" \
        '{version:1,started_unix:$started,finished_unix:$ended,generation:$generation,
          path_verified:true,validity_scope:"rtnl_and_snapshots",universal_generation:false,
          cache_sha256:$cache,manifest_sha256:$manifest,records:$records[0],diagnostics:$diagnostics[0]}'
    exit 0
}
