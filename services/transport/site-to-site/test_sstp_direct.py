"""Focused permanent policy and local-facade regressions."""
from datetime import datetime, timezone
import importlib.util
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

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE))
import direct_controller as ctl
import direct_panel as panel
import sstp_direct as p


def test_device_revision_ignores_unrelated_dhcp_and_labels(tmp_path):
    from controller import write
    write(tmp_path / 'config.json', dict(version=1, baseline={'fethiye': 'a', 'nakhimova': 'b'}))
    write(tmp_path / 'state.json', dict(version=1, generation=0, clients={}))
    instance = ctl.DirectController(tmp_path)
    key = '52:EB:3F:26:E9:5A'
    target = dict(mac=key, ip='192.168.89.196', lease='*12', label='Laptop', online=True)
    revision = instance.device_revision(key, target)
    assert revision == instance.device_revision(key, dict(target, label='Renamed', online=False))
    for update in (dict(ip='192.168.89.195'), dict(lease='*13')):
        assert revision != instance.device_revision(key, dict(target, **update))
    instance.state['generation'] += 1
    assert revision != instance.device_revision(key, target)


def test_revision_conflict_is_action_error_not_transport_error(tmp_path, monkeypatch):
    from controller import write
    write(tmp_path / 'config.json', dict(version=1))
    write(tmp_path / 'state.json', dict(version=1, generation=0, clients={}))
    healthy = dict(available=True, can_remove=True, error=None, devices=[])
    monkeypatch.setattr(ctl.DirectController, 'status', lambda self: dict(healthy))
    def conflict(*args):
        raise ValueError('device_list_changed_refresh_and_retry')
    monkeypatch.setattr(ctl.DirectController, 'action', conflict)
    result = ctl.execute('add', '52:EB:3F:26:E9:5A', '0' * 64, tmp_path)
    assert result['success'] is False
    assert result['error'] is None
    assert result['error_code'] == 'device_list_changed_refresh_and_retry'
    assert 'No settings were changed' in result['operation_error']


def test_failed_action_checkpoints_diagnostic_and_audit(tmp_path, monkeypatch):
    from controller import write
    import direct_private
    write(tmp_path / 'config.json', dict(version=1))
    write(tmp_path / 'state.json', dict(version=1, generation=0, clients={}))
    monkeypatch.setattr(ctl.access, 'PRIVATE', tmp_path)
    monkeypatch.setattr(ctl.DirectController, 'status', lambda self: dict(error=None))
    def conflict(*args):
        raise ValueError('device_list_changed_refresh_and_retry')
    monkeypatch.setattr(ctl.DirectController, 'action', conflict)
    checkpoints = []
    monkeypatch.setattr(direct_private, 'checkpoint', lambda paths: checkpoints.append(set(paths)))
    ctl.execute('add', '52:EB:3F:26:E9:5A', '0' * 64, tmp_path)
    assert checkpoints == [{tmp_path / 'last-error.json', tmp_path / 'actions.jsonl'}]


def test_transport_independent_and_scoped():
    for site in p.SITES:
        commands = p.stage_commands(site, '194.61.140.217', 'x' * 40)
        text = '\n'.join(commands)
        assert 'wg-s2s-tw' not in text and 'ipip-s2s' not in text
        assert '10.60.60.' not in text and '10.60.61.' not in text
        assert '/system scheduler' not in text and 'add-default-route=yes' not in text
        assert all(' remove ' not in c and ' disable ' not in c for c in commands)
        assert ':observe' not in text
        assert all('place-before' not in c for c in commands if ':mss-' in c)
    assert 'verify-client-certificate=yes' in p.enable_server()
    assert 'verify-server-certificate=yes' in '\n'.join(p.stage_commands('nakhimova', '194.61.140.217', 'x' * 40))


def test_permanent_lifetime_and_private_ca():
    from cryptography import x509
    now = datetime.now(timezone.utc)
    files, meta = p.bundle('194.61.140.217', now, b'x' * 32)
    ca = x509.load_pem_x509_certificate(files['ca.pem'])
    assert 824 <= (ca.not_valid_after_utc - now).days <= 825
    assert p.CA == meta['ca']['name']


