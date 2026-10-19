"""Loopback-only operator console for the reviewed uplink controllers."""
import argparse
from datetime import datetime, timezone
from http.cookies import SimpleCookie
import html
import ipaddress
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import math
import os
from pathlib import Path
import re
import secrets
import subprocess
import threading
import time
from urllib.parse import parse_qs, urlsplit

from .runtime import read_json
from .storage import current


CONTROLLERS = {
    'cenuta': '/usr/local/sbin/timeweb-cenuta-wg-console-transport',
    'fornex': '/usr/local/sbin/timeweb-fornex-wg-console-transport',
}
ACTIONS = {'native', 'backup'}
FLEX_CONTROLLER = '/usr/local/sbin/timeweb-flex-fleet'
FLEX_EXITS = {'fx', 'cen'}
FLEX_RU = {'on', 'off'}
FLEX_SCOPES = {'all', 'macbook', 'iphone12', 'macmini'}
HISTORY_LIMIT = 6
S2S_CONTROLLER = '/usr/local/sbin/timeweb-s2s'
S2S_MAC = re.compile(r'(?:[0-9A-F]{2}:){5}[0-9A-F]{2}')
S2S_REVISION = re.compile(r'[0-9a-f]{64}')
S2S_MAX_AGE = 45


def s2s_unavailable(error):
    return {'available': False, 'can_remove': False, 'revision': '', 'checked_at': 0,
            'tunnel': {'state': 'unknown', 'path': 'TimeWeb',
                       'egress': 'unknown', 'detail': ''},
            'devices': [], 'error': error}


def s2s_status(value):
    """Validate and project only the public controller contract."""
    def text(value, limit=512):
        return isinstance(value, str) and len(value) <= limit and not any(ord(c) < 32 for c in value)

    if not isinstance(value, dict):
        raise ValueError('invalid_s2s_output')
    tunnel, devices = value.get('tunnel'), value.get('devices')
    checked = value.get('checked_at')
    if (type(value.get('available')) is not bool or type(value.get('can_remove')) is not bool
            or not isinstance(value.get('revision'), str)
            or not S2S_REVISION.fullmatch(value['revision'])
            or type(checked) not in (int, float) or not math.isfinite(checked)
            or not 0 <= checked <= 253402300799
            or not isinstance(tunnel, dict)
            or tunnel.get('state') not in ('up', 'down', 'unknown')
            or tunnel.get('path') != 'TimeWeb'
            or tunnel.get('egress') not in ('route-ready', 'blocked', 'unknown')
            or not text(tunnel.get('detail'))
            or not isinstance(devices, list) or len(devices) > 1024
            or 'error' not in value
            or (value['error'] is not None and not text(value['error']))):
        raise ValueError('invalid_s2s_output')
    public_devices, seen = [], set()
    for device in devices:
        if (not isinstance(device, dict) or not isinstance(device.get('id'), str)
                or not S2S_MAC.fullmatch(device['id']) or device['id'] in seen
                or not text(device.get('label'), 128)
                or not text(device.get('ip'), 45)
                or type(device.get('online')) is not bool
                or type(device.get('selected')) is not bool
                or device.get('status') not in ('local', 'remote', 'blocked', 'pending', 'unknown')):
            raise ValueError('invalid_s2s_output')
        if device['ip']:
            ipaddress.ip_address(device['ip'])
        seen.add(device['id'])
        public_devices.append({key: device[key] for key in
                               ('id', 'label', 'ip', 'online', 'selected', 'status')})
    return {'available': value['available'], 'can_remove': value['can_remove'], 'revision': value['revision'],
            'checked_at': checked,
            'tunnel': {key: tunnel[key] for key in ('state', 'path', 'egress', 'detail')},
            'devices': public_devices, 'error': value['error']}

PAGE_STYLE = '''body{font:16px system-ui;margin:2rem;background:#101216;color:#e9ecf1}main{max-width:1100px;margin:auto}.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(320px,1fr));gap:1rem}.card{border:1px solid #4e5663;border-radius:6px;padding:1rem}.card h2{font-size:1.2rem;margin:0}.card-head{display:flex;align-items:center;justify-content:space-between;gap:1rem}.ok{border-top:4px solid #75c46b}.warn{border-top:4px solid #e7b94c}.error{border-top:4px solid #ef6666}.error-text{color:#ff8585;font-weight:600}dl{display:grid;grid-template-columns:110px 1fr;gap:.45rem;margin:1rem 0}dt{color:#aab2c0}dd{margin:0;overflow-wrap:anywhere}.info{display:inline-grid;place-items:center;width:1.45rem;height:1.45rem;border:1px solid #aab2c0;border-radius:50%;background:none;color:#cbd2da;cursor:pointer;font:inherit;font-size:.85rem}.details{border-top:1px solid #363d47;margin-top:1rem;padding-top:.65rem}.details summary{color:#cbd2da;cursor:pointer}.details dl{font-size:.88rem;margin:.7rem 0 0}.transport{border:0;margin:0;padding:0}.transport legend{color:#aab2c0;font-size:.88rem;margin-bottom:.45rem}.transport-options{display:inline-flex;border:1px solid #76808d;border-radius:5px;overflow:hidden}.transport-options label{display:block;min-width:5.5rem;text-align:center;padding:.48rem .85rem;cursor:pointer;background:#252a31}.transport-options label+input+label{border-left:1px solid #76808d}.transport-options input{position:absolute;opacity:0;width:1px;height:1px}.transport-options input:checked+label{background:#315b40;color:#f0fff0;font-weight:700}.transport-options input:focus-visible+label{outline:2px solid #b9d9ff;outline-offset:-3px}.transport-options input:disabled+label{opacity:.5;cursor:not-allowed}.transport-progress,.transport-error{margin:.45rem 0 0;font-size:.85rem}.transport-progress:empty,.transport-error:empty{display:none}.transport-progress{color:#b9d9ff}.transport-error{color:#ff8585}.failover-alert{color:#ff8585;font-size:.85rem;margin:.35rem 0}.flex{margin-top:1rem}.flex form{display:flex;gap:.6rem;align-items:end;flex-wrap:wrap}.flex label{display:grid;gap:.25rem;color:#aab2c0}select{padding:.5rem;background:#20242b;color:#e9ecf1;border:1px solid #4e5663}button{padding:.55rem .8rem}button:disabled{opacity:.45}.spinner{display:none;width:.8rem;height:.8rem;border:2px solid currentColor;border-right-color:transparent;border-radius:50%;margin-right:.45rem;vertical-align:-.1rem;animation:spin .7s linear infinite}button.executing .spinner{display:inline-block}.transport-progress .spinner{display:inline-block}@keyframes spin{to{transform:rotate(360deg)}}.activity{margin-top:1rem}.activity h2{font-size:1.2rem}.activity ol{list-style:none;padding:0;margin:0}.activity li{display:grid;grid-template-columns:210px 1fr auto;gap:.75rem;padding:.7rem 0;border-top:1px solid #363d47}.activity time,.activity .detail{color:#aab2c0}.activity time{white-space:nowrap}.activity .result{white-space:nowrap}.activity .failed{color:#ff8585}.activity .empty{color:#aab2c0}@media(max-width:650px){body{margin:1rem}.activity li{grid-template-columns:1fr;gap:.2rem}}'''
PAGE_STYLE += '''.health-indicator{position:relative;display:inline-flex;align-items:center;gap:.45rem;padding:.25rem .4rem;border-radius:4px;font-size:.85rem;font-weight:700;cursor:help}.health-indicator::before{content:"";width:.65rem;height:.65rem;border-radius:50%;background:currentColor}.ok .health-indicator{color:#85d47c}.warn .health-indicator{color:#f0c66e}.error .health-indicator{color:#ff8585}.health-indicator:focus-visible{outline:2px solid currentColor;outline-offset:2px}.health-indicator .health-tooltip{display:none;position:absolute;z-index:5;top:calc(100% + .4rem);right:0;width:max-content;max-width:min(20rem,80vw);padding:.5rem .65rem;border:1px solid #687382;border-radius:4px;background:#252a31;color:#e9ecf1;font-size:.8rem;font-weight:400;line-height:1.4;overflow-wrap:anywhere;white-space:normal;box-shadow:0 5px 16px #0008}.health-indicator:hover .health-tooltip,.health-indicator:focus .health-tooltip{display:block}'''
PAGE_STYLE += '''.flex{max-width:calc((1100px - 1rem)/2)}.flex .card{min-width:0}.flex form{display:flex;gap:1rem;align-items:start;flex-wrap:wrap}.flex .transport-options label{min-width:3.4rem}.flex .transport-options input:checked+label{background:#315b40;color:#f0fff0;font-weight:700}.flex-progress,.flex-error{margin:.45rem 0 0;font-size:.85rem}.flex-progress:empty,.flex-error:empty{display:none}.flex-progress{color:#b9d9ff}.flex-error{color:#ff8585}.flex-progress .spinner{display:inline-block}@media(max-width:720px){.flex{max-width:none}}'''
PAGE_STYLE += '''.flex{max-width:none}.flex-summary{color:#aab2c0;margin:.55rem 0 1rem}.flex-devices{border-top:1px solid #363d47;margin-top:1rem;padding-top:.7rem}.flex-devices summary{cursor:pointer;color:#cbd2da}.flex-device{display:grid;grid-template-columns:minmax(11rem,1fr) auto auto;gap:1rem;align-items:start;padding:.8rem 0;border-bottom:1px solid #363d47}.flex-device:last-child{border-bottom:0}.flex-device strong,.flex-device small{display:block}.flex-device small{color:#aab2c0}.flex-device .transport-options label{min-width:3rem}.flex-device .transport legend{font-size:.8rem}.flex-device-state{font-size:.85rem}.flex-device-state.active{color:#85d47c}.flex-device-state.inactive{color:#aab2c0}.flex-device-state.unknown{color:#ff8585}@media(max-width:720px){.flex-device{grid-template-columns:1fr}.flex form{gap:.55rem}}'''

