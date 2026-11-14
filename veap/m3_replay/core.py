"""M3 replay contract and forensic evidence audit (Python standard library only).

The contract is explicitly observational. Safety claims require separately
calibrated ground truth. Recorded ROS timestamps are not trusted clock truth.
"""
from __future__ import annotations
import hashlib
import json
import math
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

CONTRACT_SCHEMA = 'veap.m3.contract/1'
RECORD_SCHEMA = 'veap.m3.record/1'
REPORT_SCHEMA = 'veap.m3.audit/1'
MAX_CHANNELS = 48
MAX_RECORDS = 1_000_000
MAX_LINE_BYTES = 1_048_576
MAX_DURATION_NS = 7 * 24 * 3600 * 1_000_000_000


class ContractError(ValueError):
    pass


def canonical_bytes(data: dict) -> bytes:
    return json.dumps(data, sort_keys=True, ensure_ascii=False,
                      separators=(',', ':'), allow_nan=False).encode('utf-8')


def sha256_obj(data: dict) -> str:
    return hashlib.sha256(canonical_bytes(data)).hexdigest()


def _bounded_int(value: Any, name: str, *, maximum: int = MAX_DURATION_NS, allow_zero: bool = True) -> int:
    if type(value) is not int or value < (0 if allow_zero else 1) or value > maximum:
        raise ContractError(f'{name}: invalid integer range')
    return value


def load_contract(path: str | Path) -> dict:
    value = json.loads(Path(path).read_text(encoding='utf-8'))
    validate_contract(value)
    return value


def validate_contract(contract: Any) -> None:
    if not isinstance(contract, dict) or contract.get('schema_version') != CONTRACT_SCHEMA:
        raise ContractError(f'expected {CONTRACT_SCHEMA}')
    if not isinstance(contract.get('id'), str) or not re.fullmatch(r'[a-zA-Z0-9_.-]{3,96}', contract['id']):
        raise ContractError('invalid contract id')
    if contract.get('purpose') != 'read_only_evidence_audit':
        raise ContractError('control/actuation contracts are not accepted by the M3 replay auditor')
    if contract.get('source_trust') != 'unattested':
        raise ContractError('this auditor cannot assert source authenticity')
    channels = contract.get('channels')
    if not isinstance(channels, dict) or not 1 <= len(channels) <= MAX_CHANNELS:
        raise ContractError('channels must be a nonempty mapping of bounded size')
    topics: set[str] = set()
    for logical, conf in channels.items():
        if not isinstance(logical, str) or not re.fullmatch(r'[a-z][a-z0-9_]{0,63}', logical):
            raise ContractError('invalid logical channel')
        if not isinstance(conf, dict):
            raise ContractError(f'{logical}: channel configuration must be an object')
        topic = conf.get('topic')
        if not isinstance(topic, str) or not re.fullmatch(r'/[A-Za-z0-9_][A-Za-z0-9_/]*', topic):
            raise ContractError(f'{logical}: explicit absolute ROS topic required')
        if topic in topics:
            raise ContractError(f'{logical}: duplicate ROS topic')
        topics.add(topic)
        if type(conf.get('required')) is not bool:
            raise ContractError(f'{logical}: required must be boolean')
        if not isinstance(conf.get('ros_type'), str) or not re.fullmatch(r'[A-Za-z0-9_]+/msg/[A-Za-z0-9_]+', conf['ros_type']):
            raise ContractError(f'{logical}: explicit ROS message type required')
        max_gap = conf.get('max_gap_ns')
        if max_gap is not None:
            _bounded_int(max_gap, f'{logical}.max_gap_ns', allow_zero=False)
        max_skew = conf.get('max_header_lag_ns')
        if max_skew is not None:
            _bounded_int(max_skew, f'{logical}.max_header_lag_ns')
        frame = conf.get('frame_id')
        if frame is not None and (not isinstance(frame, str) or not 1 <= len(frame) <= 128):
            raise ContractError(f'{logical}: invalid frame_id')
    window = contract.get('window')
    if not isinstance(window, dict) or window.get('mode') not in ('observed', 'explicit'):
        raise ContractError('window.mode must be observed or explicit')
    if window['mode'] == 'explicit':
        start = _bounded_int(window.get('start_ns'), 'window.start_ns', maximum=10**20)
        end = _bounded_int(window.get('end_ns'), 'window.end_ns', maximum=10**20)
        if end <= start or end-start > MAX_DURATION_NS:
            raise ContractError('explicit observation window invalid')
    if contract.get('calibration_status') != 'UNVALIDATED_EXAMPLE' and not isinstance(contract.get('calibration_reference'), str):
        raise ContractError('calibration_reference required for non-example contract')


def iter_jsonl(path: str | Path) -> Iterable[dict]:
    with open(path, 'rb') as f:
        for lineno, line in enumerate(f, 1):
            if lineno > MAX_RECORDS:
                raise ContractError('maximum evidence records exceeded')
            if len(line) > MAX_LINE_BYTES:
                raise ContractError(f'line {lineno} exceeds size limit')
            if not line.strip():
                continue
            try:
                record = json.loads(line)
            except (json.JSONDecodeError, UnicodeDecodeError) as exc:
                raise ContractError(f'malformed JSONL on line {lineno}') from exc
            if not isinstance(record, dict):
                raise ContractError(f'line {lineno} is not a JSON object')
            yield record


