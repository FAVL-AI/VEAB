"""Mechanism regression tests. Deliberately constructed records, not robot validation."""
import copy
import importlib
import json
import subprocess
import sys
from pathlib import Path
import pytest
from veab.m3_replay.core import (
    CONTRACT_SCHEMA, RECORD_SCHEMA, ContractError, audit_records, canonical_bytes,
    iter_jsonl, load_contract, sha256_obj, validate_contract,
)
from veab.m3_replay.rosbag2_adapter import iter_rosbag2_mcap,require_rosbag_input

ROOT=Path(__file__).resolve().parents[1]
CONTRACT=ROOT/'contracts/m3_nav_v1.template.json'
FIX=ROOT/'examples/m3'
BASE=json.loads(CONTRACT.read_text())


def load(name):
    return list(iter_jsonl(FIX/(name+'.jsonl')))


def report(name, contract=None):
    return audit_records(contract or BASE, load(name),evidence_source='synthetic_control')


def test_contract_example_is_readonly_and_unattested():
    assert BASE['purpose']=='read_only_evidence_audit'
    assert BASE['source_trust']=='unattested'
    validate_contract(BASE)


def test_contract_digest_order_invariant():
    assert sha256_obj(BASE)==sha256_obj(json.loads(json.dumps(BASE,sort_keys=True)))
    assert canonical_bytes(BASE)==canonical_bytes(json.loads(json.dumps(BASE,sort_keys=True)))


def test_contract_mutation_changes_digest():
    c=copy.deepcopy(BASE);c['channels']['odometry']['topic']='/somewhere'
    assert sha256_obj(BASE)!=sha256_obj(c)

@pytest.mark.parametrize('field,value',[
    ('purpose','robot_actuation'),('source_trust','trusted'),('schema_version','other')
])
def test_contract_cannot_claim_control_or_provenance(field,value):
    c=copy.deepcopy(BASE);c[field]=value
    with pytest.raises(ContractError):validate_contract(c)


def test_contract_duplicate_topic_rejected():
    c=copy.deepcopy(BASE);c['channels']['imu']['topic']='/odom'
    with pytest.raises(ContractError,match='duplicate'):validate_contract(c)


def test_contract_missing_required_mapping_rejected():
    c=copy.deepcopy(BASE);c['channels']['odometry']['topic']=None
    with pytest.raises(ContractError):validate_contract(c)


def test_contract_bool_masquerading_as_int_rejected():
    c=copy.deepcopy(BASE);c['channels']['odometry']['max_gap_ns']=True
    with pytest.raises(ContractError):validate_contract(c)


def test_contract_explicit_window_valid():
    c=copy.deepcopy(BASE);c['window']={'mode':'explicit','start_ns':1_000_000_000,'end_ns':1_400_000_000}
    assert report('clean',c)['status']=='CONTRACT_OBSERVED'


def test_contract_explicit_window_bad():
    c=copy.deepcopy(BASE);c['window']={'mode':'explicit','start_ns':1_400_000_000,'end_ns':1_000_000_000}
    with pytest.raises(ContractError):validate_contract(c)

@pytest.mark.parametrize('case',[
 'clean','missing_header','unknown_extra_topic','truncated_one_sample'
])
def test_constructed_valid_cases_accept(case):
    r=report(case)
    assert r['status']=='CONTRACT_OBSERVED',r['errors']
    assert r['physical_safety_validated'] is False
    assert r['sensor_authenticity_validated'] is False

@pytest.mark.parametrize('case,code',[
 ('no_odom','REQUIRED_TOPIC_MISSING'),('no_cmd','REQUIRED_TOPIC_MISSING'),
 ('no_scan','REQUIRED_TOPIC_MISSING'),('wrong_type','TYPE_MISMATCH'),
 ('type_flip_lidar','TYPE_MISMATCH'),('backwards_timestamp','TIME_REVERSED'),
 ('large_gap','TOPIC_GAP')
])
def test_constructed_invalid_cases_reject(case,code):
    r=report(case)
    assert r['status']=='EVIDENCE_INCOMPLETE'
    assert code in {e['code'] for e in r['errors']}
    assert all(a['attribution_status']=='HYPOTHESIS_ONLY' for a in r['candidate_attributions'])


def test_empty_recording_rejected():
    assert report('clean')['diagnostics']['record_count']>0
    r=audit_records(BASE,[],evidence_source='empty')
    assert 'EMPTY_RECORDING' in [e['code'] for e in r['errors']]


