"""Offline controls for locked replay. These are NOT native physics tests."""
from __future__ import annotations

import copy
import math
import pytest
from veab.spec import load_scenario
from veab.simulation.locked_replay import (
    create_tape, standard_tape, validate_tape, validate_execution, paired_physics_report)
from veab.simulation.telemetry import PhysicsRecorder, make_sample
from veab.simulation.isaaclab_locked_collector import IsaacLabTapeCollector
from veab.simulation.native_locked_runner import run_mujoco_tape


def scenario():
    return load_scenario('warehouse-transfer')


def synthetic_trace(tape, *, engine='mujoco', x_shift=0., contact=None):
    s=scenario()
    r=PhysicsRecorder(s,engine,'synthetic-fixture-not-native',tape['scene_sha256'],seed=tape['seed'])
    sx,sy=s.start.x,s.start.y
    r.append(make_sample(0,0,[sx,sy,.16]))
    for i,cmd in enumerate(tape['commands_vx_vy_yaw'],1):
        x=sx+x_shift+0.01*i
        r.append(make_sample(i, s.dt*i,[x,sy,.16],[.05,0,0], command=cmd, contacts=contact))
    return r.finish('unknown')


def test_tape_reproducible_and_referentially_bound():
    s=scenario()
    t=standard_tape(s,seed=17,steps=16)
    validate_tape(s,t)
    assert t==standard_tape(s,seed=17,steps=16)
    assert t['calibration_status']=='unmeasured_research_surrogate'
    assert t['scene_sha256']
    assert t['tape_sha256']
    assert len(t['commands_vx_vy_yaw'])==16


def test_tape_rejects_invalid_commands_and_metadata():
    s=scenario()
    bad=[[s.max_speed*2,0,0]]
    with pytest.raises(ValueError,match='velocity limit'):
        create_tape(s,bad)
    with pytest.raises(ValueError,match='finite'):
        create_tape(s,[[math.nan,0,0]])
    with pytest.raises(ValueError,match='yaw rate'):
        create_tape(s,[[0,0,3]])
    with pytest.raises(ValueError,match='command requires'):
        create_tape(s,[[0,0]])
    t=standard_tape(s)
    for key,value in [
        ('scene_sha256','f'*64), ('coordinate_frame','NED'), ('calibration_status','calibrated'),
        ('seed',-1), ('dt_s',s.dt/2), ('tape_sha256','0'*64)
    ]:
        fake=copy.deepcopy(t); fake[key]=value
        with pytest.raises(ValueError): validate_tape(s,fake)
    fake=copy.deepcopy(t)
    fake['commands_vx_vy_yaw'][0][0]=0.8
    with pytest.raises(ValueError):validate_tape(s,fake)


def test_locked_execution_accepts_synthetic_fixture_without_authenticity_claim():
    t=standard_tape(scenario(),steps=12)
    trace=synthetic_trace(t)
    report=validate_execution(scenario(),t,trace)
    assert report['tape_matches']
    assert report['physical_source_authenticity']=='not_established'
    assert report['trace_integrity']


def test_missing_and_changed_action_rejected():
    t=standard_tape(scenario(),steps=12)
    trace=synthetic_trace(t)
    forged=copy.deepcopy(trace)
    forged['samples'].pop()
    # This would fail even with a self-consistent rehash because it has a missing step.
    from veab.spec import canonical,digest
    import hashlib
    forged['manifest']['sample_count']=len(forged['samples'])
    root='0'*64
    for s in forged['samples']:
        root=hashlib.sha256(bytes.fromhex(root)+canonical(s)).hexdigest()
    forged['manifest']['sample_chain_sha256']=root
    forged['manifest']['manifest_sha256']=digest({k:v for k,v in forged['manifest'].items() if k!='manifest_sha256'})
    with pytest.raises(ValueError,match='missing or extra'):
        validate_execution(scenario(),t,forged)
    altered=copy.deepcopy(trace)
    altered['samples'][3]['command_vx_vy_yaw']=[0.,0.,0.]
    root='0'*64
    for s in altered['samples']:
        root=hashlib.sha256(bytes.fromhex(root)+canonical(s)).hexdigest()
    altered['manifest']['sample_chain_sha256']=root
    altered['manifest']['manifest_sha256']=digest({k:v for k,v in altered['manifest'].items() if k!='manifest_sha256'})
    with pytest.raises(ValueError,match='command differs'):
        validate_execution(scenario(),t,altered)


def test_paired_comparison_zero_error_remains_unvalidated():
    t=standard_tape(scenario(),steps=12)
    a=synthetic_trace(t,engine='mujoco',contact=None)
    b=synthetic_trace(t,engine='isaaclab',contact=None)
    result=paired_physics_report(scenario(),t,a,b)
    assert result['position_rmse_m']==0
    assert result['matched_controls']
    assert not result['contacts_comparable']
    assert result['eligible_for_physics_equivalence_claim'] is False
    assert not result['independently_attested_ground_truth']


def test_paired_comparison_detects_divergence_and_wrong_engines():
    t=standard_tape(scenario(),steps=12)
    a=synthetic_trace(t,engine='mujoco',contact=0)
    b=synthetic_trace(t,engine='isaaclab',x_shift=.2,contact=1)
    r=paired_physics_report(scenario(),t,a,b,max_position_rmse_m=.1)
    assert r['position_rmse_m']>.1
    assert r['position_p90_m']>.1
    assert not r['position_rmse_within_target']
    assert r['contact_count_disagreement_samples']==12
    with pytest.raises(ValueError,match='distinct engines'):
        paired_physics_report(scenario(),t,a,a)


def test_isaac_bridge_uses_native_observation_contract_not_fabricated_engine():
    s=scenario()
    t=standard_tape(s,steps=4)
    recorder=IsaacLabTapeCollector(s,t,engine_version='fixture')
    recorder.append_state(time_s=0,position_xyz_m=[s.start.x,s.start.y,.16],
                          quaternion_xyzw=[0,0,0,1],velocity_xyz_m_s=[0,0,0])
    for tick in range(1,5):
        recorder.append_state(time_s=tick*s.dt,
          position_xyz_m=[s.start.x+.01*tick,s.start.y,.16],
          quaternion_xyzw=[0,0,0,1],velocity_xyz_m_s=[.05,0,0])
    result=recorder.finish()
    assert result['control_contract']['tape_matches']
    assert not result['native_execution_asserted_by_veab']
    assert result['trace']['manifest']['engine']=='isaaclab'


def test_native_mujoco_never_falls_back_to_toy_world(tmp_path):
    import importlib.util
    if importlib.util.find_spec('mujoco') is None:
        with pytest.raises(RuntimeError,match='Native MuJoCo is required'):
            run_mujoco_tape(scenario(),standard_tape(scenario(),steps=4),tmp_path)
    else:
        pytest.skip('This is an offline missing-dependency control, not the native physics integration suite')
