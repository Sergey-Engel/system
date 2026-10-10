"""Build the provisioned device-first VPN peer dashboards.

Run with the VPN monitoring virtual environment. The source-of-truth is this
file plus the JSON that it renders into ``provisioning/dashboards``; Grafana UI
edits remain deliberately disabled by provisioning.
"""

import copy
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
DASHBOARDS = ROOT / "grafana" / "provisioning" / "dashboards"
MAIN_DASHBOARD = DASHBOARDS / "timeweb-uplink-pilot.json"
DETAIL_DASHBOARD = DASHBOARDS / "wg-device-live.json"
INVENTORY = ROOT.parents[2] / "config/inventory/observations.json"
SOURCE_MARKER = "device-first-vpn-tiles-v5"
PREVIOUS_SOURCE_MARKERS = (
    "device-first-wg-tiles-v1",
    "device-first-wg-tiles-v2",
    "device-first-wg-tiles-v3",
    "device-first-vpn-tiles-v4",
)
POSITIONED_LEGACY_SOURCE_MARKER = "device-first-wg-tiles-v1"


def load_devices(path=INVENTORY):
    """Derive device card mappings from the exporter inventory."""
    raw = json.loads(path.read_text(encoding="utf-8"))
    devices = []
    for entry in raw["devices"]:
        codes = {
            "-1": ("Нет свежих наблюдений", "gray"),
            "0": ("Нет активного наблюдаемого тоннеля", "yellow"),
        }
        observations = (
            *((observation, False) for observation in entry["peers"]),
            *((observation, True) for observation in entry.get("xray_clients", [])),
        )
        for observation, is_xray in observations:
            code = str(observation["tunnel_code"])
            if code in codes:
                raise ValueError(f"duplicate tunnel code for {entry['id']}: {code}")
            codes[code] = (
                observation["tunnel"] + (" · access <90s" if is_xray else ""),
                "yellow" if is_xray else "green",
            )
            if observation["tunnel"] == "SOCKS-TW-FLEX":
                codes[code] = ("SOCKS-TW-FLEX · маршрут неизвестен · access <90s", "yellow")
                for exit_code, exit_name in ((1, "FX"), (3, "CEN")):
                    for ru_direct in (0, 1):
                        routed_code = str(observation["tunnel_code"] * 10 + exit_code + ru_direct)
                        ru_name = "TW" if ru_direct else exit_name
                        if routed_code in codes:
                            raise ValueError(f"duplicate route code for {entry['id']}: {routed_code}")
                        codes[routed_code] = (
                            f"SOCKS-TW-FLEX · {exit_name} · RU {ru_name} · access <90s", "yellow"
                        )
        devices.append({"id": entry["id"], "name": entry["name"], "tunnel_codes": codes})
    if not devices:
        raise ValueError("WireGuard inventory contains no devices")
    return tuple(devices)


DEVICES = load_devices()


