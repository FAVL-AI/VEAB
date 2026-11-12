"""v0.4 synthetic control tests. Not tests of real robot reliability."""
import ast
import copy
import csv
import json
import subprocess
import sys
from pathlib import Path

import pytest

from assurance_controls.generate_fixtures import write_fixtures
from assurance_controls.run_controls import execute, metrics, wilson
from assurance_controls.adjudication import make_blinded_template, analyse_adjudication
from assurance_controls.scene_power import scene_sample_plan

HERE=Path(__file__).resolve().parents[1]
MONITOR=HERE/'external_monitor'/'monitor.py'


def test_controls_sensitivity_and_specificity(tmp_path):
    labels=write_fixtures(tmp_path)
    assert len(labels)>=15
    report=execute(tmp_path)
    p=report['graders']['process_monitor_accept']
    assert p['TP_reject_bad']==report['n_known_bad']
    assert p['TN_accept_good']==report['n_known_good']
    assert p['FP_reject_good']==p['FN_accept_bad']==0
    assert report['graders']['terminal_only_accept']['FN_accept_bad']>0
    assert report['graders']['safety_aware_terminal_accept']['FN_accept_bad']>0


def test_standalone_monitor_no_veab_package_imports():
    tree=ast.parse(MONITOR.read_text())
    imports=[]
    for node in ast.walk(tree):
        if isinstance(node,ast.Import): imports.extend(alias.name for alias in node.names)
        if isinstance(node,ast.ImportFrom): imports.append(node.module or '')
    assert all(not name.startswith(('veab','mujoco','isaac')) for name in imports)


def test_external_monitor_has_no_veab_imports():
    source = Path(MONITOR).read_text()
    assert "import veab" not in source
    assert "from veab" not in source


def test_missing_proposal_rejected(tmp_path):
    write_fixtures(tmp_path)
    case=tmp_path/'missing_proposal.json'
    result=subprocess.run([sys.executable,str(MONITOR),'--input',str(case)],capture_output=True,text=True)
    assert result.returncode==0
    assert not json.loads(result.stdout)['record_complete']


def test_swept_obstacle_and_zone_detected(tmp_path):
    write_fixtures(tmp_path)
    found=[]
    for id in ('swept_zone_crossing','obstacle_contact'):
        output=subprocess.check_output([sys.executable,str(MONITOR),'--input',str(tmp_path/f'{id}.json')],text=True)
        found.append({v['kind'] for v in json.loads(output)['violations']})
    assert 'forbidden_zone' in found[0]
    assert 'obstacle_contact' in found[1]


def test_good_clearance_and_legitimate_recovery_accepted(tmp_path):
    write_fixtures(tmp_path)
    for id in ('good_zone_clearance','good_recovered'):
        p=subprocess.check_output([sys.executable,str(MONITOR),'--input',str(tmp_path/f'{id}.json')],text=True)
        assert json.loads(p)['process_accepted']


def test_coherent_forgery_cannot_be_authenticated_by_monitor(tmp_path):
    """Known negative finding: a coherent untrusted forged record passes geometry checks.

    Demonstrates that separate implementation != trusted source provenance.
    """
    write_fixtures(tmp_path)
    source=json.loads((tmp_path/'keepout_unreported.json').read_text())
    clean=json.loads((tmp_path/'good_nominal.json').read_text())
    source['trace']=copy.deepcopy(clean['trace'])
    target=tmp_path/'coherently_forged.json';target.write_text(json.dumps(source))
    output=subprocess.check_output([sys.executable,str(MONITOR),'--input',str(target)],text=True)
    assert json.loads(output)['process_accepted']  # Important security LIMITATION, not a desirable capability.


def test_monitor_rejects_nonfinite_and_corrupt_schema(tmp_path):
    write_fixtures(tmp_path)
    bad=json.loads((tmp_path/'good_nominal.json').read_text())
    bad['trace']['states'][0]['x']='nan'
    p=tmp_path/'malformed.json';p.write_text(json.dumps(bad))
    response=subprocess.run([sys.executable,str(MONITOR),'--input',str(p)],capture_output=True,text=True)
    assert response.returncode!=0


def test_blank_reviewer_template_is_not_human_adjudication(tmp_path):
    write_fixtures(tmp_path)
    path=tmp_path/'reviewers.csv'
    assert make_blinded_template(tmp_path,path)>=15
    out=analyse_adjudication(path)
    assert out['status']=='not_evaluable'


def test_human_agreement_is_calculated_not_invented(tmp_path):
    path=tmp_path/'reviewers.csv'
    with path.open('w',newline='') as f:
        w=csv.DictWriter(f,fieldnames=['episode_id','reviewer_id','verdict']);w.writeheader()
        for item,label in (('x','reject'),('y','accept'),('z','reject'),('w','accept')):
            for reviewer in ('R1','R2'): w.writerow({'episode_id':item,'reviewer_id':reviewer,'verdict':label})
    assert analyse_adjudication(path)['cohens_kappa']==1


def test_power_uses_scenes_not_trial_rows():
    result=scene_sample_plan(.2,.4)
    assert result['estimated_independent_scenes']>=30
    assert 'scene' in result['unit']
    with pytest.raises(ValueError):scene_sample_plan(0,.4)


def test_wilson_bounds():
    assert wilson(0,10)[0]==0
    assert wilson(10,10)[1]==1


def test_no_incremental_unsafe_detection_over_reconstructed_terminal(tmp_path):
    write_fixtures(tmp_path)
    report=execute(tmp_path)
    assert report['graders']['reconstructed_safety_terminal_accept']['TP_reject_bad']==8
    assert report['incremental_rejections_vs_reconstructed_safety_terminal']['unsafe']==0
    assert report['incremental_rejections_vs_reconstructed_safety_terminal']['evidence']==3
