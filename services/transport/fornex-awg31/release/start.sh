#!/bin/bash
set -euo pipefail
awg-quick up /opt/fornex-awg31/awg0.conf
iptables -A FORWARD -i awg0 -o eth0 -s 10.83.1.0/24 -j ACCEPT
iptables -A FORWARD -i eth0 -o awg0 -m conntrack --ctstate ESTABLISHED,RELATED -j ACCEPT
iptables -t nat -A POSTROUTING -s 10.83.1.0/24 -o eth0 -j MASQUERADE
exec tail -f /dev/null
