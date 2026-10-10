#!/usr/bin/env bash
set -euo pipefail

BASE=/opt/wg-router
WG_ROOT=/opt/wg
WG_CONFS=/opt/wg/config/wg_confs
COMPOSE=/opt/wg/docker-compose.yml
CONTAINER=wg-relay
PUBLIC_ENDPOINT=94.241.171.65
CLIENT_PORT=51850
CLIENT_SUBNET=10.50.50.0/24
CLIENT_SERVER_IP=10.50.50.1
CLIENT_IPV6_PREFIX=fd00:50:50
CLIENT_ALLOWED_IPS="::/0, 1.0.0.0/8, 2.0.0.0/8, 3.0.0.0/8, 4.0.0.0/6, 8.0.0.0/7, 11.0.0.0/8, 12.0.0.0/6, 16.0.0.0/4, 32.0.0.0/3, 64.0.0.0/2, 128.0.0.0/3, 160.0.0.0/5, 168.0.0.0/6, 172.0.0.0/12, 172.32.0.0/11, 172.64.0.0/10, 172.128.0.0/9, 173.0.0.0/8, 174.0.0.0/7, 176.0.0.0/4, 192.0.0.0/9, 192.128.0.0/11, 192.160.0.0/13, 192.169.0.0/16, 192.170.0.0/15, 192.172.0.0/14, 192.176.0.0/12, 192.192.0.0/10, 193.0.0.0/8, 194.0.0.0/7, 196.0.0.0/6, 200.0.0.0/5, 208.0.0.0/4, 1.1.1.1/32, 8.8.8.8/32"
CENUTA_ENDPOINT=89.252.153.129:51840
CENUTA_PUBLIC_KEY=3fg6rK3jeTdtGxtr0yX896BhEtH33OvWyx3ncTm6uR0=
TIMEWEB_CENUTA_EXPECTED_PUBLIC=OfeWs9lG/g29GYP1paZyN9sslIyocgfs2rqn8b4etHQ=
STATE_CLIENTS=$BASE/state/clients.tsv
SERVER_KEY=$BASE/keys/server/wg-clients.key
SERVER_PUB=$BASE/keys/server/wg-clients.pub
UPSTREAM_KEY=$BASE/keys/upstream/timeweb-wg-up-cenuta.key
UPSTREAM_PUB=$BASE/keys/upstream/timeweb-wg-up-cenuta.pub
HANDOFF_CONF=/root/wireguard-handoff/timeweb-wg-up-cenuta.conf
MANAGED_CLIENTS_CONF=$BASE/configs/server/wg-clients.conf
MANAGED_CENUTA_CONF=$BASE/configs/server/wg-up-cenuta.conf
ACTIVE_CLIENTS_CONF=$WG_CONFS/wg-clients.conf
ACTIVE_CENUTA_CONF=$WG_CONFS/wg-up-cenuta.conf
RU_BTH_SCRIPT=$BASE/apply-ru-bth.sh

log() { printf '[wg-router] %s\n' "$*"; }
fatal() { printf '[wg-router] ERROR: %s\n' "$*" >&2; exit 1; }
need_root() { [ "${EUID:-$(id -u)}" -eq 0 ] || fatal 'run as root'; }
# This legacy writer is retired: BTH pins the entire RPDB and exact configs.
# Read-only viewers remain available. No bypass or automatic re-signing.
refuse_legacy_change() {
  fatal 'RETIRED mutation: use System/transport/timeweb-reality/run_backup.py and maintenance_preflight.py --check; WG changes require a reviewed BTH contract update. No bypass.'
}
valid_name() { [[ "$1" =~ ^[a-zA-Z0-9_.-]+$ ]]; }

init_dirs() {
  refuse_legacy_change
  need_root
  install -d -m 0750 -o root -g root "$BASE" "$BASE/env" "$BASE/configs" "$BASE/configs/server" "$BASE/configs/snippets" "$BASE/client-configs" "$BASE/logs" "$BASE/state" "$BASE/backups" "$BASE/docs"
  install -d -m 0700 -o root -g root "$BASE/keys" "$BASE/keys/server" "$BASE/keys/upstream" "$BASE/keys/clients"
  touch "$STATE_CLIENTS"
  chmod 0600 "$STATE_CLIENTS"
  cat > "$BASE/env/routes.env" <<EOF
PUBLIC_ENDPOINT=$PUBLIC_ENDPOINT
CLIENT_PORT=$CLIENT_PORT
CLIENT_SUBNET=$CLIENT_SUBNET
CLIENT_SERVER_IP=$CLIENT_SERVER_IP
CENUTA_ENDPOINT=$CENUTA_ENDPOINT
CENUTA_TABLE=200
FORNEX_TABLE=100
EOF
  chmod 0640 "$BASE/env/routes.env"
  log "initialized $BASE"
}

ensure_server_key() {
  refuse_legacy_change
  init_dirs >/dev/null
  if [ ! -s "$SERVER_KEY" ]; then
    umask 077
    wg genkey > "$SERVER_KEY"
    wg pubkey < "$SERVER_KEY" > "$SERVER_PUB"
  elif [ ! -s "$SERVER_PUB" ]; then
    wg pubkey < "$SERVER_KEY" > "$SERVER_PUB"
  fi
  chmod 0600 "$SERVER_KEY"
  chmod 0644 "$SERVER_PUB"
}

public_from_private_file() { wg pubkey < "$1"; }

client_line() {
  local name=$1
  awk -F '\t' -v n="$name" '$1==n {print; found=1} END {exit found?0:1}' "$STATE_CLIENTS"
}

ip_in_use() {
  local ip=$1
  awk -F '\t' -v ip="$ip" '$3==ip {found=1} END {exit found?0:1}' "$STATE_CLIENTS"
}

alloc_ip() {
  local name=$1 route=$2 ip octet
  case "$name:$route" in
    client-1:fornex) echo 10.50.50.11; return 0 ;;
    client-2:cenuta) echo 10.50.50.12; return 0 ;;
  esac
  for octet in $(seq 20 254); do
    ip="10.50.50.$octet"
    if ! ip_in_use "$ip"; then echo "$ip"; return 0; fi
  done
  fatal 'no free IPs in 10.50.50.0/24 allocation range'
}

