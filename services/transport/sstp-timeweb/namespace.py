"""Own one namespace; never change root routes, links or firewall tables."""
import json
import subprocess
import sys

NAME='sstp-timeweb'

def run(*args):
    return subprocess.check_output(args,text=True,timeout=15)

def main(action):
    raw=run('ip','-j','netns','list')
    inventory=json.loads(raw) if raw.strip() else []
    if not isinstance(inventory,list) or any(not isinstance(n,dict) or not isinstance(n.get('name'),str) for n in inventory):
        raise ValueError('Invalid namespace inventory')
    names={n['name'] for n in inventory}
    if action=='up':
        if NAME in names:
            raise RuntimeError('Namespace already exists; explicit review required')
        run('ip','netns','add',NAME)
        try:
            run('ip','-n',NAME,'link','set','lo','up')
            run('ip','netns','exec',NAME,'sysctl','-qw','net.ipv4.ip_forward=0','net.ipv6.conf.all.forwarding=0')
            run('ip','netns','exec',NAME,'nft','-f','/etc/sstp-timeweb/namespace.nft')
        except Exception:
            run('ip','netns','delete',NAME)
            raise
    elif action=='down':
        if NAME not in names:
            return
        if run('ip','netns','pids',NAME).strip():
            raise RuntimeError('Namespace still has processes; refusing forced cleanup')
        run('ip','netns','delete',NAME)
    else:
        raise ValueError('Invalid namespace operation')

if __name__=='__main__':
    if len(sys.argv)!=2:
        raise SystemExit('Expected up or down')
    main(sys.argv[1])