PAGE_SCRIPT = '''let submitting=false;
let refreshTimer;
function showError(element,message){
  element.textContent=message;
  clearTimeout(element.errorTimer);
  element.errorTimer=setTimeout(()=>{element.textContent=''},10000);
}
async function refreshState(){
  if(submitting)return;
  if(location.hash==='#site-to-site')return refreshSiteToSite();
  clearTimeout(refreshTimer);
  const abort=new AbortController();
  const timeout=setTimeout(()=>abort.abort(),30000);
  try{
    const response=await fetch('/state',{cache:'no-store',signal:abort.signal});
    if(!response.ok)throw new Error('status request failed');
    const next=new DOMParser().parseFromString(await response.text(),'text/html');
    for(const oldCard of document.querySelectorAll('[data-upstream]')){
      const newCard=next.querySelector(`[data-upstream="${oldCard.dataset.upstream}"]`);
      if(!newCard)throw new Error('missing upstream');
      oldCard.className=newCard.className;
      oldCard.querySelector('.card-head').replaceWith(newCard.querySelector('.card-head'));
      oldCard.querySelector('.summary').replaceWith(newCard.querySelector('.summary'));
      oldCard.querySelector('.failover-alert')?.remove();
      oldCard.querySelector('.error-text')?.remove();
      const condition=newCard.querySelector('.error-text');
      if(condition)oldCard.querySelector('.summary').after(condition);
      const alert=newCard.querySelector('.failover-alert');
      if(alert)(oldCard.querySelector('.error-text')||oldCard.querySelector('.summary')).after(alert);
      const oldDetails=oldCard.querySelector('details');
      const open=oldDetails.open;
      oldDetails.replaceWith(newCard.querySelector('details'));
      oldCard.querySelector('details').open=open;
      const selected=newCard.querySelector('input[name="action"]:checked');
      oldCard.querySelector('form').dataset.mode=newCard.querySelector('form').dataset.mode;
      oldCard.querySelectorAll('input[name="action"]').forEach(input=>{
        input.checked=selected?.value===input.value;
        input.disabled=!selected;
      });
      const serverError=newCard.querySelector('.transport-error').textContent.trim();
      const oldError=oldCard.querySelector('.transport-error');
      if(serverError && serverError!==oldError.textContent)showError(oldError,serverError);
    }
    const oldFlex=document.querySelector('[data-flex]');
    const newFlex=next.querySelector('[data-flex]');
    if(!newFlex)throw new Error('missing FLEX route');
    oldFlex.className=newFlex.className;
    oldFlex.querySelector('.card-head').replaceWith(newFlex.querySelector('.card-head'));
    const flexDetailsOpen=oldFlex.querySelector('details').open;
    oldFlex.querySelector('.flex-summary').replaceWith(newFlex.querySelector('.flex-summary'));
    oldFlex.querySelector('details').replaceWith(newFlex.querySelector('details'));
    oldFlex.querySelector('details').open=flexDetailsOpen;
    oldFlex.querySelectorAll('input[type="radio"]').forEach(input=>{
      const current=newFlex.querySelector(`[id="${input.id}"]`);
      if(current){input.checked=current.checked;input.disabled=current.disabled;}
    });
    const activity=next.getElementById('activity');
    if(!activity)throw new Error('missing activity');
    const currentActivity=document.getElementById('activity');
    if(currentActivity.innerHTML!==activity.innerHTML)currentActivity.innerHTML=activity.innerHTML;
    document.getElementById('refresh-state').textContent=`Last update: ${new Date().toISOString().slice(11,19)} UTC`;
  }catch(_){document.getElementById('refresh-state').textContent='Refresh failed; retrying';}
  finally{clearTimeout(timeout);if(!submitting)refreshTimer=setTimeout(refreshState,15000);}
}
async function switchTransport(input){
  const form=input.form;
  const card=form.closest('[data-upstream]');
  const progress=card.querySelector('.transport-progress');
  const error=card.querySelector('.transport-error');
  if(submitting)return;
  const requested=input.value;
  form.querySelectorAll('input[name="action"]').forEach(radio=>radio.checked=radio.value===form.dataset.mode);
  submitting=true;
  clearTimeout(refreshTimer);
  progress.innerHTML='<span class="spinner" aria-hidden="true"></span>Switching…';
  form.querySelectorAll('input[name="action"]').forEach(radio=>radio.disabled=true);
  try{
    const body=new URLSearchParams(new FormData(form));
    body.set('action',requested);
    const response=await fetch('/action',{method:'POST',body,credentials:'same-origin',headers:{'Accept':'application/json','Content-Type':'application/x-www-form-urlencoded'},cache:'no-store'});
    if(!response.ok)throw new Error(`Request failed (${response.status})`);
    const result=await response.json();
    if(!result.success)throw new Error(result.error||'Switch not confirmed by controller');
  }catch(exc){showError(error,exc.message||'Switch failed');}
  finally{
    progress.textContent='';
    submitting=false;
    await refreshState();
  }
}
async function switchFlex(input){
  const form=input.form;
  const card=form.closest('[data-flex]');
  const progress=card.querySelector('.flex-progress');
  const error=card.querySelector('.flex-error');
  if(submitting)return;
  const body=new URLSearchParams({csrf:form.elements.csrf.value,
    scope:form.elements.scope.value,field:input.name,value:input.value});
  submitting=true;
  clearTimeout(refreshTimer);
  progress.innerHTML='<span class="spinner" aria-hidden="true"></span>Switching…';
  form.querySelectorAll('input[type="radio"]').forEach(radio=>radio.disabled=true);
  try{
    const response=await fetch('/flex-action',{method:'POST',body,credentials:'same-origin',headers:{'Accept':'application/json','Content-Type':'application/x-www-form-urlencoded'},cache:'no-store'});
    if(!response.ok)throw new Error(`Request failed (${response.status})`);
    const result=await response.json();
    if(!result.success)throw new Error(result.error||'Route change not confirmed by controller');
  }catch(exc){showError(error,exc.message||'Route change failed');}
  finally{
    progress.textContent='';
    submitting=false;
    await refreshState();
  }
}
document.addEventListener('DOMContentLoaded',()=>{
  if(location.search)history.replaceState(null,'',location.pathname+location.hash);
  document.querySelectorAll('.transport-error').forEach(error=>{
    if(error.textContent.trim())showError(error,error.textContent.trim());
  });
  refreshTimer=setTimeout(refreshState,15000);
});'''

