"""Unified routing view. Read progress timers never refresh data or write routes."""

STYLE = '''<style>
.direct-nav{display:flex;gap:1rem;padding:1rem 0;max-width:1100px;margin:auto}
.direct-nav a{color:#b9d9ff;text-decoration:none;padding:.5rem;border-bottom:2px solid transparent}
.direct-nav a[aria-selected=true]{border-color:#75c46b;color:#fff}
#routing-panel{max-width:1100px;margin:auto;letter-spacing:0}#routing-panel[hidden]{display:none}
#routing-panel h2{font-size:1.2rem;margin:0}#routing-panel button,#routing-panel select{font:inherit;letter-spacing:0}
.routing-heading,.routing-feedback{display:flex;align-items:center;justify-content:space-between;gap:1rem}
#routing-sites{display:flex;gap:.7rem;margin:1rem 0 1.5rem}#routing-sites button{background:none;color:inherit;border:0;border-bottom:2px solid transparent;padding:.6rem}
#routing-sites button[aria-selected=true]{border-color:#75c46b}
.routing-icon{width:40px;height:40px;padding:0;flex-shrink:0;display:inline-flex;align-items:center;justify-content:center;background:none;color:inherit;border:1px solid #4e5663;border-radius:4px}
.routing-icon svg{width:18px;height:18px;stroke:currentColor;fill:none;stroke-width:2;stroke-linecap:round;stroke-linejoin:round}
#routing-panel button:disabled,#routing-panel select:disabled{opacity:.45}
#routing-channels{display:flex;flex-wrap:wrap;gap:.6rem 1.5rem;padding:1.2rem 0;border-bottom:1px solid #4e5663}
.routing-channel[data-ready=true]{color:#85d47c}.routing-channel[data-ready=false]{color:#aab2c0}
#routing-panel small,#routing-checked{color:#aab2c0}#routing-checked{font-size:.85rem}
#routing-error,#routing-outside,[data-error=true]{color:#ff8585}
#routing-error,#routing-outside,#routing-message{overflow-wrap:anywhere}
.routing-row{display:grid;grid-template-columns:minmax(140px,1fr) minmax(130px,.7fr) minmax(180px,1fr) 88px;align-items:center;gap:1rem;padding:1rem 0;border-bottom:1px solid #4e5663}
.routing-actions{display:flex;gap:8px;width:88px}
.routing-row>*{min-width:0}.routing-device strong,.routing-device small{display:block;overflow-wrap:anywhere}.routing-device small{margin-top:.3rem}
.routing-row select{width:100%;height:40px;min-width:0;background:#20252c;color:inherit;border:1px solid #4e5663;border-radius:4px;padding:0 .5rem}
.routing-current{overflow-wrap:anywhere}.routing-row-head{font-size:.85rem;color:#aab2c0;padding-bottom:.7rem}
.routing-feedback{padding:.7rem 0}.routing-feedback[hidden]{display:none}
#routing-poll{padding:1rem 0 .3rem;min-width:0}
#routing-poll[hidden],.routing-poll-stage[hidden],.routing-spinner[hidden]{display:none}
.routing-poll-summary{display:flex;justify-content:space-between;gap:1rem;color:#aab2c0;font-size:.85rem;font-variant-numeric:tabular-nums}
#routing-poll-bar{display:block;width:100%;height:8px;margin:.6rem 0 .7rem;border:0;border-radius:2px;overflow:hidden;appearance:none;background:#303640;accent-color:#89bfff}
#routing-poll-bar::-webkit-progress-bar{background:#303640}#routing-poll-bar::-webkit-progress-value{background:#89bfff}
#routing-poll-bar::-moz-progress-bar{background:#89bfff}
#routing-poll[data-state=error] #routing-poll-bar::-webkit-progress-value{background:#ff8585}
#routing-poll[data-state=error] #routing-poll-bar::-moz-progress-bar{background:#ff8585}
.routing-poll-stage{display:flex;align-items:center;gap:.6rem;min-height:24px;line-height:1.5}
#routing-poll-stage-text{min-width:0;overflow-wrap:anywhere}
.routing-spinner{display:inline-block;width:16px;height:16px;flex:0 0 16px;border:2px solid #4e5663;border-top-color:#b9d9ff;border-radius:50%;animation:routing-spin .8s linear infinite}
#routing-poll-queue,#routing-poll-error{font-size:.9rem;overflow-wrap:anywhere;margin:.4rem 0}
#routing-poll-queue{color:#aab2c0}#routing-poll-error{color:#ff8585}
@keyframes routing-spin{to{transform:rotate(360deg)}}
@media(prefers-reduced-motion:reduce){.routing-spinner{animation:none}}
@media(max-width:650px){.routing-row{grid-template-columns:minmax(0,1fr) 88px;gap:.7rem}.routing-device{grid-column:1}.routing-current{grid-column:1;font-size:.9rem}.routing-row select{grid-column:1}.routing-actions{grid-column:2;grid-row:3}.routing-row-head{display:none}}
</style>'''