gen_upstream() {
  refuse_legacy_change
  need_root
  local target=${1:-}
  [ "$target" = cenuta ] || fatal 'usage: gen-upstream cenuta'
  init_dirs >/dev/null
  if [ ! -s "$UPSTREAM_KEY" ]; then
    [ -f "$HANDOFF_CONF" ] || fatal "handoff config not found: $HANDOFF_CONF"
    sed -nE 's/^[[:space:]]*PrivateKey[[:space:]]*=[[:space:]]*(.*[^[:space:]])[[:space:]]*$/\1/p' "$HANDOFF_CONF" > "$UPSTREAM_KEY"
    chmod 0600 "$UPSTREAM_KEY"
  fi
  public_from_private_file "$UPSTREAM_KEY" > "$UPSTREAM_PUB"
  chmod 0644 "$UPSTREAM_PUB"
  local pub
  pub=$(cat "$UPSTREAM_PUB")
  [ "$pub" = "$TIMEWEB_CENUTA_EXPECTED_PUBLIC" ] || fatal "TimeWeb-Cenuta public key mismatch: $pub"
  render_upstream
  log "prepared wg-up-cenuta; public=$pub"
}

ensure_client_key() {
  refuse_legacy_change
  local name=$1 key="$BASE/keys/clients/$name.key" pub="$BASE/keys/clients/$name.pub"
  if [ ! -s "$key" ]; then
    umask 077
    wg genkey > "$key"
    wg pubkey < "$key" > "$pub"
  elif [ ! -s "$pub" ]; then
    wg pubkey < "$key" > "$pub"
  fi
  chmod 0600 "$key"
  chmod 0644 "$pub"
}

gen_client() {
  refuse_legacy_change
  need_root
  local name=${1:-} route=${2:-}
  valid_name "$name" || fatal 'client name must contain only latin letters, digits, underscore, dash or dot'
  [[ "$route" =~ ^(fornex|cenuta)$ ]] || fatal 'route must be fornex or cenuta'
  init_dirs >/dev/null
  ensure_server_key
  if client_line "$name" >/dev/null 2>&1; then
    local existing
    existing=$(client_line "$name")
    local existing_route
    existing_route=$(printf '%s\n' "$existing" | awk -F '\t' '{print $2}')
    [ "$existing_route" = "$route" ] || fatal "client exists with route $existing_route"
    log "client $name already exists; regenerating exported config"
  else
    local ip pub created
    ip=$(alloc_ip "$name" "$route")
    if ip_in_use "$ip"; then fatal "allocated IP already in use: $ip"; fi
    ensure_client_key "$name"
    pub=$(cat "$BASE/keys/clients/$name.pub")
    created=$(date -u +%Y-%m-%dT%H:%M:%SZ)
    printf '%s\t%s\t%s\t%s\t%s\n' "$name" "$route" "$ip" "$pub" "$created" >> "$STATE_CLIENTS"
    log "registered client $name route=$route ip=$ip public=$pub"
  fi
  render_client_config "$name"
}

render_client_config() {
  refuse_legacy_change
  local name=$1 line route ip ipv6 server_pub priv out
  line=$(client_line "$name") || fatal "unknown client: $name"
  route=$(printf '%s\n' "$line" | awk -F '\t' '{print $2}')
  ip=$(printf '%s\n' "$line" | awk -F '\t' '{print $3}')
  ipv6=$(client_ipv6_for_ip "$ip")
  server_pub=$(cat "$SERVER_PUB")
  priv=$(cat "$BASE/keys/clients/$name.key")
  out="$BASE/client-configs/$(selector_display_name "$name" "$route")"
  umask 077
  cat > "$out" <<EOF
[Interface]
#Client: $name
PrivateKey = $priv
Address = $ip/32, $ipv6/128
DNS = 1.1.1.1, 8.8.8.8

[Peer]
PublicKey = $server_pub
Endpoint = $PUBLIC_ENDPOINT:$CLIENT_PORT
AllowedIPs = $CLIENT_ALLOWED_IPS
PersistentKeepalive = 25
EOF
  chmod 0600 "$out"
  log "client config ready: $out"
}

route_table_for() { [ "$1" = fornex ] && echo 100 || echo 200; }
out_iface_for() { [ "$1" = fornex ] && echo wg1 || echo wg-up-cenuta; }
priority_for_ip() { local last=${1##*.}; echo $((200 + last)); }
client_ipv6_for_ip() { local last=${1##*.}; printf '%s::%s' "$CLIENT_IPV6_PREFIX" "$last"; }

read_conf_value() {
  local file=$1 key=$2
  sed -nE "s/^[[:space:]]*$key[[:space:]]*=[[:space:]]*(.*[^[:space:]])[[:space:]]*$/\1/p" "$file" | head -n 1
}

selector_name_from_display() {
  local base=${1%.conf}
  if [ -s "$STATE_CLIENTS" ] && awk -F '\t' -v n="$base" '$1==n {found=1} END {exit found?0:1}' "$STATE_CLIENTS"; then
    printf '%s\n' "$base"
    return 0
  fi
  case "$base" in
    *-cenuta-domru) printf '%s\n' "${base%-cenuta-domru}" ;;
    *-fornex-domru) printf '%s\n' "${base%-fornex-domru}" ;;
    *-fornex) printf '%s\n' "${base%-fornex}" ;;
    *-cenuta) printf '%s\n' "${base%-cenuta}" ;;
    *) fatal "cannot derive selector client name from $1" ;;
  esac
}

selector_display_name() {
  local name=$1 route=$2
  case "$name:$route" in
    *-cenuta-domru:cenuta|*-fornex-domru:fornex)
      printf '%s.conf\n' "$name"
      ;;
    *)
      printf '%s-%s.conf\n' "$name" "$route"
      ;;
  esac
}

client_name_from_entry() {
  local source=$1 display=$2 path=$3
  case "$source" in
    selector) selector_name_from_display "$display" ;;
    legacy|bth) basename "$(dirname "$path")" ;;
    *) fatal "unknown client source: $source" ;;
  esac
}

list_client_entries() {
  if [ -s "$STATE_CLIENTS" ]; then
    while IFS=$'\t' read -r client_name client_route client_ip client_pub client_created; do
      [ -n "${client_name:-}" ] || continue
      local display export_path local_path selected_path
      display=$(selector_display_name "$client_name" "$client_route")
      export_path="/root/wg-client-exports/$display"
      local_path="$BASE/client-configs/$display"
      selected_path=""
      [ -f "$export_path" ] && selected_path="$export_path"
      [ -z "$selected_path" ] && [ -f "$local_path" ] && selected_path="$local_path"
      [ -n "$selected_path" ] && printf 'selector\t%s\t%s\n' "$display" "$selected_path"
    done < "$STATE_CLIENTS"
  fi
  find "$WG_ROOT/clients" -mindepth 2 -maxdepth 2 -type f -name '*.conf' -printf 'legacy\t%f\t%p\n' 2>/dev/null || true
  find "$WG_ROOT/clients_bth" -mindepth 2 -maxdepth 2 -type f -name '*.conf' -printf 'bth\t%f\t%p\n' 2>/dev/null || true
}

