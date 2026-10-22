"""RU direct exceptions must never expand the existing exact address coverage."""
import sys
from pathlib import Path
import pytest
sys.path.insert(0,str(Path(__file__).parent))
import ru_policy as p


def test_cidr_and_routeros_ranges_have_identical_coverage():
    values=['31.135.244.0-31.135.251.255','77.88.8.0/24','77.88.8.8']
    result=p.networks(values)
    assert result==['31.135.244.0/22','31.135.248.0/22','77.88.8.0/24']
    assert p.digest(values)==p.digest(result)
    assert p.contains(values,'77.88.8.8') and not p.contains(values,'1.1.1.1')


@pytest.mark.parametrize('values',[[],['0.0.0.0/0'],['192.168.0.0/16'],['::/0'],['example.com'],
                                   ['31.135.251.255-31.135.244.0'],['1.1.1.1-192.168.1.1']])
def test_invalid_or_broad_country_lists_are_rejected(values):
    with pytest.raises(ValueError):p.networks(values)