PAGE_STYLE += '''[hidden]{display:none!important}.console-tabs{display:flex;gap:1.2rem;border-bottom:1px solid #4e5663;margin:1rem 0}.console-tabs a{color:#aab2c0;text-decoration:none;padding:.6rem .1rem;border-bottom:3px solid transparent}.console-tabs a[aria-selected="true"]{color:#e9ecf1;border-color:#85d47c}.s2s-status{display:flex;flex-wrap:wrap;gap:.7rem 2rem;padding:.6rem 0;border-bottom:1px solid #363d47;margin:0}.s2s-status div{min-width:8rem}.s2s-status dt{font-size:.8rem}.s2s-status dd{margin-top:.2rem}.s2s-detail{color:#aab2c0;font-size:.85rem;overflow-wrap:anywhere}.s2s-columns{display:grid;grid-template-columns:minmax(0,1fr) minmax(0,1fr);gap:2rem;margin-top:1.1rem}.s2s-columns h2{font-size:1rem;margin:0 0 .7rem}.s2s-add{display:flex;align-items:end;gap:.5rem}.s2s-add label{display:grid;gap:.35rem;min-width:0;flex:1;font-size:.85rem;color:#aab2c0}.s2s-add select{width:100%;min-width:0}.s2s-add button{flex-shrink:0;min-height:2.5rem}.s2s-selected{list-style:none;margin:0;padding:0}.s2s-selected li{display:grid;grid-template-columns:minmax(0,1fr) auto 2.5rem;align-items:center;gap:.65rem;border-bottom:1px solid #363d47;padding:.55rem 0;min-height:2.5rem}.s2s-selected strong,.s2s-selected small{display:block;overflow-wrap:anywhere}.s2s-selected small{color:#aab2c0;font-size:.8rem}.s2s-device-status{font-size:.85rem}.s2s-remove{width:2.5rem;height:2.5rem;padding:0;position:relative;background:none;color:#e9ecf1;border:1px solid #687382;border-radius:4px;cursor:pointer;font-size:1.15rem}.s2s-remove span{display:none;position:absolute;right:0;bottom:calc(100% + .3rem);width:max-content;max-width:70vw;padding:.4rem;background:#252a31;border:1px solid #687382;font-size:.8rem;z-index:5}.s2s-remove:hover span,.s2s-remove:focus-visible span{display:block}.s2s-error{color:#ff8585;overflow-wrap:anywhere}.s2s-message{min-height:1.4rem;font-size:.85rem;overflow-wrap:anywhere}.s2s-empty{color:#aab2c0;font-size:.85rem}@media(max-width:650px){.s2s-columns{grid-template-columns:1fr;gap:1.2rem}.s2s-status{gap:.7rem 1rem}.s2s-selected li{gap:.4rem}}'''

