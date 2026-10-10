#!/bin/bash
set -euo pipefail
umask 077
cd @REMOTE@
if [ "$1" != rollback-unlocked ]; then exec 9>/run/lock/reality-stage9.lock; flock -w 20 9; fi
hash() { sha256sum "$1" | cut -d ' ' -f 1; }
nscheck() {
 [ "$(docker inspect -f '{{.State.Pid}}' wg-relay)" = @PID@ ]
 [ "$(readlink /proc/@PID@/ns/net)" = '@NS@' ]
 [ "$(hash /opt/wg/config/wg_confs/wg-home.conf)" = @wg.before@ ]
}
rnft() { nsenter -t @PID@ -n nft "$@"; }
replace_guard() { { echo 'delete table inet reality_fornex'; cat "$1"; } | nft -f -; }
peer_on() {
 nscheck
 diff -u relay.expected <(rnft -s list table inet reality_b5)
 nsenter -t @PID@ -n wg set wg-home peer "$(cat peer.public)" preshared-key peer.psk allowed-ips 10.30.30.5/32
}
case "$1" in
validate)
 nscheck
 [ "$(hash /opt/timeweb-reality/config.json)" = @config.before@ ]
 diff -u guard.expected.before <(nft -s list table inet reality_fornex)
 ! rnft list table inet reality_b5 >/dev/null 2>&1
 ! nsenter -t @PID@ -n wg show wg-home allowed-ips | grep -q '10.30.30.5'
 /opt/timeweb-reality/xray run -test -format json -config config.after
 unshare -n bash -c 'nft -f guard.nft.after; nft -s list table inet reality_fornex' >guard.expected.after
 unshare -n bash -c 'nft -f relay.nft; nft -s list table inet reality_b5' >relay.expected
 echo VALIDATED;;
apply)
 nscheck
 [ "$(hash /opt/timeweb-reality/config.json)" = @config.before@ ]
 diff -u guard.expected.before <(nft -s list table inet reality_fornex)
 ! rnft list table inet reality_b5 >/dev/null 2>&1
 ! nsenter -t @PID@ -n wg show wg-home allowed-ips | grep -q '10.30.30.5'
 systemd-run --unit=reality-stage9-rollback --on-active=180s --timer-property=AccuracySec=1s --property=Restart=on-failure --property=RestartSec=5s /bin/bash @REMOTE@/control.sh rollback
 systemctl is-active --quiet reality-stage9-rollback.timer
 trap 'trap - ERR; bash ./control.sh rollback-unlocked; exit 1' ERR
 rnft -f relay.nft
 peer_on
 systemctl stop xray-timeweb-reality
 replace_guard guard.nft.after
 install -o 10001 -g 10001 -m600 config.after /opt/timeweb-reality/config.json
 install -m600 guard.nft.after /opt/timeweb-reality/guard.nft
 install -m600 guard.expected.after /opt/timeweb-reality/guard.expected
 systemctl start xray-timeweb-reality
 systemctl is-active --quiet xray-timeweb-reality
 trap - ERR
 echo APPLIED_TIMER_180S;;
commit)
 nscheck
 [ "$(hash /opt/timeweb-reality/config.json)" = @config.after@ ]
 diff -u guard.expected.after <(nft -s list table inet reality_fornex)
 diff -u relay.expected <(rnft -s list table inet reality_b5)
 systemctl is-active --quiet xray-timeweb-reality
 systemctl stop reality-stage9-rollback.timer
 echo COMMITTED_RUNTIME_PEER_ONLY;;
peer-off)
 nscheck
 nsenter -t @PID@ -n wg set wg-home peer "$(cat peer.public)" remove
 echo NEW_PEER_REMOVED;;
peer-on) peer_on; echo NEW_PEER_RESTORED;;
rollback|rollback-unlocked)
 current=$(hash /opt/timeweb-reality/config.json)
 [ "$current" = @config.before@ ] || [ "$current" = @config.after@ ]
 systemctl stop xray-timeweb-reality
 replace_guard guard.nft.before
 install -o 10001 -g 10001 -m600 config.before /opt/timeweb-reality/config.json
 install -m600 guard.nft.before /opt/timeweb-reality/guard.nft
 install -m600 guard.expected.before /opt/timeweb-reality/guard.expected
 systemctl start xray-timeweb-reality
 if [ "$(readlink /proc/@PID@/ns/net 2>/dev/null)" = '@NS@' ]; then
   nsenter -t @PID@ -n wg set wg-home peer "$(cat peer.public)" remove
   if rnft list table inet reality_b5 >/dev/null 2>&1; then rnft delete table inet reality_b5; fi
 fi
 systemctl stop reality-stage9-rollback.timer || true
 echo ROLLED_BACK_ROUTER_SOURCE_GUARDS_RETAINED;;
*) exit 2;;
esac
