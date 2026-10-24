import json
import os
import shutil
import subprocess
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from types import SimpleNamespace
import urllib.error
import urllib.parse
import urllib.request

import pytest

sys.path.insert(0,str(Path(__file__).resolve().parent))
import direct_panel as panel


def test_unconfirmed_route_is_red_selectable_and_requires_confirmation(tmp_path):
    if not shutil.which('node'):
        pytest.skip('Node required')
    html=panel.inject('<html><head><meta charset="utf-8"><style>body{background:#101216;color:#eee;font:16px sans-serif}*{box-sizing:border-box}</style></head><body><main>VPN</main></body></html>', 'fixture-token', unified=True)
    script=r'''
const {chromium}=require('playwright'),assert=require('node:assert/strict');
const input=JSON.parse(require('node:fs').readFileSync(0,'utf8'));
(async()=>{const browser=await chromium.launch({headless:true,channel:'chrome'});try{
 const page=await browser.newPage({viewport:{width:1280,height:900}});let mode='cenuta',writes=0;
 await page.route('http://127.0.0.1:19994/**',async route=>{
  const req=route.request(),path=new URL(req.url()).pathname;
  if(path==='/')return route.fulfill({contentType:'text/html',body:input.html});
  if(path.startsWith('/routing-progress/'))return route.fulfill({status:404,body:''});
  if(req.method()==='POST'){writes++;mode=new URLSearchParams(req.postData()).get('mode');}
  return route.fulfill({json:{site:'nakhimova',checked_at:Date.now()/1000,source_ready:true,error:null,
   success:true,channels:{local:{ready:true},cenuta:{ready:true},fornex:{ready:true},direct:{ready:true},
    sstp_cenuta:{ready:false,apply_allowed:true},sstp_fornex:{ready:false,apply_allowed:false}},
   devices:[{id:'02:11:22:33:44:55',label:'Test laptop',ip:'192.168.88.100',online:true,mode,
    pending:false,can_apply:true,can_rollback:false,revision:'fixture',
    allowed_modes:['local','cenuta','sstp_cenuta','sstp_fornex']}]}});
 });
 await page.goto('http://127.0.0.1:19994/#site-to-site');
 const select=page.locator('.routing-row select'),apply=page.locator('.routing-apply');
 await select.waitFor();await page.waitForFunction(()=>!document.getElementById('routing-refresh').disabled);
 assert.equal(await select.locator('option[value="sstp_cenuta"]').isEnabled(),true);
 assert.equal(await select.locator('option[value="sstp_fornex"]').isEnabled(),false);
 await select.selectOption('sstp_cenuta');assert.equal(await apply.isEnabled(),true);
 assert.equal(await select.getAttribute('data-unverified'),'true');
 assert.equal(await select.evaluate(n=>getComputedStyle(n).color),'rgb(255, 133, 133)');
 page.once('dialog',d=>{assert.match(d.message(),/Connectivity may be lost/);d.dismiss();});
 await apply.click();assert.equal(writes,0);
 page.once('dialog',d=>d.accept());await apply.click();
 await page.waitForFunction(()=>document.querySelector('.routing-current').textContent==='SSTP-Cenuta-RU');
 assert.equal(writes,1);assert.equal(await page.locator('.routing-current').getAttribute('data-unverified'),'true');
 assert.equal(await page.locator('.routing-current').evaluate(n=>getComputedStyle(n).color),'rgb(255, 133, 133)');
 await page.screenshot({path:input.directory+'/unconfirmed-desktop.png'});
 await page.setViewportSize({width:390,height:844});
 assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth),false);
 await page.screenshot({path:input.directory+'/unconfirmed-mobile.png'});
 }finally{await browser.close();}})().catch(e=>{console.error(e);process.exitCode=1});
'''
    result=subprocess.run(['node','-e',script],input=json.dumps(dict(html=html,directory=str(tmp_path))),
                          text=True,capture_output=True,timeout=60,env=os.environ)
    assert result.returncode==0,result.stdout+result.stderr