print_client_config_file() {
  local path=$1
  [ -r "$path" ] || fatal "client config is not readable: $path"
  command -v qrencode >/dev/null 2>&1 || fatal 'qrencode is not installed'
  printf '\n===== WireGuard client config: %s =====\n\n' "$(basename "$path")"
  cat "$path"
  printf '\n===== QR code: %s =====\n\n' "$(basename "$path")"
  qrencode -t ansiutf8 < "$path"
}

sync_wg_interface() {
  refuse_legacy_change
  local iface=$1
  docker exec "$CONTAINER" sh -c "wg syncconf '$iface' <(wg-quick strip '$iface')"
}

container_running() {
  docker ps --format '{{.Names}}' | grep -Fxq "$CONTAINER"
}

selector_port_published() {
  docker ps --filter "name=^/${CONTAINER}$" --format '{{.Ports}}' | grep -q '51850/udp'
}

selector_soft_reload_ready() {
  container_running && selector_port_published
}

selector_runtime_cmd() {
  refuse_legacy_change
  local op=$1 ip=$2 route=$3 table outif pref
  table=$(route_table_for "$route")
  outif=$(out_iface_for "$route")
  pref=$(priority_for_ip "$ip")
  case "$op" in
    apply)
      docker exec "$CONTAINER" sh -c "
        ip rule del from '$ip/32' table '$table' priority '$pref' 2>/dev/null || true
        ip rule add from '$ip/32' table '$table' priority '$pref'
        iptables -D FORWARD -i wg-clients -s '$ip/32' -o '$outif' -j ACCEPT 2>/dev/null || true
        iptables -D FORWARD -i '$outif' -d '$ip/32' -o wg-clients -j ACCEPT 2>/dev/null || true
        iptables -t nat -D POSTROUTING -s '$ip/32' -o '$outif' -j MASQUERADE 2>/dev/null || true
        iptables -A FORWARD -i wg-clients -s '$ip/32' -o '$outif' -j ACCEPT
        iptables -A FORWARD -i '$outif' -d '$ip/32' -o wg-clients -j ACCEPT
        iptables -t nat -A POSTROUTING -s '$ip/32' -o '$outif' -j MASQUERADE
      "
      ;;
    remove)
      docker exec "$CONTAINER" sh -c "
        ip rule del from '$ip/32' table '$table' priority '$pref' 2>/dev/null || true
        iptables -D FORWARD -i wg-clients -s '$ip/32' -o '$outif' -j ACCEPT 2>/dev/null || true
        iptables -D FORWARD -i '$outif' -d '$ip/32' -o wg-clients -j ACCEPT 2>/dev/null || true
        iptables -t nat -D POSTROUTING -s '$ip/32' -o '$outif' -j MASQUERADE 2>/dev/null || true
      "
      ;;
    *) fatal "unknown selector runtime operation: $op" ;;
  esac
}

apply_selector_client_runtime() {
  refuse_legacy_change
  local name=$1 line route ip
  line=$(client_line "$name") || fatal "unknown selector client: $name"
  route=$(printf '%s\n' "$line" | awk -F '\t' '{print $2}')
  ip=$(printf '%s\n' "$line" | awk -F '\t' '{print $3}')
  selector_runtime_cmd apply "$ip" "$route"
}

apply_all_selector_runtime() {
  refuse_legacy_change
  [ -s "$STATE_CLIENTS" ] || return 0
  while IFS=$'\t' read -r client_name client_route client_ip client_pub client_created; do
    [ -n "${client_name:-}" ] || continue
    selector_runtime_cmd apply "$client_ip" "$client_route"
  done < "$STATE_CLIENTS"
}

soft_reload_selector() {
  refuse_legacy_change
  apply_firewall
  if ! selector_soft_reload_ready; then
    fatal 'selector soft reload unavailable; REFUSED without container recreate'
  fi
  if ! sync_wg_interface wg-clients; then
    fatal 'selector syncconf failed; REFUSED without container recreate'
  fi
  if ! apply_all_selector_runtime; then
    fatal 'selector runtime rule apply failed; REFUSED without container recreate'
  fi
  apply_ru_bth
  log 'selector soft reload applied'
  return 0
}

remove_peer_block_by_client() {
  refuse_legacy_change
  local conf=$1 name=$2 tmp
  [ -f "$conf" ] || fatal "WireGuard config not found: $conf"
  if ! grep -Fxq "#Client: $name" "$conf" \
    && ! grep -Fxq "# Client: $name" "$conf" \
    && ! grep -Fxq "# Клиент: $name" "$conf"; then
    fatal "peer block not found in $conf for client $name"
  fi
  tmp=$(mktemp)
  awk -v target="#Client: $name" -v legacy_target="# Client: $name" -v ru_target="# Клиент: $name" '
    function flush_block() {
      if (block != "" && skip == 0) {
        printf "%s", block
      }
      block = ""
      skip = 0
    }
    /^\[Peer\]$/ {
      flush_block()
      block = $0 ORS
      next
    }
    {
      if (block != "") {
        block = block $0 ORS
        if ($0 == target || $0 == legacy_target || $0 == ru_target) {
          skip = 1
        }
      } else {
        print
      }
    }
    END { flush_block() }
  ' "$conf" > "$tmp"
  install -m "$(stat -c '%a' "$conf")" -o root -g root "$tmp" "$conf"
  rm -f "$tmp"
}

update_clients_list() {
  refuse_legacy_change
  local list_file=$1 name=$2 public_key=${3:-} tmp
  [ -f "$list_file" ] || return 0
  tmp=$(mktemp)
  awk -v prefix="$name: " 'index($0, prefix) != 1 {print}' "$list_file" > "$tmp"
  if [ -n "$public_key" ]; then
    printf '%s: %s\n' "$name" "$public_key" >> "$tmp"
  fi
  install -m "$(stat -c '%a' "$list_file")" -o root -g root "$tmp" "$list_file"
  rm -f "$tmp"
}

confirm_delete_client() {
  local source=$1 display=$2
  if [ "${WG_ROUTER_CONFIRM_DELETE:-}" = yes ]; then
    return 0
  fi
  [ -t 0 ] || fatal 'delete requires an interactive terminal or WG_ROUTER_CONFIRM_DELETE=yes'
  printf '\nDelete %s client %s? Type DELETE and press ENTER to confirm: ' "$source" "$display"
  local answer
  read -r answer
  [ "$answer" = DELETE ] || fatal 'delete cancelled'
}

