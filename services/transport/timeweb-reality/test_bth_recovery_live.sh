#!/bin/bash
set -euo pipefail
umask 077
base=/opt/timeweb-reality/bth-recovery
work=$(mktemp -d /run/bth-recovery-test.XXXXXXXX)
trap 'systemctl start bth-recovery.service || true; rm -rf -- "$work"' EXIT
pid=$(docker inspect -f '{{.State.Pid}}' wg-relay)
cid=$(docker inspect -f '{{.Id}}' wg-relay)
xpid=$(systemctl show -p MainPID --value xray-timeweb-reality)
key=$(cat "$base/peer.public")
nsenter -t "$pid" -n wg show wg-home allowed-ips | sort >"$work/peers.before"
flock -w 5 /run/lock/reality-stage9.lock bash -c '
  nsenter -t "$1" -n wg set wg-home peer "$2" remove
  nsenter -t "$1" -n nft delete table inet reality_b5
' _ "$pid" "$key"
systemctl start bth-recovery.service
jq -e '.restored == true' /run/bth-recovery-state.json >/dev/null
bash "$base/bth_recover.sh" --check
nsenter -t "$pid" -n wg show wg-home allowed-ips | sort >"$work/peers.after"
cmp "$work/peers.before" "$work/peers.after"
[ "$(systemctl show -p MainPID --value xray-timeweb-reality)" = "$xpid" ]
[ "$(docker inspect -f '{{.Id}}' wg-relay)" = "$cid" ]
echo 'PASS: own guard and peer restored; all peer AllowedIPs match; Xray and relay not restarted'
systemctl start bth-recovery.service
jq -e '.restored == false' /run/bth-recovery-state.json >/dev/null
echo 'PASS: second run idempotent'
