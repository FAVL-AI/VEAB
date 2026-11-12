"""Source reconciliation checks are distinct from native-simulation validity."""
from __future__ import annotations
import importlib.util
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
SPEC=importlib.util.spec_from_file_location('v06base',ROOT/'scripts/check_v06_base.py')
mod=importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(mod)


def test_local_studio_snapshot_has_required_base():
    result=mod.check_base(ROOT)
    assert result['eligible']
    assert not result['missing']


def test_older_public_main_like_tree_is_rejected(tmp_path):
    (tmp_path/'veab').mkdir()
    (tmp_path/'veab/spec.py').write_text('')
    report=mod.check_base(tmp_path)
    assert not report['eligible']
    assert 'veab/simulation/scene.py' in report['missing']
    assert 'veab/enterprise/api.py' in report['missing']