def test_metadata_only_header_requirement_fails_closed():
    c=copy.deepcopy(BASE);c['channels']['odometry']['max_header_lag_ns']=50_000_000
    r=report('clean',c)
    assert 'HEADER_TIMESTAMP_MISSING' in [e['code'] for e in r['errors']]


def test_header_clock_gap_detected():
    c=copy.deepcopy(BASE);c['channels']['odometry']['max_header_lag_ns']=10_000_000
    rows=load('clean')
    for r in rows:
        if r['topic']=='/odom':r['header_stamp_ns']=r['log_time_ns']
    rows[0]['header_stamp_ns']-=20_000_000
    audit=audit_records(c,rows,evidence_source='synthetic')
    assert 'HEADER_CLOCK_GAP' in [e['code'] for e in audit['errors']]


def test_frame_conflict_detected():
    c=copy.deepcopy(BASE);c['channels']['odometry']['frame_id']='odom'
    rows=load('clean'); rows[0]['frame_id']='map'
    r=audit_records(c,rows,evidence_source='synthetic')
    assert 'FRAME_MISMATCH' in [e['code'] for e in r['errors']]


def test_jsonl_rejects_oversized_input(tmp_path):
    p=tmp_path/'oversize.jsonl';p.write_text('X'*(1_048_576+1))
    with pytest.raises(ContractError,match='size limit'):list(iter_jsonl(p))


def test_jsonl_rejects_non_object(tmp_path):
    p=tmp_path/'bad.jsonl';p.write_text('42\n')
    with pytest.raises(ContractError):list(iter_jsonl(p))


def test_jsonl_rejects_bad_json(tmp_path):
    p=tmp_path/'bad.jsonl';p.write_text('{x}\n')
    with pytest.raises(ContractError):list(iter_jsonl(p))


def test_native_rosbag_missing_path_rejected():
    with pytest.raises(ContractError): require_rosbag_input('/none/synthetic/does-not-exist.mcap')


def test_cli_success_and_failure(tmp_path):
    for case,rc in [('clean',0),('no_odom',3)]:
        dest=tmp_path/f'{case}.json'
        result=subprocess.run([sys.executable,'-m','veab.m3_replay.cli',
             '--contract',str(CONTRACT),'--jsonl',str(FIX/(case+'.jsonl')),'--out',str(dest)],
             cwd=ROOT,capture_output=True,text=True)
        assert result.returncode==rc,result.stderr
        assert json.loads(dest.read_text())['status']==('CONTRACT_OBSERVED' if rc==0 else 'EVIDENCE_INCOMPLETE')


def test_independent_monitor_import_isolation():
    text=(ROOT/'external_monitor/m3_record_monitor.py').read_text()
    import ast
    tree=ast.parse(text)
    for node in ast.walk(tree):
        if isinstance(node,ast.Import):
            assert all(not a.name.startswith('veab') for a in node.names)
        if isinstance(node,ast.ImportFrom):
            assert not (node.module or '').startswith('veab')

@pytest.mark.parametrize('case,pass_expected',[
 ('clean',True),('no_scan',False),('wrong_type',False),
 ('backwards_timestamp',False),('large_gap',False)
])
def test_independent_monitor_agrees_on_constructed_cases(case,pass_expected):
    import importlib.util
    path=ROOT/'external_monitor/m3_record_monitor.py'
    spec=importlib.util.spec_from_file_location('m3_record_monitor',path)
    mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod)
    verdict=mod.independently_check(CONTRACT,FIX/(case+'.jsonl'))
    assert (verdict['verdict']=='OBSERVED') is pass_expected
    assert verdict['external_ground_truth'] is False


def test_cross_monitor_agreement_on_all_bounded_fixtures():
    import importlib.util
    spec=importlib.util.spec_from_file_location('m3_record_monitor', ROOT/'external_monitor/m3_record_monitor.py')
    mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod)
    meta=json.loads((FIX/'FIXTURE_LABELS.json').read_text())
    for entry in meta['labels']:
        case=entry['id']
        a=report(case)['status']=='CONTRACT_OBSERVED'
        b=mod.independently_check(CONTRACT,FIX/(case+'.jsonl'))['verdict']=='OBSERVED'
        assert a==b,case
        assert a==entry['expected_topic_audit_pass'],case


