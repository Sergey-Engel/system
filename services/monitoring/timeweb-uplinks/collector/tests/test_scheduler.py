import sys
import time
from uplink_monitor.scheduler import Scheduler, run_bounded
from uplink_monitor.timing import LEGACY_TIMING


def test_success_error_and_output_limit():
    assert run_bounded([sys.executable,'-c','print("ok")']).stdout=='ok\n'
    assert run_bounded(['/does/not/exist']).reason=='spawn_error'
    assert run_bounded([sys.executable,'-c','raise SystemExit(2)']).reason=='batch_failed'
    assert run_bounded([sys.executable,'-c','print("x"*20000)'],output_limit=1000).reason=='output_limit'


def test_descendant_cannot_keep_pipe_open():
    start=time.monotonic()
    command=[sys.executable,'-c','import subprocess,sys; subprocess.Popen([sys.executable,"-c","import time; time.sleep(20)"])']
    assert run_bounded(command,timeout=0.2).reason=='scheduler_deadline'
    assert time.monotonic()-start<1.5


def test_scheduler_no_catchup_and_clock_regression():
    s=Scheduler(0, timing=LEGACY_TIMING)
    assert s.due(0,100)['slot']==100
    assert s.due(1,101) is None
    assert s.due(31,131)['missed']==2
    assert s.missed==2 and s.next_due==40
    assert s.due(40,90)['reason']=='clock_regression'


def test_first_cycle_aligned_to_wall_slot():
    s=Scheduler(100,wall_started=108.5, timing=LEGACY_TIMING)
    assert s.due(100,108.5) is None
    assert s.due(101.5,110)['slot']==110