delete_selector_client() {
  refuse_legacy_change
  local name=$1 line route ip tmp
  line=$(client_line "$name") || fatal "unknown selector client: $name"
  route=$(printf '%s\n' "$line" | awk -F '\t' '{print $2}')
  ip=$(printf '%s\n' "$line" | awk -F '\t' '{print $3}')
  backup
  tmp=$(mktemp)
  awk -F '\t' -v OFS='\t' -v n="$name" '$1 != n {print}' "$STATE_CLIENTS" > "$tmp"
  install -m 0600 -o root -g root "$tmp" "$STATE_CLIENTS"
  rm -f "$tmp"
  local display
  display=$(selector_display_name "$name" "$route")
  rm -f "$BASE/keys/clients/$name.key" "$BASE/keys/clients/$name.pub"
  rm -f "$BASE/client-configs/$display" "/root/wg-client-exports/$display"
  render_clients
  if soft_reload_selector; then
    selector_runtime_cmd remove "$ip" "$route"
  fi
  backup
  log "deleted selector client $name route=$route"
}

delete_file_client() {
  refuse_legacy_change
  local source=$1 path=$2 name client_dir server_conf iface list_file
  name=$(basename "$(dirname "$path")")
  client_dir=$(dirname "$path")
  case "$source" in
    legacy)
      server_conf="$WG_CONFS/wg0.conf"
      iface=wg0
      list_file="$WG_ROOT/clients/clients-list.txt"
      ;;
    bth)
      server_conf="$WG_CONFS/wg-home.conf"
      iface=wg-home
      list_file="$WG_ROOT/clients_bth/clients-list.txt"
      ;;
    *) fatal "delete is not supported for source $source" ;;
  esac
  backup
  remove_peer_block_by_client "$server_conf" "$name"
  rm -rf "$client_dir"
  update_clients_list "$list_file" "$name"
  rm -f "/root/wg-client-exports/$(basename "$path")" "/root/wg-client-exports/$name-$source.conf"
  sync_wg_interface "$iface"
  backup
  log "deleted $source client $name"
}

delete_selected_client() {
  refuse_legacy_change
  local source=$1 display=$2 path=$3 name
  confirm_delete_client "$source" "$display"
  case "$source" in
    selector)
      name=$(selector_name_from_display "$display")
      delete_selector_client "$name"
      ;;
    legacy|bth)
      delete_file_client "$source" "$path"
      ;;
    *) fatal "delete is not supported for source $source" ;;
  esac
}

regenerate_file_client() {
  refuse_legacy_change
  local source=$1 path=$2 name client_dir server_conf iface list_file server_pub_file
  local address dns endpoint allowed_ips private public psk relay_public tmp_conf
  name=$(basename "$(dirname "$path")")
  client_dir=$(dirname "$path")
  case "$source" in
    legacy)
      server_conf="$WG_CONFS/wg0.conf"
      iface=wg0
      list_file="$WG_ROOT/clients/clients-list.txt"
      server_pub_file="$WG_ROOT/relay_public.key"
      ;;
    bth)
      server_conf="$WG_CONFS/wg-home.conf"
      iface=wg-home
      list_file="$WG_ROOT/clients_bth/clients-list.txt"
      server_pub_file="$WG_ROOT/server_pub"
      ;;
    *) fatal "regenerate is not supported for source $source" ;;
  esac
  [ -f "$path" ] || fatal "client config not found: $path"
  [ -f "$server_pub_file" ] || fatal "server public key file not found: $server_pub_file"
  address=$(read_conf_value "$path" Address)
  dns=$(read_conf_value "$path" DNS)
  endpoint=$(read_conf_value "$path" Endpoint)
  allowed_ips=$(read_conf_value "$path" AllowedIPs)
  [ -n "$address" ] || fatal "cannot read Address from $path"
  [ -n "$endpoint" ] || fatal "cannot read Endpoint from $path"
  [ -n "$allowed_ips" ] || fatal "cannot read AllowedIPs from $path"
  [ -z "$dns" ] && dns="1.1.1.1, 8.8.8.8"
  private=$(wg genkey)
  public=$(printf '%s\n' "$private" | wg pubkey)
  psk=$(wg genpsk)
  relay_public=$(cat "$server_pub_file")
  backup
  umask 077
  printf '%s\n' "$private" > "$client_dir/private.key"
  printf '%s\n' "$public" > "$client_dir/public.key"
  printf '%s\n' "$psk" > "$client_dir/psk.key"
  tmp_conf=$(mktemp)
cat > "$tmp_conf" <<EOF
[Interface]
#Client: $name
PrivateKey = $private
Address = $address
DNS = $dns

[Peer]
# Relay Server
PublicKey = $relay_public
PresharedKey = $psk
Endpoint = $endpoint
AllowedIPs = $allowed_ips
PersistentKeepalive = 25
EOF
  install -m 0600 -o root -g root "$tmp_conf" "$path"
  rm -f "$tmp_conf"
  remove_peer_block_by_client "$server_conf" "$name"
  cat <<EOF >> "$server_conf"

[Peer]
#Client: $name
PublicKey = $public
PresharedKey = $psk
AllowedIPs = $address
EOF
  update_clients_list "$list_file" "$name" "$public"
  if [ "$source" = bth ]; then
    install -d -m 0700 -o root -g root /root/wg-client-exports
    install -m 0600 -o root -g root "$path" "/root/wg-client-exports/$name-bth.conf"
  fi
  sync_wg_interface "$iface"
  backup
  log "regenerated $source client $name"
  print_client_config_file "$path"
}

regenerate_selected_client() {
  refuse_legacy_change
  local source=$1 display=$2 path=$3 name line route export_path
  case "$source" in
    selector)
      name=$(selector_name_from_display "$display")
      line=$(client_line "$name") || fatal "unknown selector client: $name"
      route=$(printf '%s\n' "$line" | awk -F '\t' '{print $2}')
      rotate_client "$name"
      export_path="/root/wg-client-exports/$(selector_display_name "$name" "$route")"
      print_client_config_file "$export_path"
      ;;
    legacy|bth)
      regenerate_file_client "$source" "$path"
      ;;
    *) fatal "regenerate is not supported for source $source" ;;
  esac
}

