import importlib.util
from pathlib import Path

import pytest

SPEC = importlib.util.spec_from_file_location('direct_path_probe', Path(__file__).with_name('direct_path_probe.py'))
p = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(p)


def test_rotation_is_only_owned_interface_and_input_observers_cover_both_ports():
    text = '\n'.join(p.stage_commands('nakhimova', '194.61.140.217'))
    assert 'listen-port=51973' in text
    assert 'dst-port=51973,51974' in text and 'src-port=51973,51974' in text
    assert '51971' not in text and 'DD-' not in text
    assert p.OWNER in p.rotate_command() and p.IFACE in p.rotate_command()
    assert 'wg-s2s-tw' not in text + p.rotate_command()


@pytest.mark.parametrize('port', (51973, 51974))
def test_additional_listener_collision_fails_closed(port):
    with pytest.raises(ValueError):
        p.assert_free({'/interface wireguard': [{'listen-port': port}]})


def test_cleanup_does_not_remove_previous_candidate_or_working_channel():
    text = '\n'.join(p.cleanup_commands())
    assert p.OWNER in text and 's2s-direct-diag-' not in text
    assert 'wg-s2s-tw' not in text and 'DD-' not in text
