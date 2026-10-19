"""Names are presentation metadata, never identity or routing authority."""
import json
from pathlib import Path
import subprocess
import sys

import pytest

sys.path.insert(0, str(Path(__file__).parent))


def resolver(tmp_path, bindings=(), prefixes=None):
    import direct_names as names
    inventory, cache = tmp_path / 'inventory.json', tmp_path / 'vendors.json'
    inventory.write_text(json.dumps(dict(schema_version=1, bindings=list(bindings))))
    cache.write_text(json.dumps(dict(schema_version=1, fetched_at=4_000_000_000, prefixes=prefixes or {})))
    return names.DeviceNames(inventory, cache)


def test_exact_private_mac_uses_confirmed_inventory(tmp_path):
    lookup = resolver(tmp_path, [dict(mac='a2-c1-5e-29-f5-8e', name='MacBook Air (Sergey)')])
    value = lookup.resolve('A2:C1:5E:29:F5:8E', 'MacBookAir')
    assert value['label'] == 'MacBook Air (Sergey)'
    assert value['name_source'] == 'inventory' and value['mac_type'] == 'local'
    assert value['manufacturer'] is None


def test_unknown_local_mac_never_uses_vendor_prefix(tmp_path):
    lookup = resolver(tmp_path, prefixes={'52EB3F': 'Not a device identity'})
    value = lookup.resolve('52:EB:3F:26:E9:5A', '52:EB:3F:26:E9:5A')
    assert value['label'] == 'Unknown device (private MAC)'
    assert value['name_source'] == 'unknown' and value['manufacturer'] is None


def test_hostname_precedes_vendor_and_vendor_is_not_model(tmp_path):
    lookup = resolver(tmp_path, prefixes={'001122': 'Manufacturer Inc'})
    assert lookup.resolve('00:11:22:33:44:55', 'Printer')['label'] == 'Printer'
    value = lookup.resolve('00:11:22:33:44:55', '')
    assert value['label'] == 'Manufacturer Inc device'
    assert value['name_source'] == 'manufacturer'
    assert value['manufacturer'] == 'Manufacturer Inc'


def test_vendor_longest_prefix_and_distinct_full_mac(tmp_path):
    lookup = resolver(tmp_path, [dict(mac='00:11:22:33:44:55', name='Known device')],
                      {'001122': 'Large', '0011223': 'Medium', '001122334': 'Small'})
    value = lookup.resolve('00:11:22:33:44:56', '')
    assert value['manufacturer'] == 'Small' and value['name_source'] != 'inventory'


def test_duplicate_binding_and_broken_cache_degrade_without_guessing(tmp_path):
    lookup = resolver(tmp_path, [dict(mac='00:11:22:33:44:55', name=name) for name in ('One', 'Two')])
    assert lookup.resolve('00:11:22:33:44:55', 'DHCP name')['label'] == 'DHCP name'
    assert lookup.health['inventory'] == 'unavailable'
    (tmp_path / 'vendors.json').write_text('not json')
    import direct_names as names
    lookup = names.DeviceNames(tmp_path / 'missing.json', tmp_path / 'vendors.json')
    assert lookup.resolve('00:11:22:33:44:55', '')['label'] == 'Unknown device'
    assert lookup.health['vendors'] == 'unavailable'


def test_ieee_csv_uses_parser_and_validates_prefix():
    import direct_names as names
    blob = b'Registry,Assignment,Organization Name,Organization Address\nMA-L,001122,"Example, Inc",ignored\n'
    assert names.parse_csv(blob, 6) == {'001122': 'Example, Inc'}
    with pytest.raises(ValueError):
        names.parse_csv(blob.replace(b'001122', b'bad-prefix'), 6)


def test_ambiguous_ieee_assignment_blocks_parent_fallback(tmp_path):
    import direct_names as names
    blob = b'Registry,Assignment,Organization Name\nMA-L,001122,One\nMA-L,001122,Two\n'
    assert names.parse_csv(blob, 6) == {'001122': ''}
    lookup = resolver(tmp_path, prefixes={'001122': 'Parent', '001122334': ''})
    value = lookup.resolve('00:11:22:33:44:55', '')
    assert value['name_source'] == 'unknown' and value['manufacturer'] is None