def test_browser_completed_poll_collapses_after_twenty_seconds(tmp_path):
    if not shutil.which('node'):
        pytest.skip('Node required')
    html = panel.inject('<html><head><meta name="viewport" content="width=device-width,initial-scale=1">'
        '<style>body{font:16px sans-serif;padding:16px}*{box-sizing:border-box}</style>'
        '</head><body><main>Original VPN</main></body></html>', 'fixture-token', unified=True)
    script = r'''
const {chromium}=require('playwright'),assert=require('node:assert/strict');
const input=JSON.parse(require('node:fs').readFileSync(0,'utf8'));
(async()=>{const browser=await chromium.launch({headless:true,channel:'chrome'});try{
 const page=await browser.newPage({viewport:{width:1280,height:900}}),errors=[];
 let checks=0,hold=true,release,result='ok';page.on('pageerror',e=>errors.push(e.message));
 const checkedAt=1792648800;
 await page.clock.install();
 await page.route('http://127.0.0.1:19995/**',async route=>{
  const req=route.request(),path=new URL(req.url()).pathname;assert.equal(req.method(),'GET');
  if(path==='/')return route.fulfill({contentType:'text/html; charset=utf-8',body:input.html});
  if(path.startsWith('/routing-progress/'))return route.fulfill({status:404,body:'Not found'});
  assert.ok(path.startsWith('/routing-state/'));checks++;
  if(hold)await new Promise(resolve=>release=resolve);
  if(result==='http-error')return route.fulfill({status:503,body:'Unavailable'});
  return route.fulfill({json:{site:path.split('/').pop(),source_ready:true,checked_at:checkedAt,
   error:result==='status-error'?'Pending device operation':null,channels:{local:{ready:true}},devices:[]}});
 });
 const settled=()=>page.waitForFunction(()=>!document.getElementById('routing-refresh').disabled);
 const good=()=>page.locator('#routing-checked').getAttribute('data-state');
 await page.goto('http://127.0.0.1:19995/#site-to-site');
 await page.clock.pauseAt(await page.evaluate(()=>Date.now()+1000));hold=false;release();await settled();
 assert.equal(await good(),'success');
 const stamp=await page.locator('#routing-checked').innerText();assert.match(stamp,/Updated/);
 assert.ok(stamp.includes(new Date(checkedAt*1000).toLocaleTimeString()));
 const placement=await page.locator('#routing-checked').evaluate(n=>{
  const r=n.getBoundingClientRect(),b=document.getElementById('routing-refresh').getBoundingClientRect();
  return r.top>=b.bottom&&r.right<=innerWidth;
 });assert.ok(placement);
 await page.clock.fastForward(19999);assert.equal(await page.locator('#routing-poll').isVisible(),true);
 await page.clock.fastForward(1);assert.equal(await page.locator('#routing-poll').isVisible(),false);
 assert.equal(await good(),'success');assert.equal(await page.locator('#routing-checked').innerText(),stamp);assert.equal(checks,1);
 await page.screenshot({path:input.directory+'/collapsed-desktop.png'});
 await page.setViewportSize({width:390,height:844});assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth),false);
 await page.screenshot({path:input.directory+'/collapsed-mobile.png'});
 await page.click('#routing-refresh');await settled();await page.clock.fastForward(10000);
 hold=true;await page.click('#routing-refresh');await page.waitForFunction(()=>document.getElementById('routing-refresh').disabled);
 assert.notEqual(await good(),'success');await page.clock.fastForward(20000);
 assert.equal(await page.locator('#routing-poll').isVisible(),true);
 result='http-error';hold=false;release();await settled();
 assert.notEqual(await good(),'success');await page.clock.fastForward(60000);
 assert.equal(await page.locator('#routing-poll').isVisible(),true);
 assert.equal(await page.locator('#routing-error').isVisible(),true);
 result='status-error';await page.click('#routing-refresh');await settled();await page.clock.fastForward(60000);
 assert.notEqual(await good(),'success');assert.equal(await page.locator('#routing-poll').isVisible(),true);
 assert.equal(await page.locator('#routing-error').innerText(),'Pending device operation');
 result='ok';await page.click('#routing-refresh');await settled();await page.clock.fastForward(10000);
 hold=true;await page.click('[data-site="fethiye"]');await page.waitForFunction(()=>document.getElementById('routing-refresh').disabled);
 assert.notEqual(await good(),'success');await page.clock.fastForward(20000);
 assert.equal(await page.locator('#routing-poll').isVisible(),true);
 hold=false;release();await settled();await page.clock.fastForward(20000);
 assert.equal(await good(),'success');assert.equal(await page.locator('#routing-poll').isVisible(),false);
 assert.equal(checks,6);assert.deepEqual(errors,[]);
 }finally{await browser.close();}})().catch(e=>{console.error(e);process.exitCode=1});
'''
    result = subprocess.run(['node', '-e', script], input=json.dumps(dict(html=html, directory=str(tmp_path))),
                            text=True, capture_output=True, timeout=60, env=os.environ)
    assert result.returncode == 0, result.stdout + result.stderr


