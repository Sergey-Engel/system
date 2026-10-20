"""Isolated transport policy; no production route or old transport mutator."""
import ipaddress
import re

RELEASE='1.1.1'
OWNER='sstp-tw-v1'
PORT=443
ENDPOINT='91.222.238.208'
LOCAL='10.60.65.1'
PEER='10.60.65.2'
NAMESPACE='sstp-timeweb'
INTERFACE='sstp-timeweb'
PROFILE=OWNER+'-profile'
CA=OWNER+'-ca'
USER=OWNER+'-nakhimova'
PREFIX='/opt/sstp-timeweb/releases/b8a3c54'

def guard_anchor(rows,chain):
    """Dynamic FastTrack placeholders are not persistent ordering anchors."""
    for row in rows:
        if (row.get('chain')==chain and not row.get('dynamic')
                and not str(row.get('comment','')).startswith('s2s-sstp-reverse-v1:device-')):
            return row['.id']
    return None


def quote(value):
    if not isinstance(value,str) or any(c in value for c in '\r\n\0'):
        raise ValueError('invalid_router_value')
    return '"'+value.replace('\\','\\\\').replace('"','\\"').replace('$','\\$')+'"'


def client_command(password):
    if not re.fullmatch(r'[A-Za-z0-9_-]{32,128}',password):
        raise ValueError('invalid_ppp_credential')
    return ('/interface sstp-client add disabled=yes name='+INTERFACE+' connect-to='+ENDPOINT+
        ' port='+str(PORT)+' user='+USER+' password='+quote(password)+' profile='+PROFILE+
        ' authentication=mschap2 verify-server-certificate=yes verify-server-address-from-certificate=yes'+
        ' tls-version=only-1.2 ciphers=aes256-gcm-sha384 pfs=required max-mtu=1400 max-mru=1400'+
        ' keepalive-timeout=10 add-default-route=no comment='+quote(OWNER+':interface'))


def profile_command():
    return ('/ppp profile add name='+PROFILE+' use-ipv6=no use-compression=no use-encryption=no'+
            ' change-tcp-mss=no only-one=yes comment='+quote(OWNER+':profile'))


def guards():
    return [
        ('/ip firewall filter','chain=input action=accept in-interface='+INTERFACE+' src-address='+LOCAL+
         ' dst-address='+PEER+' protocol=icmp',OWNER+':icmp'),
        ('/ip firewall filter','chain=input action=accept in-interface='+INTERFACE+' src-address='+LOCAL+
         ' dst-address='+PEER+' protocol=tcp dst-port=22',OWNER+':ssh-test'),
        ('/ip firewall filter','chain=input action=drop in-interface='+INTERFACE,OWNER+':input-drop'),
        ('/ip firewall filter','chain=forward action=drop in-interface='+INTERFACE,OWNER+':forward-in'),
        ('/ip firewall filter','chain=forward action=drop out-interface='+INTERFACE,OWNER+':forward-out'),
        ('/ipv6 firewall filter','chain=input action=drop in-interface='+INTERFACE,OWNER+':v6-input'),
        ('/ipv6 firewall filter','chain=forward action=drop in-interface='+INTERFACE,OWNER+':v6-in'),
        ('/ipv6 firewall filter','chain=forward action=drop out-interface='+INTERFACE,OWNER+':v6-out'),
    ]


def server_config():
    return '''[modules]
log_file
sstp
auth_mschap_v2
chap-secrets
connlimit

[core]
log-error=/var/lib/sstp-timeweb/core.log
thread-count=2

[common]
max-sessions=1
max-starting=2
single-session=deny

[client-ip-range]
127.0.0.1/32

[ppp]
verbose=0
min-mtu=1280
mtu=1400
mru=1400
ipv4=require
ipv6=deny
ccp=0
mppe=deny
lcp-echo-interval=10
lcp-echo-failure=3

[sstp]
verbose=0
bind=127.0.0.1
port=5444
accept=ssl
ssl-protocol=tls1.2
ssl-ciphers=ECDHE-RSA-AES256-GCM-SHA384
ssl-pemfile=/etc/sstp-timeweb/server.pem
ssl-keyfile=/etc/sstp-timeweb/server.key
cert-hash-proto=sha256
hello-interval=10
timeout=30
ppp-mode=async
ppp-max-mtu=1400
ifname=sstptw0

[chap-secrets]
gw-ip-address=10.60.65.1
chap-secrets=/etc/sstp-timeweb/chap-secrets
encrypted=0

[connlimit]
limit=10/min
burst=10
timeout=30

[log]
log-file=/var/lib/sstp-timeweb/accel.log
level=3
copy=0
color=0
'''