def test_device_policy_activation_and_reversal():
    specs = p.client_policy('4A:CE:4B:D0:88:E5', '192.168.89.197')
    assert specs[0]['comment'].endswith(':leak')
    assert specs[-1]['properties'].startswith('action=lookup-only-in-table table=sstp_direct')
    assert all('disabled=yes' in p.device_add(s) for s in specs)
    assert any('to-addresses=1.1.1.1' in s['properties'] for s in specs)
    assert not any('s2s_remote' in s['properties'] for s in specs)


@pytest.mark.parametrize('direction,ip,table',[('forward','192.168.89.197',p.TABLE),('reverse','192.168.88.100',p.REVERSE_TABLE)])
def test_ru_policy_does_not_reapply_a_catch_all_source_route(direction,ip,table):
    specs=p.client_policy('02:11:22:33:44:55',ip,direction,ru_bypass=True)
    by={s['comment'].rsplit(':',1)[1]:s for s in specs}
    assert 'dst-address=1.1.1.1/32' in by['route']['properties']
    assert 'new-routing-mark='+table in by['main-policy']['properties']
    assert 'dst-address-list=!RU_Networks' in by['main-policy']['properties']
    assert 'dst-address-type=!local' in by['main-policy']['properties']
    assert 'action=accept' in by['ru-policy']['properties']
    assert 'dst-address-list='+p.REVERSE_OWNER+'-private' in by['private-policy']['properties']
    assert 'out-interface=ether1 dst-address-list=RU_Networks' in by['ru-out']['properties']
    assert 'src-address-list=RU_Networks' in by['ru-in']['properties']
    assert 'connection-state=established,related' in by['ru-in']['properties']
    assert all('dst-address-list=!RU_Networks' in by['dns-'+proto]['properties'] for proto in ('udp','tcp'))
    assert specs.index(by['leak'])<specs.index(by['ru-out'])
    assert specs.index(by['main-policy'])<specs.index(by['private-policy'])<specs.index(by['ru-policy'])
    assert all(s['head'] for k,s in by.items() if k.endswith('-policy'))


@pytest.mark.parametrize('mac,ip', [('AA;quit', '192.168.89.197'), ('4A:CE:4B:D0:88:E5', '192.168.68.100'), ('FF:FF:FF:FF:FF:FF', '192.168.89.2')])
def test_no_foreign_devices(mac, ip):
    with pytest.raises(ValueError):
        p.client_policy(mac, ip)


def test_hash_keeps_shared_transport_and_ignores_only_registered_lease():
    base = '/interface sstp-client add name=sstp-direct-out\n'
    lease = '/ip dhcp-server lease add address=192.168.89.197 mac-address=4A:CE:4B:D0:88:E5\n'
    clients = [dict(mac='4A:CE:4B:D0:88:E5')]
    assert ctl.configuration_hash(base + lease, clients) == ctl.configuration_hash(base)
    assert ctl.configuration_hash(base + lease) != ctl.configuration_hash(base)
    assert ctl.configuration_hash(base.replace('out', 'evil')) != ctl.configuration_hash(base)
    continuation = '/system script add source="unrelated ' + chr(92) + '\n script source"\n'
    assert ctl.configuration_hash(base + continuation) != ctl.configuration_hash(base)


def test_injection_preserves_vpn_and_escapes_token():
    html = panel.inject('<html><main>Original VPN</main></html>', 'safe-token')
    assert 'Original VPN' in html and 'Direct SSTP' in html
    assert 'DIRECT_TOKEN' not in html
    with pytest.raises(ValueError):
        panel.inject('unknown markup', 'token')


