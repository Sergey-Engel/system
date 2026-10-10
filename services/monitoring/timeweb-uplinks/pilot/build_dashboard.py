"""Generate the separate pilot dashboard; never rewrites the Mac connectivity board."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
panels = []


def panel(title, kind, x, y, w, h, expr=None, legend=None):
    value = dict(id=len(panels)+1, title=title, type=kind,
                 gridPos=dict(x=x, y=y, w=w, h=h),
                 fieldConfig=dict(defaults=dict(noValue='NO DATA'), overrides=[]))
    if expr:
        value['targets'] = [dict(expr=expr, refId='A', legendFormat=legend or '{{upstream}}',
                                instant=kind=='stat')]
    panels.append(value)
    return value


def stat(title, expr, x, y, w=8):
    value = panel(title, 'stat', x, y, w, 4, expr)
    value['options'] = dict(colorMode='value', graphMode='none',
        reduceOptions=dict(calcs=['last'], fields='', values=False), textMode='value_and_name')
    value['fieldConfig']['defaults']['color'] = dict(mode='fixed', fixedColor='gray')
    value['fieldConfig']['defaults']['mappings'] = [dict(type='special',options=dict(
        match='null',result=dict(text='NO DATA',color='gray')))]
    return value


def live(expr):
    return f'({expr}) and on(job,instance) (up{{job="timeweb-uplink-pilot"}} == 1)'


banner = panel('TimeWeb uplinks / PILOT', 'text', 0, 0, 24, 3)
banner['options'] = dict(mode='markdown', content=(
    '**Измерения: 120 секунд.** TimeWeb → WireGuard → Cenuta / Fornex → HTTPS. '
    'Пилот: RTNL + снимки состояния, без полной защиты от WG/firewall ABA. '
    '**UNKNOWN / NO DATA не означают исправную связь.** '
    'История Grafana накапливается, пока Mac подключён; автономная история хранится на TimeWeb.'))
mapping = [{'type':'value', 'options': {str(i):dict(text=name,color=color)
    for i,name,color in [(0,'UNKNOWN','gray'),(1,'UP','green'),(2,'DEGRADED','yellow'),(3,'DOWN','red')]}}]
for up, x in [('cenuta',0),('fornex',8)]:
    value = stat(up.title(), live(f'vpn_uplink_state{{upstream="{up}"}}'), x,3)
    value['fieldConfig']['defaults']['mappings']=mapping
value=stat('Exporter / SSH', 'up{job="timeweb-uplink-pilot"}',16,3)
value['targets'][0]['legendFormat']='TimeWeb'
value['fieldConfig']['defaults']['mappings']=[dict(type='value', options={
    '0':dict(text='NO CONNECTION',color='red'),'1':dict(text='CONNECTED',color='green')})]
value=stat('Возраст измерения',live('time() - (vpn_uplink_last_cycle_timestamp_seconds > 0)'),0,7,6)
value['fieldConfig']['defaults']['unit']='s'
value['fieldConfig']['defaults'].update(color=dict(mode='thresholds'),thresholds=dict(
    mode='absolute',steps=[dict(color='green',value=None),dict(color='orange',value=150),dict(color='red',value=180)]))
value=stat('Возраст handshake',live('vpn_uplink_handshake_age_seconds'),6,7,6)
value['fieldConfig']['defaults']['unit']='s'
value=stat('Причина состояния',live('vpn_uplink_reason_info'),12,7,12)
value['targets'][0]['legendFormat']='{{upstream}}: {{reason}}'
value['options']['textMode']='name'
value=panel('История состояний', 'state-timeline',0,11,24,6,live('vpn_uplink_state'))
value['fieldConfig']['defaults'].update(mappings=mapping, custom=dict(fillOpacity=85, lineWidth=0, spanNulls=False))
value['options']=dict(mergeValues=True,showValue='auto',rowHeight=0.8,legend=dict(showLegend=True))
for title,y,expr,unit in [
    ('HTTPS: результат по целям',17,'vpn_uplink_probe_success','short'),
    ('HTTPS: длительность (timeout не является RTT)',24,'vpn_uplink_probe_duration_seconds','s')]:
    value=panel(title,'timeseries',0,y,24,7,live(expr),'{{upstream}} / {{target}}')
    value['fieldConfig']['defaults'].update(unit=unit, custom=dict(spanNulls=False,showPoints='always',pointSize=4))
    if unit=='short': value['fieldConfig']['defaults'].update(min=0,max=1)
    value['options']=dict(legend=dict(displayMode='list',placement='bottom'),tooltip=dict(mode='multi'))
value=stat('Дифференциальные признаки',live('vpn_uplink_signal_info'),0,31,24)
value['targets'][0]['legendFormat']='{{upstream}}: {{signal}}'
value['options']['textMode']='name'
dashboard = dict(uid='timeweb-uplink-pilot',title='TimeWeb Uplinks - Pilot',
    schemaVersion=39,version=1,editable=True,tags=['vpn','pilot','timeweb'],
    refresh='10s',timezone='browser',time={'from':'now-1h','to':'now'},panels=panels,
    annotations={'list':[]},templating={'list':[]})
(ROOT/'timeweb-uplink-pilot.json').write_text(json.dumps(dashboard,ensure_ascii=False,indent=2)+'\n')