# Lucide refresh-cw, check and x icons, kept inline to avoid remote assets.
ICONS = {
    'refresh': '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M3 12a9 9 0 0 1 15.4-6.4L21 8M21 3v5h-5M21 12a9 9 0 0 1-15.4 6.4L3 16M3 21v-5h5"/></svg>',
    'apply': '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="m20 6-11 11-5-5"/></svg>',
    'close': '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="m18 6-12 12M6 6l12 12"/></svg>',
    'undo': '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M3 7v6h6M3 13l4-4a7 7 0 0 1 12 5v4"/></svg>',
}

SECTION = '''<section id="routing-panel" hidden>
<div id="routing-sites" role="tablist" aria-label="Site">
<button type="button" role="tab" data-site="nakhimova" aria-selected="true">Nakhimova</button>
<button type="button" role="tab" data-site="fethiye" aria-selected="false">Fethiye</button></div>
<div class="routing-heading"><h2 id="routing-title">Nakhimova · Device routing</h2>
<button id="routing-refresh" class="routing-icon" title="Refresh status" aria-label="Refresh status">REFRESH_ICON</button></div>
<div id="routing-poll" data-state="queued" hidden>
<div class="routing-poll-summary"><span id="routing-poll-count">0 of 5 stages completed</span><span id="routing-poll-elapsed">0s elapsed</span></div>
<progress id="routing-poll-bar" max="5" value="0" aria-label="Polling progress" aria-describedby="routing-poll-count"></progress>
<div id="routing-poll-stage" class="routing-poll-stage" role="status" aria-live="polite" hidden><span id="routing-poll-spinner" class="routing-spinner" aria-hidden="true" hidden></span><span id="routing-poll-stage-text"></span></div>
<p id="routing-poll-queue" role="status" hidden>Waiting for another check or operation</p>
<p id="routing-poll-error" role="alert" hidden></p></div>
<div id="routing-channels" aria-label="Routes"></div><p id="routing-checked"></p>
<p id="routing-error" role="alert"></p><p id="routing-outside"></p>
<div class="routing-row routing-row-head" aria-hidden="true"><span>Device / IP</span><span>Current route</span><span>New route</span><span></span></div>
<div id="routing-devices"></div><p id="routing-empty" hidden>No eligible devices</p>
<div id="routing-feedback" class="routing-feedback" hidden><p id="routing-message" role="status"></p>
<button id="routing-dismiss" class="routing-icon" title="Dismiss message" aria-label="Dismiss message">CLOSE_ICON</button></div>
</section>'''.replace('REFRESH_ICON', ICONS['refresh']).replace('CLOSE_ICON', ICONS['close'])

