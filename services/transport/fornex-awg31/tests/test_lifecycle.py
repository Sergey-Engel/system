"""Offline lifecycle tests. Never read credentials/profiles or run remote tools."""
import base64
import builtins
from contextlib import ExitStack, redirect_stderr, redirect_stdout
import datetime
import hashlib
import io
import json
import os
from pathlib import Path
import re
import secrets
import socket
import subprocess
import sys
import tarfile
import time
import types
import unittest
from unittest.mock import Mock, patch
import urllib.request


ROOT = Path(__file__).resolve().parents[1]
RETIRED = ('prepare', 'deploy', 'finalize', 'expand_fleet')


class PythonLifecycleTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Only script sources are read; all runtime data access below is forbidden.
        cls.sources = {
            name: (ROOT / (name + '.py')).read_text()
            for name in (*RETIRED, 'build', 'verify')
        }

    def setUp(self):
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)
        self.stdout, self.stderr = io.StringIO(), io.StringIO()
        self.stack.enter_context(redirect_stdout(self.stdout))
        self.stack.enter_context(redirect_stderr(self.stderr))
        self.stack.enter_context(patch.object(sys, 'path', sys.path.copy()))
        self.stack.enter_context(patch.dict(sys.modules, {
            'stage8_cenuta': None, 'run_backup': None, 'prepare_stage3': None,
        }))
        self.blocked = []
        targets = [
            (builtins, 'open'), (io, 'open'), (os, 'open'),
            (os, 'umask'), (os, 'chmod'), (os, 'mkdir'), (os, 'rename'),
            (os, 'remove'), (os, 'unlink'), (os, 'system'),
            (subprocess, 'Popen'), (subprocess, 'run'), (subprocess, 'check_output'),
            (socket, 'socket'), (socket, 'create_connection'),
            (urllib.request, 'urlopen'), (urllib.request, 'urlretrieve'),
            (secrets, 'token_bytes'), (time, 'sleep'),
        ]
        targets.extend((Path, name) for name in (
            'open', 'read_text', 'read_bytes', 'write_text', 'write_bytes',
            'mkdir', 'chmod', 'rename', 'replace', 'unlink', 'iterdir',
        ))
        for owner, name in targets:
            blocked = self.stack.enter_context(patch.object(
                owner, name, side_effect=AssertionError('Forbidden runtime I/O')
            ))
            self.blocked.append((name, blocked))
        self.prepare = self.load('prepare')

    def tearDown(self):
        for name, blocked in self.blocked:
            self.assertFalse(blocked.called, 'Forbidden operation: ' + name)

    def load(self, name, *, cli=False, optimize=0):
        module = types.ModuleType('__main__' if cli else name)
        module.__file__ = str(ROOT / (name + '.py'))
        if not cli:
            sys.modules[name] = module
        code = compile(self.sources[name], module.__file__, 'exec', optimize=optimize)
        exec(code, module.__dict__)
        return module

    def assert_retired(self, action, entrypoint):
        with self.assertRaises(SystemExit) as caught:
            action()
        message = caught.exception.code
        self.assertIsInstance(message, str)
        for text in ('RETIRED:', entrypoint, '11 peers', 'AWG2 has been removed',
                     'README.md', 'fresh backup', 'scoped', 'No bypass flag'):
            self.assertIn(text, message)
        self.assertEqual(self.stdout.getvalue(), '')
        self.assertEqual(self.stderr.getvalue(), '')

    def test_imports_do_not_read_state_write_or_run_commands(self):
        for name in (*RETIRED, 'build'):
            with self.subTest(script=name):
                module = self.load(name)
                self.assertTrue(callable(module.main))
        self.assertEqual(self.stdout.getvalue(), '')
        self.assertEqual(self.stderr.getvalue(), '')

    def test_retired_cli_cannot_be_bypassed_by_arguments_or_optimization(self):
        variants = ([], ['--sources'], ['--help'], ['--force'],
                    ['--allow-retired'], ['--sources', '--force'])
        for optimize in (0, 1):
            for name in RETIRED:
                for args in variants:
                    with self.subTest(script=name, args=args, optimize=optimize):
                        with patch.object(sys, 'argv', [name + '.py', *args]):
                            self.assert_retired(
                                lambda: self.load(name, cli=True, optimize=optimize),
                                name + '.py',
                            )

    def test_direct_mutators_fail_even_without_backup_or_service_markers(self):
        for exists in (False, True):
            with patch.object(Path, 'exists', return_value=exists):
                for name in RETIRED:
                    with self.subTest(script=name, state_exists=exists):
                        self.assert_retired(self.load(name).main, name + '.py')
                self.assert_retired(
                    lambda: self.prepare.fetch(ROOT / 'backup'), 'prepare.py fetch'
                )
                fleet = self.load('expand_fleet')
                self.assert_retired(
                    lambda: fleet.sync('fleet-next.conf'), 'expand_fleet.py sync'
                )

    def test_shared_helpers_remain_callable_without_import_side_effects(self):
        stage = types.ModuleType('stage8_cenuta')
        stage.call = Mock(return_value=b'synthetic reply')
        stage.put = Mock(return_value=None)
        backup = types.ModuleType('run_backup')
        backup.ssh_args = Mock(return_value=['synthetic-ssh'])
        with patch.dict(sys.modules, {'stage8_cenuta': stage, 'run_backup': backup}):
            self.assertEqual(self.prepare.call('fornex', 'synthetic'), b'synthetic reply')
            stage.call.assert_called_once_with('fornex', 'synthetic', None, timeout=60)
            self.prepare.call('fornex', 'synthetic', b'input', timeout=240)
            stage.call.assert_called_with('fornex', 'synthetic', b'input', timeout=240)
            self.prepare.put(ROOT / 'synthetic.txt', b'content')
            stage.put.assert_called_once_with(ROOT / 'synthetic.txt', b'content')
            self.assertEqual(self.prepare.ssh_args('fornex'), ['synthetic-ssh'])
            backup.ssh_args.assert_called_once_with('fornex')

    def test_build_remains_available_with_synthetic_inputs_and_mocked_remote(self):
        base = 'synthetic/image@sha256:' + '0' * 64
        dockerfile = 'FROM amneziavpn/amneziawg-go:latest\nRUN true\n'
        rendered = dockerfile.replace('amneziavpn/amneziawg-go:latest', base)
        fixtures = {
            ROOT / 'base-image.json': json.dumps({'RepoDigests': [base]}),
            ROOT / 'source/Dockerfile': dockerfile,
        }
        remote = Mock(return_value=b'synthetic build log')
        write = Mock()
        with patch.object(Path, 'read_text', lambda path: fixtures[path]), \
                patch.object(self.prepare, 'call', remote), \
                patch.object(self.prepare, 'put', write):
            self.load('build', cli=True)
        remote.assert_called_once()
        args, kwargs = remote.call_args
        self.assertEqual(args[:2], ('fornex', 'docker build -t fornex-awg31:20260913 -'))
        self.assertEqual(kwargs, {'timeout': 240})
        with tarfile.open(fileobj=io.BytesIO(args[2]), mode='r:') as archive:
            self.assertEqual(archive.getnames(), ['Dockerfile'])
            self.assertEqual(archive.extractfile('Dockerfile').read(), rendered.encode())
        self.assertEqual(write.call_count, 2)
        write.assert_any_call(ROOT / 'Dockerfile', rendered)
        write.assert_any_call(ROOT / 'build.log', b'synthetic build log')
        self.assertEqual(self.stdout.getvalue(), 'Build complete\n')

    def test_all_python_sources_compile_without_bytecode_files(self):
        for name, source in self.sources.items():
            with self.subTest(script=name):
                compile(source, str(ROOT / (name + '.py')), 'exec')