def test_add_failure_preserves_pending_intent(tmp_path, monkeypatch):
    from controller import write
    key, ip = '4A:CE:4B:D0:88:E5', '192.168.89.197'
    write(tmp_path / 'config.json', dict(version=1))
    write(tmp_path / 'state.json', dict(version=1, generation=0, clients={}))
    class Connection:
        def close(self):
            pass
    instance = ctl.DirectController(tmp_path, connector=lambda _: Connection())
    monkeypatch.setattr(instance, 'status', lambda: dict(revision='a' * 64, available=True, can_remove=True))
    lease = dict(mac=key, ip=ip, label='Test', online=True, lease='*1')
    device = dict(id=key, revision=instance.device_revision(key, lease))
    monkeypatch.setattr(instance, 'status', lambda: dict(revision='a' * 64, available=True, can_remove=True, devices=[device]))
    monkeypatch.setattr(instance, 'inspect', lambda _: ({key: lease}, {}))
    monkeypatch.setattr(ctl.access, 'value', lambda *args: False)
    operations = []
    def fail(c, command):
        operations.append(command)
        if len(operations) == 2:
            raise RuntimeError('injected_write_failure')
    monkeypatch.setattr(ctl.access, 'mutate', fail)
    with pytest.raises(RuntimeError):
        instance.action('add', key, 'a' * 64)
    saved = json.loads((tmp_path / 'state.json').read_text())['clients'][key]
    assert saved['selected'] is True and saved['pending'] is True
    assert all('disabled=yes' in c for c in operations)
    assert not any(' enable ' in c for c in operations)


def test_stale_revision_never_writes(tmp_path, monkeypatch):
    from controller import write
    write(tmp_path / 'config.json', dict(version=1))
    write(tmp_path / 'state.json', dict(version=1, generation=0, clients={}))
    instance = ctl.DirectController(tmp_path, connector=lambda _: pytest.fail('No connection permitted'))
    monkeypatch.setattr(instance, 'status', lambda: dict(revision='a' * 64))
    with pytest.raises(ValueError, match='changed'):
        instance.action('add', '4A:CE:4B:D0:88:E5', 'b' * 64)


@pytest.mark.parametrize('change', ['unrelated', 'ip', 'lease', 'offline', 'generation', 'second_read'])
def test_target_revision_checks_before_first_write(tmp_path, monkeypatch, change):
    from controller import write
    key = '52:EB:3F:26:E9:5A'
    write(tmp_path / 'config.json', dict(version=1, baseline={'fethiye': 'a'}))
    write(tmp_path / 'state.json', dict(version=1, generation=0, clients={}))
    class Connection:
        def close(self):
            pass
    instance = ctl.DirectController(tmp_path, connector=lambda _: Connection())
    lease = dict(mac=key, ip='192.168.89.196', lease='*12', label='Laptop', online=True)
    approved = instance.device_revision(key, lease)
    if change == 'generation':
        instance.state['generation'] += 1
    fresh = dict(lease)
    if change == 'ip':
        fresh['ip'] = '192.168.89.195'
    if change == 'lease':
        fresh['lease'] = '*13'
    if change == 'offline':
        fresh['online'] = False
    device = dict(id=key, revision=instance.device_revision(key, fresh))
    monkeypatch.setattr(instance, 'status', lambda: dict(revision='b' * 64, available=True, can_remove=True, devices=[device]))
    second = dict(fresh, lease='*14') if change == 'second_read' else fresh
    monkeypatch.setattr(instance, 'inspect', lambda _: ({key: second}, {}))
    writes = []
    monkeypatch.setattr(instance, 'save', lambda: writes.append('save'))
    monkeypatch.setattr(ctl.access, 'value', lambda *args: False)
    def mutate(*args):
        writes.append('router')
        raise RuntimeError('first_write_reached')
    monkeypatch.setattr(ctl.access, 'mutate', mutate)
    with pytest.raises((ValueError, RuntimeError)) as exc:
        instance.action('add', key, approved)
    if change == 'unrelated':
        assert str(exc.value) == 'first_write_reached'
        assert writes == ['save', 'router']
    else:
        assert writes == []
        assert not instance.state['clients']
        assert str(exc.value) in ('device_list_changed_refresh_and_retry', 'device_not_online')


