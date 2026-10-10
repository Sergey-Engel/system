set -Eeuo pipefail
stage=/root/uplink-guards-stage-20260911
dest=/opt/vpn-monitoring/guards
test ! -e "$dest"
install -d -m 700 "$dest"
install -m 700 "$stage/guardctl.sh" "$dest/guardctl.sh"
install -m 600 "$stage/guard-manifest.json" "$dest/guard-manifest.json"
install -m 600 "$stage/probe-targets.json" "$dest/probe-targets.json"
ctl() { bash "$dest/guardctl.sh" "$dest/guard-manifest.json" "$@"; }
unit=timeweb-uplink-guards-canary-rollback-20260911
systemd-run --unit="$unit" --on-active=5m --timer-property=AccuracySec=1s \
  /bin/bash "$dest/guardctl.sh" "$dest/guard-manifest.json" rollback
finish() {
    rc=$?
    if ctl rollback; then
        systemctl stop "$unit.timer"
    else
        printf 'ROLLBACK_FAILED safety timer left armed\n' >&2
        exit 2
    fi
    exit "$rc"
}
trap finish EXIT
printf 'CANARY_START %s\n' "$(date -u +%FT%TZ)"
ctl apply
ctl apply
ctl check
dig @172.19.0.2 example.org A +time=2 +tries=1 +noall +comments +answer
curl -q --noproxy '*' --connect-timeout 2 --max-time 3 -fsS http://172.19.0.2:8080/health
ctl probe fornex "$dest/probe-targets.json" gstatic
ctl probe cenuta "$dest/probe-targets.json" gstatic
printf 'CANARY_CHECKS_DONE %s\n' "$(date -u +%FT%TZ)"
