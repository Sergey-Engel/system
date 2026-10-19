"""Reverse egress must be independent of forward selections and TimeWeb."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import threading
import urllib.error
import urllib.request

import pytest

sys.path.insert(0, str(Path(__file__).parent))
import direct_controller as ctl
import managed
import sstp_direct as policy
from controller import write
import direct_panel as panel

KEY = '02:11:22:33:44:55'


def test_reverse_tab_is_first_without_changing_default_direction():
    html = panel.inject('<html><main>Original VPN</main></html>', 'fixture-token')
    assert html.index('data-direction="reverse"') < html.index('data-direction="forward"')
    assert 'data-direction="forward" aria-selected="true"' in html
    assert "direction='forward'" in html


@pytest.mark.parametrize('done,status,expected',[(None,'unknown',False),(0,'up',False),(True,'up',False),(1,'up',True),(1,'down',False)])
def test_netwatch_requires_fresh_numeric_counter(done,status,expected):
    assert policy.fresh_http_observation({'done-tests':done,'status':status},0,True) is expected


def test_netwatch_unknown_is_not_a_negative_result():
    assert not policy.fresh_http_observation({'done-tests':1,'status':'unknown'},0,False)
    assert policy.fresh_http_observation({'done-tests':1,'status':'down'},0,False)


def test_reverse_policy_is_scoped_and_mangle_precedes_route():
    specs = policy.client_policy(KEY, '192.168.88.100', direction='reverse')
    text = '\n'.join(s['properties'] for s in specs)
    assert specs[0]['comment'].endswith(':leak')
    assert 'out-interface=!sstp-direct-out' in specs[0]['properties']
    assert all(s['comment'].startswith('s2s-sstp-reverse-v1:device-') for s in specs)
    assert any(s['path'] == '/ip firewall mangle' and 'action=accept' in s['properties'] for s in specs)
    assert specs[-1]['properties'].startswith('action=lookup-only-in-table table=sstp_fethiye')
    assert 'wg-' not in text and 'ipip' not in text
    assert sum('to-addresses=1.1.1.1' in s['properties'] for s in specs) == 2
    assert all('disabled=yes' in policy.device_add(s) for s in specs)
    with pytest.raises(ValueError):
        policy.client_policy(KEY, '192.168.89.100', direction='reverse')
    with pytest.raises(ValueError):
        policy.client_policy(KEY, '192.168.88.100')


def test_reverse_infrastructure_never_changes_transport():
    for site in ('fethiye', 'nakhimova'):
        commands = policy.reverse_commands(site)
        text = '\n'.join(commands)
        assert all(' add ' in c for c in commands)
        assert all(token not in text for token in ('wg-', 'ipip', '/interface ', '/ppp ', '/certificate ', '/system '))
        if site == 'fethiye':
            assert 'src-address=10.60.64.2/32' in text and 'action=masquerade' in text
            assert '!s2s-sstp-reverse-v1-private' in text
            assert 'forward-out' in text
        else:
            assert 'blackhole' in text and 'distance=254' in text
            assert 'src-address=192.168.88.0/24' in text
            client_nat = next(c for c in commands if ':client-nat' in c)
            assert 'dst-address-list="!s2s-sstp-reverse-v1-private"' in client_nat


def test_reverse_state_and_revisions_are_direction_bound(tmp_path):
    write(tmp_path / 'config.json', dict(version=1, baseline={'fethiye':'a','nakhimova':'b'}, reverse_enabled=True))
    write(tmp_path / 'state.json', dict(version=1, generation=0, clients={}))
    reverse = tmp_path / 'reverse'
    reverse.mkdir()
    write(reverse / 'state.json', dict(version=1, generation=0, clients={}))
    forward = ctl.DirectController(tmp_path)
    other = ctl.DirectController(reverse, direction='reverse')
    assert other.source == 'nakhimova' and other.remote == 'fethiye'
    assert other.table == 'sstp_fethiye'
    lease = dict(ip='192.168.88.100', lease='*1')
    assert other.device_revision(KEY, lease) != forward.device_revision(KEY, dict(lease, ip='192.168.89.100'))
    other.state['clients'][KEY] = dict(mac=KEY, ip='192.168.88.100', label='Test', lease='*1', selected=False, pending=False)
    other.save()
    assert not json.loads((tmp_path / 'state.json').read_text())['clients']
    assert managed.leases([{'.id':'*1','server':'defconf','mac-address':KEY,'address':'192.168.88.100','status':'bound'}],
                          'defconf', subnet='192.168.88.0/24')[KEY]['online']


def test_empty_global_revisions_cannot_cross_directions(tmp_path,monkeypatch):
    write(tmp_path/'config.json',dict(version=1,baseline={},reverse_enabled=True,
        endpoint='194.61.140.217',certificate_expires=4_000_000_000))
    write(tmp_path/'state.json',dict(version=1,generation=0,clients={}))
    (tmp_path/'reverse').mkdir()
    write(tmp_path/'reverse/state.json',dict(version=1,generation=0,clients={}))
    class Connection:
        def __init__(self,site):
            self.site=site
        def close(self):
            pass
    monkeypatch.setattr(ctl.DirectController,'inspect',lambda *args:({},{}))
    monkeypatch.setattr(ctl.access,'value',lambda *args:True)
    monkeypatch.setattr(ctl.access,'get',lambda c,e:([{'gateway':policy.SERVER if c.site=='fethiye' else policy.CLIENT}]
        if e.startswith('[/routing') else '194.61.140.217'))
    states=[ctl.DirectController(tmp_path if d=='forward' else tmp_path/'reverse',connector=Connection,direction=d).status()
            for d in ('forward','reverse')]
    assert all(s['available'] for s in states)
    assert states[0]['revision']!=states[1]['revision']


def test_reverse_add_remove_only_writes_source(tmp_path, monkeypatch):
    write(tmp_path/'config.json',dict(version=1,baseline={},reverse_enabled=True))
    write(tmp_path/'state.json',dict(version=1,generation=8,clients={}))
    directory = tmp_path/'reverse'
    directory.mkdir()
    write(directory/'state.json',dict(version=1,generation=0,clients={}))
    original_forward = (tmp_path/'state.json').read_bytes()
    sites, commands, flags = [], [], {}
    class Connection:
        def close(self):
            pass
    def connector(site):
        sites.append(site)
        return Connection()
    instance = ctl.DirectController(directory,connector=connector,direction='reverse')
    lease = dict(mac=KEY,ip='192.168.88.100',lease='*1',online=True,label='Laptop')
    def status():
        return dict(available=True,can_remove=True,devices=[dict(id=KEY,revision=instance.device_revision(KEY,lease))],revision='a'*64)
    monkeypatch.setattr(instance,'status',status)
    monkeypatch.setattr(instance,'inspect',lambda c:({KEY:lease},dict(flags)))
    monkeypatch.setattr(ctl.access,'value',lambda *args:False)
    monkeypatch.setattr(ctl.access,'rows',lambda *args:[])
    def mutate(c,command):
        commands.append(command)
        spec = next(s for s in instance.specs(KEY,lease['ip']) if s['comment'] in command)
        flags[spec['comment']] = ' disable ' in command or 'disabled=yes' in command
    monkeypatch.setattr(ctl.access,'mutate',mutate)
    with pytest.raises(ValueError,match='changed'):
        instance.action('add',KEY,'wrong-direction-revision')
    assert not commands and not sites
    assert instance.action('add',KEY,status()['devices'][0]['revision'])['success']
    assert instance.state['clients'][KEY]['selected'] is True
    enabled = [c for c in commands if ' enable ' in c]
    assert ':leak' in enabled[0] and ':route' in enabled[-1]
    assert instance.action('remove',KEY,status()['devices'][0]['revision'])['success']
    disabled = [c for c in commands if ' disable ' in c]
    assert ':route' in disabled[0] and ':leak' in disabled[-1]
    assert sites == ['nakhimova','nakhimova']
    assert instance.state['clients'][KEY]['selected'] is False
    assert (tmp_path/'state.json').read_bytes() == original_forward
    assert all('s2s-sstp-reverse-v1:device-' in c for c in commands)


def test_reverse_http_dispatch_cache_and_csrf():
    calls = []
    def execute(*args,**kwargs):
        direction = kwargs.get('direction','forward')
        calls.append((args,direction))
        return dict(direction=direction,devices=[])
    httpd = panel.server(0,execute=execute)
    thread = threading.Thread(target=httpd.serve_forever,daemon=True)
    thread.start()
    url = 'http://127.0.0.1:'+str(httpd.server_port)
    try:
        for path,direction in [('/s2s-state','forward'),('/s2s-reverse-state','reverse'),('/s2s-state','forward')]:
            with urllib.request.urlopen(url+path) as response:
                assert json.load(response)['direction'] == direction
        assert calls == [((),'forward'),((),'reverse')]
        body = ('csrf='+'a'*43+'&action=add&device='+KEY+'&revision='+'b'*64).encode()
        for headers,expected in [({},400),({'Cookie':'direct_sstp_csrf='+'a'*43,'Origin':'https://evil.example'},403)]:
            with pytest.raises(urllib.error.HTTPError) as exc:
                urllib.request.urlopen(urllib.request.Request(url+'/s2s-reverse-action',data=body,headers=headers))
            assert exc.value.code == expected
        assert len(calls) == 2
        with urllib.request.urlopen(urllib.request.Request(url+'/s2s-reverse-action',data=body,
                headers={'Cookie':'direct_sstp_csrf='+'a'*43,'Origin':url})) as response:
            assert json.load(response)['direction'] == 'reverse'
        assert calls[-1] == (('add',KEY,'b'*64),'reverse')
    finally:
        httpd.shutdown()
        httpd.server_close()
        thread.join(2)


def test_browser_direction_isolation_and_sticky_errors(tmp_path):
    if not shutil.which('node'):
        pytest.skip('Node required')
    html = panel.inject('<html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">'
        '<style>body{background:#101317;color:white;font:16px sans-serif;padding:16px}*{box-sizing:border-box}</style>'
        '</head><body><main>Original VPN</main></body></html>','fixture-token')
    script = r'''
const {chromium}=require('playwright'),assert=require('node:assert/strict');
const input=JSON.parse(require('node:fs').readFileSync(0,'utf8'));
(async()=>{const browser=await chromium.launch({headless:true,channel:'chrome'});try{
const page=await browser.newPage({viewport:{width:1280,height:900}}),errors=[],requests=[];
page.on('pageerror',e=>errors.push(e.message));let selected=false;
await page.route('http://127.0.0.1:19998/**',async route=>{
 const path=new URL(route.request().url()).pathname;if(path==='/')return route.fulfill({contentType:'text/html; charset=utf-8',body:input.html});
 const reverse=path.includes('reverse'),direction=reverse?'reverse':'forward';requests.push(path);
 const key=reverse?'02:11:22:33:44:55':'A2:C1:5E:29:F5:8E';
 const state=()=>({direction,available:true,can_remove:true,error:null,checked_at:Date.now()/1000,
 tunnel:{state:'up',detail:'TCP/443'},devices:[{id:key,ip:reverse?'192.168.88.100':'192.168.89.197',label:reverse?'Nakhimova Laptop':'MacBook Air',
 online:true,selected:reverse&&selected,status:reverse&&selected?'remote':'local',revision:direction+'-revision'}]});
 if(path.endsWith('state'))return route.fulfill({json:state()});
 const fields=new URLSearchParams(route.request().postData());assert.equal(fields.get('device'),key);assert.equal(fields.get('revision'),direction+'-revision');
 if(!reverse)return route.fulfill({json:{...state(),success:false,operation_error:'Forward error stays visible'}});
 selected=fields.get('action')==='add';return route.fulfill({json:{...state(),success:true}});
});
await page.goto('http://127.0.0.1:19998/#site-to-site');await page.locator('#direct-device option[value="A2:C1:5E:29:F5:8E"]').waitFor({state:'attached'});
await page.selectOption('#direct-device','A2:C1:5E:29:F5:8E');await page.click('#direct-add-button');await page.getByText('Forward error stays visible',{exact:true}).waitFor();
await page.click('[data-direction="reverse"]');await page.locator('#direct-device option[value="02:11:22:33:44:55"]').waitFor({state:'attached'});
assert.equal(await page.locator('#direct-device option[value="A2:C1:5E:29:F5:8E"]').count(),0);
assert.equal(await page.locator('#direct-feedback').isVisible(),false);assert.equal(await page.locator('#direct-egress').innerText(),'Internet via Fethiye');
await page.selectOption('#direct-device','02:11:22:33:44:55');await page.click('#direct-add-button');await page.locator('#direct-selected button').waitFor();
await page.screenshot({path:input.directory+'/reverse-selected-desktop.png'});
await page.click('#direct-selected button');await page.locator('#direct-empty').waitFor();
await page.click('[data-direction="forward"]');await page.getByText('Forward error stays visible',{exact:true}).waitFor();
await page.waitForFunction(()=>!document.getElementById('direct-refresh').disabled);
assert.equal(await page.locator('#direct-device').inputValue(),'A2:C1:5E:29:F5:8E');
assert.equal(requests.length,6);await page.clock.install();await page.clock.fastForward(65000);assert.equal(requests.length,6);
await page.setViewportSize({width:390,height:844});assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth),false);
await page.screenshot({path:input.directory+'/reverse-direction-mobile.png'});assert.deepEqual(errors,[]);
}finally{await browser.close();}})().catch(e=>{console.error(e);process.exitCode=1});
'''
    result = subprocess.run(['node','-e',script],input=json.dumps(dict(html=html,directory=str(tmp_path))),
                            text=True,capture_output=True,timeout=60,env=os.environ)
    assert result.returncode == 0, result.stdout+result.stderr
