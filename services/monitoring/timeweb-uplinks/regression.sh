set -Eeuo pipefail
pid=$(docker inspect -f '{{.State.Pid}}' wg-relay)
ns() { nsenter -t "$pid" -n "$@"; }
printf 'REGRESSION_START %s pid=%s\n' "$(date -u +%FT%TZ)" "$pid"
printf 'MATRIX_BEGIN\n'
for source in $(ns ip -j -4 rule show | jq -r '.[]|select(.priority>=219 and .priority<=238)|.src'); do
    ingress=wg-clients
    if [ "$source" = 10.10.10.0 ]; then source=10.10.10.7; ingress=wg0; fi
    for mark in 0 0x30; do
        for destination in 1.1.1.1 10.50.50.20 10.10.10.7; do
            ns ip -4 route get "$destination" from "$source" iif "$ingress" mark "$mark"
        done
    done
done
for source in 10.20.0.1 10.40.40.2; do
    for destination in 10.10.10.7 10.50.50.20 10.30.30.2 172.19.0.1 10.20.0.2; do
        ns ip -4 route get "$destination" from "$source"
    done
done
printf 'MATRIX_END\n'
printf 'DNS_UDP_FROM_HOST\n'
dig @172.19.0.2 example.org A +time=2 +tries=1 +noall +comments +answer
printf 'DNS_TCP_FROM_HOST\n'
dig @172.19.0.2 example.org A +tcp +time=2 +tries=1 +noall +comments +answer
curl -q --noproxy '*' --connect-timeout 2 --max-time 3 -sS -w ' health_http=%{http_code}\n' http://172.19.0.2:8080/health
printf 'PEER_TOTALS_BEGIN\n'
for interface in wg0 wg-clients wg-home wg1 wg-up-cenuta; do
    printf '%s ' "$interface"
    ns wg show "$interface" transfer | awk '{rx+=$2;tx+=$3;n++} END {printf "peers=%d rx=%.0f tx=%.0f\n",n,rx,tx}'
done
printf 'PEER_TOTALS_END\n'
printf 'REGRESSION_END %s\n' "$(date -u +%FT%TZ)"
