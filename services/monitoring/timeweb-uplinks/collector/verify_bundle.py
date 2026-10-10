"""Validate the local candidate inventory and write non-secret reproducibility evidence."""
import ast
import datetime
import hashlib
import json
from pathlib import Path
import subprocess
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT.parents[2] / '.local/evidence'/'20260911-batch-daemon'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    config = json.loads((ROOT/'collector/config.candidate.json').read_text())
    assert config['allow_snapshot_scope'] is False
    for name, expected in config['helper_sha256'].items():
        assert sha(ROOT/'candidate'/name)==expected, name
    assert sha(ROOT/'guardctl.sh')=='2f883e3ea356b1d88719a148acb89a5b50ccc629b6b51fd619fe2f67ab88cde1'
    inventory = {}
    for base in (ROOT/'collector', ROOT/'candidate'):
        for path in sorted(base.rglob('*')):
            if not path.is_file() or path.suffix not in ('.py','.sh','.json','.txt','.ini'):
                continue
            if any(x in path.parts for x in ('__pycache__','.pytest_cache')):
                continue
            if path.suffix=='.py':
                ast.parse(path.read_text(), filename=str(path))
            if path.suffix=='.sh':
                subprocess.run(['/bin/bash','-n',str(path)],check=True)
            inventory[str(path.relative_to(ROOT))] = sha(path)
    tests = ET.parse(OUT/'pytest.xml').getroot().find('testsuite').attrib
    assert tests['errors']==tests['failures']==tests['skipped']=='0'
    load = json.loads((OUT/'load-final/load-report.json').read_text())
    assert load['local_budget_pass'] and load['channel_rows']==43200
    labs = sorted((ROOT.parents[2] / '.local/evidence').glob('*-batch-lab/result.json'))
    latest = json.loads(labs[-1].read_text())
    assert latest['returncode']==0 and 'SUMMARY failures=0' in latest['stdout']
    assert 'LIVE_ROUTING_UNCHANGED' in latest['stdout']
    assert 'PASS full TLS timeout batch stays bounded' in latest['stdout']
    value = dict(timestamp=datetime.datetime.now(datetime.timezone.utc).isoformat(),
        files=inventory, tests={k:tests[k] for k in ('tests','errors','failures','skipped','time')},
        load_report='load-final/load-report.json',
        linux_evidence=str(labs[-1].relative_to(ROOT)), installed_helper_changed=False,
        production_deployed=False, universal_generation_accepted=False)
    (OUT/'source-manifest.json').write_text(json.dumps(value,indent=2)+'\n')
    print(json.dumps({k:v for k,v in value.items() if k!='files'},indent=2))
    print('Verified source files:',len(inventory))


if __name__=='__main__':
    main()
