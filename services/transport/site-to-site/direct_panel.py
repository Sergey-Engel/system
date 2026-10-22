"""Loopback facade: unchanged upstream VPN console plus local SSTP controls."""
import argparse
from http.cookies import SimpleCookie
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import secrets
import threading
import time
from urllib.parse import parse_qs
import urllib.error
import urllib.request

import direct_access as access
import direct_controller
import device_routing
import routing_panel

STYLE = '''<style>
.direct-nav{display:flex;gap:1rem;padding:1rem 0;max-width:1100px;margin:auto}
.direct-nav a{color:#b9d9ff;text-decoration:none;padding:.5rem;border-bottom:2px solid transparent}
.direct-nav a[aria-selected=true]{border-color:#75c46b;color:#fff}
#direct-sstp{max-width:1100px;margin:auto}#direct-sstp[hidden]{display:none}
.direct-grid{display:grid;grid-template-columns:minmax(0,1fr) minmax(0,1fr);gap:2rem;border-top:1px solid #4e5663;padding-top:1rem}
#direct-sstp h2{font-size:1.2rem}#direct-sstp form{display:flex;gap:.7rem;align-items:end;flex-wrap:wrap}
#direct-sstp label{display:grid;gap:.4rem;min-width:0;max-width:100%}#direct-sstp select{max-width:100%;min-width:13rem}
#direct-sstp li{display:flex;justify-content:space-between;align-items:center;gap:1rem;border-bottom:1px solid #4e5663;padding:.8rem 0}
#direct-sstp li span{min-width:0;overflow-wrap:anywhere}#direct-sstp .remove{flex-shrink:0}
#direct-sstp ul{list-style:none;padding:0}#direct-sstp small{display:block;color:#aab2c0}
#direct-sstp .remove{font-size:1.3rem;width:2.5rem;height:2.5rem;padding:0;background:none;color:#ff8585;border:1px solid #4e5663;border-radius:4px}
#direct-sstp .direct-heading{display:flex;align-items:center;justify-content:space-between;gap:1rem}
#direct-direction{display:flex;flex-wrap:wrap;gap:.5rem;margin:1rem 0}
#direct-direction button{background:none;color:inherit;border:0;border-bottom:2px solid transparent;padding:.6rem;font:inherit}
#direct-direction button[aria-selected=true]{border-color:#75c46b}
#direct-sstp .direct-icon{flex-shrink:0;width:2.5rem;height:2.5rem;font-size:1.3rem;padding:0;border:1px solid #4e5663;border-radius:4px;background:none;color:inherit}
#direct-feedback{display:flex;gap:1rem;align-items:center;justify-content:space-between}#direct-feedback[hidden]{display:none}
#direct-message{overflow-wrap:anywhere}#direct-message[data-error=true]{color:#ff8585}
#direct-error{color:#ff8585;overflow-wrap:anywhere}#direct-status{color:#85d47c}
#direct-status[data-state=unknown]{color:#aab2c0}#direct-status[data-state=down]{color:#ff8585}
@media(max-width:650px){.direct-grid{grid-template-columns:1fr}#direct-sstp select{min-width:0;width:100%}#direct-sstp label{width:100%}}
</style>'''
SECTION = '''<section id="direct-sstp" hidden>
<div id="direct-direction" role="tablist" aria-label="Internet direction">
<button type="button" role="tab" data-direction="reverse" aria-selected="false">Nakhimova → Fethiye</button>
<button type="button" role="tab" data-direction="forward" aria-selected="true">Fethiye → Nakhimova</button></div>
<div class="direct-heading"><h2 id="direct-title">Fethiye → Nakhimova · Direct SSTP</h2>
<button id="direct-refresh" class="direct-icon" type="button" title="Refresh status" aria-label="Refresh status">↻</button></div>
<p id="direct-status" role="status" data-state="unknown">Checking…</p><p id="direct-detail"></p>
<p id="direct-error" role="alert"></p>
<div class="direct-grid"><section><h2>Available devices</h2>
<form id="direct-add"><label>Device<select id="direct-device"><option value="">Select a device</option></select></label>
<button type="submit" id="direct-add-button" disabled>+ Add</button></form></section>
<section><h2 id="direct-egress">Internet via Nakhimova</h2><ul id="direct-selected"></ul><p id="direct-empty">No devices selected</p></section></div>
<div id="direct-feedback" hidden><p id="direct-message" role="status"></p>
<button id="direct-dismiss" class="direct-icon" type="button" title="Dismiss message" aria-label="Dismiss message">×</button></div></section>'''
SCRIPT = '''<script>
(()=>{let data=null,busy=false,reading=false,failed=true,direction='forward';
const by=id=>document.getElementById(id),token=DIRECT_TOKEN;
const feedback={},choices={};
const endpoint=kind=>'/s2s-'+(direction==='reverse'?'reverse-':'')+kind;
function message(text,error=false){feedback[direction]={text,error};by('direct-feedback').hidden=!text;by('direct-message').textContent=text;by('direct-message').dataset.error=String(error);}
function buttons(){by('direct-refresh').disabled=busy||reading;by('direct-dismiss').disabled=busy;
 document.querySelectorAll('#direct-direction button').forEach(b=>b.disabled=busy||reading);
 by('direct-add-button').disabled=busy||reading||failed||!data||!data.available||!by('direct-device').value;
 document.querySelectorAll('#direct-selected button').forEach(b=>b.disabled=busy||reading||failed||!data||!data.can_remove);}
function render(value){if(value.direction&&value.direction!==direction)throw Error('Direction mismatch');data=value;failed=false;
 by('direct-status').dataset.state=value.tunnel.state;
 by('direct-status').textContent=value.tunnel.state==='up'?'Connected · TCP/443':value.tunnel.state==='down'?'Disconnected':'Status unavailable';
 by('direct-detail').textContent=value.tunnel.detail+' · '+new Date(value.checked_at*1000).toLocaleTimeString();
 by('direct-error').textContent=value.error||'';
 const select=by('direct-device'),previous=select.value;select.replaceChildren(new Option('Select a device',''));
 by('direct-selected').replaceChildren();let count=0;
 for(const d of value.devices){if(!d.selected){if(d.online){const option=new Option(d.label+' · '+d.ip+' · '+d.id,d.id);option.title='MAC: '+d.id+' · Name source: '+(d.name_source||'dhcp');select.add(option);}continue;}
 count++;const li=document.createElement('li'),label=document.createElement('span'),name=document.createElement('strong'),detail=document.createElement('small');
 name.textContent=d.label;name.title='Name source: '+(d.name_source||'dhcp');detail.textContent=d.ip+' · '+d.status+(d.online?'':' · offline')+' · '+d.id;label.append(name,detail);
 const b=document.createElement('button');b.type='button';b.className='remove';b.textContent='×';b.title='Return to local internet';b.setAttribute('aria-label','Remove '+d.label);b.onclick=()=>action('remove',d.id);li.append(label,b);by('direct-selected').append(li);}
 if([...select.options].some(o=>o.value===previous))select.value=previous;by('direct-empty').hidden=count>0;buttons();}
async function refresh(){if(busy||reading||location.hash!=='#site-to-site')return;reading=true;buttons();
 try{const r=await fetch(endpoint('state'),{cache:'no-store',signal:AbortSignal.timeout(60000)});if(!r.ok)throw Error('Status request failed');render(await r.json());}
 catch(e){failed=true;by('direct-status').dataset.state='unknown';by('direct-status').textContent='Status unavailable';by('direct-error').textContent='Status unavailable; selection is retained';}finally{reading=false;buttons();}}
async function action(kind,device){if(busy||reading||failed||!data)return;
 const target=data.devices.find(d=>d.id===device);if(!target)return;busy=true;buttons();message(kind==='add'?'Adding device…':'Returning device to local internet…');
 try{const r=await fetch(endpoint('action'),{method:'POST',headers:{'Content-Type':'application/x-www-form-urlencoded'},credentials:'same-origin',body:new URLSearchParams({csrf:token,action:kind,device,revision:target.revision}),signal:AbortSignal.timeout(130000)});
 if(!r.ok)throw Error('Request rejected; refresh status before retrying');const v=await r.json();render(v);
 message(v.success?'Change confirmed':v.operation_error||'Change not confirmed; refresh status before retrying',!v.success);}
 catch(e){message('Response not confirmed. Refresh status before retrying.',true);failed=true;}finally{busy=false;buttons();}}
function tab(){const direct=location.hash==='#site-to-site';document.querySelector('main').hidden=direct;by('direct-sstp').hidden=!direct;
 document.querySelectorAll('.direct-nav a').forEach(a=>a.setAttribute('aria-selected',String(a.hash===(direct?'#site-to-site':'#vpn'))));refresh();}
document.addEventListener('DOMContentLoaded',()=>{by('direct-add').onsubmit=e=>{e.preventDefault();if(!by('direct-add-button').disabled)action('add',by('direct-device').value);};by('direct-device').onchange=buttons;
 document.querySelectorAll('#direct-direction button').forEach(b=>b.onclick=()=>{if(busy||reading||b.dataset.direction===direction)return;
 choices[direction]=by('direct-device').value;direction=b.dataset.direction;data=null;failed=true;
 document.querySelectorAll('#direct-direction button').forEach(t=>t.setAttribute('aria-selected',String(t.dataset.direction===direction)));
 by('direct-title').textContent=(direction==='reverse'?'Nakhimova → Fethiye':'Fethiye → Nakhimova')+' · Direct SSTP';
 by('direct-egress').textContent='Internet via '+(direction==='reverse'?'Fethiye':'Nakhimova');
 by('direct-device').replaceChildren(new Option('Select a device',''));by('direct-selected').replaceChildren();by('direct-empty').hidden=false;
 by('direct-status').dataset.state='unknown';by('direct-status').textContent='Checking…';by('direct-detail').textContent='';by('direct-error').textContent='';
 const saved=feedback[direction]||{text:'',error:false};message(saved.text,saved.error);refresh().then(()=>{if([...by('direct-device').options].some(o=>o.value===choices[direction]))by('direct-device').value=choices[direction];buttons();});});
 by('direct-refresh').onclick=refresh;by('direct-dismiss').onclick=()=>message('');window.addEventListener('hashchange',tab);tab();});})();
</script>'''


