from __future__ import annotations
import copy
import hashlib
import json
from pathlib import Path
import pytest
from veab.governance.claims import validate_registry,check_public_copy

BASE=Path(__file__).resolve().parents[1]


def test_current_registry_passes():
    result=validate_registry(BASE)
    assert result['valid'] and result['claim_count']>=3
    assert check_public_copy(BASE)['valid']


def test_missing_or_fake_external_validation_rejected(tmp_path):
    tmp_path.joinpath('docs').mkdir()
    original=json.loads((BASE/'docs/CLAIMS_REGISTER.json').read_text())
    for status in ('VALIDATED','CERTIFIED'):
        forged=copy.deepcopy(original)
        forged['claims'][0]['status']=status
        forged['claims'][0]['artifact']='docs/dummy.txt'
        (tmp_path/'docs/dummy.txt').write_text('known synthetic evidence')
        forged['claims'][0]['artifact_sha256']=hashlib.sha256(b'known synthetic evidence').hexdigest()
        (tmp_path/'docs/CLAIMS_REGISTER.json').write_text(json.dumps(forged))
        with pytest.raises(ValueError,match='independent reviewer'):
            validate_registry(tmp_path)


def test_evidence_tampering_fails_closed(tmp_path):
    tmp_path.joinpath('docs').mkdir()
    content=b'controlled fixture'
    (tmp_path/'docs/fixture.txt').write_bytes(content)
    source=json.loads((BASE/'docs/CLAIMS_REGISTER.json').read_text())
    claim=source['claims'][0]
    claim['artifact']='docs/fixture.txt'
    claim['artifact_sha256']=hashlib.sha256(content).hexdigest()
    source['claims']=[claim]
    (tmp_path/'docs/CLAIMS_REGISTER.json').write_text(json.dumps(source))
    assert validate_registry(tmp_path)['valid']
    (tmp_path/'docs/fixture.txt').write_bytes(b'controlled fixture modified')
    with pytest.raises(ValueError,match='checksum mismatch'):
        validate_registry(tmp_path)


def test_claim_linter_catches_unqualified_marketing(tmp_path):
    (tmp_path/'docs').mkdir()
    filename=tmp_path/'docs/PUBLIC_PRODUCT_CLAIMS.md'
    filename.write_text('VEAB is production-ready for every robot.\n')
    with pytest.raises(ValueError,match='unqualified'):
        check_public_copy(tmp_path,files=["docs/PUBLIC_PRODUCT_CLAIMS.md"])
    filename.write_text('VEAB is not production-ready for any physical-robot use.\n')
    assert check_public_copy(tmp_path,files=["docs/PUBLIC_PRODUCT_CLAIMS.md"])['valid']
