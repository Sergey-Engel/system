import sys
import json
import threading
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent))
from routing_progress import Polls
import direct_panel as panel


def test_elapsed_time_does_not_advance_completed_stages():
    now = [10.0]
    polls = Polls(clock=lambda: now[0])
    poll = polls.create('a' * 32, 'nakhimova')
    assert poll.snapshot()['state'] == 'queued'
    now[0] += 15
    assert poll.snapshot()['completed'] == 0
    assert poll.snapshot()['queue_seconds'] == 15
    poll.stage(0)
    now[0] += 80
    value = poll.snapshot()
    assert value['state'] == 'running' and value['completed'] == 0
    assert value['elapsed_seconds'] == 95 and value['queue_seconds'] == 15
    poll.stage(1)
    assert poll.snapshot()['completed'] == 1
    now[0] += 80
    assert poll.snapshot()['completed'] == 1
    poll.stage(None)
    value = poll.snapshot()
    assert value['state'] == 'error' and value['completed'] == 1
    assert value['stage'] == 'Reading router configuration'
    poll.finish(True)
    assert poll.snapshot()['state'] == 'error'


def test_success_capacity_expiry_and_unknown_tokens():
    now = [0.0]
    polls = Polls(clock=lambda: now[0], capacity=1, retention=10)
    poll = polls.create('a' * 32, 'fethiye')
    for i in range(5):
        poll.stage(i)
        assert poll.snapshot()['completed'] == i
    poll.finish(True)
    assert poll.snapshot()['completed'] == 5
    assert poll.snapshot()['state'] == 'complete'
    with pytest.raises(FileExistsError):
        polls.create('a' * 32, 'fethiye')
    with pytest.raises(OverflowError):
        polls.create('b' * 32, 'nakhimova')
    now[0] = 11
    assert polls.get('a' * 32) is None
    assert polls.create('b' * 32, 'nakhimova')
    with pytest.raises(ValueError):
        polls.create('../private', 'nakhimova')
    with pytest.raises(ValueError):
        polls.create('c' * 32, 'other')


def test_progress_only_accepts_sequential_stages_and_preserves_failure():
    poll = Polls().create('a' * 32, 'nakhimova')
    with pytest.raises(ValueError):
        poll.stage(2)
    poll.stage(0)
    poll.stage(1)
    with pytest.raises(ValueError):
        poll.stage(0)
    poll.finish(False)
    poll.stage(2)
    assert poll.snapshot()['completed'] == 1
    assert poll.snapshot()['state'] == 'error'


def test_progress_is_available_while_capture_and_queue_are_locked():
    started, release = threading.Event(), threading.Event()
    calls = []
    def execute(site, progress):
        calls.append(site)
        progress(0)
        started.set()
        assert release.wait(5)
        for i in range(1, 5):progress(i)
        return dict(site=site, source_ready=True, devices=[])
    httpd = panel.server(0, unified=True, routing_execute=execute)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    url = 'http://127.0.0.1:' + str(httpd.server_port)
    def read(path, token=None, host=None):
        headers = {'X-Routing-Poll': token} if token else {}
        if host:headers['Host'] = host
        with urllib.request.urlopen(urllib.request.Request(url+path, headers=headers), timeout=5) as response:
            return json.load(response)
    try:
        with ThreadPoolExecutor(max_workers=2) as workers:
            first = workers.submit(read, '/routing-state/nakhimova', 'a'*32)
            assert started.wait(2)
            live = read('/routing-progress/'+'a'*32)
            assert live['state'] == 'running' and live['completed'] == 0
            second = workers.submit(read, '/routing-state/nakhimova', 'b'*32)
            # Wait for registration, never for the capture lock.
            for _ in range(100):
                try:
                    waiting = read('/routing-progress/'+'b'*32)
                    break
                except urllib.error.HTTPError as error:
                    assert error.code == 404
            else:pytest.fail('Queued progress was not registered')
            assert waiting['state'] == 'queued' and waiting['completed'] == 0
            for path, token, host, code in [('/routing-state/nakhimova', 'a'*32, None, 409),
                    ('/routing-state/nakhimova', 'invalid', None, 400),
                    ('/routing-progress/'+'c'*32, None, None, 404),
                    ('/routing-progress/'+'a'*32, None, 'evil.example', 404)]:
                with pytest.raises(urllib.error.HTTPError) as error:read(path, token, host)
                assert error.value.code == code
            release.set()
            a, b = first.result(), second.result()
            assert a['poll_progress']['completed'] == b['poll_progress']['completed'] == 5
            assert b['poll_progress']['state'] == 'complete'
            assert calls == ['nakhimova']
    finally:
        release.set()
        httpd.shutdown();httpd.server_close();thread.join(2)


def test_unhandled_read_failure_exposes_no_exception_or_false_completion():
    def execute(site, progress):
        for i in range(3):progress(i)
        raise RuntimeError('PRIVATE_EXCEPTION_VALUE')
    httpd = panel.server(0, unified=True, routing_execute=execute)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    request = urllib.request.Request('http://127.0.0.1:'+str(httpd.server_port)+'/routing-state/fethiye',
        headers={'X-Routing-Poll': 'a'*32})
    try:
        with pytest.raises(urllib.error.HTTPError) as error:urllib.request.urlopen(request)
        assert error.value.code == 500
        body = error.value.read().decode()
        assert 'PRIVATE_EXCEPTION_VALUE' not in body
        value = json.loads(body)['poll_progress']
        assert value['state'] == 'error' and value['completed'] == 2
    finally:
        httpd.shutdown();httpd.server_close();thread.join(2)
