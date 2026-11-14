"""CLI: offline, read-only VEAP M3 evidence completeness inspection."""
from __future__ import annotations
import argparse
import json
import sys
from pathlib import Path
from .core import ContractError, audit_records, iter_jsonl, load_contract, sha256_obj, source_sha256
from .rosbag2_adapter import iter_rosbag2_mcap, require_rosbag_input


def main(argv=None):
    p=argparse.ArgumentParser(description='VEAP-M3: read-only ROS2/MCAP evidence audit (no actuator interface)')
    p.add_argument('--contract',required=True, help='JSON contract with verified topic mapping')
    source=p.add_mutually_exclusive_group(required=True)
    source.add_argument('--jsonl',help='normalized observation envelopes (offline test/input)')
    source.add_argument('--bag',help='ROS 2 rosbag2 MCAP path (ROS 2 interpreter required)')
    p.add_argument('--out',help='JSON report destination; prints stdout when omitted')
    p.add_argument('--hash-bag',action='store_true',help='hash the entire .mcap file; can be slow')
    p.add_argument('--decode-headers',action='store_true',help='decode ROS header clock and frame IDs; requires ROS2 Python runtime')
    args=p.parse_args(argv)
    try:
        contract=load_contract(args.contract)
        if args.jsonl:
            path=Path(args.jsonl)
            report=audit_records(contract,iter_jsonl(path),evidence_source='unattested_jsonl',source_digest=source_sha256(path))
        else:
            path=Path(require_rosbag_input(args.bag))
            digest=source_sha256(path) if args.hash_bag and path.is_file() else None
            report=audit_records(contract,iter_rosbag2_mcap(path,decode_headers=args.decode_headers),
                evidence_source='rosbag2_mcap_decoded_headers' if args.decode_headers else 'rosbag2_mcap_metadata_only',source_digest=digest)
            if not args.decode_headers:
                report['warnings'].append({'code':'BAG_PAYLOAD_NOT_DECODED',
                     'message':'Bag receive timestamps are audited; ROS header stamps, TF and sensor truth are not checked'})
            else:
                report['warnings'].append({'code':'FRAME_GRAPH_AND_SENSOR_TRUTH_UNVERIFIED',
                     'message':'Decoding headers does not calibrate clocks, TF transforms, range accuracy or independent ground truth'})
        payload=json.dumps(report,indent=2,sort_keys=True,allow_nan=False)+'\n'
        if args.out:
            out=Path(args.out)
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_text(payload,encoding='utf-8')
        else:
            print(payload,end='')
        return 0 if report['status']=='CONTRACT_OBSERVED' else 3
    except (ValueError,TypeError,KeyError,OSError,RuntimeError) as exc:
        print(json.dumps({'error':str(exc),'status':'INPUT_REJECTED'}),file=sys.stderr)
        return 2

if __name__=='__main__':
    raise SystemExit(main())