def source_sha256(path: str | Path) -> str:
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for block in iter(lambda: f.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


@dataclass
class TopicStats:
    count: int = 0
    first_ns: int | None = None
    last_ns: int | None = None
    max_gap_ns: int = 0
    reversed_stamps: int = 0
    max_header_lag_ns: int = 0
    wrong_types: int = 0
    wrong_frames: int = 0
    missing_header_stamps: int = 0
    frames_checked: int = 0


def audit_records(contract: dict, records: Iterable[dict], *,
                  evidence_source: str, source_digest: str | None = None) -> dict:
    validate_contract(contract)
    channels = contract['channels']
    by_topic = {v['topic']: (k, v) for k, v in channels.items()}
    stats = {logical: TopicStats() for logical in channels}
    errors: list[dict] = []
    warnings: list[dict] = []
    all_first: int | None = None
    all_last: int | None = None
    total = 0
    unknown_topics: set[str] = set()
    for i, rec in enumerate(records):
        total += 1
        if total > MAX_RECORDS:
            raise ContractError('record count limit exceeded')
        if rec.get('schema_version') != RECORD_SCHEMA:
            raise ContractError(f'record {i}: unsupported schema')
        topic = rec.get('topic')
        if not isinstance(topic, str) or not topic.startswith('/'):
            raise ContractError(f'record {i}: invalid topic')
        ts = _bounded_int(rec.get('log_time_ns'), f'record {i}.log_time_ns',maximum=10**20)
        all_first = ts if all_first is None else min(all_first, ts)
        all_last = ts if all_last is None else max(all_last, ts)
        if topic not in by_topic:
            unknown_topics.add(topic)
            continue
        logical, conf = by_topic[topic]
        st = stats[logical]
        if st.last_ns is not None:
            if ts < st.last_ns:
                st.reversed_stamps += 1
                errors.append({'code':'TIME_REVERSED', 'channel':logical, 'record':i})
            else:
                st.max_gap_ns = max(st.max_gap_ns, ts-st.last_ns)
        st.first_ns = ts if st.first_ns is None else min(st.first_ns, ts)
        st.last_ns = ts if st.last_ns is None else max(st.last_ns, ts)
        st.count += 1
        if rec.get('ros_type') != conf['ros_type']:
            st.wrong_types += 1
            errors.append({'code':'TYPE_MISMATCH','channel':logical,'record':i})
        header_ts = rec.get('header_stamp_ns')
        if header_ts is not None:
            hdr = _bounded_int(header_ts, f'record {i}.header_stamp_ns', maximum=10**20)
            lag = abs(ts-hdr)
            st.max_header_lag_ns = max(st.max_header_lag_ns, lag)
            if conf.get('max_header_lag_ns') is not None and lag > conf['max_header_lag_ns']:
                errors.append({'code':'HEADER_CLOCK_GAP','channel':logical,'record':i,'lag_ns':lag})
        elif conf.get('max_header_lag_ns') is not None:
            st.missing_header_stamps += 1
            errors.append({'code':'HEADER_TIMESTAMP_MISSING','channel':logical,'record':i})
        frame = rec.get('frame_id')
        if conf.get('frame_id') and frame is not None:
            st.frames_checked += 1
        if conf.get('frame_id') and frame is not None and frame != conf['frame_id']:
            st.wrong_frames += 1
            errors.append({'code':'FRAME_MISMATCH','channel':logical,'record':i})
        # Frame absence cannot be assessed when only bag message metadata is read.
        # This is explicitly flagged below rather than being accepted as a pass.
    if all_first is None or all_last is None:
        errors.append({'code':'EMPTY_RECORDING'})
        all_first = all_last = 0
    window = contract['window']
    start, end = ((all_first, all_last) if window['mode']=='observed' else
                  (window['start_ns'], window['end_ns']))
    if end-start > MAX_DURATION_NS:
        raise ContractError('recording duration exceeds accepted bound')
    for logical, conf in channels.items():
        st = stats[logical]
        if st.count == 0:
            if conf['required']:
                errors.append({'code':'REQUIRED_TOPIC_MISSING','channel':logical,'topic':conf['topic']})
            else:
                warnings.append({'code':'OPTIONAL_TOPIC_MISSING','channel':logical,'topic':conf['topic']})
            continue
        limit = conf.get('max_gap_ns')
        if limit is not None:
            actual = max(st.max_gap_ns, (st.first_ns or 0)-start, end-(st.last_ns or 0))
            if actual > limit:
                errors.append({'code':'TOPIC_GAP','channel':logical,'max_gap_ns':actual,'limit_ns':limit})
        if conf.get('frame_id') and st.frames_checked != st.count:
            errors.append({'code':'FRAME_EVIDENCE_MISSING','channel':logical,
                           'missing_records':st.count-st.frames_checked})
    n_required = sum(v['required'] for v in channels.values())
    n_present = sum(conf['required'] and stats[logical].count>0 for logical,conf in channels.items())
    from .attribution import triage
    measurements = {name:vars(st) for name,st in stats.items()}
    diagnostics = {'required_channels_present':n_present, 'required_channels_total':n_required,
                   'required_channel_coverage':round(n_present/n_required,6) if n_required else 1.0,
                   'record_count':total, 'unknown_topic_count':len(unknown_topics),
                   'time_start_ns':start,'time_end_ns':end}
    return {
      'schema_version':REPORT_SCHEMA,'contract_id':contract['id'],
      'contract_sha256':sha256_obj(contract),
      'scope':'read-only recording completeness, type and timestamp audit; NOT collision or physical safety validation',
      'source':{'kind':evidence_source,'trust':'UNATTESTED','sha256':source_digest},
      'status':'CONTRACT_OBSERVED' if not errors else 'EVIDENCE_INCOMPLETE',
      'physical_safety_validated':False,'sensor_authenticity_validated':False,
      'diagnostics':diagnostics,'channels':measurements,
      'errors':errors,'warnings':warnings,'candidate_attributions':triage(errors),
    }
