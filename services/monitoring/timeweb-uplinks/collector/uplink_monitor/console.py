"""Loopback-only operator console for the reviewed uplink controllers."""
import argparse
from datetime import datetime, timezone
from http.cookies import SimpleCookie
import html
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
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
        self.audit_path = self.state_dir / 'console-actions.jsonl'

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
            if not self.allowed_host() or path not in ('/', '/state'):
                self.reply(404, 'Not found')
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
                    f'<span id="refresh-state" role="status"></span></p>{content}</main></html>')
            self.reply(200, body, headers=headers)

        def do_POST(self):
            path = urlsplit(self.path).path
            if not self.allowed_host() or path not in ('/action', '/flex-action'):
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
                if set(fields) != expected or any(len(v) != 1 for v in fields.values()):
                    raise ValueError('invalid_fields')
                if not secrets.compare_digest(fields['csrf'][0], self.token() or ''):
                    raise ValueError('invalid_csrf')
                if path == '/action':
                    result = console.action(fields['upstream'][0], fields['action'][0])
                else:
                    result = console.flex_action(fields['scope'][0], fields['field'][0], fields['value'][0])
            except (UnicodeDecodeError, ValueError, KeyError) as exc:
                reason = str(exc) if str(exc) in ('invalid_length', 'invalid_fields', 'invalid_csrf') else 'invalid_request'
                print(json.dumps({'event': 'console_post_rejected', 'reason': reason,
                                  'path': path}), flush=True)
                self.reply(400, 'Bad request')
                return
            if self.headers.get('Accept') == 'application/json':
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