def test_failed_download_keeps_previous_cache(tmp_path):
    import direct_names as names
    target = tmp_path / 'vendors.json'
    target.write_bytes(b'original')
    def fail(*args, **kwargs):
        raise subprocess.TimeoutExpired('fixture', 20)
    with pytest.raises(subprocess.TimeoutExpired):
        names.refresh(target, runner=fail)
    assert target.read_bytes() == b'original'


def test_downloads_only_fixed_public_lists_without_device_mac(tmp_path):
    import direct_names as names
    calls = []
    def download(args, **kwargs):
        calls.append(args)
        url = args[-1]
        width = next(width for source, width in names.SOURCES if source == url)
        prefix = '001122334'[:width]
        return subprocess.CompletedProcess(args, 0,
            ('Registry,Assignment,Organization Name,Organization Address\nMA-L,' + prefix + ',Vendor,unused\n').encode(), b'')
    result = names.refresh(tmp_path / 'vendors.json', runner=download)
    assert len(calls) == len(names.SOURCES)
    assert all('-k' not in args and '--insecure' not in args for args in calls)
    assert all(args[-1].startswith('https://standards-oui.ieee.org/') for args in calls)
    assert set(result['prefixes']) == {'001122', '0011223', '001122334'}


def test_status_name_changes_do_not_change_selection_or_revision(tmp_path, monkeypatch):
    import direct_controller as ctl
    import direct_names as names
    from controller import write
    key = 'A2:C1:5E:29:F5:8E'
    lease = dict(mac=key, ip='192.168.89.197', label='MacBookAir', lease='*D', online=True)
    write(tmp_path / 'config.json', dict(version=1, certificate_expires=4_000_000_000,
          endpoint='194.61.140.217', baseline={'nakhimova': ctl.configuration_hash('')}))
    write(tmp_path / 'state.json', dict(version=1, generation=8, clients={key: dict(lease, selected=True, pending=False, prepared=True)}))
    before = (tmp_path / 'state.json').read_bytes()
    class Connection:
        def close(self):
            pass
    instance = ctl.DirectController(tmp_path, connector=lambda site: Connection())
    monkeypatch.setattr(instance, 'inspect', lambda c: ({key: lease}, {}))
    monkeypatch.setattr(ctl.access, 'value', lambda *args: True)
    monkeypatch.setattr(ctl.access, 'get', lambda c, expression: [{'gateway': 'sstp-direct-in'}] if expression.startswith('[/routing') else '194.61.140.217')
    monkeypatch.setattr(ctl.access, 'run', lambda *args: b'')
    lookup = resolver(tmp_path, [dict(mac=key, name='MacBook Air (Sergey)')])
    monkeypatch.setattr(names, 'DeviceNames', lambda: lookup)
    first = instance.status()
    assert first['devices'][0]['label'] == 'MacBook Air (Sergey)'
    assert first['devices'][0]['selected'] is True and first['devices'][0]['status'] == 'remote'
    lookup.bindings[key] = 'Renamed Laptop'
    second = instance.status()
    assert second['devices'][0]['label'] == 'Renamed Laptop'
    assert first['revision'] == second['revision']
    assert first['devices'][0]['revision'] == second['devices'][0]['revision']
    assert (tmp_path / 'state.json').read_bytes() == before


def test_repository_bindings_have_evidence_and_no_unknown_guess():
    import direct_names as names
    data = json.loads(names.INVENTORY.read_text())
    assert len(data['bindings']) == 21
    assert all((names.ROOT / item['evidence']).is_file() for item in data['bindings'])
    keys = [names.canonical(item['mac']) for item in data['bindings']]
    assert len(set(keys)) == len(keys)
    assert '52:EB:3F:26:E9:5A' not in keys
