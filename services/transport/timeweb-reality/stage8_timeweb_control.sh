#!/bin/bash
set -euo pipefail
umask 077
cd @REMOTE@
if [ "$1" != rollback-unlocked ]; then
  exec 9>/run/lock/reality-stage8.lock
  flock -w 20 9
fi
hash() { sha256sum "$1" | cut -d ' ' -f 1; }
replace_guard() {
  { if nft list table inet reality_fornex >/dev/null 2>&1; then echo 'delete table inet reality_fornex'; fi; cat "$1"; } | nft -f -
}
case "$1" in
validate)
  [ "$(hash /opt/timeweb-reality/config.json)" = @config.before@ ]
  diff -u guard.expected.before <(nft -s list table inet reality_fornex)
  /opt/timeweb-reality/xray run -test -format json -config config.after
  unshare -n bash -c 'nft -f guard.nft.after; nft -s list table inet reality_fornex' > guard.expected.after
  echo VALIDATED
  ;;
apply)
  [ "$(hash /opt/timeweb-reality/config.json)" = @config.before@ ]
  diff -u guard.expected.before <(nft -s list table inet reality_fornex)
  [ -s guard.expected.after ]
  systemd-run --unit=reality-stage8-rollback --on-active=180s --timer-property=AccuracySec=1s --property=Restart=on-failure --property=RestartSec=5s /bin/bash @REMOTE@/control.sh rollback
  systemctl is-active --quiet reality-stage8-rollback.timer
  trap 'trap - ERR; bash ./control.sh rollback-unlocked; exit 1' ERR
  systemctl stop xray-timeweb-reality
  replace_guard guard.nft.after
  install -o 10001 -g 10001 -m600 config.after /opt/timeweb-reality/config.json
  install -m600 guard.nft.after /opt/timeweb-reality/guard.nft
  install -m600 guard.expected.after /opt/timeweb-reality/guard.expected
  systemctl start xray-timeweb-reality
  systemctl is-active --quiet xray-timeweb-reality
  trap - ERR
  echo APPLIED_ROLLBACK_TIMER_ACTIVE_180S
  ;;
commit)
  [ "$(hash /opt/timeweb-reality/config.json)" = @config.after@ ]
  diff -u guard.expected.after <(nft -s list table inet reality_fornex)
  systemctl is-active --quiet xray-timeweb-reality
  systemctl stop reality-stage8-rollback.timer
  echo COMMITTED
  ;;
rollback|rollback-unlocked)
  current=$(hash /opt/timeweb-reality/config.json)
  [ "$current" = @config.after@ ] || [ "$current" = @config.before@ ]
  systemctl stop xray-timeweb-reality
  replace_guard guard.nft.before
  install -o 10001 -g 10001 -m600 config.before /opt/timeweb-reality/config.json
  install -m600 guard.nft.before /opt/timeweb-reality/guard.nft
  install -m600 guard.expected.before /opt/timeweb-reality/guard.expected
  systemctl start xray-timeweb-reality
  systemctl is-active --quiet xray-timeweb-reality
  systemctl stop reality-stage8-rollback.timer || true
  echo ROLLED_BACK
  ;;
*) exit 2;;
esac
