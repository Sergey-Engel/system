"""Explicit split data plane; never selects a device or a fallback transport."""
import ipaddress
import json

RELEASE = '2.0.0'
OWNER = 'sstp-split-v1'
LINK = 'sstpsplit0'
RELAY_LINK = 'sstprelay0'
NETWORK = '10.60.66.0/30'
SERVER = '10.60.66.1'
RELAY = '10.60.66.2'
MODES = {
    'sstp_cenuta': dict(label='SSTP-Cenuta', list='SSTP_CENUTA_Devices',
        table='SSTP-CENUTA', source='10.60.65.10', probe='10.60.65.12',
        relay_source='10.50.50.245', uplink='wg-up-cenuta', legacy='CENUTA_Devices'),
    'sstp_fornex': dict(label='SSTP-Fornex', list='SSTP_FORNEX_Devices',
        table='SSTP-FORNEX', source='10.60.65.11', probe='10.60.65.13',
        relay_source='10.10.10.245', uplink='wg1', legacy='VPN_Devices'),
}
PRIVATE = ('0.0.0.0/8','10.0.0.0/8','100.64.0.0/10','127.0.0.0/8',
    '169.254.0.0/16','172.16.0.0/12','192.168.0.0/16','192.0.0.0/24',
    '192.0.2.0/24','198.18.0.0/15','198.51.100.0/24','203.0.113.0/24',
    '224.0.0.0/4','240.0.0.0/4', '94.241.171.65/32','91.222.238.208/32',
    '103.75.126.143/32','89.252.153.129/32')


def quote(value):
    if not isinstance(value,str) or any(c in value for c in '\r\n\0'):
        raise ValueError('invalid_split_value')
    return '"'+value.replace('\\','\\\\').replace('"','\\"').replace('$','\\$')+'"'


def properties(fields):
    return ' '.join(k if k in ('fib','blackhole') and v=='yes' else k+'='+quote(str(v))
                    for k,v in fields.items())


def router_objects(existing_mangle):
    """Clone reviewed native exceptions, including their original order."""
    result=[]
    def add(path,tag,**fields):
        fields['comment']=OWNER+':'+tag
        result.append(dict(path=path,fields=fields,tag=fields['comment']))
    for mode,item in MODES.items():
        suffix=mode.removeprefix('sstp_')
        add('/routing table',suffix+'-table',name=item['table'],fib='yes')
        add('/ip address',suffix+'-source',address=item['source']+'/32',network=item['source'],interface='sstp-timeweb')
        add('/ip route',suffix+'-default',**{'dst-address':'0.0.0.0/0','gateway':'sstp-timeweb',
            'routing-table':item['table'],'distance':'1'})
        add('/ip route',suffix+'-blackhole',**{'dst-address':'0.0.0.0/0','blackhole':'yes',
            'routing-table':item['table'],'distance':'254'})
        add('/routing rule',suffix+'-probe-route',**{'src-address':item['source']+'/32',
            'action':'lookup-only-in-table','table':item['table']})
        rules=[dict(r) for r in existing_mangle if r.get('src-address-list')==item['legacy']]
        if (len(rules)<3 or rules[0].get('dst-address-list')!='Local_Networks'
                or not any(r.get('dst-address-list')=='RU_Networks' and r.get('action')=='accept' for r in rules)
                or rules[-1].get('action')!='mark-routing'):
            raise ValueError('unreviewed_native_split_policy')
        for index,rule in enumerate(rules):
            if set(rule)-{'action','chain','comment','src-address-list','dst-address-list',
                         'dst-address','new-routing-mark','passthrough','protocol','src-port','dst-port'}:
                raise ValueError('unsupported_native_split_selector')
            rule.pop('comment',None)
            if rule.get('chain')!='prerouting':raise ValueError('unexpected_split_chain')
            rule['src-address-list']=item['list']
            rule['in-interface']='bridge'
            if 'new-routing-mark' in rule:rule['new-routing-mark']=item['table']
            add('/ip firewall mangle',suffix+'-mangle-'+str(index),**rule)
        add('/ip firewall nat',suffix+'-nat',**{'chain':'srcnat','action':'src-nat',
            'src-address-list':item['list'],'out-interface':'sstp-timeweb','to-addresses':item['source']})
        add('/ip firewall filter',suffix+'-out',**{'chain':'forward','action':'accept',
            'in-interface':'bridge','out-interface':'sstp-timeweb','src-address-list':item['list']})
        add('/ip firewall filter',suffix+'-in',**{'chain':'forward','action':'accept',
            'in-interface':'sstp-timeweb','out-interface':'bridge','dst-address-list':item['list'],
            'connection-state':'established,related'})
        add('/ip firewall filter',suffix+'-probe-reply',**{'chain':'input','action':'accept',
            'in-interface':'sstp-timeweb','dst-address':item['source'],'protocol':'icmp',
            'connection-state':'established,related'})
    add('/ip firewall mangle','mss-out',**{'chain':'forward','action':'change-mss',
        'out-interface':'sstp-timeweb','protocol':'tcp','tcp-flags':'syn','tcp-mss':'1361-65535','new-mss':'1360'})
    add('/ip firewall mangle','mss-in',**{'chain':'forward','action':'change-mss',
        'in-interface':'sstp-timeweb','protocol':'tcp','tcp-flags':'syn','tcp-mss':'1361-65535','new-mss':'1360'})
    return result