class ShellLifecycleTests(unittest.TestCase):
    def test_rollback_syntax(self):
        result = subprocess.run(
            ['/bin/sh', '-n', str(ROOT / 'rollback.sh')],
            capture_output=True, env={'PATH': ''}, timeout=5,
        )
        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stdout + result.stderr, b'')

    def test_rollback_refuses_execution_and_sourcing_without_running_docker(self):
        # Sourcing also traps Docker as a shell function; no external tools are in PATH.
        source_wrapper = '''docker() {
    printf '%s\\n' 'FORBIDDEN_DOCKER_CALL' >&2
    return 97
}
. "$1"
'''
        for sourced in (False, True):
            for args in ([], ['--force'], ['--allow-retired']):
                with self.subTest(sourced=sourced, args=args):
                    command = ['/bin/sh']
                    if sourced:
                        command += ['-c', source_wrapper, 'lifecycle-test']
                    result = subprocess.run(
                        [*command, str(ROOT / 'rollback.sh'), *args],
                        capture_output=True, text=True, env={'PATH': ''}, timeout=5,
                    )
                    self.assertEqual(result.returncode, 1)
                    self.assertEqual(result.stdout, '')
                    for text in ('RETIRED:', '11-peer AWG31', 'does not restore AWG2',
                                 'README.md', 'fresh backup', 'No bypass flag'):
                        self.assertIn(text, result.stderr)
                    self.assertNotIn('FORBIDDEN_DOCKER_CALL', result.stderr)


if __name__ == '__main__':
    unittest.main()
