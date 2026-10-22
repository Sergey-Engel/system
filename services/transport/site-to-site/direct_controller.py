"""Serialized local direct-SSTP device selection and observed status."""
import fcntl
import json
from pathlib import Path
import secrets
import time

import direct_access as access
import direct_names as names
import managed
import sstp_direct as policy
from controller import write

CONTROLLER_RELEASE = '3.1.0'


def configuration_hash(export, clients=(), owner=policy.OWNER):
    keys = {c['mac'] for c in clients}
    result = []
    for line in managed.export_lines(export):
        # Unrelated script source can contain RouterOS continuation lines, not shell tokens.
        if owner + ':device-' in line or line.startswith('/ip dhcp-server lease add '):
            path, fields = managed.tokens(line)
            if str(fields.get('comment', '')).startswith(owner + ':device-'):
                continue
            if path == '/ip dhcp-server lease' and fields.get('mac-address') in keys:
                continue
        result.append(line)
    return managed.digest(result)


def clear_device_connections(c, ip, subnet='192.168.89.0/24'):
    ip = managed.address(ip, subnet)
    for row in access.rows(c, '/ip firewall connection'):
        if not any(str(row.get(field, '')).split(':')[0] == ip
                   for field in ('src-address', 'dst-address', 'reply-src-address', 'reply-dst-address')):
            continue
        ident = managed.identity(row['.id'])
        try:
            access.mutate(c, '/ip firewall connection remove ' + ident)
        except RuntimeError:
            # A tracked flow can expire after the snapshot. Reconcile by reading, never replay a write.
            if any(r.get('.id') == ident for r in access.rows(c, '/ip firewall connection')):
                raise