def router_probe(mode):
    source=MODES[mode]['source']
    return ':put [/ping 1.1.1.1 src-address='+source+' count=3 interval=500ms size=1200 do-not-fragment]'


def namespace_rules(base):
    sources=', '.join(i['source'] for i in MODES.values())
    probes=', '.join(i['probe'] for i in MODES.values())
    # Replace only the owned empty forward chain; preserve management input rules.
    old=' chain forward { type filter hook forward priority 0; policy drop; }'
    if base.count(old)!=1:raise ValueError('namespace_guard_revision_changed')
    forward=''' chain forward { type filter hook forward priority 0; policy drop;
  iifname "sstptw0" oifname "LINK" ip saddr { SOURCES } ip daddr { PRIVATE } drop
  iifname "sstptw0" oifname "LINK" ip saddr { SOURCES } accept
  iifname "LINK" oifname "sstptw0" ip daddr { SOURCES } ct state established,related accept
 }'''.replace('LINK',LINK).replace('SOURCES',sources).replace('PRIVATE',', '.join(PRIVATE))
    output='  oifname "lo" accept\n'
    if base.count(output)!=1:raise ValueError('namespace_output_revision_changed')
    result=base.replace(old,forward).replace(output,output+
        '  oifname "'+LINK+'" ip saddr { '+probes+' } ip daddr { '+', '.join(PRIVATE)+' } drop\n'+
        '  oifname "'+LINK+'" ip saddr { '+probes+' } accept\n')
    result+='table ip sstp_split_nat {\n chain postrouting { type nat hook postrouting priority srcnat; policy accept;\n'
    for item in MODES.values():
        result+='  oifname "'+LINK+'" ip saddr { '+item['source']+', '+item['probe']+' } snat to '+item['relay_source']+'\n'
    return result+' }\n}\n'


def relay_guard():
    text='table inet sstp_split_relay {\n chain input { type filter hook input priority -20; policy accept; iifname "'+RELAY_LINK+'" drop; }\n'
    text+=' chain forward { type filter hook forward priority -20; policy accept;\n'
    for item in MODES.values():
        text+='  iifname "'+RELAY_LINK+'" ip saddr '+item['relay_source']+' ip daddr { '+', '.join(PRIVATE)+' } drop\n'
        text+='  iifname "'+RELAY_LINK+'" oifname "'+item['uplink']+'" ip saddr '+item['relay_source']+' accept\n'
        text+='  iifname "'+item['uplink']+'" oifname "'+RELAY_LINK+'" ip daddr '+item['relay_source']+' ct state established,related accept\n'
    text+='  iifname "'+RELAY_LINK+'" drop\n  oifname "'+RELAY_LINK+'" drop\n }\n'
    text+=' chain postrouting { type nat hook postrouting priority 99; policy accept;\n'
    for item in MODES.values():
        text+='  oifname "'+item['uplink']+'" ip saddr '+item['relay_source']+' masquerade\n'
    return text+' }\n}\n'
