"""Restore the narrowly identified runtime state lost during Docker maintenance."""
import json
import subprocess


def run(*args):
    return subprocess.check_output(args, text=True, timeout=40).strip()


container = json.loads(run('docker', 'inspect', 'wg-relay'))[0]
assert container['Image'] == 'sha256:d3e46bc7a1510142afb30b4f5375c7d4470c75ed89483e798813c1acd6e7c1cb'
assert container['State']['Running']
pid = str(container['State']['Pid'])


def ns(*args):
    return run('nsenter', '-t', pid, '-n', *args)


tables = json.loads(ns('nft', '-j', 'list', 'tables'))['nftables']
if not any(x.get('table', {}).get('name') == 'ru_bth' for x in tables):
    source = '/var/backups/os-maintenance-20260927/ru-bth.restore.json'
    ns('nft', '-c', '-j', '-f', source)
    ns('nft', '-j', '-f', source)

rules = json.loads(ns('ip', '-j', '-4', 'rule', 'show'))
for priority, selector in [(180, ['to', '10.50.50.0/24', 'lookup', 'main']),
                           (181, ['to', '10.10.10.0/24', 'lookup', 'main']),
                           (190, ['fwmark', '0x30', 'lookup', '300'])]:
    if not any(rule['priority'] == priority for rule in rules):
        ns('ip', 'rule', 'add', 'priority', str(priority), *selector)

routes = json.loads(ns('ip', '-j', '-4', 'route', 'show', 'table', 'main'))
for address in ['89.252.153.129', '103.75.126.143']:
    if not any(route['dst'] in (address, address + '/32') for route in routes):
        ns('ip', 'route', 'add', address + '/32', 'via', '172.19.0.1', 'dev', 'eth0')

forward = [['-s', '10.10.100.0/24', '-o', 'eth0', '-j', 'ACCEPT'],
           ['-i', 'wg0', '-o', 'wg1', '-j', 'ACCEPT'],
           ['-i', 'wg1', '-o', 'wg0', '-j', 'ACCEPT']]
for rule in forward:
    ns('iptables', '-C', 'FORWARD', *rule)
for rule in forward:
    ns('iptables', '-D', 'FORWARD', *rule)
for index, rule in enumerate(forward, 1):
    ns('iptables', '-I', 'FORWARD', str(index), *rule)

nat = [['-s', '10.10.100.0/24', '-o', 'eth0', '-j', 'MASQUERADE'],
       ['-s', '10.10.10.0/24', '-o', 'wg1', '-j', 'MASQUERADE']]
for rule in nat:
    ns('iptables', '-t', 'nat', '-C', 'POSTROUTING', *rule)
for rule in nat:
    ns('iptables', '-t', 'nat', '-D', 'POSTROUTING', *rule)
for index, rule in enumerate(nat, 2):
    ns('iptables', '-t', 'nat', '-I', 'POSTROUTING', str(index), *rule)
print('IDENTIFIED_RUNTIME_STATE_RESTORED')