class DirectController:
    def __init__(self, directory=access.PRIVATE, connector=access.connect, direction='forward'):
        if direction not in ('forward', 'reverse'):
            raise ValueError('invalid_direct_direction')
        self.direction = direction
        reverse = direction == 'reverse'
        self.source, self.remote = ('nakhimova', 'fethiye') if reverse else ('fethiye', 'nakhimova')
        self.owner, self.table = (policy.REVERSE_OWNER, policy.REVERSE_TABLE) if reverse else (policy.OWNER, policy.TABLE)
        self.iface = policy.CLIENT if reverse else policy.SERVER
        self.subnet = '192.168.88.0/24' if reverse else '192.168.89.0/24'
        self.directory, self.connector = Path(directory), connector
        self.shared = self.directory.parent if reverse else self.directory
        self.config = access.private_json(self.shared / 'config.json')
        if reverse and not self.config.get('reverse_enabled'):
            raise ValueError('reverse_not_installed')
        self.state = access.private_json(self.directory / 'state.json')
        if self.config.get('version') != 1 or self.state.get('version') != 1:
            raise ValueError('invalid_direct_schema')
        if type(self.state.get('generation')) is not int or self.state['generation'] < 0:
            raise ValueError('invalid_direct_generation')
        if not isinstance(self.state.get('clients'), dict) or len(self.state['clients']) > 64:
            raise ValueError('invalid_direct_clients')
        for key, client in self.state['clients'].items():
            if managed.mac(key) != client['mac'] or managed.address(client['ip'], self.subnet) != client['ip']:
                raise ValueError('invalid_direct_identity')
            if type(client['selected']) is not bool or type(client['pending']) is not bool:
                raise ValueError('invalid_direct_selection')

    def save(self):
        self.state['generation'] += 1
        write(self.directory / 'state.json', self.state)
        if self.shared.resolve() == access.PRIVATE.resolve():
            from direct_private import checkpoint
            checkpoint([self.directory / 'state.json'])

    def device_revision(self, key, item):
        # Bind approval to this lease and persisted selection, not unrelated DHCP activity.
        return managed.digest(dict(direction=self.direction, generation=self.state['generation'], baseline=self.config.get('baseline'),
            mac=managed.mac(key), ip=managed.address(item['ip'], self.subnet), lease=managed.identity(item['lease']),
            selected=bool(self.state['clients'].get(key, {}).get('selected'))))

    def specs(self, key, ip):
        return policy.client_policy(key, ip, direction=self.direction,
                                    ru_bypass=self.config.get('ru_bypass_enabled') is True)

    def inspect(self, c):
        export = access.run(c, '/export terse').decode()
        clients = list(self.state['clients'].values())
        expected = configuration_hash(self.config['baseline_exports'][self.source], clients, self.owner)
        if configuration_hash(export, clients, self.owner) != expected:
            raise ValueError(self.source + '_configuration_drift')
        server = self.config.get('reverse_dhcp_server', 'defconf') if self.direction == 'reverse' else self.config['dhcp_server']
        leases = managed.leases(access.rows(c, '/ip dhcp-server lease'), server, self.subnet)
        owned = {spec['comment']: spec for client in clients for spec in self.specs(client['mac'], client['ip'])}
        found = {}
        for line in managed.export_lines(export):
            if self.owner + ':device-' not in line:
                continue
            path, fields = managed.tokens(line)
            comment = fields.get('comment', '')
            if not str(comment).startswith(self.owner + ':device-'):
                continue
            if comment not in owned or comment in found:
                raise ValueError('unregistered_direct_object')
            spec = owned[comment]
            _, expected = managed.tokens(path + ' add ' + spec['properties'])
            allowed = dict(expected, comment=comment, disabled=fields.get('disabled', 'no'))
            defaults = {'log': 'no', 'log-prefix': ''}
            if path != spec['path'] or any(k not in allowed and defaults.get(k) != v for k, v in fields.items()):
                raise ValueError('direct_object_selector_drift')
            implicit = {'action': 'accept', 'disabled': 'no'}
            if any(managed.norm(fields.get(k, implicit.get(k)), k) != managed.norm(v, k)
                   for k, v in allowed.items()):
                raise ValueError('direct_object_value_drift')
            found[comment] = fields.get('disabled', 'no') == 'yes'
        for client in clients:
            key = client['mac']
            if key in leases and leases[key]['ip'] != client['ip']:
                raise ValueError('direct_lease_identity_changed')
            if not client['pending'] and client.get('prepared'):
                values = [found.get(s['comment']) for s in self.specs(key, client['ip'])]
                if any(v is not (not client['selected']) for v in values):
                    raise ValueError('direct_selection_drift')
        lines = managed.export_lines(export)
        if self.config.get('ru_bypass_enabled') is True:
            positions={}
            for i,line in enumerate(lines):
                if self.owner+':device-' in line:
                    path,fields=managed.tokens(line)
                    positions[fields.get('comment')]=i
            for client in clients:
                prefix=self.owner+':device-'+client['mac'].replace(':','').lower()
                for earlier,later in [('ru-policy','private-policy'),('private-policy','main-policy'),
                                      ('ru-out','leak'),('ru-in','leak')]:
                    first,last=prefix+':'+earlier,prefix+':'+later
                    if first in positions and last in positions and positions[first]>positions[last]:
                        raise ValueError('direct_ru_rule_order_changed')
        for spec in owned.values():
            if spec['comment'] not in found or not spec['head']:
                continue
            _, expected = managed.tokens(spec['path'] + ' add ' + spec['properties'])
            own_position = next(i for i, line in enumerate(lines) if line.startswith(spec['path'] + ' add ')
                                and managed.tokens(line)[1].get('comment') == spec['comment'])
            for i, line in enumerate(lines):
                if not line.startswith(spec['path'] + ' add '):
                    continue
                path, fields = managed.tokens(line)
                if (path == spec['path'] and fields.get('chain') == expected.get('chain')
                        and not str(fields.get('comment', '')).startswith(self.owner + ':device-')
                        and i < own_position):
                    raise ValueError('direct_device_rule_order_changed')
        return leases, found

    def status(self):
        leases, errors, validated = {}, [], False
        tunnel_up = False
        try:
            c = self.connector(self.source)
            try:
                leases, _ = self.inspect(c)
                validated = True
                path = '/interface sstp-client' if self.direction == 'reverse' else '/interface sstp-server'
                tunnel_up = access.value(c, path, '[find where name="' + self.iface + '"]', 'running') is True
                active = access.get(c, '[/routing route print as-value where routing-table="' + self.table + '" and active=yes]')
                if len(active) != 1 or active[0].get('gateway') != self.iface:
                    tunnel_up = False
                cloud = access.get(c, '[/ip cloud get public-address]') if self.source == 'fethiye' else None
                if cloud and cloud != self.config['endpoint']:
                    errors.append('Public address changed; reviewed certificate renewal required')
            finally:
                c.close()
        except (RuntimeError, ValueError, OSError, KeyError, TypeError):
            errors.append(self.source.title() + ' unavailable or configuration requires review')
        if validated:
            try:
                c = self.connector(self.remote)
                try:
                    if self.config.get('reverse_enabled'):
                        peer_dir = self.shared if self.direction == 'reverse' else self.shared / 'reverse'
                        peer = DirectController(peer_dir, connector=self.connector, direction='forward' if self.direction == 'reverse' else 'reverse')
                        peer.inspect(c)
                    elif configuration_hash(access.run(c, '/export terse').decode()) != self.config['baseline'][self.remote]:
                        raise ValueError(self.remote + '_configuration_drift')
                    path = '/interface sstp-server' if self.direction == 'reverse' else '/interface sstp-client'
                    iface = policy.SERVER if self.direction == 'reverse' else policy.CLIENT
                    if access.value(c, path, '[find where name="' + iface + '"]', 'running') is not True:
                        tunnel_up = False
                    if self.remote == 'fethiye':
                        cloud = access.get(c, '[/ip cloud get public-address]')
                        if cloud and cloud != self.config['endpoint']:
                            errors.append('Public address changed; reviewed certificate renewal required')
                finally:
                    c.close()
            except access.RouterUnavailable as exc:
                errors.append(self.remote.title() + ' management unavailable after connection retry (' + exc.reason + '); selection unchanged')
            except ValueError:
                errors.append(self.remote.title() + ' configuration requires review')
            except (RuntimeError, OSError, KeyError, TypeError):
                errors.append(self.remote.title() + ' management read or identity validation failed; selection unchanged')
        remaining = int((self.config['certificate_expires'] - time.time()) / 86400)
        if remaining <= 30:
            errors.append('Certificate renewal required: ' + str(remaining) + ' days remaining')
        devices, lookup = [], names.DeviceNames()
        for key in sorted(set(leases) | set(self.state['clients'])):
            live, saved = leases.get(key), self.state['clients'].get(key)
            selected = bool(saved and saved['selected'])
            if not selected and not (live and live['online']):
                continue
            item = live or saved
            state = 'local'
            if selected:
                state = 'pending' if saved['pending'] else 'unknown' if not validated or errors else 'remote' if tunnel_up else 'blocked'
            devices.append(dict(id=key, **lookup.resolve(key, item['label']), ip=item['ip'], online=bool(live and live['online']),
                                selected=selected, status=state, revision=self.device_revision(key, item)))
        revision = managed.digest(dict(direction=self.direction, state=self.state, leases=leases, validated=validated))
        pending = any(c['pending'] for c in self.state['clients'].values())
        if pending:
            errors.append('Pending device operation; local internet may still be in use; remove after review')
        return dict(controller_release=CONTROLLER_RELEASE, direction=self.direction, source=self.source, destination=self.remote,
                    available=validated and tunnel_up and not errors, can_remove=validated, revision=revision,
                    checked_at=time.time(), tunnel=dict(state='unknown' if errors else 'up' if tunnel_up else 'down' if validated else 'unknown',
                        path='Direct SSTP', egress='unknown' if errors else 'route-ready' if tunnel_up and validated else 'blocked' if validated else 'unknown',
                        detail='TCP/443; no automatic fallback; certificate: ' + str(remaining) + ' days'),
                    devices=devices, name_lookup=lookup.health, error='; '.join(errors) or None)

    def action(self, action, device, revision):
        self.operation_phase = 'preflight'
        if self.config.get('routing_enabled') is True:
            raise ValueError('use_unified_device_routing')
        if action not in ('add', 'remove'):
            raise ValueError('invalid_direct_action')
        key = managed.mac(device)
        before = self.status()
        target = next((d for d in before.get('devices', []) if d['id'] == key), None)
        if (not target or not isinstance(revision, str)
                or not any(secrets.compare_digest(revision, candidate)
                           for candidate in (target['revision'], before['revision']))):
            raise ValueError('device_list_changed_refresh_and_retry')
        if not before['can_remove'] or action == 'add' and not before['available']:
            raise ValueError('validated_direct_route_unavailable')
        c = self.connector(self.source)
        try:
            leases, found = self.inspect(c)
            client = self.state['clients'].get(key)
            binding = leases.get(key) or client
            if not binding or not secrets.compare_digest(self.device_revision(key, binding), target['revision']):
                raise ValueError('device_list_changed_refresh_and_retry')
            self.change_selection(c,key,action,binding,found)
            self.operation_phase = 'status'
            result = self.status()
            return dict(result, success=True)
        finally:
            c.close()

    def change_selection(self,c,key,action,lease,found,require_online=True):
        """Apply a source-validated selection under the caller's shared lock."""
        key=managed.mac(key)
        ip=managed.address(lease['ip'],self.subnet)
        if lease['mac']!=key or action not in ('add','remove'):
            raise ValueError('invalid_direct_identity')
        client=self.state['clients'].get(key)
        if client and client['ip']!=ip:
            raise ValueError('direct_lease_identity_changed')
        if action=='add':
            if require_online and not lease['online']:
                raise ValueError('device_not_online')
            if not client:
                if len(self.state['clients'])>=64:
                    raise ValueError('direct_device_limit')
                client=dict(lease,selected=True,pending=True,prepared=False)
                self.state['clients'][key]=client
            self.operation_phase='prepare_device'
            client.update(selected=True,pending=True)
            self.save()
            ident=managed.identity(lease['lease'])
            if access.value(c,'/ip dhcp-server lease',ident,'dynamic'):
                access.mutate(c,'/ip dhcp-server lease make-static '+ident)
            specs=self.specs(key,ip)
            for spec in specs:
                if spec['comment'] not in found:
                    access.mutate(c,policy.device_add(spec))
            self.operation_phase='device_policy'
            for spec in specs:
                access.mutate(c,spec['path']+' enable [find where comment="'+spec['comment']+'"]')
        else:
            if not client or not client['selected']:
                raise ValueError('device_not_selected')
            self.operation_phase='prepare_device'
            client['pending']=True
            self.save()
            specs=self.specs(key,ip)
            self.operation_phase='device_policy'
            for spec in reversed(specs):
                if spec['comment'] in found:
                    access.mutate(c,spec['path']+' disable [find where comment="'+spec['comment']+'"]')
            client['selected']=False
        self.operation_phase='connection_cleanup'
        clear_device_connections(c,ip,self.subnet)
        self.operation_phase='readback'
        _,flags=self.inspect(c)
        if any(flags.get(s['comment'],action=='remove') is not (action=='remove') for s in specs):
            raise RuntimeError('direct_device_readback_failed')
        self.operation_phase='commit'
        # A failed Add may have created only some disabled objects. Remove can
        # confirm Local without fabricating the missing rules or marking them prepared.
        client.update(prepared=all(s['comment'] in flags for s in specs),pending=False)
        self.save()