PAGE_SCRIPT += '''
let s2sData=null;
let s2sEpoch=0;
let s2sReadFailed=false;
function s2sFresh(){
  const age=Date.now()/1000-(s2sData?.checked_at||0);
  return age>=0 && age<=S2S_MAX_AGE;
}
function updateS2sControls(){
  const panel=document.getElementById('site-to-site');
  if(!panel)return;
  const usable=s2sData && /^[0-9a-f]{64}$/.test(s2sData.revision);
  const ready=usable && s2sData.available && !s2sReadFailed && !s2sData.error && s2sFresh()
    && s2sData.tunnel.state==='up' && s2sData.tunnel.egress==='route-ready';
  panel.querySelector('[name="device"]').disabled=submitting;
  panel.querySelector('.s2s-add button').disabled=submitting || !ready
    || !panel.querySelector('[name="device"]').value;
  panel.querySelectorAll('.s2s-remove').forEach(button=>button.disabled=submitting || !usable || !s2sData.can_remove);
  panel.querySelector('[data-s2s="availability"]').textContent=s2sReadFailed
    ? 'Unavailable' : !s2sData ? 'Not checked' : !s2sData.available
    ? 'Unavailable' : !s2sFresh() ? 'Stale' : 'Available';
}
function renderSiteToSite(data){
  const panel=document.getElementById('site-to-site');
  s2sData=data;
  const values={availability:data.available?'Available':'Unavailable',
    tunnel:data.tunnel.state,path:data.tunnel.path,egress:data.tunnel.egress,
    checked:data.checked_at?new Date(data.checked_at*1000).toISOString().replace('T',' ').replace('.000Z',' UTC'):'Not checked',
    detail:data.tunnel.detail,error:data.error||''};
  for(const [key,value] of Object.entries(values))panel.querySelector(`[data-s2s="${key}"]`).textContent=value;
  const select=panel.querySelector('[name="device"]');
  const choice=select.value;
  select.replaceChildren(new Option('Select a device',''));
  for(const device of data.devices.filter(device=>device.online && !device.selected)){
    select.add(new Option(`${device.label||device.id} - ${device.ip||'No IP'} - ${device.status}`,device.id));
  }
  select.value=Array.from(select.options).some(option=>option.value===choice)?choice:'';
  const list=panel.querySelector('.s2s-selected');
  list.replaceChildren();
  for(const device of data.devices.filter(device=>device.selected)){
    const row=document.createElement('li');
    const identity=document.createElement('div');
    const label=document.createElement('strong');
    label.textContent=device.label||device.id;
    const address=document.createElement('small');
    address.textContent=`${device.ip||'No IP'} · ${device.id} · ${device.online?'Online':'Offline'}`;
    identity.append(label,address);
    const status=document.createElement('span');
    status.className='s2s-device-status';
    status.textContent=device.status;
    const remove=document.createElement('button');
    remove.type='button';remove.className='s2s-remove';
    remove.title='Return to local internet';
    remove.setAttribute('aria-label',`Return to local internet: ${device.label||device.id}`);
    remove.append(document.createTextNode('×'));
    const tooltip=document.createElement('span');
    tooltip.textContent='Return to local internet';tooltip.setAttribute('aria-hidden','true');
    remove.append(tooltip);
    remove.onclick=()=>s2sAction('remove',device.id);
    row.append(identity,status,remove);list.append(row);
  }
  panel.querySelector('.s2s-empty').hidden=list.children.length>0;
  updateS2sControls();
}
async function refreshSiteToSite(){
  if(submitting || location.hash!=='#site-to-site')return;
  clearTimeout(refreshTimer);
  const epoch=++s2sEpoch;
  const abort=new AbortController();
  const timeout=setTimeout(()=>abort.abort(),130000);
  try{
    const response=await fetch('/s2s-state',{cache:'no-store',signal:abort.signal});
    if(!response.ok)throw new Error(`Status request failed (${response.status})`);
    const data=await response.json();
    if(submitting || epoch!==s2sEpoch || location.hash!=='#site-to-site')return;
    s2sReadFailed=false;
    renderSiteToSite(data);
  }catch(exc){
    if(!submitting && epoch===s2sEpoch){
      s2sReadFailed=true;
      document.querySelector('[data-s2s="error"]').textContent=exc.message||'Site-to-site refresh failed';
      updateS2sControls();
    }
  }finally{
    clearTimeout(timeout);
    if(!submitting && epoch===s2sEpoch && location.hash==='#site-to-site')refreshTimer=setTimeout(refreshState,15000);
  }
}
async function s2sAction(action,device){
  if(submitting || !s2sData)return;
  const panel=document.getElementById('site-to-site');
  const message=panel.querySelector('.s2s-message');
  const body=new URLSearchParams({csrf:panel.querySelector('[name="csrf"]').value,
    action,device,revision:s2sData.revision});
  submitting=true;++s2sEpoch;clearTimeout(refreshTimer);
  message.classList.remove('s2s-error');message.textContent=action==='add'?'Adding device...':'Returning device to local internet...';
  updateS2sControls();
  const abort=new AbortController();
  const timeout=setTimeout(()=>abort.abort(),130000);
  try{
    const response=await fetch('/s2s-action',{method:'POST',body,signal:abort.signal,
      credentials:'same-origin',headers:{'Accept':'application/json','Content-Type':'application/x-www-form-urlencoded'},cache:'no-store'});
    if(!response.ok)throw new Error(`Request failed (${response.status})`);
    const result=await response.json();
    s2sReadFailed=false;
    renderSiteToSite(result);
    if(result.success!==true)throw new Error(result.error||'Change not confirmed by controller');
    message.textContent='Change confirmed';
  }catch(exc){s2sReadFailed=true;message.classList.add('s2s-error');message.textContent=exc.message||'Site-to-site change failed';}
  finally{
    clearTimeout(timeout);submitting=false;updateS2sControls();
    await refreshState();
  }
}
function selectConsoleTab(initial=false){
  const active=location.hash==='#site-to-site';
  ++s2sEpoch;clearTimeout(refreshTimer);
  document.getElementById('vpn').hidden=active;
  document.getElementById('site-to-site').hidden=!active;
  document.querySelectorAll('[role="tab"]').forEach(tab=>{
    tab.setAttribute('aria-selected',String(tab.hash===(active?'#site-to-site':'#vpn')));
  });
  if(!submitting){
    if(active || !initial)refreshState();
    else refreshTimer=setTimeout(refreshState,15000);
  }
}
document.addEventListener('DOMContentLoaded',()=>{
  window.addEventListener('hashchange',()=>selectConsoleTab());
  document.querySelector('.s2s-add').addEventListener('submit',event=>{
    event.preventDefault();
    updateS2sControls();
    if(!event.target.querySelector('button').disabled)s2sAction('add',event.target.elements.device.value);
  });
  document.querySelector('.s2s-add select').addEventListener('change',updateS2sControls);
  setInterval(updateS2sControls,1000);
  selectConsoleTab(true);
});'''.replace('S2S_MAX_AGE', str(S2S_MAX_AGE))


def s2s_panel(csrf):
    return f'''<section id="site-to-site" role="tabpanel" aria-labelledby="s2s-tab" hidden>
      <h2>Fethiye → Nakhimova</h2>
      <dl class="s2s-status">
        <div><dt>Status</dt><dd data-s2s="availability">Not checked</dd></div>
        <div><dt>Tunnel</dt><dd data-s2s="tunnel">unknown</dd></div>
        <div><dt>Path</dt><dd data-s2s="path">TimeWeb</dd></div>
        <div><dt>Last checked</dt><dd data-s2s="checked">Not checked</dd></div>
        <div><dt>Egress readiness</dt><dd data-s2s="egress">unknown</dd></div>
      </dl>
      <p class="s2s-detail" data-s2s="detail"></p><p class="s2s-error" data-s2s="error" role="status"></p>
      <div class="s2s-columns"><section><h2>Available devices</h2>
        <form class="s2s-add"><input type="hidden" name="csrf" value="{html.escape(csrf, quote=True)}">
          <label>Device<select name="device"><option value="">Select a device</option></select></label>
          <button type="submit" disabled><span aria-hidden="true">+</span> Add</button>
        </form></section><section><h2>Internet via Nakhimova</h2>
        <ul class="s2s-selected"></ul><p class="s2s-empty">No devices selected</p>
      </section></div><p class="s2s-message" role="status" aria-live="polite"></p>
    </section>'''