def test_overlapping_reads_share_only_inflight_site_snapshot(monkeypatch):
    started, release, queued = threading.Event(), threading.Event(), threading.Event()
    clock_calls = []
    calls = []
    def clock():
        clock_calls.append(threading.get_ident())
        if len(clock_calls) == 2:
            queued.set()
        return time.monotonic()
    monkeypatch.setattr(panel, 'time', SimpleNamespace(monotonic=clock))
    def execute(**kwargs):
        calls.append(kwargs)
        if len(calls) == 1:
            started.set()
            assert release.wait(5)
        return dict(site=kwargs['site'], devices=[], checked_at=len(calls), success=True)
    httpd = panel.server(0, unified=True, routing_execute=execute)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    url = 'http://127.0.0.1:' + str(httpd.server_port)
    def read(site='nakhimova'):
        with urllib.request.urlopen(url + '/routing-state/' + site, timeout=8) as response:
            return json.load(response)
    try:
        with ThreadPoolExecutor(max_workers=2) as workers:
            first = workers.submit(read)
            assert started.wait(3)
            second = workers.submit(read)
            try:
                assert queued.wait(3), 'Queued reads must record their arrival before waiting'
            finally:
                release.set()
            assert first.result() == second.result()
        assert calls == [dict(site='nakhimova')]
        assert read()['checked_at'] == 2
        assert read('fethiye')['checked_at'] == 3
        headers = {'Cookie': 'direct_sstp_csrf=' + 'a' * 43, 'Origin': url}
        fields = dict(csrf='a' * 43, site='nakhimova', device='02:11:22:33:44:55', mode='local', revision='b' * 64)
        request = urllib.request.Request(url + '/routing-action', headers=headers,
            data=urllib.parse.urlencode(fields).encode())
        with urllib.request.urlopen(request) as response:
            assert json.load(response)['success']
        assert calls[-1]['mode'] == 'local'
        assert read()['checked_at'] == 5
    finally:
        release.set()
        httpd.shutdown(); httpd.server_close(); thread.join(2)


def test_unified_http_is_closed_and_legacy_writers_retired():
    calls=[]
    def execute(**kwargs):
        calls.append(kwargs)
        return dict(site=kwargs['site'],devices=[],success=True)
    httpd=panel.server(0,unified=True,routing_execute=execute,
                       execute=lambda *a,**kw:pytest.fail('Legacy writer invoked'))
    thread=threading.Thread(target=httpd.serve_forever,daemon=True)
    thread.start()
    url='http://127.0.0.1:'+str(httpd.server_port)
    headers={'Cookie':'direct_sstp_csrf='+'a'*43,'Origin':url}
    fields=dict(csrf='a'*43,site='nakhimova',device='02:11:22:33:44:55',mode='cenuta',revision='b'*64)
    def post(path,values=fields,h=headers):
        return urllib.request.urlopen(urllib.request.Request(url+path,data=urllib.parse.urlencode(values).encode(),headers=h))
    try:
        for site in ('nakhimova','fethiye'):
            with urllib.request.urlopen(url+'/routing-state/'+site) as r:
                assert json.load(r)['site']==site
        with post('/routing-action') as r:
            assert json.load(r)['success']
        assert calls[-1]=={k:v for k,v in fields.items() if k!='csrf'}
        count=len(calls)
        for path,values,h,code in [
            ('/routing-action',dict(fields,site='fethiye'),headers,400),
            ('/routing-action',dict(fields,site='other'),headers,400),
            ('/routing-action',dict(fields,extra='x'),headers,400),
            ('/routing-action',dict(fields,csrf='wrong'),headers,400),
            ('/routing-action',fields,{},400),
            ('/routing-action',fields,dict(headers,Origin='https://evil.example'),403),
            ('/s2s-action',fields,headers,410),
            ('/s2s-reverse-action',fields,headers,410),
        ]:
            with pytest.raises(urllib.error.HTTPError) as e:
                post(path,values,h)
            assert e.value.code==code
        assert len(calls)==count
        with pytest.raises(urllib.error.HTTPError) as e:
            urllib.request.urlopen(url+'/routing-state/other')
        assert e.value.code==404
    finally:
        httpd.shutdown();httpd.server_close();thread.join(2)


