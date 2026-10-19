"""Independent persistent SSTP policy; never modifies the TimeWeb path."""
import importlib.util
from pathlib import Path

_spec = importlib.util.spec_from_file_location('sstp_direct_primitives', Path(__file__).with_name('sstp_trial.py'))
tls = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(tls)
OWNER = 's2s-sstp-direct-v1'
CLIENT, SERVER = 'sstp-direct-out', 'sstp-direct-in'
PROFILE, USER = OWNER + '-profile', OWNER + '-user'
CA, SERVER_CERT, CLIENT_CERT = OWNER + '-ca', OWNER + '-server', OWNER + '-client'
for _name in ('OWNER', 'CLIENT', 'SERVER', 'PROFILE', 'USER', 'CA', 'SERVER_CERT', 'CLIENT_CERT'):
    setattr(tls, _name, globals()[_name])
SITES, SERVER_FIELDS = tls.SITES, tls.SERVER_FIELDS
TABLE = 'sstp_direct'
REVERSE_OWNER, REVERSE_TABLE = 's2s-sstp-reverse-v1', 'sstp_fethiye'
PATHS = ('/ip firewall filter', '/ip firewall nat', '/ip firewall mangle',
         '/ipv6 firewall filter', '/routing rule', '/ip route', '/routing table',
         '/ip firewall address-list')
PRIVATE = ('0.0.0.0/8', '10.0.0.0/8', '100.64.0.0/10', '127.0.0.0/8',
           '169.254.0.0/16', '172.16.0.0/12', '192.168.0.0/16',
           '224.0.0.0/4', '240.0.0.0/4')
quote, public_ip = tls.quote, tls.public_ip
safe_mode_confirmed = tls.safe_mode_confirmed
certificate_snapshot, assert_free, restore_server = tls.certificate_snapshot, tls.assert_free, tls.restore_server


def bundle(endpoint, now, password):
    return tls.bundle(endpoint, now, password, valid_days=825)


def stage_commands(site, endpoint, password):
    commands = [c for c in tls.stage_commands(site, endpoint, password)
                if ':observe' not in c]
    head = 'place-before=([find where dynamic=no]->0)'
    iface = CLIENT if site == 'nakhimova' else SERVER
    anchor = head
    # Accept only tunnel-address NAT traffic to public destinations, before FastTrack.
    if site == 'nakhimova':
        for i, subnet in enumerate(PRIVATE):
            commands.append(f'/ip firewall address-list add list="{OWNER}-private" address={subnet} comment="{OWNER}:private-{i}"')
        commands += [
            f'/ip firewall filter add chain=forward action=accept in-interface="{iface}" out-interface=ether1 src-address=10.60.64.1/32 dst-address-list="!{OWNER}-private" connection-state=new,established,related {anchor} comment="{OWNER}:internet-out"',
            f'/ip firewall filter add chain=forward action=accept out-interface="{iface}" in-interface=ether1 dst-address=10.60.64.1/32 connection-state=established,related {anchor} comment="{OWNER}:internet-in"',
            f'/ip firewall nat add chain=srcnat action=masquerade src-address=10.60.64.1/32 out-interface=ether1 {head} comment="{OWNER}:internet-nat"',
            # Prevent unrelated Nakhimova policy marks from overriding return traffic.
            f'/ip firewall mangle add chain=prerouting action=accept in-interface="{iface}" {head} comment="{OWNER}:main-out"',
            f'/ip firewall mangle add chain=prerouting action=accept dst-address=10.60.64.1/32 {head} comment="{OWNER}:main-return"']
    else:
        commands += [f'/routing table add name={TABLE} fib',
                     f'/ip route add dst-address=0.0.0.0/0 gateway="{iface}" routing-table={TABLE} distance=1 comment="{OWNER}:default"',
                     f'/ip route add blackhole dst-address=0.0.0.0/0 routing-table={TABLE} distance=254 comment="{OWNER}:blackhole"',
                     f'/ip firewall nat add chain=srcnat action=src-nat src-address=192.168.89.0/24 out-interface="{iface}" to-addresses=10.60.64.1 {head} comment="{OWNER}:client-nat"']
    for direction in ('in', 'out'):
        commands.append(f'/ip firewall mangle add chain=forward action=change-mss protocol=tcp tcp-flags=syn {direction}-interface="{iface}" new-mss=1360 tcp-mss=1361-65535 comment="{OWNER}:mss-{direction}"')
    return commands


enable_server = tls.enable_server