def test_no_robot_publish_or_actuator_api():
    root=ROOT/'veab/m3_replay'
    texts='\n'.join(p.read_text() for p in root.glob('*.py'))
    assert '.publish(' not in texts
    assert 'create_publisher(' not in texts
    assert 'send_goal(' not in texts


def test_optional_missing_channel_is_only_warning():
    c=copy.deepcopy(BASE)
    c['channels']['tf']['required']=False
    r=audit_records(c,[x for x in load('clean') if x['topic']!='/tf'],evidence_source='synthetic')
    assert r['status']=='CONTRACT_OBSERVED'
    assert any(w['code']=='OPTIONAL_TOPIC_MISSING' for w in r['warnings'])


def test_expected_frame_missing_fails_closed():
    c=copy.deepcopy(BASE)
    c['channels']['odometry']['frame_id']='odom'
    r=audit_records(c,load('clean'),evidence_source='synthetic')
    assert 'FRAME_EVIDENCE_MISSING' in {e['code'] for e in r['errors']}


def test_matching_explicit_frame_accepted():
    c=copy.deepcopy(BASE)
    c['channels']['odometry']['frame_id']='odom'
    rows=load('clean')
    for r in rows:
        if r['topic']=='/odom':r['frame_id']='odom'
    report=audit_records(c,rows,evidence_source='synthetic')
    assert report['status']=='CONTRACT_OBSERVED',report['errors']


def test_mcap_reader_metadata_mock(monkeypatch,tmp_path):
    import types
    fake_mcap=tmp_path/'recorded.mcap';fake_mcap.write_bytes(b'demo')
    class Reader:
        def __init__(self):self.i=0
        def open(self,*a): pass
        def get_all_topics_and_types(self):
            return [types.SimpleNamespace(name='/odom',type='nav_msgs/msg/Odometry')]
        def has_next(self):return self.i<2
        def read_next(self):
            self.i+=1
            return '/odom',b'bytes',self.i*100_000_000
    class Options:
        def __init__(self,**kwargs):self.kwargs=kwargs
    monkeypatch.setitem(sys.modules,'rosbag2_py',types.SimpleNamespace(SequentialReader=Reader,StorageOptions=Options,ConverterOptions=Options))
    records=list(iter_rosbag2_mcap(fake_mcap))
    assert len(records)==2
    assert records[0]['ros_type']=='nav_msgs/msg/Odometry'
    assert 'header_stamp_ns' not in records[0]


def test_mcap_reader_mock_decoded_headers(monkeypatch,tmp_path):
    import types
    fake_mcap=tmp_path/'recorded.mcap';fake_mcap.write_bytes(b'demo')
    class Reader:
        def __init__(self):self.i=0
        def open(self,*a): pass
        def get_all_topics_and_types(self):
            return [types.SimpleNamespace(name='/odom',type='nav_msgs/msg/Odometry')]
        def has_next(self):return self.i<1
        def read_next(self):
            self.i+=1
            return '/odom',b'bytes',2_000_000_200
    class Options:
        def __init__(self,**kwargs):self.kwargs=kwargs
    monkeypatch.setitem(sys.modules,'rosbag2_py',types.SimpleNamespace(SequentialReader=Reader,StorageOptions=Options,ConverterOptions=Options))
    rclpy=types.ModuleType('rclpy')
    serial=types.ModuleType('rclpy.serialization')
    serial.deserialize_message=lambda _raw,_cls:types.SimpleNamespace(
      header=types.SimpleNamespace(stamp=types.SimpleNamespace(sec=2,nanosec=50),frame_id='odom'))
    rclpy.serialization=serial
    runtime=types.ModuleType('rosidl_runtime_py')
    utils=types.ModuleType('rosidl_runtime_py.utilities')
    utils.get_message=lambda name:object
    runtime.utilities=utils
    monkeypatch.setitem(sys.modules,'rclpy',rclpy)
    monkeypatch.setitem(sys.modules,'rclpy.serialization',serial)
    monkeypatch.setitem(sys.modules,'rosidl_runtime_py',runtime)
    monkeypatch.setitem(sys.modules,'rosidl_runtime_py.utilities',utils)
    rows=list(iter_rosbag2_mcap(fake_mcap,decode_headers=True))
    assert rows[0]['header_stamp_ns']==2_000_000_050
    assert rows[0]['frame_id']=='odom'