def write_json(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def prom_query(template, ref_id, expression, legend, instant=True):
    query = copy.deepcopy(template)
    query["spec"]["refId"] = ref_id
    query["spec"]["query"]["spec"].update(
        expr=expression,
        instant=instant,
        legendFormat=legend,
    )
    return query


def value_mapping(items):
    return {
        value: {"text": text, "color": color}
        for value, (text, color) in items.items()
    }


def field_override(name, unit=None, mappings=None, color=None):
    properties = []
    if unit:
        properties.append({"id": "unit", "value": unit})
    if mappings is not None:
        properties.append(
            {"id": "mappings", "value": [{"type": "value", "options": mappings}]}
        )
    if color:
        properties.append({"id": "color", "value": {"mode": "fixed", "fixedColor": color}})
    return {"matcher": {"id": "byName", "options": name}, "properties": properties}


def canvas_value(
    name,
    *,
    field=None,
    text=None,
    color="text",
    left=0,
    right=0,
    top=0,
    height=20,
    size=14,
):
    """Create one responsive Canvas text value.

    Canvas ``scale`` constraints express left and right offsets as percentages,
    so the three metric columns remain aligned when Grafana changes panel width.
    """
    dynamic = field is not None
    return {
        "name": name,
        "type": "metric-value",
        "config": {
            "text": {
                "mode": "field" if dynamic else "fixed",
                "field": field or "",
                "fixed": "" if dynamic else text,
            },
            "color": {"field": field} if dynamic else {"fixed": color},
            "align": "left",
            "valign": "middle",
            "size": size,
        },
        "placement": {
            "left": left,
            "right": right,
            "top": top,
            "height": height,
        },
        "constraint": {"horizontal": "scale", "vertical": "top"},
        "background": {"color": {"fixed": "transparent"}},
    }


def gate(expression):
    return (
        f"({expression}) and on(job,instance) "
        '(up{job="macbook-wg-peer"} == 1)'
    )


def device_tile(template, device, panel_id):
    device_id = device["id"]
    url = f"/d/wg-device-live/wireguard-device-live?var-device={device_id}"
    panel = copy.deepcopy(template)
    spec = panel["spec"]
    spec.update(
        id=panel_id,
        title=device["name"],
        description=(
            f"{SOURCE_MARKER}. Серверная телеметрия TimeWeb WG, TimeWeb Xray/REALITY "
            "и Fornex AWG31. Выбирается самое новое наблюдение: handshake WG/AWG "
            "младше 180 с либо подписанное Xray access-событие младше 90 с. "
            "Xray-событие означает недавний доступ, не подтверждение текущего соединения. "
            "Для FLEX маршрут FX/CEN и RU-direct показан только при свежем read-back "
            "контроллера TimeWeb. Это не агент на устройстве и не проверка полного "
            "клиентского пути."
        ),
        links=[{"title": "Подробности", "url": url, "targetBlank": False}],
    )

    query_template = spec["data"]["spec"]["queries"][0]
    active = gate(f'vpn_device_active_tunnel_code{{device="{device_id}"}}')
    observation_kind = gate(f'vpn_device_active_observation_kind{{device="{device_id}"}}')
    observation_age = gate(f'vpn_device_active_observation_age_seconds{{device="{device_id}"}}')
    in_rate = gate(
        f'vpn_device_active_client_in_bps{{device="{device_id}"}} '
        f'and on(job,instance) (vpn_device_active_rate_valid{{device="{device_id}"}} == 1)'
    )
    out_rate = gate(
        f'vpn_device_active_client_out_bps{{device="{device_id}"}} '
        f'and on(job,instance) (vpn_device_active_rate_valid{{device="{device_id}"}} == 1)'
    )
    spec["data"] = {
        "kind": "QueryGroup",
        "spec": {
            "queries": [
                prom_query(query_template, "A", active, "Тоннель"),
                prom_query(query_template, "B", f"({observation_kind}) or on() vector(0/0)", "Наблюдение"),
                prom_query(query_template, "C", f"({observation_age}) or on() vector(0/0)", "Возраст"),
                prom_query(query_template, "D", f"({in_rate}) or on() vector(0/0)", "IN"),
                prom_query(query_template, "E", f"({out_rate}) or on() vector(0/0)", "OUT"),
            ],
            "queryOptions": {},
            "transformations": [],
        },
    }

    viz = spec["vizConfig"]["spec"]
    viz["fieldConfig"] = {
        "defaults": {
            "color": {"mode": "fixed", "fixedColor": "text"},
            "noValue": "—",
            "mappings": [
                {
                    "type": "special",
                    "options": {"match": "nan", "result": {"text": "—", "color": "gray"}},
                }
            ],
            "links": [{"title": "Подробности", "url": url}],
        },
        "overrides": [
            field_override("Тоннель", mappings=value_mapping(device["tunnel_codes"])),
            field_override(
                "Наблюдение",
                mappings=value_mapping(
                    {
                        "1": ("Handshake", "text"),
                        "2": ("Xray access <90s", "text"),
                    }
                ),
            ),
            field_override("Возраст", unit="s"),
            field_override("IN", unit="bps", color="blue"),
            field_override("OUT", unit="bps", color="orange"),
        ],
    }
    spec["vizConfig"]["group"] = "canvas"
    viz["options"] = {
        "inlineEditing": False,
        "panZoom": False,
        "zoomToContent": False,
        "showAdvancedTypes": False,
        "tooltip": {"mode": "none"},
        "root": {
            "name": f"{device['name']} VPN tunnel telemetry",
            "type": "frame",
            "background": {"color": {"fixed": "transparent"}},
            "elements": [
                canvas_value(
                    "active-tunnel",
                    field="Тоннель",
                    left=2,
                    right=2,
                    top=0,
                    height=24,
                    size=15,
                ),
                canvas_value(
                    "observation-kind",
                    field="Наблюдение",
                    left=2,
                    right=68,
                    top=27,
                    height=16,
                    size=11,
                ),
                canvas_value(
                    "in-label",
                    text="IN",
                    color="blue",
                    left=35,
                    right=35,
                    top=27,
                    height=16,
                    size=11,
                ),
                canvas_value(
                    "out-label",
                    text="OUT",
                    color="orange",
                    left=68,
                    right=2,
                    top=27,
                    height=16,
                    size=11,
                ),
                canvas_value(
                    "observation-age",
                    field="Возраст",
                    left=2,
                    right=68,
                    top=43,
                    height=24,
                    size=15,
                ),
                canvas_value(
                    "in-value",
                    field="IN",
                    left=35,
                    right=35,
                    top=43,
                    height=24,
                    size=15,
                ),
                canvas_value(
                    "out-value",
                    field="OUT",
                    left=68,
                    right=2,
                    top=43,
                    height=24,
                    size=15,
                ),
            ],
        },
    }
    return panel


def ensure_transport_fields(elements, layout_items):
    """Show the selected transport inside each upstream's existing status card."""
    transport_mapping = {
        "type": "value",
        "options": {
            "0": {"color": "green", "text": "NATIVE UDP"},
            "1": {"color": "orange", "text": "WSS BACKUP"},
        },
    }
    for panel_name, upstream in (("panel-2", "cenuta"), ("panel-3", "fornex")):
        panel = elements[panel_name]
        spec = panel["spec"]
        queries = spec["data"]["spec"]["queries"]
        template = queries[0]
        queries[:] = [query for query in queries if query["spec"]["refId"] != "C"]
        queries.append(
            prom_query(
                template,
                "C",
                f'sum by (upstream) (vpn_uplink_selected_transport_info{{upstream="{upstream}",mode="backup"}}) '
                f'or on(upstream) (0 * sum by (upstream) (vpn_uplink_selected_transport_info{{upstream="{upstream}"}}))',
                "Транспорт",
            )
        )
        spec["description"] = (
            "Состояние uplink и выбранный контроллером транспорт. NATIVE UDP - "
            "прямой UDP; WSS BACKUP - резервный WSS/mTLS."
        )
        overrides = spec["vizConfig"]["spec"]["fieldConfig"]["overrides"]
        overrides[:] = [
            override for override in overrides
            if override["matcher"].get("options") != "Транспорт"
        ]
        overrides.append(field_override("Транспорт", mappings=transport_mapping["options"]))

    elements.pop("panel-12", None)
    top_positions = {"panel-2": 0, "panel-3": 8, "panel-4": 16}
    retained = []
    for item in layout_items:
        name = item["spec"]["element"]["name"]
        if name == "panel-12":
            continue
        if name in top_positions:
            item["spec"].update(x=top_positions[name], width=8, y=0, height=4)
        retained.append(item)
    return retained


def build_main_dashboard():
    dashboard = json.loads(MAIN_DASHBOARD.read_text(encoding="utf-8"))
    elements = dashboard["spec"]["elements"]
    layout_items = dashboard["spec"]["layout"]["spec"]["items"]
    layout_items = ensure_transport_fields(elements, layout_items)

    previous_tiles = {
        name
        for name, element in elements.items()
        if SOURCE_MARKER in element.get("spec", {}).get("description", "")
        or any(marker in element.get("spec", {}).get("description", "") for marker in PREVIOUS_SOURCE_MARKERS)
    }
    source_was_legacy = any(
        POSITIONED_LEGACY_SOURCE_MARKER in elements[name].get("spec", {}).get("description", "")
        for name in previous_tiles
    )
    if not previous_tiles:
        previous_tiles = {"panel-100", "panel-101", "panel-102"}
    retained_items = [
        item for item in layout_items if item["spec"]["element"]["name"] not in previous_tiles
    ]
    if source_was_legacy:
        for item in retained_items:
            item["spec"]["y"] = max(0, item["spec"]["y"] - 6)

    template = copy.deepcopy(elements["panel-100"])
    for name in previous_tiles:
        elements.pop(name, None)
    bottom_y = max(
        item["spec"]["y"] + item["spec"]["height"] for item in retained_items
    )
    for index, device in enumerate(DEVICES):
        panel_id = 100 + index
        element_name = f"panel-{panel_id}"
        elements[element_name] = device_tile(template, device, panel_id)
        retained_items.append(
            {
                "kind": "GridLayoutItem",
                "spec": {
                    "element": {"kind": "ElementReference", "name": element_name},
                    "height": 4,
                    "width": 8,
                    "x": (index % 3) * 8,
                    "y": bottom_y + (index // 3) * 4,
                },
            }
        )
    dashboard["spec"]["layout"]["spec"]["items"] = retained_items
    write_json(MAIN_DASHBOARD, dashboard)


def stat_panel(
    panel_id,
    title,
    expression,
    x,
    y,
    unit="short",
    mappings=None,
    text_mode="value",
    width=6,
    legend_format="",
):
    defaults = {"unit": unit, "noValue": "—", "color": {"mode": "thresholds"}}
    if mappings is not None:
        defaults["mappings"] = [{"type": "value", "options": mappings}]
    return {
        "id": panel_id,
        "title": title,
        "type": "stat",
        "datasource": {"type": "prometheus", "uid": "PBFA97CFB590B2093"},
        "gridPos": {"x": x, "y": y, "w": width, "h": 4},
        "targets": [{"refId": "A", "expr": expression, "instant": True, "legendFormat": legend_format}],
        "fieldConfig": {"defaults": defaults, "overrides": []},
        "options": {
            "reduceOptions": {"calcs": ["lastNotNull"], "fields": "", "values": False},
            "colorMode": "value",
            "graphMode": "none",
            "textMode": text_mode,
        },
    }


def build_detail_dashboard():
    activity_mapping = {
        "0": {"text": "Нет свежих наблюдений", "color": "gray"},
        "1": {"text": "Активен", "color": "green"},
        "2": {"text": "Нет активного наблюдаемого тоннеля", "color": "yellow"},
        "3": {"text": "Недавний Xray access (<90 с)", "color": "yellow"},
    }
    device_options = ",".join(device["id"] for device in DEVICES)
    dashboard = {
        "uid": "wg-device-live",
        "title": "VPN: устройство и активный тоннель",
        "schemaVersion": 39,
        "version": 1,
        "refresh": "10s",
        "time": {"from": "now-1h", "to": "now"},
        "timepicker": {"refresh_intervals": ["5s", "10s", "15s", "30s", "1m", "5m"]},
        "templating": {
            "list": [
                {
                    "name": "device",
                    "label": "Устройство",
                    "type": "custom",
                    "query": device_options,
                    "current": {
                        "selected": True,
                        "text": DEVICES[0]["id"],
                        "value": DEVICES[0]["id"],
                    },
                    "hide": 0,
                    "includeAll": False,
                    "multi": False,
                }
            ]
        },
        "links": [
            {
                "type": "link",
                "title": "К устройствам",
                "url": "/d/timeweb-uplink-pilot/timeweb-uplinks-pilot",
            }
        ],
        "panels": [],
    }
    active_tunnel = (
        'vpn_device_active_tunnel{device="$device"} '
        'or on() label_replace(vector(0), "tunnel", "Нет активного наблюдаемого тоннеля", "__name__", ".*")'
    )
    dashboard["panels"].extend(
        [
            stat_panel(
                1,
                "Наблюдаемый тоннель",
                active_tunnel,
                0,
                0,
                unit="short",
                text_mode="name",
                width=8,
                legend_format="{{tunnel}}",
            ),
            stat_panel(2, "Состояние устройства", "vpn_device_activity{device=\"$device\"}", 8, 0, mappings=activity_mapping, width=4),
            stat_panel(3, "Последнее наблюдение", "vpn_device_active_observation_age_seconds{device=\"$device\"}", 12, 0, unit="s", width=4),
            stat_panel(4, "IN (WG/AWG)", "vpn_device_active_client_in_bps{device=\"$device\"}", 16, 0, unit="bps", width=4),
            stat_panel(5, "OUT (WG/AWG)", "vpn_device_active_client_out_bps{device=\"$device\"}", 20, 0, unit="bps", width=4),
            {
                "id": 10,
                "title": "Трафик по тоннелям устройства",
                "type": "timeseries",
                "datasource": {"type": "prometheus", "uid": "PBFA97CFB590B2093"},
                "gridPos": {"x": 0, "y": 8, "w": 24, "h": 8},
                "targets": [
                    {"refId": "A", "expr": "vpn_wg_peer_client_in_bps{device=\"$device\",source=~\".+\"}", "legendFormat": "{{tunnel}} IN"},
                    {"refId": "B", "expr": "vpn_wg_peer_client_out_bps{device=\"$device\",source=~\".+\"}", "legendFormat": "{{tunnel}} OUT"},
                ],
                "fieldConfig": {"defaults": {"unit": "bps", "custom": {"spanNulls": False}}, "overrides": []},
                "options": {"legend": {"displayMode": "table", "placement": "bottom"}, "tooltip": {"mode": "multi"}},
            },
            {
                "id": 11,
                "title": "Состояние каждого наблюдаемого тоннеля",
                "type": "state-timeline",
                "datasource": {"type": "prometheus", "uid": "PBFA97CFB590B2093"},
                "gridPos": {"x": 0, "y": 16, "w": 24, "h": 6},
                "targets": [
                    {
                        "refId": "A",
                        "expr": "vpn_wg_peer_activity{device=\"$device\",source=~\".+\"} or vpn_xray_client_activity{device=\"$device\",source=~\".+\"}",
                        "legendFormat": "{{tunnel}}",
                    }
                ],
                "fieldConfig": {"defaults": {"mappings": [{"type": "value", "options": activity_mapping}]}, "overrides": []},
                "options": {"mergeValues": True, "showValue": "auto", "alignValue": "left"},
            },
            {
                "id": 12,
                "title": "Семантика",
                "type": "text",
                "gridPos": {"x": 0, "y": 22, "w": 24, "h": 5},
                "options": {
                    "mode": "markdown",
                    "content": (
                        "Активным считается самое новое наблюдение: server-side handshake младше "
                        "180 секунд для TimeWeb WG/Fornex AWG31 либо подписанное access-событие "
                        "TimeWeb Xray/REALITY младше 90 секунд. Для Xray это недавний доступ, "
                        "а не подтверждение открытого VPN-соединения. При переключении профилей выбирается "
                        "более новое событие. IN - server TX к клиенту; OUT - server RX от клиента. Скорости "
                        "доступны только для WG/AWG после двух последовательных отсчетов; access-"
                        "журнал Xray не содержит побайтной статистики по клиенту.\n\n"
                        "Для SOCKS-TW-FLEX суффикс FX/CEN и RU TW/FX/CEN берётся из "
                        "проверенного состояния контроллера TimeWeb; если его опрос недоступен, "
                        "маршрут неизвестен. Наличие access-события не доказывает работу "
                        "пользовательского приложения.\n\n"
                        "Опрос TimeWeb и Fornex независим: сбой одного источника не стирает "
                        "последний срез другого, но после 45 секунд отсутствия источник считается "
                        "ненаблюдаемым. Отсутствующий серверный peer или Xray access-event - это "
                        "конфигурационное несоответствие либо отсутствие недавней активности, а не "
                        "доказательство выключенного клиента."
                    ),
                },
            },
        ]
    )
    write_json(DETAIL_DASHBOARD, dashboard)


if __name__ == "__main__":
    build_main_dashboard()
    build_detail_dashboard()
