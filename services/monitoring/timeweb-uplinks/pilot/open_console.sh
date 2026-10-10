#!/bin/sh
# Open the loopback-only TimeWeb console through the existing SSH host profile.
set -eu

script=$0
while [ -L "$script" ]; do
  link=$(readlink "$script")
  case "$link" in /*) script=$link ;; *) script=$(dirname "$script")/$link ;; esac
done
root=$(CDPATH='' cd -- "$(dirname "$script")/../../../.." && pwd)
ssh_config="$root/.local/ssh/config"
if [ ! -r "$ssh_config" ]; then
  printf 'Run .venv/bin/python scripts/setup_mac.py --install from the project root first.\n' >&2
  exit 1
fi
ssh() { command ssh -F "$ssh_config" "$@"; }
host=timeweb-console
socket="${TMPDIR:-/tmp}/timeweb-vpn-console-${UID:-$(id -u)}.sock"
port=$(ssh -G "$host" 2>/dev/null | awk '$1 == "localforward" { print $2; exit }')
case "$port" in
  ''|*[!0-9]*) printf 'Missing numeric LocalForward for %s in ~/.ssh/config\n' "$host" >&2; exit 1 ;;
esac
url="http://127.0.0.1:$port/"
log_dir="$root/.local/runtime/timeweb-vpn"
log="$log_dir/launcher.log"
mkdir -p "$log_dir"
chmod 700 "$log_dir"

report() {
  printf '%s\n' "$*"
  printf '%s %s\n' "$(date '+%Y-%m-%d %H:%M:%S %z')" "$*" >> "$log"
  chmod 600 "$log"
}

describe() {
  if managed_tunnel; then
    report 'SSH tunnel: managed, running in background (not a terminal job).'
  else
    report 'SSH tunnel: external listener; this launcher does not own it.'
  fi
  pids=$(lsof -nP -t -iTCP:"$port" -sTCP:LISTEN | sort -u)
  for pid in $pids; do
    report "Process: $(ps -p "$pid" -o pid=,ppid=,etime=,comm= | awk '{$1=$1;print}') (PID PPID ELAPSED COMMAND)"
  done
  report "Console URL: $url"
  report 'Commands: timeweb-vpn status | timeweb-vpn stop | timeweb-vpn logs'
  report "Launcher log: $log"
}

console_ready() {
  curl --fail --silent --show-error --max-time 30 "$url" 2>/dev/null |
    grep -q '<title>TimeWeb: VPN control</title>'
}

managed_tunnel() {
  ssh -S "$socket" -O check -o PermitLocalCommand=no "$host" >/dev/null 2>&1
}

case "${1:-start}" in
  start)
    report "Checking console at $url (HTTP timeout: 30 s)..."
    if ! console_ready; then
      if lsof -nP -iTCP:"$port" -sTCP:LISTEN >/dev/null 2>&1; then
        report "ERROR: port $port is occupied, but the console is not responding. No process was stopped."
        exit 1
      fi
      if managed_tunnel; then
        report 'ERROR: managed SSH tunnel is running, but the console is not responding.'
        exit 1
      fi
      report "Starting background SSH tunnel via $host..."
      if ! ssh -fN -o BatchMode=yes -o PermitLocalCommand=no \
        -o ExitOnForwardFailure=yes -o ControlMaster=yes \
        -o ConnectTimeout=10 -o ServerAliveInterval=30 -o ServerAliveCountMax=3 \
        -o "ControlPath=$socket" "$host"; then
        report 'ERROR: SSH startup failed. No ready console confirmed.'
        exit 1
      fi
      report 'SSH started. Waiting for the remote console...'
      attempt=0
      until console_ready; do
        attempt=$((attempt + 1))
        if [ "$attempt" -ge 3 ]; then
          report "ERROR: SSH started, but console did not respond at $url. Use status/stop to inspect or stop it."
          exit 1
        fi
        sleep 1
      done
    else
      report 'Existing console connection reused; no new SSH process started.'
    fi
    report 'Console: READY'
    describe
    report 'Opening browser. SSH remains in the background; repeated start reuses it.'
    open "$url"
    ;;
  status)
    report "Checking console at $url..."
    if console_ready; then
      report 'Console: READY'
      describe
    else
      report "Console: NOT RESPONDING at $url"
      if managed_tunnel; then describe; else report 'No responsive managed SSH master.'; fi
      exit 1
    fi
    ;;
  stop)
    if managed_tunnel; then
      ssh -S "$socket" -O exit -o PermitLocalCommand=no "$host" >/dev/null
      report 'Managed SSH tunnel stopped. Remote VPN services remain running.'
    else
      report 'No managed tunnel to stop. Any external SSH session was left untouched.'
    fi
    ;;
  logs)
    if [ -f "$log" ]; then tail -n 80 "$log"; else printf 'No launcher log yet.\n'; fi
    ;;
  *)
    printf 'Usage: %s {start|status|stop|logs}\n' "$0" >&2
    exit 64
    ;;
esac