def age(value):
    if not isinstance(value, (int, float)) or value < 0:
        return 'no data'
    if value < 60:
        return f'{value:.0f} s'
    if value < 3600:
        return f'{value / 60:.1f} min'
    return f'{value / 3600:.1f} h'


class Console:
    def __init__(self, database, state_dir, *, runner=subprocess.run, clock=time.time):
        self.database = Path(database)
        self.state_dir = Path(state_dir)
        self.runner, self.clock = runner, clock
        self.lock = threading.Lock()
        self._view_cache = None
        self._view_time = 0
        self._s2s_lock = threading.Lock()
        self._s2s_cache = None
        self._s2s_time = 0
        self.audit_path = self.state_dir / 'console-actions.jsonl'

    def _s2s_controller(self, action='status', device=None, revision=None):
        args = [S2S_CONTROLLER, action]
        if action != 'status':
            args.extend((device, revision))
        try:
            result = self.runner(args, text=True, capture_output=True, timeout=125, check=False)
            if result.returncode != 0:
                return s2s_unavailable('Site-to-site controller failed'), False
            if len(result.stdout) > 1048576:
                raise ValueError('oversized_s2s_output')
            raw = json.loads(result.stdout)
            value = s2s_status(raw)
            confirmed = raw.get('success') is True and (
                value['available'] and value['error'] is None if action == 'add' else value['can_remove'])
            return value, confirmed
        except subprocess.TimeoutExpired:
            return s2s_unavailable('Site-to-site controller timed out'), False
        except (OSError, subprocess.SubprocessError):
            return s2s_unavailable('Site-to-site controller unavailable'), False
        except (ValueError, TypeError, OverflowError, RecursionError):
            return s2s_unavailable('Invalid site-to-site controller output'), False

    def s2s_view(self):
        # Keep router reads independent of the existing VPN view and its lock.
        with self._s2s_lock:
            if self._s2s_cache is None or time.monotonic() - self._s2s_time >= 15:
                value, _ = self._s2s_controller()
                self._s2s_cache = self._retain_s2s_selection(value)
                self._s2s_time = time.monotonic()
            return self._s2s_cache

    def _retain_s2s_selection(self, value):
        if not value['revision'] and self._s2s_cache:
            value = dict(value, devices=[dict(d, status='unknown', online=False)
                                        for d in self._s2s_cache['devices'] if d['selected']])
            value['tunnel'] = dict(value['tunnel'], detail='Last known selection; controller status unavailable')
        return value

    def s2s_action(self, action, device, revision):
        if (action not in ('add', 'remove') or not isinstance(device, str)
                or not S2S_MAC.fullmatch(device) or not isinstance(revision, str)
                or not S2S_REVISION.fullmatch(revision)):
            raise ValueError('invalid_s2s_request')
        with self._s2s_lock:
            after, confirmed = self._s2s_controller(action, device, revision)
            after = self._retain_s2s_selection(after)
            observed = next((item for item in after['devices'] if item['id'] == device), None)
            matches = (observed is not None and observed['selected']
                       and observed['status'] == 'remote') if action == 'add' else (
                           observed is None or not observed['selected'])
            success = confirmed and matches
            self._s2s_cache = after
            self._s2s_time = time.monotonic()
            return dict(after, success=success, error=None if success else (
                after['error'] or 'Site-to-site controller did not confirm the requested state'))

    def view(self):
        # Share expensive controller reads across tabs and serialize with writes.
        with self.lock:
            if self._view_cache is None or time.monotonic() - self._view_time >= 5:
                upstreams = self.snapshot()
                flex_data = self.flex_controller()
                self._view_cache = (upstreams, flex_data)
                self._view_time = time.monotonic()
            return self._view_cache

    def controller(self, upstream, action='status'):
        if upstream not in CONTROLLERS or action not in ACTIONS | {'status'}:
            raise ValueError('invalid_controller_request')
        attempts = 3 if action == 'status' else 1
        error = 'controller_unavailable'
        for attempt in range(attempts):
            try:
                result = self.runner([CONTROLLERS[upstream], action], text=True,
                                     capture_output=True, timeout=12 if action == 'status' else 35,
                                     check=False)
            except subprocess.TimeoutExpired:
                error = 'controller_timeout'
                result = None
            except (OSError, subprocess.SubprocessError):
                error = 'controller_exec_failed'
                result = None
            if result is not None and result.returncode == 0:
                fields = dict(item.split('=', 1) for item in result.stdout.split() if '=' in item)
                mode = fields.get('mode')
                if mode in ('native', 'backup', 'partial'):
                    return {'mode': mode, 'endpoint': fields.get('endpoint', 'no data'),
                            'relay_mode': fields.get('relay_mode', mode if mode != 'partial' else 'no data'),
                            'xray_mode': fields.get('xray_mode', 'no data'),
                            'xray_endpoint': fields.get('xray_endpoint', 'no data'),
                            'handshake_age': fields.get('handshake_age'), 'ok': True,
                            'error': None}
                error = 'invalid_controller_output'
            elif result is not None:
                error = f'controller_exit_{result.returncode}'
            if attempt + 1 < attempts:
                time.sleep(0.2)
        return {'mode': 'unavailable', 'endpoint': 'no data', 'relay_mode': 'no data',
                'xray_mode': 'no data', 'xray_endpoint': 'no data',
                'ok': False, 'error': error}

    def state(self, upstream):
        try:
            value = read_json(self.state_dir / f'{upstream}-auto-failover.json')
            return {'reason': value.get('last_reason', 'no data'),
                    'failures': value.get('consecutive_failures', 0),
                    'last_switch': value.get('last_switch_unix', 0)}
        except (OSError, ValueError, TypeError):
            return {'reason': 'no data', 'failures': 0, 'last_switch': 0}

    def recent_actions(self):
        try:
            with self.audit_path.open('rb') as log:
                log.seek(0, os.SEEK_END)
                start = max(0, log.tell() - 65536)
                log.seek(start)
                if start:
                    log.readline()
                lines = log.readlines()
        except OSError:
            return []
        actions = []
        for line in reversed(lines):
            if len(line) > 8192:
                continue
            try:
                entry = json.loads(line)
            except (ValueError, UnicodeDecodeError):
                continue
            if isinstance(entry, dict) and entry.get('upstream') in (*CONTROLLERS, 'flex-macbook', 'flex-fleet'):
                actions.append(entry)
                if len(actions) == HISTORY_LIMIT:
                    break
        return actions

    def snapshot(self):
        try:
            observed = current(self.database, self.clock())
        except Exception:
            observed = {}
        return {upstream: {'monitor': observed.get(upstream, {}),
                           'controller': self.controller(upstream),
                           'auto': self.state(upstream)} for upstream in CONTROLLERS}

    def flex_controller(self, scope=None, field=None, value=None):
        if scope is None and field is None and value is None:
            args = [FLEX_CONTROLLER, 'status']
        elif (scope in FLEX_SCOPES and field in ('exit', 'ru_direct')
              and value in (FLEX_EXITS if field == 'exit' else FLEX_RU) | {'default'}
              and not (scope == 'all' and value == 'default')):
            args = [FLEX_CONTROLLER, 'set', scope, field, value]
        else:
            raise ValueError('invalid_flex_request')
        try:
            result = self.runner(args, text=True, capture_output=True, timeout=110, check=False)
            if result.returncode == 0:
                value = json.loads(result.stdout)
                if (value.get('default', {}).get('exit') in FLEX_EXITS
                        and value.get('default', {}).get('ru_direct') in FLEX_RU
                        and set(value.get('devices', {})) == {'macbook', 'iphone12', 'macmini'}):
                    return value
        except (OSError, subprocess.SubprocessError, ValueError, TypeError):
            pass
        return {'default': {'exit': None, 'ru_direct': None}, 'devices': {},
                'counts': {'active': 0, 'inactive': 0, 'unknown': 2, 'total': 2, 'route_ready': 0}}

    def flex_action(self, scope, field, value):
        if (scope not in FLEX_SCOPES or field not in ('exit', 'ru_direct')
                or value not in ((FLEX_EXITS if field == 'exit' else FLEX_RU) | {'default'})
                or (scope == 'all' and value == 'default')):
            raise ValueError('invalid_flex_request')
        with self.lock:
            self._view_cache = None
            after = self.flex_controller(scope, field, value)
            success = bool(after['devices']) and all(d['route'] == 'ready' for d in after['devices'].values())
            expected = (after['default'][field] if scope == 'all'
                        else after['devices'].get(scope, {}).get('overrides', {}).get(field))
            success = success and expected == (None if value == 'default' else value)
            entry = {'timestamp': self.clock(), 'upstream': 'flex-fleet',
                     'requested': {'scope': scope, 'field': field, 'value': value},
                     'after': after, 'success': success,
                     'error': None if success else 'Fleet controller did not confirm the requested state'}
            fd = os.open(self.audit_path, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o600)
            try:
                os.write(fd, (json.dumps(entry, separators=(',', ':')) + '\n').encode())
            finally:
                os.close(fd)
            return entry

    def action(self, upstream, action):
        if upstream not in CONTROLLERS or action not in ACTIONS:
            raise ValueError('invalid_action')
        with self.lock:
            before = self.controller(upstream)
            self._view_cache = None
            command = self.controller(upstream, action)
            observed = self.controller(upstream)
            expected = 'backup' if action == 'backup' else 'native'
            success = observed['ok'] and observed['mode'] == expected
            if success:
                error = None
            elif not observed['ok']:
                error = f'Read-back unavailable ({observed["error"]}); controller: {command["error"] or command["mode"]}'
            else:
                error = f'Expected {expected}, observed {observed["mode"]}; controller: {command["error"] or command["mode"]}'
            entry = {'timestamp': self.clock(), 'upstream': upstream, 'action': action,
                     'before_mode': before['mode'], 'result_mode': observed['mode'],
                     'command_mode': command['mode'], 'command_error': command['error'],
                     'success': success, 'error': error}
            fd = os.open(self.audit_path, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o600)
            try:
                os.write(fd, (json.dumps(entry, separators=(',', ':')) + '\n').encode())
            finally:
                os.close(fd)
            return entry