def test_unified_browser_modes_explicit_apply_sticky_and_mobile(tmp_path):
    if not shutil.which('node'):
        pytest.skip('Node required')
    html=panel.inject('<html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">'
        '<style>body{background:#101317;color:white;font:16px sans-serif;padding:16px}*{box-sizing:border-box}</style>'
        '</head><body><main>Original VPN</main></body></html>','fixture-token',unified=True)
    assert 'id="direct-sstp"' not in html
    script=r'''
const {chromium}=require('playwright'),assert=require('node:assert/strict');
const input=JSON.parse(require('node:fs').readFileSync(0,'utf8'));
(async()=>{const browser=await chromium.launch({headless:true,channel:'chrome'});try{
 const page=await browser.newPage({viewport:{width:1280,height:900}}),errors=[],requests=[];let fail=true,readFail=false;
 page.on('pageerror',e=>errors.push(e.message));const modes={nakhimova:'cenuta',fethiye:'local'};let previous=null;
 await page.route('http://127.0.0.1:19997/**',async route=>{
  const req=route.request(),path=new URL(req.url()).pathname;
  if(path==='/')return route.fulfill({contentType:'text/html; charset=utf-8',body:input.html});
  requests.push({path,method:req.method()});const f=new URLSearchParams(req.postData()||'');
  const site=path==='/routing-action'?f.get('site'):path.split('/').pop();assert.ok(['nakhimova','fethiye'].includes(site));
  const state=()=>({site,checked_at:Date.now()/1000,source_ready:true,error:null,outside_assignments:1,
   channels:Object.fromEntries(['local','cenuta','fornex','sstp_cenuta','sstp_fornex','direct'].map(k=>[k,{ready:true,state:'ready'}])),
   devices:[{id:'02:11:22:33:44:55',label:site==='nakhimova'?'Office <Laptop>':'MacBook Air',ip:site==='nakhimova'?'192.168.88.100':'192.168.89.197',online:site!=='nakhimova',mode:modes[site],pending:false,can_apply:true,can_rollback:site==='nakhimova'&&previous!==null,rollback_mode:previous,allowed_modes:site==='nakhimova'?['local','cenuta','fornex','sstp_cenuta','sstp_fornex','direct']:['local','direct'],revision:site+'-r'}]});
  if(req.method()==='GET')return readFail?route.fulfill({status:503,body:'Unavailable'}):route.fulfill({json:state()});
  assert.equal(path,'/routing-action');assert.equal(f.get('device'),'02:11:22:33:44:55');assert.equal(f.get('revision'),site+'-r');
  if(fail){fail=false;return route.fulfill({json:{...state(),success:false,operation_error:'Persistent operation error'}});}
  if(f.get('mode')==='rollback'){modes[site]=previous;previous=null;}else{previous=modes[site];modes[site]=f.get('mode');}
  return route.fulfill({json:{...state(),success:true,operation_message:'Routing assignment confirmed'}});
 });
 await page.goto('http://127.0.0.1:19997/#site-to-site');await page.locator('.routing-row select').waitFor();
 assert.equal(await page.locator('[data-site="nakhimova"]').getAttribute('aria-selected'),'true');
 assert.equal(await page.locator('.routing-row select option').count(),6);assert.equal(await page.locator('.routing-device strong').innerText(),'Office <Laptop>');
 assert.equal(await page.locator('option[value="cenuta"]').innerText(),'WG-Cenuta-RU');
 assert.equal(await page.locator('option[value="fornex"]').innerText(),'WG-Fornex-RU');
 assert.ok((await page.locator('.routing-device small').innerText()).includes('Offline'));assert.equal(await page.locator('.routing-apply').isDisabled(),true);
 await page.selectOption('.routing-row select','fornex');assert.equal(requests.filter(x=>x.method==='POST').length,0);
 await page.click('.routing-apply');await page.getByText('Persistent operation error',{exact:true}).waitFor();
 await page.click('#routing-refresh');await page.waitForFunction(()=>!document.getElementById('routing-refresh').disabled);
 assert.equal(await page.locator('#routing-message').innerText(),'Persistent operation error');
 await page.selectOption('.routing-row select','direct');await page.click('.routing-apply');await page.getByText('Routing assignment confirmed',{exact:true}).waitFor();
 assert.equal(await page.locator('.routing-current').innerText(),'Direct SSTP-RU via Fethiye');
 for(const [mode,text] of [['sstp_cenuta','SSTP-Cenuta-RU'],['sstp_fornex','SSTP-Fornex-RU']]){
  await page.selectOption('.routing-row select',mode);const before=requests.filter(x=>x.method==='POST').length;
  page.once('dialog',d=>d.dismiss());await page.click('.routing-apply');assert.equal(requests.filter(x=>x.method==='POST').length,before);
  page.once('dialog',d=>d.accept());await page.click('.routing-apply');await page.waitForFunction(t=>document.querySelector('.routing-current').textContent===t,text);
  assert.equal(await page.locator('.routing-undo').isDisabled(),false);
  page.once('dialog',d=>d.accept());await page.click('.routing-undo');await page.waitForFunction(()=>document.querySelector('.routing-current').textContent==='Direct SSTP-RU via Fethiye');
 }
 await page.screenshot({path:input.directory+'/routing-desktop.png'});
 await page.click('[data-site="fethiye"]');await page.waitForFunction(()=>document.querySelector('.routing-device strong')?.textContent==='MacBook Air');
 assert.equal(await page.locator('.routing-row select option').count(),2);assert.equal(await page.locator('#routing-feedback').isVisible(),false);
 await page.selectOption('.routing-row select','direct');await page.click('#routing-refresh');await page.waitForFunction(()=>!document.getElementById('routing-refresh').disabled);
 assert.equal(await page.locator('.routing-row select').inputValue(),'direct');
 await page.click('[data-site="nakhimova"]');await page.waitForFunction(()=>document.querySelector('.routing-device strong')?.textContent==='Office <Laptop>');
 assert.equal(await page.locator('#routing-message').innerText(),'Routing assignment confirmed');
 const count=requests.length;await page.clock.install();await page.clock.fastForward(120000);assert.equal(requests.length,count);
 await page.setViewportSize({width:390,height:844});assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth),false);
 const boxes=await page.locator('.routing-row select,.routing-apply').evaluateAll(nodes=>nodes.map(n=>{const r=n.getBoundingClientRect();return {x:r.x,right:r.right,bottom:r.bottom,top:r.top};}));
 assert.ok(boxes.every(b=>b.x>=0&&b.right<=390));await page.screenshot({path:input.directory+'/routing-mobile.png'});
 await page.click('#routing-dismiss');assert.equal(await page.locator('#routing-feedback').isVisible(),false);
 readFail=true;await page.click('#routing-refresh');await page.getByText('Status unavailable. Existing assignments are retained.',{exact:true}).waitFor();
 assert.equal(await page.locator('.routing-device strong').innerText(),'Office <Laptop>');assert.equal(await page.locator('.routing-row select').isDisabled(),true);
 await page.reload();await page.getByText('Status unavailable. Existing assignments are retained.',{exact:true}).waitFor();
 assert.equal(await page.locator('#routing-checked').innerText(),'Check failed');
 await page.click('a[href="#vpn"]');await page.locator('main').waitFor();assert.equal(await page.locator('#routing-panel').isVisible(),false);
 assert.deepEqual(errors,[]);
 }finally{await browser.close();}})().catch(e=>{console.error(e);process.exitCode=1});
'''
    result=subprocess.run(['node','-e',script],input=json.dumps(dict(html=html,directory=str(tmp_path))),
                          text=True,capture_output=True,timeout=60,env=os.environ)
    assert result.returncode==0,result.stdout+result.stderr