render_upstream() {
  refuse_legacy_change
  [ -s "$UPSTREAM_KEY" ] || fatal 'upstream key is missing; run gen-upstream cenuta first'
  local priv
  priv=$(cat "$UPSTREAM_KEY")
  umask 077
  cat > "$MANAGED_CENUTA_CONF" <<EOF
[Interface]
Address = 10.40.40.2/32
PrivateKey = $priv
Table = off
PostUp = ip route replace default dev %i table 200
PostDown = ip route del default dev %i table 200 || true

[Peer]
PublicKey = $CENUTA_PUBLIC_KEY
Endpoint = $CENUTA_ENDPOINT
AllowedIPs = 0.0.0.0/0
PersistentKeepalive = 25
EOF
  install -m 0600 -o root -g root "$MANAGED_CENUTA_CONF" "$ACTIVE_CENUTA_CONF"
}

render_clients() {
  refuse_legacy_change
  ensure_server_key
  local priv
  priv=$(cat "$SERVER_KEY")
  umask 077
  {
    cat <<EOF
[Interface]
Address = $CLIENT_SERVER_IP/24
ListenPort = $CLIENT_PORT
PrivateKey = $priv
SaveConfig = false
Table = off
EOF
    if [ -s "$STATE_CLIENTS" ]; then
      while IFS=$'\t' read -r client_name client_route client_ip client_pub client_created; do
        [ -n "${client_name:-}" ] || continue
        local table outif pref
        table=$(route_table_for "$client_route")
        outif=$(out_iface_for "$client_route")
        pref=$(priority_for_ip "$client_ip")
        cat <<EOF
PostUp = ip rule add from $client_ip/32 table $table priority $pref || true
PostUp = iptables -A FORWARD -i %i -s $client_ip/32 -o $outif -j ACCEPT
PostUp = iptables -A FORWARD -i $outif -d $client_ip/32 -o %i -j ACCEPT
PostUp = iptables -t nat -A POSTROUTING -s $client_ip/32 -o $outif -j MASQUERADE
PostDown = ip rule del from $client_ip/32 table $table priority $pref || true
PostDown = iptables -D FORWARD -i %i -s $client_ip/32 -o $outif -j ACCEPT || true
PostDown = iptables -D FORWARD -i $outif -d $client_ip/32 -o %i -j ACCEPT || true
PostDown = iptables -t nat -D POSTROUTING -s $client_ip/32 -o $outif -j MASQUERADE || true
EOF
      done < "$STATE_CLIENTS"
    fi
    if [ -s "$STATE_CLIENTS" ]; then
      while IFS=$'\t' read -r client_name client_route client_ip client_pub client_created; do
        [ -n "${client_name:-}" ] || continue
        local client_ipv6
        client_ipv6=$(client_ipv6_for_ip "$client_ip")
        cat <<EOF

[Peer]
# $client_name route=$client_route created=$client_created
PublicKey = $client_pub
AllowedIPs = $client_ip/32, $client_ipv6/128
EOF
      done < "$STATE_CLIENTS"
    fi
  } > "$MANAGED_CLIENTS_CONF"
  install -m 0600 -o root -g root "$MANAGED_CLIENTS_CONF" "$ACTIVE_CLIENTS_CONF"
}

render() {
  refuse_legacy_change
  need_root
  init_dirs >/dev/null
  [ -s "$UPSTREAM_KEY" ] && render_upstream || log 'upstream key missing; skipped wg-up-cenuta render'
  render_clients
  log 'render complete'
}

apply_sysctl() {
  refuse_legacy_change
  need_root
  cat > /etc/sysctl.d/99-wg-router.conf <<EOF
net.ipv4.ip_forward = 1
net.ipv6.conf.all.forwarding = 0
net.ipv6.conf.default.forwarding = 0
EOF
  sysctl --system >/dev/null
  log 'sysctl applied'
}

apply_firewall() {
  refuse_legacy_change
  need_root
  [ -f "$COMPOSE" ] || fatal "compose file not found: $COMPOSE"
  if grep -q '51850:51850/udp' "$COMPOSE"; then
    log 'docker compose already publishes 51850/udp'
    return 0
  fi
  cp -a "$COMPOSE" "$COMPOSE.pre-wg-router-$(date -u +%Y%m%dT%H%M%SZ)"
  sed -i '/"51830:51830\/udp"/a\      - "51850:51850/udp"' "$COMPOSE"
  grep -q '51850:51850/udp' "$COMPOSE" || fatal 'failed to add 51850/udp to compose'
  log 'added 51850/udp to docker compose; run up to recreate container'
}

apply_ru_bth() {
  refuse_legacy_change
  need_root
  if [ ! -x "$RU_BTH_SCRIPT" ]; then
    log "RU-via-BTH script not installed; skipped: $RU_BTH_SCRIPT"
    return 0
  fi
  "$RU_BTH_SCRIPT" apply
}

clear_ru_bth() {
  refuse_legacy_change
  need_root
  [ -x "$RU_BTH_SCRIPT" ] || fatal "RU-via-BTH script not installed: $RU_BTH_SCRIPT"
  "$RU_BTH_SCRIPT" clear
}

test_ru_bth() {
  [ -x "$RU_BTH_SCRIPT" ] || fatal "RU-via-BTH script not installed: $RU_BTH_SCRIPT"
  "$RU_BTH_SCRIPT" test "$@"
}

up() {
  refuse_legacy_change
  need_root
  render
  apply_sysctl
  apply_firewall
  docker compose -f "$COMPOSE" up -d --force-recreate
  sleep 4
  log 'container recreated'
  apply_ru_bth
  status
}

inventory() {
  date -u
  hostnamectl --static
  docker ps --format 'table {{.Names}}\t{{.Status}}\t{{.Ports}}'
  ss -u -l -n -p | grep -E ':(51820|51830|51850)\b' || true
  docker exec "$CONTAINER" wg show || true
  docker exec "$CONTAINER" ip rule || true
  docker exec "$CONTAINER" ip route || true
  docker exec "$CONTAINER" ip route show table 100 || true
  docker exec "$CONTAINER" ip route show table 200 || true
  docker exec "$CONTAINER" ip route show table 300 || true
}

status() { inventory; }

check_upstream() {
  local target=${1:-}
  case "$target" in
    fornex) docker exec "$CONTAINER" wg show wg1 ;;
    cenuta) docker exec "$CONTAINER" wg show wg-up-cenuta ;;
    *) fatal 'usage: check-upstream fornex|cenuta' ;;
  esac
}

