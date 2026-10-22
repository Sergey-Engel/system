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