def execute(action='status', device=None, revision=None, directory=access.PRIVATE, direction='forward'):
    if direction not in ('forward', 'reverse'):
        raise ValueError('invalid_direct_direction')
    shared = Path(directory)
    directory = shared / 'reverse' if direction == 'reverse' else shared
    factory = lambda: DirectController(directory) if direction == 'forward' else DirectController(directory, direction=direction)
    with (shared / 'controller.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        ctl = factory()
        changed = []
        try:
            result = ctl.status() if action == 'status' else ctl.action(action, device, revision)
        except (RuntimeError, ValueError, OSError, KeyError, TypeError) as exc:
            write(directory / 'last-error.json', dict(type=type(exc).__name__, error=str(exc)[:256],
                  phase=getattr(ctl, 'operation_phase', 'preflight'), timestamp=time.time()))
            changed.append(directory / 'last-error.json')
            messages = {
                'device_list_changed_refresh_and_retry': 'This device or its saved selection changed. Refresh status and retry. No settings were changed.',
                'device_not_online': 'This device is no longer online. Refresh status and retry. No settings were changed.',
                'validated_direct_route_unavailable': 'The direct route is not ready. Refresh status before retrying. No settings were changed.',
                'device_not_selected': 'This device is not selected. Refresh status. No settings were changed.',
                'direct_device_limit': 'The device limit has been reached. No settings were changed.',
            }
            code = str(exc) if str(exc) in messages else 'direct_operation_not_confirmed'
            # The failed operation may have changed memory without committing that selection.
            ctl = factory()
            result = dict(ctl.status(), success=False, error_code=code,
                          operation_error=messages.get(code, 'Direct operation not confirmed; displayed selection was reloaded from saved state.'))
        if action != 'status':
            with (directory / 'actions.jsonl').open('a') as log:
                log.write(json.dumps(dict(timestamp=time.time(), action=action, device=device,
                    success=result.get('success') is True, generation=ctl.state['generation'])) + '\n')
            changed.append(directory / 'actions.jsonl')
        if changed and shared.resolve() == access.PRIVATE.resolve():
            from direct_private import checkpoint
            checkpoint(changed)
        return result