test_route_name() {
  local target=${1:-}
  case "$target" in
    fornex)
      docker exec "$CONTAINER" sh -c 'wg show wg1; ip route show table 100; curl -4 --max-time 15 --interface wg1 -fsS https://api.ipify.org || true; echo'
      ;;
    cenuta)
      docker exec "$CONTAINER" sh -c 'wg show wg-up-cenuta; ip route show table 200; curl -4 --max-time 15 --interface wg-up-cenuta -fsS https://api.ipify.org || true; echo; curl -6 --max-time 8 --interface wg-up-cenuta -fsS https://api64.ipify.org || true; echo'
      ;;
    *) fatal 'usage: test fornex|cenuta' ;;
  esac
}

test_client() {
  local name=${1:-} line route ip table outif
  line=$(client_line "$name") || fatal "unknown client: $name"
  route=$(printf '%s\n' "$line" | awk -F '\t' '{print $2}')
  ip=$(printf '%s\n' "$line" | awk -F '\t' '{print $3}')
  table=$(route_table_for "$route")
  outif=$(out_iface_for "$route")
  log "client=$name route=$route ip=$ip table=$table out=$outif"
  docker exec "$CONTAINER" sh -c "ip rule | grep -F '$ip' || true; ip route get 1.1.1.1 from '$ip' iif wg-clients || true; iptables -t nat -S | grep -F '$ip' || true; iptables -S | grep -F '$ip' || true"
}

export_client() {
  local name=${1:-} line route path export_dir
  line=$(client_line "$name") || fatal "unknown client: $name"
  route=$(printf '%s\n' "$line" | awk -F '\t' '{print $2}')
  path="$BASE/client-configs/$(selector_display_name "$name" "$route")"
  [ -f "$path" ] || render_client_config "$name"
  export_dir=/root/wg-client-exports
  install -d -m 0700 -o root -g root "$export_dir"
  install -m 0600 -o root -g root "$path" "$export_dir/$(basename "$path")"
  log "client export copied to $export_dir/$(basename "$path")"
}

refresh_clients() {
  refuse_legacy_change
  need_root
  init_dirs >/dev/null
  ensure_server_key
  [ -s "$STATE_CLIENTS" ] || fatal "no selector clients found in $STATE_CLIENTS"
  while IFS=$'\t' read -r client_name client_route client_ip client_pub client_created; do
    [ -n "${client_name:-}" ] || continue
    render_client_config "$client_name"
  done < "$STATE_CLIENTS"
  render_clients
  soft_reload_selector || true
  while IFS=$'\t' read -r client_name client_route client_ip client_pub client_created; do
    [ -n "${client_name:-}" ] || continue
    test_client "$client_name"
    export_client "$client_name"
  done < "$STATE_CLIENTS"
  backup
  log 'refreshed all selector client configs and exports'
}

rotate_client() {
  refuse_legacy_change
  need_root
  local name=${1:-} line route ip new_pub rotated tmp
  valid_name "$name" || fatal 'client name must contain only latin letters, digits, underscore, dash or dot'
  line=$(client_line "$name") || fatal "unknown selector client: $name"
  route=$(printf '%s\n' "$line" | awk -F '\t' '{print $2}')
  ip=$(printf '%s\n' "$line" | awk -F '\t' '{print $3}')
  rm -f "$BASE/keys/clients/$name.key" "$BASE/keys/clients/$name.pub"
  ensure_client_key "$name"
  new_pub=$(cat "$BASE/keys/clients/$name.pub")
  rotated=$(date -u +%Y-%m-%dT%H:%M:%SZ)
  tmp=$(mktemp)
  awk -F '\t' -v OFS='\t' -v n="$name" -v r="$route" -v ip="$ip" -v pub="$new_pub" -v ts="$rotated" \
    '$1==n {$2=r; $3=ip; $4=pub; $5=ts} {print}' "$STATE_CLIENTS" > "$tmp"
  install -m 0600 -o root -g root "$tmp" "$STATE_CLIENTS"
  rm -f "$tmp"
  log "rotated selector client $name route=$route ip=$ip public=$new_pub"
  refresh_clients
}

show_client() {
  need_root
  local query=${1:-} requested_action=${2:-} action selected choice i entry source display path entry_name

  local entries=()
  mapfile -t entries < <(list_client_entries | sort -t $'\t' -k1,1 -k2,2)
  [ "${#entries[@]}" -gt 0 ] || fatal 'no client configs found'

  if [ -n "$query" ]; then
    for entry in "${entries[@]}"; do
      IFS=$'\t' read -r source display path <<< "$entry"
      entry_name=$(client_name_from_entry "$source" "$display" "$path")
      case "$display" in
        "$query"|"$query.conf")
          selected="$path"
          break
          ;;
      esac
      case "$source/$display" in
        "$query"|"$query.conf")
          selected="$path"
          break
          ;;
      esac
      case "${display%.conf}" in
        "$query")
          selected="$path"
          break
          ;;
      esac
      case "$entry_name" in
        "$query")
          selected="$path"
          break
          ;;
      esac
    done
    [ -n "${selected:-}" ] || fatal "client config not found: $query"
  else
    [ -t 0 ] || fatal 'interactive terminal required; run from SSH terminal or pass config filename'
    printf 'Available WireGuard client configs:\n\n'
    for i in "${!entries[@]}"; do
      IFS=$'\t' read -r source display path <<< "${entries[$i]}"
      printf '  %2d) %-8s %s\n' "$((i + 1))" "$source" "$display"
    done
    printf '\nSelect config number and press ENTER: '
    read -r choice
    [[ "$choice" =~ ^[0-9]+$ ]] || fatal "invalid selection: $choice"
    [ "$choice" -ge 1 ] && [ "$choice" -le "${#entries[@]}" ] || fatal "selection out of range: $choice"
    IFS=$'\t' read -r source display selected <<< "${entries[$((choice - 1))]}"
  fi

  if [ -z "${source:-}" ] || [ -z "${display:-}" ]; then
    for entry in "${entries[@]}"; do
      IFS=$'\t' read -r source display path <<< "$entry"
      if [ "$path" = "$selected" ]; then
        break
      fi
    done
  fi

  if [ -n "$requested_action" ]; then
    action="$requested_action"
  elif [ -n "$query" ]; then
    action=view
  else
    printf '\nAction for %s (%s):\n' "$display" "$source"
    printf '  1) view\n'
    printf '  2) delete\n'
    printf '  3) regenerate\n'
    printf '\nSelect action and press ENTER: '
    read -r choice
    case "$choice" in
      1|view) action=view ;;
      2|delete) action=delete ;;
      3|regenerate) action=regenerate ;;
      *) fatal "invalid action: $choice" ;;
    esac
  fi

  case "$action" in
    view) print_client_config_file "$selected" ;;
    delete) delete_selected_client "$source" "$display" "$selected" ;;
    regenerate) regenerate_selected_client "$source" "$display" "$selected" ;;
    *) fatal 'action must be view, delete or regenerate' ;;
  esac
}