def card(upstream, data, csrf, recent_error=None):
    monitor, controller, auto = data['monitor'], data['controller'], data['auto']
    assessment = monitor.get('assessment', {}) if isinstance(monitor, dict) else {}
    mode = controller['mode']
    health = str(monitor.get('state', 'UNKNOWN'))
    klass = ('error' if mode in ('partial', 'unavailable') or health in ('DOWN', 'UNKNOWN', 'FAILED')
             else 'ok' if health == 'UP' else 'warn')
    available = mode in ('native', 'backup')
    choices = ''.join(
        f'<input type="radio" id="{upstream}-{action}" name="action" value="{action}"'
        f'{" checked" if mode == action else ""}{"" if available else " disabled"}'
        f' onchange="switchTransport(this)"><label for="{upstream}-{action}">{label}</label>'
        for action, label in (('native', 'UDP'), ('backup', 'WSS'))
    )
    reason = str(auto['reason'])
    alert = (f'<p class="failover-alert">Failover: {html.escape(reason)}</p>'
             if reason not in ('criteria_not_met', 'already_backup', 'disabled', 'no data') else '')
    condition = (f'<p class="error-text">{html.escape(mode.upper())}</p>'
                 if mode in ('partial', 'unavailable') else '')
    status_label = ('PARTIAL' if mode == 'partial' else 'UNAVAILABLE' if mode == 'unavailable'
                    else 'UP' if klass == 'ok' else 'DEGRADED' if klass == 'warn' else health)
    status_detail = f'Monitoring: {health}: {monitor.get("reason", "no_data")}; transport: {mode}'
    if controller.get('error'):
        status_detail += f'; controller: {controller["error"]}'
    path_label = {'native': 'UDP', 'backup': 'WSS', 'custom': 'CUSTOM'}
    relay_path = path_label.get(controller.get('relay_mode', mode), 'UNKNOWN')
    xray_path = path_label.get(controller.get('xray_mode'), 'UNKNOWN')
    error_text = html.escape(str(recent_error.get('error') or 'Switch not confirmed')) if recent_error else ''
    return f'''<section class="card {klass}" data-upstream="{upstream}">
      <div class="card-head"><h2>{html.escape(upstream.title())}</h2><span class="health-indicator" tabindex="0" aria-label="{html.escape(status_detail, quote=True)}">{html.escape(status_label)}<span class="health-tooltip" aria-hidden="true">{html.escape(status_detail)}</span></span></div>
      <dl class="summary"><dt>Handshake</dt><dd>{age(assessment.get('handshake_age'))}</dd></dl>{condition}{alert}
      <form method="post" action="/action" data-mode="{html.escape(mode)}" onsubmit="return false">
        <input type="hidden" name="csrf" value="{csrf}"><input type="hidden" name="upstream" value="{upstream}">
        <fieldset class="transport"><legend>Backend transport</legend><div class="transport-options">{choices}</div></fieldset>
      </form><p class="transport-progress" role="status"></p><p class="transport-error" role="alert">{error_text}</p>
      <details class="details"><summary>Details</summary><dl><dt>WG path</dt><dd>{relay_path}</dd><dt>Xray path</dt><dd>{xray_path}</dd><dt>Endpoint</dt><dd>{html.escape(str(controller['endpoint']))}</dd>
      <dt>Xray endpoint</dt><dd>{html.escape(str(controller['xray_endpoint']))}</dd>
      <dt>Failover</dt><dd>{html.escape(reason)}; confirmations: {html.escape(str(auto['failures']))}</dd></dl></details></section>'''