def inject(page, token, unified=False):
    if '<main>' not in page or '</main>' not in page or 'id="direct-sstp"' in page:
        raise ValueError('unrecognized_upstream_console')
    nav = '<nav class="direct-nav" aria-label="Console"><a href="#vpn">VPN</a><a href="#site-to-site">'+('Device routing' if unified else 'Direct SSTP')+'</a></nav>'
    section,style,script=(routing_panel.SECTION,routing_panel.STYLE,routing_panel.SCRIPT) if unified else (SECTION,STYLE,SCRIPT)
    script=script.replace('DIRECT_TOKEN',json.dumps(token))
    if unified:
        script=script.replace('APPLY_ICON',json.dumps(routing_panel.ICONS['apply']))
        script=script.replace('UNDO_ICON',json.dumps(routing_panel.ICONS['undo']))
    return page.replace('<main>', nav + '<main>', 1).replace('</main>', '</main>' + section, 1) + style + script


def server(port=19118, backend='http://127.0.0.1:19119', execute=direct_controller.execute,
           unified=False, routing_execute=device_routing.execute):
    cache, mutex = {}, threading.Lock()

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_):
            pass

        def allowed(self):
            return self.headers.get('Host') in (f'127.0.0.1:{self.server.server_port}', f'localhost:{self.server.server_port}')

        def reply(self, code, body, content='application/json', headers=()):
            data = body.encode() if isinstance(body, str) else body
            self.send_response(code)
            for k, v in [('Content-Type', content), ('Content-Length', str(len(data))), ('Cache-Control', 'no-store'),
                         ('X-Content-Type-Options', 'nosniff'), ('X-Frame-Options', 'DENY'), ('Referrer-Policy', 'no-referrer'),
                         ('Content-Security-Policy', "default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'; frame-ancestors 'none'"), *headers]:
                self.send_header(k, v)
            self.end_headers()
            self.wfile.write(data)

        def cookie(self):
            try:
                c = SimpleCookie(self.headers.get('Cookie', ''))
                value = c.get('direct_sstp_csrf')
                return value.value if value and len(value.value) == 43 else None
            except Exception:
                return None

        def proxy(self, data=None):
            headers = {'Cookie': self.headers.get('Cookie', ''), 'Accept': self.headers.get('Accept', 'text/html'),
                       'Content-Type': 'application/x-www-form-urlencoded'}
            if data is not None:
                headers['Origin'] = backend
            request = urllib.request.Request(backend + self.path, data=data, headers=headers)
            try:
                with urllib.request.urlopen(request, timeout=90) as r:
                    body = r.read(4_000_001)
                    if len(body) > 4_000_000:
                        raise ValueError('oversized_upstream')
                    forwarded = [('Set-Cookie', v) for v in r.headers.get_all('Set-Cookie', [])]
                    if self.path == '/':
                        token = self.cookie() or secrets.token_urlsafe(32)
                        forwarded.append(('Set-Cookie', 'direct_sstp_csrf=' + token + '; Path=/; HttpOnly; SameSite=Strict'))
                        body = inject(body.decode(), token, unified=unified).encode()
                    self.reply(r.status, body, r.headers.get('Content-Type', 'text/html'), forwarded)
            except (OSError, ValueError, urllib.error.URLError):
                self.reply(502, 'VPN console unavailable', 'text/plain')

        def do_GET(self):
            routing_site=self.path.removeprefix('/routing-state/') if self.path.startswith('/routing-state/') else None
            is_routing=unified and routing_site in device_routing.MODES
            if not self.allowed() or (self.path not in ('/', '/state', '/s2s-state', '/s2s-reverse-state') and not is_routing):
                return self.reply(404, '{}')
            if is_routing:
                requested_at = time.monotonic()
                with mutex:
                    key = ('routing', routing_site)
                    item = cache.get(key)
                    # Reuse only a check completed after this request arrived.
                    if item is None or item['time'] < requested_at:
                        value = routing_execute(site=routing_site)
                        item = dict(value=value, time=time.monotonic())
                        cache[key] = item
                    value = item['value']
                self.reply(200,json.dumps(value))
                return
            if self.path not in ('/s2s-state', '/s2s-reverse-state'):
                return self.proxy()
            direction = 'reverse' if self.path == '/s2s-reverse-state' else 'forward'
            with mutex:
                item = cache.setdefault(direction, {})
                if time.monotonic() - item.get('time', 0) >= 15:
                    value = execute(direction=direction) if direction == 'reverse' else execute()
                    item.update(value=value, time=time.monotonic())
                self.reply(200, json.dumps(item['value']))

        def do_POST(self):
            if not self.allowed() or self.path not in ('/action', '/flex-action', '/s2s-action', '/s2s-reverse-action', '/routing-action'):
                return self.reply(404, '{}')
            if unified and self.path in ('/s2s-action','/s2s-reverse-action'):
                return self.reply(410,'{"error":"use_unified_device_routing"}')
            if self.path=='/routing-action' and not unified:
                return self.reply(404,'{}')
            if self.headers.get('Origin') not in (None, '', 'null', 'http://' + self.headers['Host']):
                return self.reply(403, '{}')
            try:
                length = int(self.headers.get('Content-Length', 0))
                if not 0 < length <= 512:
                    raise ValueError('invalid_length')
                body = self.rfile.read(length)
                if self.path=='/routing-action':
                    fields=parse_qs(body.decode(),max_num_fields=5)
                    if set(fields)!={'csrf','site','device','mode','revision'} or any(len(v)!=1 for v in fields.values()):
                        raise ValueError('invalid_fields')
                    if not secrets.compare_digest(fields['csrf'][0],self.cookie() or ''):
                        raise ValueError('invalid_csrf')
                    site=fields['site'][0]
                    if site not in device_routing.MODES or fields['mode'][0] not in (*device_routing.MODES[site],'rollback'):
                        raise ValueError('invalid_route_mode')
                    with mutex:
                        value=routing_execute(site=site,device=fields['device'][0],mode=fields['mode'][0],revision=fields['revision'][0])
                        cache.clear()
                        self.reply(200,json.dumps(value))
                    return
                if self.path not in ('/s2s-action', '/s2s-reverse-action'):
                    return self.proxy(body)
                fields = parse_qs(body.decode(), max_num_fields=4)
                if set(fields) != {'csrf', 'action', 'device', 'revision'} or any(len(v) != 1 for v in fields.values()):
                    raise ValueError('invalid_fields')
                if not secrets.compare_digest(fields['csrf'][0], self.cookie() or ''):
                    raise ValueError('invalid_csrf')
                if fields['action'][0] not in ('add', 'remove'):
                    raise ValueError('invalid_action')
                direction = 'reverse' if self.path == '/s2s-reverse-action' else 'forward'
                with mutex:
                    args = [fields['action'][0], fields['device'][0], fields['revision'][0]]
                    value = execute(*args, direction=direction) if direction == 'reverse' else execute(*args)
                    # The other direction also validates this router's device state.
                    cache.clear()
                    cache[direction] = dict(value=value, time=time.monotonic())
                    self.reply(200, json.dumps(value))
            except (ValueError, UnicodeError):
                self.reply(400, '{}')

    return ThreadingHTTPServer(('127.0.0.1', port), Handler)


if __name__ == '__main__':
    os.umask(0o077)
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--port', type=int, default=19118)
    args = parser.parse_args()
    enabled=access.private_json(access.PRIVATE/'config.json').get('routing_enabled') is True
    with server(args.port,unified=enabled) as httpd:
        httpd.serve_forever()
