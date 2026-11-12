import copy
import pytest
from veab.spec import list_scenarios,load_scenario,digest
from veab.sim import run_episode
from veab.verifier import verify_bundle
from veab.ledger import check_chain,Ledger


@pytest.mark.parametrize('scenario',[s.id for s in list_scenarios()])
def test_route_with_safety_gate_is_verified(scenario):
    bundle=run_episode(load_scenario(scenario),'route',17,True)
    result=verify_bundle(bundle)
    assert result['trace_integrity'] and result['verified'],result
    assert result['safety_violations']==0


def test_determinism_identical_bundle_for_same_seed():
    s=load_scenario('hospital-inspection')
    a=run_episode(s,'route',42,True)
    b=run_episode(s,'route',42,True)
    assert a==b


def test_greedy_ablation_can_violate_constraints():
    s=load_scenario('warehouse-transfer')
    unsafe=verify_bundle(run_episode(s,'greedy',17,False))
    safe=verify_bundle(run_episode(s,'greedy',17,True))
    assert unsafe['safety_violations']>0
    assert safe['safety_violations']==0


def test_absence_correct_abstention_not_completion_false_positive():
    s=load_scenario('absence-rejection')
    positive=verify_bundle(run_episode(s,'route',4,True))
    negative=verify_bundle(run_episode(s,'greedy',4,True))
    assert positive['verified'] and positive['task_completed']
    assert not negative['task_completed'] and not negative['verified']


def test_sensor_dropout_intervention():
    b=run_episode(load_scenario('warehouse-transfer'),'route',17,True)
    v=verify_bundle(b)
    assert v['faults']==1 and v['recovered_faults']==1
    assert any(e['kind']=='intervention' and 'sensor' in e['payload']['reason'] for e in b['events'])


def test_event_content_tamper_fails_hash_chain():
    b=run_episode(load_scenario('campus-patrol'))
    tampered=copy.deepcopy(b)
    tampered['events'][5]['payload']['x']=500
    assert not verify_bundle(tampered)['trace_integrity']


def test_missing_event_fails_chain():
    b=run_episode(load_scenario('campus-patrol'))
    tampered=copy.deepcopy(b)
    tampered['events'].pop(4)
    assert not verify_bundle(tampered)['trace_integrity']


def test_scenario_digest_tamper_fails_even_if_trace_intact():
    b=run_episode(load_scenario('campus-patrol'))
    b['manifest']['scenario']['robot_radius']=0.001
    assert not verify_bundle(b)['trace_integrity']


def test_bad_final_manifest_root_fails():
    b=run_episode(load_scenario('campus-patrol'))
    b['manifest']['ledger_root_sha256']='f'*64
    assert not verify_bundle(b)['verified']


def test_hmac_can_validate_separate_signature_key():
    s=load_scenario('campus-patrol')
    b=run_episode(s,'route',13,True,attestation_key='fixture-key')
    assert verify_bundle(b,'fixture-key')['attestation_verified'] is True
    assert not verify_bundle(b,'wrong-key')['verified']
    assert verify_bundle(b)['attestation_verified'] is None
    b['manifest']['policy']='tampered'
    assert not verify_bundle(b,'fixture-key')['verified']


def test_unknown_terminal_claim_rejected_if_chain_rehashed():
    b=run_episode(load_scenario('campus-patrol'))
    ledger=Ledger()
    for event in b['events']:
        payload=copy.deepcopy(event['payload'])
        if event['kind']=='terminal':payload['claimed']='super-success'
        ledger.emit(event['tick'],event['kind'],payload)
    b['events']=ledger.events
    b['manifest']['ledger_root_sha256']=ledger.root
    result=verify_bundle(b)
    assert result['trace_integrity'] and not result['verified']


def test_unattested_external_trace_cannot_be_marked_verified(tmp_path):
    from veab.ingest import ingest_jsonl
    s=load_scenario('campus-patrol')
    trace=tmp_path/'trace.jsonl'
    trace.write_text('{"tick":0,"x":1.0,"y":1.0,"vx":0,"vy":0}\n{"tick":1,"x":1.1,"y":1.0,"vx":0.5,"vy":0}\n')
    b=ingest_jsonl(s,trace)
    v=verify_bundle(b)
    assert v['trace_integrity']
    assert not v['verified']
    assert any('provenance' in reason for reason in v['failure_reasons'])


def test_ingest_rejects_discontinuous_ticks(tmp_path):
    from veab.ingest import ingest_jsonl
    trace=tmp_path/'invalid.jsonl'
    trace.write_text('{"tick":0,"x":1.0,"y":1.0,"vx":0,"vy":0}\n{"tick":3,"x":1.1,"y":1.0,"vx":0.5,"vy":0}\n')
    with pytest.raises(ValueError):ingest_jsonl(load_scenario('campus-patrol'),trace)