def flex_card(data, csrf):
    counts = data['counts']
    available = bool(data['devices']) and counts['route_ready'] == counts['total']

    def options(scope, field, selected, inherit=False):
        values = ([('default', 'Default')] if inherit else [])
        values += [('fx', 'Fornex'), ('cen', 'Cenuta')] if field == 'exit' else [('off', 'OFF'), ('on', 'ON')]
        legend = 'Gateway' if field == 'exit' else 'RU-direct'
        choices = ''
        for value, label in values:
            element_id = f'flex-{scope}-{field}-{value}'
            choices += (f'<input type="radio" id="{element_id}" name="{field}" value="{value}"'
                        f'{" checked" if value == selected else ""}{"" if available else " disabled"}'
                        f' onchange="switchFlex(this)"><label for="{element_id}">{label}</label>')
        return f'<fieldset class="transport"><legend>{legend}</legend><div class="transport-options">{choices}</div></fieldset>'

    def form(scope, exit_value, ru_value, inherit=False):
        return (f'<form method="post" action="/flex-action" onsubmit="return false">'
                f'<input type="hidden" name="csrf" value="{csrf}">'
                f'<input type="hidden" name="scope" value="{scope}">'
                f'{options(scope, "exit", exit_value, inherit)}'
                f'{options(scope, "ru_direct", ru_value, inherit)}</form>')

    rows = []
    for device, info in data['devices'].items():
        overrides = info['overrides']
        activity = info['activity']
        state = activity['state']
        age_text = (f'{activity["age_seconds"]} s since Xray access'
                    if activity['age_seconds'] is not None else 'no recent Xray access')
        route = info['route']
        effective = info['effective']
        rows.append(f'''<div class="flex-device" data-device="{device}">
          <div><strong>{html.escape(info['label'])}</strong><small>{html.escape(info['peer'])} · effective: {effective['exit'].upper()}, RU {effective['ru_direct'].upper()}</small>
          <span class="flex-device-state {state}">{state.upper()} · route {route} · {html.escape(age_text)}</span></div>
          {form(device, overrides['exit'] or 'default', overrides['ru_direct'] or 'default', True)}
        </div>''')
    summary = (f'{counts["active"]} active · {counts["inactive"]} inactive · '
               f'{counts["unknown"]} unknown · {counts["route_ready"]}/{counts["total"]} routes ready')
    health = 'READY' if available else 'UNAVAILABLE'
    return f'''<section class="card {'ok' if available else 'error'}" data-flex>
      <div class="card-head"><h2>SOCKS-TW-FLEX</h2><span class="health-indicator" tabindex="0" aria-label="{html.escape(summary, quote=True)}">{health}<span class="health-tooltip" aria-hidden="true">{html.escape(summary)}</span></span></div>
      <p class="flex-summary">{html.escape(summary)}</p>
      {form('all', data['default']['exit'], data['default']['ru_direct'])}
      <p class="flex-progress" role="status"></p><p class="flex-error" role="alert"></p>
      <details class="flex-devices"><summary>Devices ({counts['total']})</summary>{''.join(rows)}</details></section>'''


def activity_section(actions):
    rows = []
    for entry in actions:
        try:
            moment = datetime.fromtimestamp(float(entry['timestamp']), timezone.utc)
        except (KeyError, ValueError, TypeError, OverflowError):
            continue
        upstream = entry['upstream']
        if upstream in CONTROLLERS:
            action = entry.get('action')
            if action not in ACTIONS:
                continue
            requested = 'WSS' if action == 'backup' else 'native UDP'
            command = f'{upstream.title()}: switch to {requested}'
            detail = f"Observed: {entry.get('before_mode', 'unknown')} -> {entry.get('result_mode', 'unknown')}"
            if entry.get('error'):
                detail += f"; Error: {entry['error']}"
            elif entry.get('command_error'):
                detail += f"; Controller report: {entry['command_error']}; mode verified by read-back"
            elif entry.get('success') is False:
                detail += '; Error: not recorded in this legacy entry'
        elif upstream == 'flex-fleet':
            requested = entry.get('requested', {})
            if not isinstance(requested, dict):
                continue
            scope = {'all': 'All devices', 'macbook': 'MacBook', 'iphone12': 'iPhone 12',
                     'macmini': 'Mac Mini'}.get(requested.get('scope'), 'FLEX')
            field = {'exit': 'Gateway', 'ru_direct': 'RU-direct'}.get(requested.get('field'), 'setting')
            command = f'{scope}: {field} {requested.get("value", "unknown")}'
            detail = entry.get('error') or 'Controller read-back verified'
        else:
            requested = entry.get('requested', {})
            after = entry.get('after', {})
            if not isinstance(requested, dict) or not isinstance(after, dict):
                continue
            exit_name = {'fx': 'Fornex', 'cen': 'Cenuta'}.get(requested.get('exit'), 'unknown')
            ru_name = 'ON' if requested.get('ru_direct') is True else 'OFF' if requested.get('ru_direct') is False else 'unknown'
            observed_exit = {'fx': 'Fornex', 'cen': 'Cenuta'}.get(after.get('exit'), 'unavailable')
            observed_ru = 'ON' if after.get('ru_direct') is True else 'OFF' if after.get('ru_direct') is False else 'unavailable'
            command = f'MacBook SOCKS: exit {exit_name}, RU-direct {ru_name}'
            detail = f'Observed: exit {observed_exit}, RU-direct {observed_ru}'
        confirmed = entry.get('success') is True
        outcome = 'Confirmed' if confirmed else 'Not confirmed'
        result_class = '' if confirmed else ' failed'
        rows.append(f'<li><time datetime="{moment.isoformat()}">{moment:%Y-%m-%d %H:%M:%S} UTC</time>'
                    f'<span><strong>{html.escape(command)}</strong><br><span class="detail">{html.escape(detail)}</span></span>'
                    f'<span class="result{result_class}">{outcome}</span></li>')
    content = '<ol>' + ''.join(rows) + '</ol>' if rows else '<p class="empty">No commands recorded.</p>'
    return f'<section class="activity" id="activity" aria-live="polite"><h2>Recent commands</h2>{content}</section>'