def test_browser_explicit_refresh_and_sticky_operation_error(tmp_path):
    if not shutil.which('node'):
        pytest.skip('Node required for browser regression')
    html = panel.inject('<html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">'
                        '<style>body{background:#101317;color:white;font:16px sans-serif;padding:16px}*{box-sizing:border-box}</style>'
                        '</head><body><main>Original VPN</main></body></html>', 'fixture-token')
    script = r'''
const { chromium } = require('playwright');
const assert = require('node:assert/strict');
const input = JSON.parse(require('node:fs').readFileSync(0, 'utf8'));
(async()=>{
 const browser=await chromium.launch({headless:true,channel:'chrome'});
 try {
 const page=await browser.newPage({viewport:{width:1280,height:900}}),errors=[];
 page.on('pageerror',e=>errors.push(e.message));
 let reads=0,writes=0,selected=false;
 const key='A2:C1:5E:29:F5:8E',revision='d'.repeat(64);
 const state=()=>({available:true,can_remove:true,checked_at:Date.now()/1000,revision:'g'.repeat(64),error:null,
 tunnel:{state:'up',detail:'TCP/443'},devices:[
 {id:key,ip:'192.168.89.197',label:'MacBook Air (Sergey)',name_source:'inventory',online:true,selected,status:selected?'remote':'local',revision},
 {id:'52:EB:3F:26:E9:5A',ip:'192.168.89.196',label:'Unknown device (private MAC)',name_source:'unknown',online:true,selected:false,status:'local',revision},
 {id:'00:11:22:33:44:55',ip:'192.168.89.198',label:'Example Manufacturer with a Deliberately Long Registered Company Name for Layout Checks device',name_source:'manufacturer',online:true,selected:false,status:'local',revision}]});
 await page.route('http://127.0.0.1:19999/**',async route=>{
  const path=new URL(route.request().url()).pathname;
  if(path==='/')return route.fulfill({contentType:'text/html; charset=utf-8',body:input.html});
  if(path==='/s2s-state'){reads++;const value=state();
   if(reads===3){value.available=false;value.tunnel.state='unknown';value.error='Nakhimova management unavailable after connection retry (timeout); selection unchanged';}
   return route.fulfill({json:value});}
  if(path==='/s2s-action'){
   const fields=new URLSearchParams(route.request().postData());assert.equal(fields.get('revision'),revision);
   assert.equal(fields.get('device'),key);writes++;
   if(writes===1)return route.fulfill({json:{...state(),success:false,error_code:'device_list_changed_refresh_and_retry',operation_error:'No settings were changed. Refresh status and retry.'}});
   if(writes===3){const value=state();value.available=false;value.devices[0].status='pending';value.error='Pending device operation';
    return route.fulfill({json:{...value,success:false,operation_error:'Remove not confirmed; saved selection is retained.'}});}
   selected=fields.get('action')==='add';return route.fulfill({json:{...state(),success:true}});
  }
  throw Error('Unexpected fixture request '+path);
 });
 await page.goto('http://127.0.0.1:19999/#site-to-site');
 await page.locator('#direct-device option[value="'+key+'"]').waitFor({state:'attached'});
 await page.selectOption('#direct-device',key);await page.click('#direct-add-button');
 await page.getByText('No settings were changed. Refresh status and retry.',{exact:true}).waitFor();
 assert.equal(reads,1);assert.equal(writes,1);
 await page.clock.install();await page.clock.fastForward(65000);
 assert.equal(reads,1);assert.equal(writes,1);assert.equal(await page.locator('#direct-feedback').isVisible(),true);
 await page.screenshot({path:input.directory+'/sticky-error-desktop.png'});
 await page.click('#direct-refresh');await page.waitForFunction(()=>!document.getElementById('direct-refresh').disabled);
 assert.equal(reads,2);assert.equal(await page.locator('#direct-device').inputValue(),key);
 assert.match(await page.locator('#direct-message').innerText(),/No settings were changed/);
 await page.click('#direct-dismiss');assert.equal(await page.locator('#direct-feedback').isVisible(),false);
 await page.click('#direct-add-button');await page.locator('#direct-selected button').waitFor();
 assert.equal(writes,2);assert.equal(await page.locator('#direct-message').innerText(),'Change confirmed');
 assert.match(await page.locator('#direct-selected small').innerText(),/A2:C1:5E:29:F5:8E/);
 assert.equal(await page.locator('#direct-selected strong').getAttribute('title'),'Name source: inventory');
 await page.click('#direct-selected button');await page.getByText('Remove not confirmed; saved selection is retained.',{exact:true}).waitFor();
 assert.equal(writes,3);assert.equal(await page.locator('#direct-empty').isVisible(),false);
 assert.match(await page.locator('#direct-selected small').innerText(),/pending/);
 assert.equal(await page.locator('#direct-selected button').isEnabled(),true);
 await page.click('#direct-selected button');await page.locator('#direct-empty').waitFor();assert.equal(writes,4);
 await page.click('#direct-refresh');await page.waitForFunction(()=>document.getElementById('direct-status').dataset.state==='unknown');
 assert.equal(await page.locator('#direct-add-button').isDisabled(),true);
 assert.equal(await page.locator('#direct-status').evaluate(e=>getComputedStyle(e).color),'rgb(170, 178, 192)');
 assert.equal(await page.locator('#direct-message').innerText(),'Change confirmed');
 await page.setViewportSize({width:390,height:844});
 assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth),false);
 await page.screenshot({path:input.directory+'/explicit-refresh-mobile.png'});
 await page.click('a[href="#vpn"]');assert.equal(await page.locator('main').innerText(),'Original VPN');
 assert.deepEqual(errors,[]);console.log(JSON.stringify({reads,writes,page_errors:errors}));
 } finally {await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1;});
'''
    result = subprocess.run(['node', '-e', script], input=json.dumps(dict(html=html, directory=str(tmp_path))),
                            text=True, capture_output=True, timeout=90, env=os.environ)
    assert result.returncode == 0, result.stdout + result.stderr


