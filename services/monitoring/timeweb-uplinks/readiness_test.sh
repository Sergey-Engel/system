set -Eeuo pipefail
timeout 8 unshare --net bash -c '
ip -ts monitor link address route rule >/dev/null &
monitor=$!
trap "kill $monitor 2>/dev/null || true; wait $monitor 2>/dev/null || true" EXIT
sleep 0.2
printf "MONITOR=%s\n" "$monitor"
ps -p "$monitor" -o pid,ppid,args
ss -a -n -p -f netlink
ls -l "/proc/$monitor/fd"
cat "/proc/$monitor/net/netlink"
'