def make_server(database, state_dir, port=19108, console=None):
    console = console or Console(database, state_dir)

    class Handler(BaseHTTPRequestHandler):
        server_version = 'UplinkConsole/1.0'

        def log_message(self, *_):
            pass

        def token(self):
            cookie = SimpleCookie(self.headers.get('Cookie'))
            value = cookie.get('uplink_console_csrf')
            return value.value if value and len(value.value) >= 32 else None

        def reply(self, code, body, *, headers=()):
            payload = body.encode()
            self.send_response(code)
            self.send_header('Content-Type', 'text/html; charset=utf-8')
            self.send_header('Content-Length', str(len(payload)))
            self.send_header('Cache-Control', 'no-store')
            self.send_header('Content-Security-Policy', "default-src 'self'; style-src 'self' 'unsafe-inline'; script-src 'self' 'unsafe-inline'; base-uri 'none'; frame-ancestors 'none'")
            self.send_header('X-Frame-Options', 'DENY')
            self.send_header('Referrer-Policy', 'no-referrer')
            for key, value in headers:
                self.send_header(key, value)
            self.end_headers()
            self.wfile.write(payload)

        def reply_json(self, code, value):
            payload = json.dumps(value).encode()
            self.send_response(code)
            self.send_header('Content-Type', 'application/json; charset=utf-8')
            self.send_header('Content-Length', str(len(payload)))
            self.send_header('Cache-Control', 'no-store')
            self.send_header('X-Content-Type-Options', 'nosniff')
            self.send_header('Referrer-Policy', 'no-referrer')
            self.end_headers()
            self.wfile.write(payload)

        def allowed_host(self):
            host = self.headers.get('Host', '')
            name, separator, local_port = host.partition(':')
            return (name in ('127.0.0.1', 'localhost') and separator == ':' and
                    local_port.isdecimal() and 1 <= int(local_port) <= 65535)

        def allowed_origin(self):
            origin = self.headers.get('Origin')
            # Chromium may serialize a loopback page opened through an SSH
            # forward as an opaque origin ("null"). CSRF remains mandatory,
            # so this is equivalent to a missing Origin, not a cross-origin grant.
            return origin in (None, '', 'null') or origin == f'http://{self.headers.get("Host", "")}'

        def do_GET(self):
            path = urlsplit(self.path).path
            if not self.allowed_host() or path not in ('/', '/state', '/s2s-state'):
                self.reply(404, 'Not found')
                return
            if path == '/s2s-state':
                self.reply_json(200, console.s2s_view())
                return
            csrf, headers = self.token(), []
            if csrf is None:
                csrf = secrets.token_urlsafe(32)
                headers.append(('Set-Cookie', f'uplink_console_csrf={csrf}; Path=/; HttpOnly; SameSite=Strict'))
            actions = console.recent_actions()
            latest = {}
            for entry in actions:
                latest.setdefault(entry['upstream'], entry)
            recent_errors = {
                upstream: entry for upstream, entry in latest.items()
                if upstream in CONTROLLERS and entry.get('success') is False
                and isinstance(entry.get('timestamp'), (int, float))
                and 0 <= console.clock() - entry['timestamp'] < 10
            }
            upstreams, flex_data = console.view()
            content = (f'<div class="grid">{''.join(card(up, data, csrf, recent_errors.get(up)) for up, data in upstreams.items())}</div>'
                       f'<div class="flex">{flex_card(flex_data, csrf)}</div>'
                       f'{activity_section(actions)}')
            if path == '/state':
                self.reply(200, content, headers=headers)
                return
            body = (f'<!doctype html><html lang="en"><meta charset="utf-8">'
                    f'<meta name="viewport" content="width=device-width,initial-scale=1">'
                    f'<title>TimeWeb: VPN control</title><style>{PAGE_STYLE}</style>'
                    f'<script>{PAGE_SCRIPT}</script><main><h1>TimeWeb: VPN control</h1>'
                    f'<p>Loopback-only console. Background refresh: 15 s. '
                    f'<span id="refresh-state" role="status"></span></p>'
                    f'<nav class="console-tabs" role="tablist" aria-label="Console">'
                    f'<a id="vpn-tab" href="#vpn" role="tab" aria-controls="vpn" aria-selected="true">VPN</a>'
                    f'<a id="s2s-tab" href="#site-to-site" role="tab" aria-controls="site-to-site" aria-selected="false">Site-to-site</a></nav>'
                    f'<section id="vpn" role="tabpanel" aria-labelledby="vpn-tab">{content}</section>'
                    f'{s2s_panel(csrf)}</main></html>')
            self.reply(200, body, headers=headers)

        def do_POST(self):
            path = urlsplit(self.path).path
            if not self.allowed_host() or path not in ('/action', '/flex-action', '/s2s-action'):
                print(json.dumps({'event': 'console_post_rejected', 'reason': 'host_or_path',
                                  'host': self.headers.get('Host', '')[:128],
                                  'path': urlsplit(self.path).path[:128]}), flush=True)
                self.reply(404, 'Not found')
                return
            # Browser form navigations may omit Origin, especially when the page
            # intentionally suppresses Referer. The unguessable same-site CSRF
            # token remains mandatory; an Origin supplied by a browser must match.
            if not self.allowed_origin():
                print(json.dumps({'event': 'console_post_rejected', 'reason': 'origin',
                                  'host': self.headers.get('Host', '')[:128],
                                  'origin': self.headers.get('Origin', '')[:128]}), flush=True)
                self.reply(403, 'Forbidden')
                return
            try:
                length = int(self.headers.get('Content-Length', '0'))
                if not 0 < length <= 512:
                    raise ValueError('invalid_length')
                fields = parse_qs(self.rfile.read(length).decode(), max_num_fields=4)
                expected = {'csrf', 'upstream', 'action'} if path == '/action' else {'csrf', 'scope', 'field', 'value'}
                if path == '/s2s-action':
                    expected = {'csrf', 'action', 'device', 'revision'}
                if set(fields) != expected or any(len(v) != 1 for v in fields.values()):
                    raise ValueError('invalid_fields')
                if not secrets.compare_digest(fields['csrf'][0].encode(), (self.token() or '').encode()):
                    raise ValueError('invalid_csrf')
                if path == '/action':
                    result = console.action(fields['upstream'][0], fields['action'][0])
                elif path == '/s2s-action':
                    result = console.s2s_action(fields['action'][0], fields['device'][0], fields['revision'][0])
                else:
                    result = console.flex_action(fields['scope'][0], fields['field'][0], fields['value'][0])
            except (UnicodeDecodeError, ValueError, KeyError) as exc:
                reason = str(exc) if str(exc) in ('invalid_length', 'invalid_fields', 'invalid_csrf') else 'invalid_request'
                print(json.dumps({'event': 'console_post_rejected', 'reason': reason,
                                  'path': path}), flush=True)
                self.reply(400, 'Bad request')
                return
            if path == '/s2s-action':
                self.reply_json(200, result)
            elif self.headers.get('Accept') == 'application/json':
                self.reply_json(200, {'success': result['success'] is True,
                                      'error': result.get('error')})
            else:
                self.send_response(303)
                self.send_header('Location', '/#activity')
                self.end_headers()

    return ThreadingHTTPServer(('127.0.0.1', port), Handler)


def main():
    parser = argparse.ArgumentParser(description='Loopback-only TimeWeb uplink operator console.')
    parser.add_argument('--database', required=True)
    parser.add_argument('--state-dir', required=True)
    parser.add_argument('--port', type=int, default=19108)
    args = parser.parse_args()
    with make_server(args.database, args.state_dir, args.port) as server:
        server.serve_forever()


if __name__ == '__main__':
    main()