def client_policy(mac, ip, direction='forward'):
    import managed
    if direction not in ('forward', 'reverse'):
        raise ValueError('invalid_direct_direction')
    reverse = direction == 'reverse'
    subnet = '192.168.88.0/24' if reverse else '192.168.89.0/24'
    mac, ip = managed.mac(mac), managed.address(ip, subnet)
    owner, table = (REVERSE_OWNER, REVERSE_TABLE) if reverse else (OWNER, TABLE)
    prefix = owner + ':device-' + mac.replace(':', '').lower()
    iface = CLIENT if reverse else SERVER
    # Order is activation order: guards, DNS, flows, then route selection.
    values = [('/ip firewall filter', 'leak', f'chain=forward action=drop in-interface=bridge src-mac-address={mac} out-interface=ether1 dst-address=!192.168.68.0/24'),
              ('/ipv6 firewall filter', 'ipv6', f'chain=forward action=drop in-interface=bridge src-mac-address={mac}'),
              ('/ipv6 firewall filter', 'dns6u', f'chain=input action=drop in-interface=bridge src-mac-address={mac} protocol=udp dst-port=53'),
              ('/ipv6 firewall filter', 'dns6t', f'chain=input action=drop in-interface=bridge src-mac-address={mac} protocol=tcp dst-port=53')]
    if reverse:
        values[0] = ('/ip firewall filter', 'leak', f'chain=forward action=drop in-interface=bridge src-mac-address={mac} out-interface=!{iface} dst-address-list=!{owner}-private')
        # Routing rules must not be overridden by legacy VPN routing marks.
        values.append(('/ip firewall mangle', 'main-policy', f'chain=prerouting action=accept in-interface=bridge src-address={ip}/32 src-mac-address={mac}'))
    for proto in ('udp', 'tcp'):
        values.append(('/ip firewall nat', 'dns-' + proto, f'chain=dstnat action=dst-nat in-interface=bridge src-address={ip}/32 src-mac-address={mac} protocol={proto} dst-port=53 to-addresses=1.1.1.1 to-ports=53'))
    values += [('/ip firewall filter', 'flow-out', f'chain=forward action=accept in-interface=bridge out-interface={iface} src-address={ip}/32 src-mac-address={mac} connection-state=new,established,related'),
               ('/ip firewall filter', 'flow-in', f'chain=forward action=accept in-interface={iface} out-interface=bridge dst-address={ip}/32 connection-state=established,related')]
    for subnet in (68, 88, 89):
        values.append(('/routing rule', 'bypass-' + str(subnet), f'action=lookup-only-in-table table=main src-address={ip}/32 dst-address=192.168.{subnet}.0/24'))
    values.append(('/routing rule', 'route', f'action=lookup-only-in-table table={table} src-address={ip}/32'))
    return [dict(path=path, comment=prefix + ':' + suffix, properties=properties,
                 head=path != '/routing rule') for path, suffix, properties in values]


def reverse_commands(site):
    """Add only reverse egress objects; the existing SSTP transport is immutable."""
    if site not in SITES:
        raise ValueError('unknown_site')
    o, table = REVERSE_OWNER, REVERSE_TABLE
    head = 'place-before=([find where dynamic=no]->0)'
    commands = [f'/ip firewall address-list add list="{o}-private" address={subnet} comment="{o}:private-{i}"'
                for i, subnet in enumerate(PRIVATE)]
    if site == 'nakhimova':
        return commands + [
            f'/routing table add name={table} fib',
            f'/ip route add disabled=no dst-address=0.0.0.0/0 gateway={CLIENT} routing-table={table} distance=1 comment="{o}:default"',
            f'/ip route add blackhole dst-address=0.0.0.0/0 routing-table={table} distance=254 comment="{o}:blackhole"',
            f'/ip firewall nat add chain=srcnat action=src-nat src-address=192.168.88.0/24 dst-address-list="!{o}-private" out-interface={CLIENT} to-addresses=10.60.64.2 {head} comment="{o}:client-nat"']
    # Stay below forward per-device head rules, but above both shared SSTP denies.
    anchor = f'place-before=[find where comment="{OWNER}:forward-out"]'
    return commands + [
        f'/ip firewall filter add chain=forward action=accept in-interface={SERVER} out-interface=ether1 src-address=10.60.64.2/32 dst-address-list="!{o}-private" connection-state=new,established,related {anchor} comment="{o}:internet-out"',
        f'/ip firewall filter add chain=forward action=accept out-interface={SERVER} in-interface=ether1 dst-address=10.60.64.2/32 connection-state=established,related {anchor} comment="{o}:internet-in"',
        f'/ip firewall nat add chain=srcnat action=masquerade src-address=10.60.64.2/32 out-interface=ether1 {head} comment="{o}:internet-nat"',
        f'/ip firewall mangle add chain=prerouting action=accept in-interface={SERVER} {head} comment="{o}:main-out"',
        f'/ip firewall mangle add chain=prerouting action=accept dst-address=10.60.64.2/32 {head} comment="{o}:main-return"']


def fresh_http_observation(observed, after, up):
    done = observed.get('done-tests')
    return type(done) in (int, float) and done > after and observed.get('status') == ('up' if up else 'down')


def device_add(spec):
    command = f'{spec["path"]} add disabled=yes {spec["properties"]} comment="{spec["comment"]}"'
    if not spec['head']:
        return command
    return (f':local first [{spec["path"]} find where dynamic=no]; '
            f':if ([:len $first] > 0) do={{ {command} place-before=($first->0) }} else={{ {command} }}')


def persistent_cleanup(site):
    commands = tls.cleanup_commands(site)
    # Only the explicitly owned permanent namespace is removable.
    for path in PATHS:
        if path == '/routing table':
            continue
        commands.append(f'{path} remove [find where comment~"^{OWNER}:"]')
    if site == 'fethiye':
        commands.append(f'/routing table remove [find where name="{TABLE}"]')
    return commands