delete_client() {
  refuse_legacy_change
  local query=${1:-}
  show_client "$query" delete
}

regenerate_client() {
  refuse_legacy_change
  local query=${1:-}
  show_client "$query" regenerate
}

add_selector_client() {
  refuse_legacy_change
  need_root
  local name=${1:-} route=${2:-} line ip export_path
  valid_name "$name" || fatal 'client name must contain only latin letters, digits, underscore, dash or dot'
  [[ "$route" =~ ^(fornex|cenuta)$ ]] || fatal 'route must be fornex or cenuta'
  gen_client "$name" "$route"
  render_clients
  soft_reload_selector || true
  test_client "$name"
  export_client "$name"
  backup
  line=$(client_line "$name")
  ip=$(printf '%s\n' "$line" | awk -F '\t' '{print $3}')
  export_path="/root/wg-client-exports/$(selector_display_name "$name" "$route")"
  log "created client=$name route=$route ip=$ip export=$export_path"
}

add_bth_client() {
  refuse_legacy_change
  need_root
  local name=${1:-} src dst
  valid_name "$name" || fatal 'client name must contain only latin letters, digits, underscore, dash or dot'
  [ -x "$WG_ROOT/add-bth.sh" ] || fatal "missing executable $WG_ROOT/add-bth.sh"
  [ ! -d "$WG_ROOT/clients_bth/$name" ] || fatal "BTH client already exists: $name"
  src="$WG_ROOT/clients_bth/$name/$name.conf"
  dst="/root/wg-client-exports/$name-bth.conf"
  (cd "$WG_ROOT" && printf '%s\n' "$name" | TERM="${TERM:-xterm}" ./add-bth.sh)
  [ -f "$src" ] || fatal "BTH client config was not created: $src"
  install -d -m 0700 -o root -g root /root/wg-client-exports
  install -m 0600 -o root -g root "$src" "$dst"
  backup
  log "created client=$name route=bth export=$dst"
}

add_client() {
  refuse_legacy_change
  local name=${1:-} route=${2:-}
  case "$route" in
    fornex|cenuta) add_selector_client "$name" "$route" ;;
    bth) add_bth_client "$name" ;;
    *) fatal 'usage: add-client <client-name> fornex|cenuta|bth' ;;
  esac
}

sessions() {
  need_root
  local iface_filter="" active_only=0 json=0 arg dump
  while [ "$#" -gt 0 ]; do
    arg=$1
    case "$arg" in
      --active)
        active_only=1
        shift
        ;;
      --interface)
        [ "$#" -ge 2 ] || fatal 'usage: sessions [--active] [--interface wg0|wg-home|wg-clients|wg1|wg-up-cenuta] [--json]'
        iface_filter=$2
        shift 2
        ;;
      --json)
        json=1
        shift
        ;;
      *)
        fatal 'usage: sessions [--active] [--interface wg0|wg-home|wg-clients|wg1|wg-up-cenuta] [--json]'
        ;;
    esac
  done

  dump=$(docker exec "$CONTAINER" wg show all dump)
  printf '%s\n' "$dump" | awk -F '\t' \
    -v state_file="$STATE_CLIENTS" \
    -v legacy_file="$WG_ROOT/clients/clients-list.txt" \
    -v bth_file="$WG_ROOT/clients_bth/clients-list.txt" \
    -v iface_filter="$iface_filter" \
    -v active_only="$active_only" \
    -v json="$json" \
    -v now="$(date +%s)" '
    function trim(s) {
      gsub(/^[[:space:]]+|[[:space:]]+$/, "", s)
      return s
    }
    function short_key(s) {
      return substr(s, 1, 12) "..."
    }
    function human_age(sec, d, h, m) {
      if (sec < 0) sec = 0
      d = int(sec / 86400)
      h = int((sec % 86400) / 3600)
      m = int((sec % 3600) / 60)
      if (d > 0) return d "d " h "h"
      if (h > 0) return h "h " m "m"
      return m "m"
    }
    function fmt_bytes(bytes, unit) {
      bytes += 0
      if (bytes >= 1073741824) {
        unit = bytes / 1073741824
        return sprintf("%.2f GiB", unit)
      }
      if (bytes >= 1048576) {
        unit = bytes / 1048576
        return sprintf("%.2f MiB", unit)
      }
      if (bytes >= 1024) {
        unit = bytes / 1024
        return sprintf("%.2f KiB", unit)
      }
      return bytes " B"
    }
    function json_escape(s) {
      gsub(/\\/, "\\\\", s)
      gsub(/"/, "\\\"", s)
      gsub(/\t/, "\\t", s)
      gsub(/\r/, "\\r", s)
      gsub(/\n/, "\\n", s)
      return s
    }
    function add_meta(pub, name, source, iface, route, config, expected_ip) {
      if (pub != "") {
        meta_name[pub] = name
        meta_source[pub] = source
        meta_iface[pub] = iface
        meta_route[pub] = route
        meta_config[pub] = config
        meta_expected_ip[pub] = expected_ip
      }
    }
    function read_client_list(file, source, iface, route, suffix, line, idx, name, pub, actual_route) {
      while ((getline line < file) > 0) {
        idx = index(line, ":")
        if (idx <= 0) continue
        name = trim(substr(line, 1, idx - 1))
        pub = trim(substr(line, idx + 1))
        if (name == "" || pub == "") continue
        actual_route = route
        if (source == "legacy") {
          if (name ~ /-cenuta-domru$/) actual_route = "legacy-cenuta-domru"
          else if (name ~ /-fornex$/) actual_route = "legacy-fornex"
        }
        add_meta(pub, name, source, iface, actual_route, name suffix, "")
      }
      close(file)
    }
    BEGIN {
      while ((getline line < state_file) > 0) {
        split(line, f, "\t")
        if (f[1] == "" || f[4] == "") continue
        config = f[1] "-" f[2] ".conf"
        if ((f[2] == "cenuta" && f[1] ~ /-cenuta-domru$/) || (f[2] == "fornex" && f[1] ~ /-fornex-domru$/)) {
          config = f[1] ".conf"
        }
        add_meta(f[4], f[1], "selector", "wg-clients", f[2], config, f[3] "/32")
      }
      close(state_file)
      read_client_list(legacy_file, "legacy", "wg0", "legacy-fornex", ".conf")
      read_client_list(bth_file, "bth", "wg-home", "bth/home", ".conf")
      if (json == 1) {
        print "["
      } else {
        printf "%-34s %-14s %-12s %-22s %-40s %-20s %-10s %-11s %-11s\n", "NAME", "SOURCE", "INTERFACE", "ROUTE", "CONFIG", "LAST_HANDSHAKE", "AGE", "RX", "TX"
      }
    }
    NF >= 9 {
      iface = $1
      pub = $2
      endpoint = $4
      allowed = $5
      handshake = $6 + 0
      rx = $7 + 0
      tx = $8 + 0
      if (iface_filter != "" && iface != iface_filter) next
      if (active_only == 1 && handshake == 0) next

      if (iface == "wg-up-cenuta") {
        name = "Cenuta upstream"
        source = "upstream"
        route = "cenuta"
        config = "wg-up-cenuta.conf"
        expected_ip = ""
      } else if (iface == "wg1") {
        name = "Fornex upstream"
        source = "upstream"
        route = "fornex"
        config = "wg1.conf"
        expected_ip = ""
      } else if (iface == "wg-home" && allowed ~ /192\.168\.88\.0\/24/) {
        name = "MikroTik Router"
        source = "infrastructure"
        route = "home/domru"
        config = "wg-home.conf"
        expected_ip = ""
      } else {
        name = meta_name[pub]
        source = meta_source[pub]
        route = meta_route[pub]
        config = meta_config[pub]
        expected_ip = meta_expected_ip[pub]
      }
      if (name == "") {
        name = short_key(pub)
        source = "unknown"
        route = "-"
        config = "-"
        expected_ip = ""
      }

      last = "never"
      age = "-"
      if (handshake > 0) {
        last = strftime("%Y-%m-%d %H:%M:%S", handshake) " UTC"
        age = human_age(now - handshake)
      }

      if (json == 1) {
        if (count > 0) print ","
        printf "  {\"name\":\"%s\",\"source\":\"%s\",\"interface\":\"%s\",\"route\":\"%s\",\"config\":\"%s\",\"allowed_ips\":\"%s\",\"expected_ip\":\"%s\",\"endpoint\":\"%s\",\"latest_handshake\":%d,\"latest_handshake_utc\":\"%s\",\"age\":\"%s\",\"rx_bytes\":%d,\"tx_bytes\":%d,\"public_key\":\"%s\"}", \
          json_escape(name), json_escape(source), json_escape(iface), json_escape(route), json_escape(config), json_escape(allowed), json_escape(expected_ip), json_escape(endpoint), handshake, json_escape(last), json_escape(age), rx, tx, json_escape(pub)
      } else {
        printf "%-34s %-14s %-12s %-22s %-40s %-20s %-10s %-11s %-11s\n", name, source, iface, route, config, last, age, fmt_bytes(rx), fmt_bytes(tx)
      }
      count++
    }
    END {
      if (json == 1) {
        if (count > 0) print ""
        print "]"
      }
    }'
}