SCRIPT = '''<script>
(()=>{const by=id=>document.getElementById(id),token=DIRECT_TOKEN,applyIcon=APPLY_ICON,undoIcon=UNDO_ICON;
let site='nakhimova',data=null,busy=false,reading=false,failed=true,activePoll=null;
const drafts={},feedback={};
const names={nakhimova:'Nakhimova',fethiye:'Fethiye'};
const label=mode=>({local:'Standard',cenuta:'WG-Cenuta-RU',fornex:'WG-Fornex-RU',sstp_cenuta:'SSTP-Cenuta-RU',sstp_fornex:'SSTP-Fornex-RU',direct:'Direct SSTP-RU via '+names[site==='nakhimova'?'fethiye':'nakhimova'],conflict:'Conflicting assignments',shared:'Shared network assignment'}[mode]||'Unavailable');
function message(text,error=false){feedback[site]={text,error};by('routing-feedback').hidden=!text;by('routing-message').textContent=text;by('routing-message').dataset.error=String(error);}
function pollError(text){by('routing-poll-error').textContent=text;by('routing-poll-error').hidden=!text;}
function paintPoll(p,v){if(activePoll!==p||v.site!==site)return;
 if(!['queued','running','complete','error'].includes(v.state)||v.total!==5||!Number.isInteger(v.completed)||v.completed<0||v.completed>5)throw Error('Invalid progress');
 p.completed=Math.max(p.completed,v.completed);p.stage=v.stage||'';
 by('routing-poll').dataset.state=v.state;by('routing-poll-bar').value=p.completed;
 by('routing-poll-count').textContent=p.completed+' of 5 stages completed';
 by('routing-poll-queue').hidden=v.state!=='queued';
 const stage=v.state==='complete'?'Poll completed':p.stage;
 by('routing-poll-stage').hidden=!stage;by('routing-poll-spinner').hidden=v.state!=='running';
 if(by('routing-poll-stage-text').textContent!==stage)by('routing-poll-stage-text').textContent=stage;
 pollError(v.state==='error'?'Status check failed. Existing assignments are retained.':'');}
function tickPoll(p){by('routing-poll-elapsed').textContent=Math.floor(((p.ended??performance.now())-p.started)/1000)+'s elapsed';}
async function observePoll(p){if(activePoll!==p)return;const controller=new AbortController();p.observer=controller;
 const timeout=setTimeout(()=>controller.abort(),3000);
 try{const r=await fetch('/routing-progress/'+p.id,{cache:'no-store',signal:controller.signal});
  if(r.status!==404){if(!r.ok)throw Error('Progress unavailable');paintPoll(p,await r.json());}}
 catch(e){if(activePoll===p)pollError('Progress updates unavailable; status check is still running.');}
 finally{clearTimeout(timeout);if(activePoll===p)p.next=setTimeout(()=>observePoll(p),1000);}}
function startPoll(){const bytes=crypto.getRandomValues(new Uint8Array(16));
 const p=activePoll={id:Array.from(bytes,b=>b.toString(16).padStart(2,'0')).join(''),started:performance.now(),completed:0,stage:''};
 by('routing-poll').hidden=false;paintPoll(p,{site,state:'queued',completed:0,total:5});tickPoll(p);
 p.clock=setInterval(()=>tickPoll(p),250);p.next=setTimeout(()=>observePoll(p),250);return p;}
function endPoll(p,success){if(activePoll!==p)return;
 clearInterval(p.clock);clearTimeout(p.next);p.observer?.abort();p.ended=performance.now();
 paintPoll(p,{site,state:success?'complete':'error',completed:success?5:p.completed,total:5,stage:p.stage});tickPoll(p);activePoll=null;}
function buttons(){by('routing-refresh').disabled=busy||reading;by('routing-dismiss').disabled=busy;
 document.querySelectorAll('#routing-sites button').forEach(b=>b.disabled=busy||reading);
 document.querySelectorAll('.routing-row select').forEach(s=>{const d=data?.devices.find(d=>d.id===s.dataset.device);s.disabled=busy||reading||failed||!d?.can_apply;});
 document.querySelectorAll('.routing-apply').forEach(b=>{const d=data?.devices.find(d=>d.id===b.dataset.device),s=b.closest('.routing-row').querySelector('select');
 b.disabled=busy||reading||failed||!d?.can_apply||!s.value||(!d.pending&&s.value===d.mode)||(s.value!=='local'&&!data?.channels[s.value]?.ready);});
 document.querySelectorAll('.routing-undo').forEach(b=>{const d=data?.devices.find(d=>d.id===b.dataset.device);b.disabled=busy||reading||failed||!d?.can_rollback;});}
function render(v){if(v.site!==site)throw Error('Site mismatch');data=v;failed=false;
 by('routing-channels').replaceChildren();
 for(const mode of (site==='nakhimova'?['local','cenuta','fornex','sstp_cenuta','sstp_fornex','direct']:['local','direct'])){const c=v.channels[mode],span=document.createElement('span');span.className='routing-channel';span.dataset.ready=String(c?.ready===true);span.title=c?.detail||label(mode);span.textContent=label(mode)+' · '+(c?.ready?(mode==='local'?'Available':'Route ready'):'Unavailable');by('routing-channels').append(span);}
 by('routing-checked').textContent='Checked '+new Date(v.checked_at*1000).toLocaleTimeString();by('routing-error').textContent=v.error||'';
 by('routing-outside').textContent=v.outside_assignments?v.outside_assignments+' assignment(s) outside this device list; unchanged':'';
 const rows=by('routing-devices');rows.replaceChildren();by('routing-empty').hidden=v.devices.length>0;
 for(const d of v.devices){const row=document.createElement('div');row.className='routing-row';
 const identity=document.createElement('div');identity.className='routing-device';identity.title='MAC: '+d.id;
 const strong=document.createElement('strong'),small=document.createElement('small');strong.textContent=d.label;small.textContent=(d.ip||'IP unavailable')+(d.online?'':' · Offline');identity.append(strong,small);
 const current=document.createElement('span');current.className='routing-current';current.textContent=d.pending?'Confirmation required':label(d.mode);
 const select=document.createElement('select');select.dataset.device=d.id;select.setAttribute('aria-label','Route for '+d.label);
 for(const mode of d.allowed_modes){const o=new Option(label(mode),mode);o.disabled=mode!=='local'&&!v.channels[mode]?.ready;select.add(o);}
 let draft=drafts[site+'|'+d.id];if(draft?.revision!==d.revision)draft=null;
 select.value=draft?.mode||(d.pending?'local':d.mode);if(!select.value)select.selectedIndex=-1;
 select.onchange=()=>{drafts[site+'|'+d.id]={mode:select.value,revision:d.revision};buttons();};
 const apply=document.createElement('button');apply.type='button';apply.className='routing-icon routing-apply';apply.dataset.device=d.id;apply.title='Apply route for '+d.label;apply.setAttribute('aria-label',apply.title);apply.innerHTML=applyIcon;apply.onclick=()=>action(d,select.value);
 const undo=document.createElement('button');undo.type='button';undo.className='routing-icon routing-undo';undo.dataset.device=d.id;undo.title='Restore previous route'+(d.rollback_mode?' · '+label(d.rollback_mode):'');undo.setAttribute('aria-label',undo.title);undo.innerHTML=undoIcon;undo.onclick=()=>action(d,'rollback');
 const actions=document.createElement('div');actions.className='routing-actions';actions.append(apply,undo);
 row.append(identity,current,select,actions);rows.append(row);}
 buttons();}
async function refresh(){if(busy||reading||location.hash!=='#site-to-site')return;reading=true;buttons();
 const p=startPoll();let success=false;
 try{const r=await fetch('/routing-state/'+site,{headers:{'X-Routing-Poll':p.id},cache:'no-store',signal:AbortSignal.timeout(120000)});const v=await r.json();
  if(v.poll_progress)paintPoll(p,v.poll_progress);if(!r.ok)throw Error('Status unavailable');render(v);
  success=v.success!==false&&v.source_ready!==false&&(!v.poll_progress||v.poll_progress.state==='complete');if(!success)failed=true;}
 catch(e){failed=true;if(!data)by('routing-checked').textContent='Check failed';by('routing-error').textContent='Status unavailable. Existing assignments are retained.';by('routing-channels').replaceChildren();}finally{endPoll(p,success);reading=false;buttons();}}
async function action(d,mode){if(busy||reading||failed)return;
 if((mode.startsWith('sstp_')||mode==='rollback')&&!window.confirm(d.label+' · '+d.ip+' · '+(mode==='rollback'?'Restore '+label(d.rollback_mode):'Apply '+label(mode))+'?'))return;
 busy=true;buttons();message(mode==='rollback'?'Restoring previous route…':'Applying route…');
 try{const r=await fetch('/routing-action',{method:'POST',headers:{'Content-Type':'application/x-www-form-urlencoded'},credentials:'same-origin',body:new URLSearchParams({csrf:token,site,device:d.id,mode,revision:d.revision}),signal:AbortSignal.timeout(240000)});
 if(!r.ok)throw Error('Request rejected');const v=await r.json();delete drafts[site+'|'+d.id];render(v);message(v.success?v.operation_message||'Change confirmed':v.operation_error||'Change not confirmed. Refresh status before retrying.',!v.success);}
 catch(e){failed=true;message('Response not confirmed. Refresh status before retrying; do not repeat blindly.',true);}finally{busy=false;buttons();}}
function tab(){const active=location.hash==='#site-to-site';document.querySelector('main').hidden=active;by('routing-panel').hidden=!active;
 document.querySelectorAll('.direct-nav a').forEach(a=>a.setAttribute('aria-selected',String(a.hash===(active?'#site-to-site':'#vpn'))));if(active&&!data)refresh();}
document.addEventListener('DOMContentLoaded',()=>{by('routing-refresh').onclick=refresh;by('routing-dismiss').onclick=()=>message('');
 document.querySelectorAll('#routing-sites button').forEach(b=>b.onclick=()=>{if(busy||reading||site===b.dataset.site)return;site=b.dataset.site;data=null;failed=true;
 document.querySelectorAll('#routing-sites button').forEach(t=>t.setAttribute('aria-selected',String(t.dataset.site===site)));by('routing-title').textContent=names[site]+' · Device routing';
 by('routing-devices').replaceChildren();by('routing-channels').replaceChildren();by('routing-error').textContent='';by('routing-outside').textContent='';by('routing-checked').textContent='Checking…';by('routing-empty').hidden=true;
 const f=feedback[site]||{text:'',error:false};message(f.text,f.error);refresh();});window.addEventListener('hashchange',tab);tab();});})();
</script>'''
