#!/bin/bash
set -euo pipefail
umask 077
cd @REMOTE@
if [ "$1" != rollback-unlocked ]; then
  exec 9>/run/lock/reality-c3.lock
  flock -w 20 9
fi
hash() { sha256sum "$1" | cut -d ' ' -f 1; }
case "$1" in
validate)
  [ "$(hash /etc/wireguard/wg-cenuta.conf)" = @wg.before@ ]
  [ "$(hash /etc/nftables.conf)" = @nft.before@ ]
  if nft list table inet reality_c3 >/dev/null 2>&1; then exit 1; fi
  if wg show wg-cenuta allowed-ips | grep -q '10.40.40.3/32'; then exit 1; fi
  nft -c -f nft.after
  unshare -n bash -c 'nft -f guard.nft; nft -s list table inet reality_c3' > guard.expected
  bash -n guard.sh
  echo VALIDATED
  ;;
apply)
  [ "$(hash /etc/wireguard/wg-cenuta.conf)" = @wg.before@ ]
  [ "$(hash /etc/nftables.conf)" = @nft.before@ ]
  [ -s guard.expected ]
  if nft list table inet reality_c3 >/dev/null 2>&1; then exit 1; fi
  if wg show wg-cenuta allowed-ips | grep -q '10.40.40.3/32'; then exit 1; fi
  systemd-run --unit=reality-c3-rollback --on-active=180s --timer-property=AccuracySec=1s --property=Restart=on-failure --property=RestartSec=5s /bin/bash @REMOTE@/control.sh rollback
  systemctl is-active --quiet reality-c3-rollback.timer
  trap 'trap - ERR; bash ./control.sh rollback-unlocked; exit 1' ERR
  if [ -d /etc/reality-c3 ]; then
    for f in guard.sh guard.nft guard.expected; do cmp "$f" "/etc/reality-c3/$f"; done
  fi
  install -d -m700 /etc/reality-c3
  install -m600 guard.sh guard.nft guard.expected /etc/reality-c3/
  bash /etc/reality-c3/guard.sh
  install -m600 nft.after /etc/nftables.conf.reality-new
  mv /etc/nftables.conf.reality-new /etc/nftables.conf
  install -m600 wg.after /etc/wireguard/wg-cenuta.conf.reality-new
  mv /etc/wireguard/wg-cenuta.conf.reality-new /etc/wireguard/wg-cenuta.conf
  wg set wg-cenuta peer "$(cat peer.public)" preshared-key peer.psk allowed-ips 10.40.40.3/32
  bash /etc/reality-c3/guard.sh
  trap - ERR
  echo APPLIED
  ;;
commit)
  [ "$(hash /etc/wireguard/wg-cenuta.conf)" = @wg.after@ ]
  [ "$(hash /etc/nftables.conf)" = @nft.after@ ]
  bash /etc/reality-c3/guard.sh
  wg show wg-cenuta allowed-ips | grep -F "$(cat peer.public)" | grep -q '10.40.40.3/32'
  systemctl stop reality-c3-rollback.timer
  echo COMMITTED
  ;;
rollback|rollback-unlocked)
  w=$(hash /etc/wireguard/wg-cenuta.conf)
  n=$(hash /etc/nftables.conf)
  [ "$w" = @wg.after@ ] || [ "$w" = @wg.before@ ]
  [ "$n" = @nft.after@ ] || [ "$n" = @nft.before@ ]
  wg set wg-cenuta peer "$(cat peer.public)" remove
  install -m600 wg.before /etc/wireguard/wg-cenuta.conf
  install -m600 nft.before /etc/nftables.conf
  if nft list table inet reality_c3 >/dev/null 2>&1; then nft delete table inet reality_c3; fi
  systemctl stop reality-c3-rollback.timer || true
  echo ROLLED_BACK_FILES_RETAINED
  ;;
*) exit 2;;
esac