def test_enabled_export_omits_default_disabled_flag(tmp_path, monkeypatch):
    from controller import write
    key, ip = '4A:CE:4B:D0:88:E5', '192.168.89.197'
    write(tmp_path / 'config.json', dict(version=1, dhcp_server='defconf', baseline_exports=dict(fethiye='')))
    write(tmp_path / 'state.json', dict(version=1, generation=1, clients={key: dict(mac=key, ip=ip,
          selected=True, pending=True, prepared=False)}))
    spec = p.client_policy(key, ip)[0]
    export = spec['path'] + ' add ' + spec['properties'] + ' comment="' + spec['comment'] + '"\n'
    monkeypatch.setattr(ctl.access, 'run', lambda *args: export.encode())
    monkeypatch.setattr(ctl.access, 'rows', lambda *args: [])
    instance = ctl.DirectController(tmp_path)
    assert instance.inspect(None)[1] == {spec['comment']: False}


def test_http_csrf_origin_and_cache():
    calls = []
    value = dict(available=True, can_remove=True, checked_at=1, revision='a' * 64, devices=[],
                 tunnel=dict(state='up', detail='TCP/443'), error=None)
    def execute(*args):
        calls.append(args)
        return value
    httpd = panel.server(0, execute=execute)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    url = 'http://127.0.0.1:' + str(httpd.server_port)
    try:
        for _ in range(2):
            with urllib.request.urlopen(url + '/s2s-state') as r:
                assert json.load(r)['available'] is True
        assert len(calls) == 1
        for headers in ({}, {'Origin': 'https://evil.example'}):
            req = urllib.request.Request(url + '/s2s-action', data=b'csrf=no&action=add&device=no&revision=no', headers=headers)
            with pytest.raises(urllib.error.HTTPError) as exc:
                urllib.request.urlopen(req)
            assert exc.value.code in (400, 403)
        assert len(calls) == 1
    finally:
        httpd.shutdown()
        httpd.server_close()
        thread.join(2)
