#!/bin/bash
# Negative checks use a private mount namespace and --check, never production writes.
set -euo pipefail
umask 077
base=/opt/timeweb-reality/bth-recovery
work=$(mktemp -d /run/bth-contract-test.XXXXXXXX)
trap 'rm -rf -- "$work"' EXIT
pid=$(docker inspect -f '{{.State.Pid}}' wg-relay)
nsenter -t "$pid" -n wg show wg-home allowed-ips >"$work/peers.before"
bash "$base/bth_recover.sh" --check
cp -a "$base" "$work/candidate"
for field in image hashes.wg hashes.routes hashes.rules hashes.hostguard hashes.expected; do
    jq --arg field "$field" 'setpath($field | split("."); "deliberate-invalid-test")' "$base/contract.json" >"$work/candidate/contract.json"
    if unshare -m --propagation private bash -c 'mount --bind "$1" /opt/timeweb-reality/bth-recovery; bash /opt/timeweb-reality/bth-recovery/bth_recover.sh --check' _ "$work/candidate" >"$work/output" 2>&1; then
        echo "FAIL: accepted invalid $field"; exit 1
    fi
    grep -q 'BTH REFUSED' "$work/output"
    bash "$base/bth_recover.sh" --check >/dev/null
    echo "PASS: refused invalid $field; original remains valid"
done
nsenter -t "$pid" -n wg show wg-home allowed-ips >"$work/peers.after"
cmp "$work/peers.before" "$work/peers.after"
echo 'PASS: live peer list unchanged'
