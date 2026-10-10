from uplink_monitor.model import Assessment
from uplink_monitor.state import Machine

OK = Assessment('healthy', 'ok', available=True)
FAIL = Assessment('failed', 'tcp_connect_failed', available=False, transport_alive=True)
PARTIAL = Assessment('partial', 'dns_udp_failed', available=True)
UNKNOWN = Assessment('unknown', 'targets_expired')


def test_transient_confirmation_and_two_successes():
    m = Machine()
    assert m.step(OK, 0) == [] and m.state == 'UP'
    assert m.step(FAIL, 10)[0]['type'] == 'opened' and m.state == 'DEGRADED'
    assert m.step(FAIL, 20) == [] and m.state == 'DEGRADED'
    assert m.step(FAIL, 30)[0]['type'] == 'confirmed' and m.state == 'DOWN'
    m.step(OK, 40)
    assert m.state == 'DOWN'
    m.step(FAIL, 50)
    m.step(PARTIAL, 60)
    events = m.step(PARTIAL, 70)
    assert events[0]['type'] == 'closed' and events[0]['ended'] == 60
    assert m.state == 'DEGRADED'
    assert m.outages == 1


def test_short_failure_preserved_not_counted_as_outage():
    m = Machine()
    m.step(FAIL, 0)
    m.step(FAIL, 10)
    m.step(OK, 20)
    end = m.step(OK, 30)
    assert end[0]['confirmed'] is False and m.outages == 0 and m.state == 'UP'


def test_unknown_interrupts_does_not_close_as_recovered():
    m = Machine()
    for slot in (0, 10, 20):
        m.step(FAIL, slot)
    events = m.step(UNKNOWN, 30)
    assert events[0]['type'] == 'interrupted'
    assert m.state == 'UNKNOWN' and m.outages == 1
    m.step(FAIL, 40)
    assert m.state == 'DEGRADED'