backup() {
  refuse_legacy_change
  need_root
  local ts dest
  ts=$(date -u +%Y%m%dT%H%M%SZ)
  dest="$BASE/backups/$ts"
  install -d -m 0700 -o root -g root "$dest"
  cp -a "$BASE/env" "$BASE/state" "$BASE/configs" "$BASE/client-configs" "$dest/"
  cp -a "$COMPOSE" "$dest/" 2>/dev/null || true
  cp -a "$WG_ROOT/add-client.sh" "$WG_ROOT/add-bth.sh" "$WG_ROOT/check-status.sh" "$dest/" 2>/dev/null || true
  cp -a "$WG_ROOT/clients" "$dest/" 2>/dev/null || true
  cp -a "$ACTIVE_CENUTA_CONF" "$dest/" 2>/dev/null || true
  cp -a "$ACTIVE_CLIENTS_CONF" "$dest/" 2>/dev/null || true
  cp -a "$WG_CONFS/wg0.conf" "$dest/" 2>/dev/null || true
  cp -a "$WG_CONFS/wg1.conf" "$dest/" 2>/dev/null || true
  cp -a "$WG_CONFS/wg-home.conf" "$dest/" 2>/dev/null || true
  cp -a "$WG_ROOT/clients_bth" "$dest/" 2>/dev/null || true
  inventory > "$dest/runtime.txt" 2>&1 || true
  chmod -R go-rwx "$dest"
  log "backup created: $dest"
}

usage() {
  cat <<EOF
Usage: $0 <command> [args]
Commands (legacy mutators are RETIRED; viewing remains available):
  inventory|status
  init-dirs
  check-upstream fornex|cenuta
  add-client <client-name> fornex|cenuta|bth
  show-client [config-name] [view|delete|regenerate]
  delete-client [config-name]
  regenerate-client [config-name]
  sessions [--active] [--interface wg0|wg-home|wg-clients|wg1|wg-up-cenuta] [--json]
  refresh-clients
  rotate-client <selector-client-name>
  gen-upstream cenuta
  gen-client <client-name> fornex|cenuta
  render
  apply-sysctl
  apply-firewall
  apply-ru-bth
  clear-ru-bth
  test-ru-bth [client-ip] [ru-ip] [non-ru-ip]
  up
  test fornex|cenuta
  test-client <client-name>
  export-client <client-name>
  backup
EOF
}

cmd=${1:-}
shift || true
case "$cmd" in
  inventory) inventory ;;
  status) status ;;
  init-dirs) init_dirs ;;
  check-upstream) check_upstream "$@" ;;
  add-client) add_client "$@" ;;
  show-client) show_client "$@" ;;
  delete-client) delete_client "$@" ;;
  regenerate-client) regenerate_client "$@" ;;
  sessions) sessions "$@" ;;
  refresh-clients) refresh_clients ;;
  rotate-client) rotate_client "$@" ;;
  gen-upstream) gen_upstream "$@" ;;
  gen-client) gen_client "$@" ;;
  render) render ;;
  apply-sysctl) apply_sysctl ;;
  apply-firewall) apply_firewall ;;
  apply-ru-bth) apply_ru_bth ;;
  clear-ru-bth) clear_ru_bth ;;
  test-ru-bth) test_ru_bth "$@" ;;
  up) up ;;
  test) test_route_name "$@" ;;
  test-client) test_client "$@" ;;
  export-client) export_client "$@" ;;
  backup) backup ;;
  -h|--help|help|'') usage ;;
  *) usage; fatal "unknown command: $cmd" ;;
esac
