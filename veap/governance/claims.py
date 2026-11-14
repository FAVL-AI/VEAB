"""Controlled scientific and product claims; no safety certification is implied.

A file digest checks artifact integrity, not external review, source authenticity or
fitness for operational deployment. The policy intentionally fails closed.
"""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

STATUSES={"IMPLEMENTED","DEMONSTRATED","VALIDATED","CERTIFIED"}
HIGH_RISK=re.compile(r"(?i)\b(?:production[- ]ready|enterprise[- ]grade|certified safety|validated safety|"
                     r"(?<!agent-)independent verification|state[- ]of[- ]the[- ]art|SOTA|trusted provenance)\b")


def validate_registry(root: str|Path, relative: str = "docs/CLAIMS_REGISTER.json") -> dict:
    base=Path(root).resolve()
    path=(base/relative).resolve()
    if not path.is_relative_to(base):
        raise ValueError("claim registry outside repository")
    data=json.loads(path.read_text(encoding='utf8'))
    if set(data)!={"schema_version","claims","source_notice"} or data['schema_version']!='veab-claims/1':
        raise ValueError('registry schema invalid')
    if not isinstance(data['source_notice'],str) or not data['source_notice']:
        raise ValueError('registry needs source notice')
    if not isinstance(data['claims'],list) or not data['claims']:
        raise ValueError('no claims in register')
    seen=set()
    for claim in data['claims']:
        expected={"id","status","statement","scope","limitations","artifact","artifact_sha256", "reviewer", "intended_use", "external_certification"}
        if not isinstance(claim,dict) or set(claim)!=expected:
            raise ValueError('claim schema invalid')
        code=claim['id']
        if not isinstance(code,str) or not re.fullmatch(r'E\d{3,5}',code) or code in seen:
            raise ValueError('invalid or duplicate claim id')
        seen.add(code)
        if claim['status'] not in STATUSES:
            raise ValueError(f'{code} unsupported status')
        for key in ('statement','scope','limitations'):
            if not isinstance(claim[key],str) or len(claim[key].strip())<12:
                raise ValueError(f'{code} missing {key}')
        artifact=claim['artifact']
        if not isinstance(artifact,str) or artifact.startswith('/') or '..' in Path(artifact).parts:
            raise ValueError(f'{code} invalid artifact path')
        full=(base/artifact).resolve()
        if not full.is_relative_to(base) or not full.is_file():
            raise ValueError(f'{code} artifact missing or outside repository')
        digest=hashlib.sha256(full.read_bytes()).hexdigest()
        if digest!=claim['artifact_sha256']:
            raise ValueError(f'{code} evidence checksum mismatch')
        if claim['status'] in ('VALIDATED','CERTIFIED'):
            if not claim['reviewer'] or not claim['intended_use']:
                raise ValueError(f'{code} needs independent reviewer and intended use')
            if claim['reviewer'].strip().lower() in {'internal','developer','veab team'}:
                raise ValueError(f'{code} cannot claim external validation based on internal review')
        if claim['status']=='CERTIFIED' and not claim['external_certification']:
            raise ValueError(f'{code} needs external accredited certification evidence')
        if claim['status']!='CERTIFIED' and claim['external_certification']:
            raise ValueError(f'{code} cannot attach certification outside certified state')
    return {"valid":True,"claim_count":len(seen),"statuses":sorted({x['status'] for x in data['claims']})}


def check_public_copy(root: str|Path, files=None) -> dict:
    """Fail if high-risk phrases appear without qualified context in release copy.

    Scope intentionally covers ONLY new controlled copy. Legacy docs need a
    separately reviewed migration; keyword policing every historical research
    discussion would incorrectly flag legitimate negative statements.
    """
    base=Path(root).resolve()
    files=files or ['docs/PUBLIC_PRODUCT_CLAIMS.md', 'docs/release/V06_FUNDING_POSITION.md', 'web/v06_product_positioning.md', '.github/pull_request_template.md']
    failures=[]
    for filename in files:
        path=(base/filename).resolve()
        if not path.is_relative_to(base) or not path.is_file():
            failures.append(f'{filename}: missing controlled public copy')
            continue
        body=path.read_text(encoding='utf8')
        for line_number,line in enumerate(body.splitlines(),1):
            for match in HIGH_RISK.finditer(line):
                preceding=line[max(0,match.start()-40):match.start()].lower()
                following=line[match.end():min(len(line),match.end()+36)].lower()
                # Accept only an immediately scoped denial or a nearby claim ID.
                qualified_before=re.search(r"\b(?:not|no|never|without|pending|unproven|target|cannot)\b[^.!?]{0,25}$",preceding)
                qualified_after=re.search(r"^.{0,16}\b(?:not claimed|unproven|pending|target only)\b",following)
                claim_id=re.search(r"\bE\d{3,5}\b",line[max(0,match.start()-12):match.end()+18])
                if not (qualified_before or qualified_after or claim_id):
                    failures.append(f'{filename}:{line_number}: unqualified high-risk claim')
    if failures:
        raise ValueError('; '.join(failures))
    return {"valid":True,"files_checked":len(files)}