def test_browser_real_stage_progress_queue_failure_and_timer_cleanup(tmp_path):
    if not shutil.which('node'):
        pytest.skip('Node required')
    html=panel.inject('<html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">'
        '<style>body{background:#101317;color:white;font:16px sans-serif;padding:16px}*{box-sizing:border-box}</style>'
        '</head><body><main>Original VPN</main></body></html>','fixture-token',unified=True)
    script=r'''
const {chromium}=require('playwright'),assert=require('node:assert/strict');
const input=JSON.parse(require('node:fs').readFileSync(0,'utf8'));
(async()=>{const browser=await chromium.launch({headless:true,channel:'chrome'});try{
 const page=await browser.newPage({viewport:{width:1280,height:900}}),errors=[],ids=[];
 let checks=0,observations=0,observationFail=false,release;
 let phase={site:'nakhimova',state:'queued',completed:0,total:5,stage:null};
 const pending=new Promise(resolve=>release=resolve);
 page.on('pageerror',e=>errors.push(e.message));
 const state=()=>({site:'nakhimova',source_ready:true,error:null,checked_at:Date.now()/1000,outside_assignments:0,
  channels:{local:{ready:true}},devices:[{id:'02:11:22:33:44:55',label:'Office Laptop',ip:'192.168.88.100',online:true,
  mode:'local',pending:false,can_apply:true,allowed_modes:['local'],revision:'revision'}]});
 await page.route('http://127.0.0.1:19996/**',async route=>{
  const req=route.request(),path=new URL(req.url()).pathname;assert.equal(req.method(),'GET');
  if(path==='/')return route.fulfill({contentType:'text/html; charset=utf-8',body:input.html});
  if(path.startsWith('/routing-progress/')){observations++;assert.equal(path.split('/').pop(),ids.at(-1));
   return observationFail?route.fulfill({status:503,body:'Unavailable'}):route.fulfill({json:phase});}
  assert.equal(path,'/routing-state/nakhimova');checks++;
  const id=req.headers()['x-routing-poll'];assert.match(id,/^[0-9a-f]{32}$/);assert.ok(!ids.includes(id));ids.push(id);
  if(checks===1){await pending;return route.fulfill({status:500,json:{error:'Status unavailable',poll_progress:phase}});}
  return route.fulfill({json:{...state(),poll_progress:{...phase,state:'complete',completed:5}}});
 });
 await page.goto('http://127.0.0.1:19996/#site-to-site');
 await page.getByText('Waiting for another check or operation',{exact:true}).waitFor();
 assert.equal(await page.locator('#routing-poll-bar').getAttribute('value'),'0');
 assert.equal(await page.locator('#routing-poll-spinner').isVisible(),false);
 phase={...phase,state:'running',stage:'Checking Direct SSTP'};
 await page.getByText('Checking Direct SSTP',{exact:true}).waitFor();
 assert.equal(await page.locator('#routing-poll-spinner').isVisible(),true);
 await page.waitForFunction(()=>parseInt(document.getElementById('routing-poll-elapsed').textContent)>=2);
 assert.equal(await page.locator('#routing-poll-bar').getAttribute('value'),'0');
 phase={...phase,completed:1,stage:'Reading router configuration'};
 await page.waitForFunction(()=>document.getElementById('routing-poll-bar').value===1);
 assert.equal(await page.locator('#routing-poll-count').innerText(),'1 of 5 stages completed');
 assert.equal(await page.locator('#routing-poll-queue').isVisible(),false);
 await page.screenshot({path:input.directory+'/progress-desktop.png'});
 await page.setViewportSize({width:390,height:844});
 assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth),false);
 await page.screenshot({path:input.directory+'/progress-mobile.png'});
 observationFail=true;await page.getByText('Progress updates unavailable; status check is still running.',{exact:true}).waitFor();
 assert.equal(await page.locator('#routing-poll-bar').getAttribute('value'),'1');
 observationFail=false;phase={...phase,completed:3,stage:'Reading devices and assignments'};
 await page.waitForFunction(()=>document.getElementById('routing-poll-bar').value===3);
 phase={...phase,state:'error'};release();
 await page.getByText('Status check failed. Existing assignments are retained.',{exact:true}).waitFor();
 assert.equal(await page.locator('#routing-poll-spinner').isVisible(),false);
 assert.equal(await page.locator('#routing-poll-bar').getAttribute('value'),'3');
 await page.waitForFunction(()=>!document.getElementById('routing-refresh').disabled);
 const elapsed=await page.locator('#routing-poll-elapsed').innerText(),count=observations;
 await page.clock.install();await page.clock.fastForward(60000);
 assert.equal(await page.locator('#routing-poll-elapsed').innerText(),elapsed);assert.equal(observations,count);assert.equal(checks,1);
 await page.click('#routing-refresh');await page.getByText('Office Laptop',{exact:true}).waitFor();
 assert.equal(await page.locator('#routing-poll-bar').getAttribute('value'),'5');
 assert.equal(await page.locator('#routing-poll-stage-text').innerText(),'Poll completed');
 assert.equal(await page.locator('#routing-poll-spinner').isVisible(),false);assert.equal(checks,2);
 assert.equal(await page.locator('#routing-poll-error').isVisible(),false);assert.deepEqual(errors,[]);
 }finally{await browser.close();}})().catch(e=>{console.error(e);process.exitCode=1});
'''
    result=subprocess.run(['node','-e',script],input=json.dumps(dict(html=html,directory=str(tmp_path))),
                          text=True,capture_output=True,timeout=60,env=os.environ)
    assert result.returncode==0,result.stdout+result.stderr