def namespace_guard():
    return '''table inet sstp_timeweb {
 chain input { type filter hook input priority 0; policy drop;
  iifname "lo" accept
  ct state established,related accept
  iifname "sstptw0" ip saddr 10.60.65.2 ip daddr 10.60.65.1 ip protocol icmp accept
  iifname "sstptw0" ip saddr 10.60.65.2 ip daddr 10.60.65.1 tcp dport 8080 accept
 }
 chain output { type filter hook output priority 0; policy drop;
  oifname "lo" accept
  ct state established,related accept
  oifname "sstptw0" ip saddr 10.60.65.1 ip daddr 10.60.65.2 ip protocol icmp accept
  oifname "sstptw0" ip saddr 10.60.65.1 ip daddr 10.60.65.2 tcp dport 22 accept
 }
 chain forward { type filter hook forward priority 0; policy drop; }
}
'''


def units(source_ip):
    if not ipaddress.IPv4Address(source_ip).is_global:
        raise ValueError('invalid_source_ip')
    common='''[Unit]
Requires=sstp-timeweb-netns.service
After=sstp-timeweb-netns.service
BindsTo=sstp-timeweb-netns.service

[Service]
NetworkNamespacePath=/run/netns/sstp-timeweb
NoNewPrivileges=yes
ProtectSystem=strict
ProtectHome=yes
PrivateTmp=yes
ProtectKernelTunables=yes
ProtectControlGroups=yes
InaccessiblePaths=-/opt/wg -/opt/wg-router -/opt/timeweb-reality -/etc/wireguard
UMask=0077
CPUQuota=25%
MemoryMax=128M
TasksMax=32
'''
    return {
        'sstp-timeweb-netns.service':'''[Unit]
Description=Isolated namespace for the alternate SSTP transport
Before=sstp-timeweb-server.service sstp-timeweb-proxy.service sstp-timeweb-probe.service

[Service]
Type=oneshot
RemainAfterExit=yes
ExecStart=/usr/bin/python3 -B /opt/sstp-timeweb/namespace.py up
ExecStop=/usr/bin/python3 -B /opt/sstp-timeweb/namespace.py down
UMask=0077

[Install]
WantedBy=multi-user.target
''',
        'sstp-timeweb-server.service':common+'''Type=simple
StateDirectory=sstp-timeweb
StateDirectoryMode=0700
RuntimeDirectory=sstp-timeweb-accel
CapabilityBoundingSet=CAP_NET_ADMIN CAP_NET_RAW
DevicePolicy=closed
DeviceAllow=/dev/ppp rw
Environment=LD_LIBRARY_PATH='''+PREFIX+'/runtime-libs:'+PREFIX+'''/lib64/accel-ppp
ExecStart='''+PREFIX+'''/sbin/accel-pppd -c /etc/sstp-timeweb/accel.conf -p /run/sstp-timeweb-accel/accel.pid
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target
''',
        'sstp-timeweb-proxy.socket':'''[Unit]
Description=Separate public TCP listener for Nakhimova SSTP
Requires=sstp-timeweb-netns.service
After=sstp-timeweb-netns.service

[Socket]
ListenStream='''+ENDPOINT+':'+str(PORT)+'''
FreeBind=yes
Accept=no
NoDelay=yes
Backlog=8
IPAddressDeny=any
IPAddressAllow='''+source_ip+'''/32
IPAddressAllow=94.241.171.65/32
IPAddressAllow='''+ENDPOINT+'''/32

[Install]
WantedBy=sockets.target
''',
        'sstp-timeweb-proxy.service':common.replace('[Service]','Requires=sstp-timeweb-server.service\nAfter=sstp-timeweb-server.service\n\n[Service]')+'''DynamicUser=yes
CapabilityBoundingSet=
ExecStart=/usr/lib/systemd/systemd-socket-proxyd --connections-max=4 127.0.0.1:5444
Restart=on-failure
RestartSec=5
''',
        'sstp-timeweb-probe.service':common+'''DynamicUser=yes
CapabilityBoundingSet=
ExecStart=/usr/bin/python3 -B /opt/sstp-timeweb/probe.py
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target
''',
    }
