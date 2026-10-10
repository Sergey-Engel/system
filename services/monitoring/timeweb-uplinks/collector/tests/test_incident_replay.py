import sys
from pathlib import Path

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from replay_incident import failed_observations, replay
from uplink_monitor.model import assess


def test_actual_cenuta_failure_not_hidden_by_helper_exit_zero():
    probes=failed_observations()
    assert all(p.valid and p.success is False and p.phase=='tcp_connect' for p in probes['cenuta'])
    assert all(p.valid and p.success is True for p in probes['fornex'])
    a=assess(probes['cenuta'],path_verified=True)
    assert a.kind=='failed' and a.scope=='undetermined'
    # A separately timestamped diagnostic context must not be invented from curl.
    assert a.transport_alive is None


def test_real_failure_and_recovery_synthetic_thresholds(tmp_path):
    report=replay(tmp_path/'replay')
    assert report['actual_recovery']['cenuta']['kind']=='healthy'
    timeline=report['synthetic_timeline']
    assert [x['channels']['cenuta']['state'] for x in timeline]==[
        'DEGRADED','DEGRADED','DOWN','DOWN','UP','UNKNOWN','UP','UP']
    assert report['synthetic_summary']['failed_seconds']==30
    assert report['synthetic_summary']['unknown_seconds']==10
    assert report['synthetic_summary']['outage_segments_started']==1
    assert report['synthetic_incidents']['items'][0]['ended']==30
    assert report['stale_snapshot']['cenuta']['state']=='UNKNOWN'
