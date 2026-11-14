"""Adversarial public-key custody protocol tests; all fixtures are synthetic."""
from __future__ import annotations
import copy
import json
import os
from pathlib import Path
import stat
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from r13 import public_custody as pc


class PublicCustodyTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        root = Path(self.tmp.name)
        self.eval = root / "evaluator"
        self.vault = root / "custodian_vault"
        self.eval.mkdir(mode=0o700)
        self.vault.mkdir(mode=0o700)
        self.bundle_file = self.eval / "bundle.json"
        self.reference_file = self.vault / "sealed_reference.json"
        self.nonce_file = self.vault / "nonce.secret"
        self.private_key = self.vault / "ed25519.key.pem"
        self.public_key = self.eval / "custodian-public.pem"
        self.submission_file = self.eval / "submission.json"
        self.bundle = {
            "schema": "veap.r13.evaluator_bundle/1", "study_id": "trial-X", "n_cases": 2,
            "cases": [
                {"case_id":"caseA", "scene_id":"familyA", "trace": {"samples":[{"t_s":0.0,"x":0,"y":0}]}, "contract":{}},
                {"case_id":"caseB", "scene_id":"familyB", "trace": {"samples":[{"t_s":0.0,"x":1,"y":1}]}, "contract":{}},
            ],
        }
        self.reference = {
            "schema":"veap.r13.sealed_reference/1", "study_id":"trial-X",
            "evaluator_bundle_sha256":pc._sha(pc._canonical(self.bundle)),
            "cases":{"caseA":{"expected_verdict":"COMPLIANT"},"caseB":{"expected_verdict":"VIOLATING"}},
        }
        self.bundle_file.write_text(json.dumps(self.bundle))
        self.reference_file.write_text(json.dumps(self.reference))
        self.reference_file.chmod(0o600)
        self.fingerprint = pc.generate_key_pair(self.private_key, self.public_key)
        self.precommit = pc.make_precommit(self.bundle_file, self.reference_file,
                                            self.private_key, self.nonce_file)
        methods = list(pc.PUBLIC_METHODS)
        self.submission = {
            "schema":pc.SUBMISSION_SCHEMA,
            "study_id":"trial-X", "n_cases":2, "n_scenes":2,
            "evaluator_bundle_sha256":pc._sha(pc._canonical(self.bundle)),
            "methods":methods,
            "predictions_by_method":{
                meth:{"caseA":"COMPLIANT","caseB":"VIOLATING"} for meth in methods},
            "veap_certificates":{"caseA":{"verdict":"COMPLIANT"},"caseB":{"verdict":"VIOLATING"}},
        }
        self.submission["submission_sha256"] = pc._sha(pc._canonical(self.submission))
        self.submission_file.write_text(json.dumps(self.submission))
        self.receipt = pc.make_receipt(self.precommit, self.bundle_file, self.submission_file,
                                       self.private_key, self.public_key)

    def test_public_verify_without_private_key(self):
        binding = pc.verify_locked_run(self.precommit, self.receipt, self.bundle_file,
                                       self.submission_file, self.public_key)
        self.assertEqual(binding["status"], "PUBLIC_SIGNATURES_AND_CONTENT_BINDINGS_VALID")
        self.assertFalse(binding["external_independence_established"])
        self.assertFalse(binding["physical_truth_established"])
        self.assertEqual(binding["public_key_sha256"], self.fingerprint)

    def test_reference_commitment_can_be_revealed(self):
        pc.verify_reference_reveal(self.precommit,self.reference_file,self.nonce_file,self.public_key)

    def test_private_key_mode(self):
        self.assertEqual(stat.S_IMODE(self.private_key.stat().st_mode),0o600)
        self.assertEqual(stat.S_IMODE(self.nonce_file.stat().st_mode),0o600)

    def test_signing_with_wrong_key_rejected(self):
        path = self.vault / 'alternative.key.pem'
        pub = self.eval / 'alternative.pub.pem'
        pc.generate_key_pair(path,pub)
        sig = pc.sign('submission_receipt',self.receipt['body'],path)
        with self.assertRaises(pc.CustodyError):
            pc.verify(sig,'submission_receipt',self.public_key)

    def test_rehashed_prediction_edit_after_receipt_is_detected(self):
        mutated=copy.deepcopy(self.submission)
        mutated['predictions_by_method']['goal_only']['caseB']='COMPLIANT'
        mutated.pop('submission_sha256')
        mutated['submission_sha256']=pc._sha(pc._canonical(mutated))
        self.submission_file.write_text(json.dumps(mutated))
        with self.assertRaises(pc.CustodyError):
            pc.verify_locked_run(self.precommit,self.receipt,self.bundle_file,
                                 self.submission_file,self.public_key)

    def test_bundle_whitespace_change_after_precommit_is_detected(self):
        self.bundle_file.write_text(json.dumps(self.bundle,indent=2,sort_keys=True))
        with self.assertRaises(pc.CustodyError):
            pc.verify_locked_run(self.precommit,self.receipt,self.bundle_file,
                                 self.submission_file,self.public_key)

    def test_tampered_signed_precommit_body_is_rejected(self):
        modified=copy.deepcopy(self.precommit)
        modified['body']['n_cases']=999
        with self.assertRaises(pc.CustodyError):pc.verify(modified,'precommit',self.public_key)

    def test_tampered_receipt_signature_is_rejected(self):
        modified=copy.deepcopy(self.receipt)
        modified['signature_base64']='AA=='
        with self.assertRaises(pc.CustodyError):pc.verify(modified,'submission_receipt',self.public_key)

    def test_wrong_envelope_kind_rejected(self):
        with self.assertRaises(pc.CustodyError):pc.verify(self.receipt,'precommit',self.public_key)

    def test_tampered_reference_rejected(self):
        self.reference['cases']['caseA']['expected_verdict']='VIOLATING'
        self.reference_file.write_text(json.dumps(self.reference))
        with self.assertRaises(pc.CustodyError):pc.verify_reference_reveal(
            self.precommit,self.reference_file,self.nonce_file,self.public_key)

    def test_tampered_nonce_rejected(self):
        self.nonce_file.write_bytes(b'Z'*32)
        with self.assertRaises(pc.CustodyError):pc.verify_reference_reveal(
            self.precommit,self.reference_file,self.nonce_file,self.public_key)

    def test_missing_case_rejected(self):
        for p in self.submission['predictions_by_method'].values():p.pop('caseB')
        self.submission['veap_certificates'].pop('caseB')
        self.submission.pop('submission_sha256')
        self.submission['submission_sha256']=pc._sha(pc._canonical(self.submission))
        self.submission_file.write_text(json.dumps(self.submission))
        with self.assertRaises(pc.CustodyError):pc.make_receipt(
            self.precommit,self.bundle_file,self.submission_file,self.private_key,self.public_key)

    def test_missing_method_rejected(self):
        self.submission['methods'].remove('goal_only')
        self.submission['predictions_by_method'].pop('goal_only')
        self.submission.pop('submission_sha256')
        self.submission['submission_sha256']=pc._sha(pc._canonical(self.submission))
        self.submission_file.write_text(json.dumps(self.submission))
        with self.assertRaises(pc.CustodyError):pc.make_receipt(
            self.precommit,self.bundle_file,self.submission_file,self.private_key,self.public_key)

    def test_secret_ref_beneath_evaluator_workspace_rejected(self):
        secret=self.eval/'reference.json';secret.write_text(json.dumps(self.reference))
        with self.assertRaises(pc.CustodyError):pc.make_precommit(
            self.bundle_file,secret,self.private_key,self.vault/'alternate_nonce')

    def test_duplicate_json_key_rejected(self):
        p=self.eval/'duplicate.json';p.write_text('{"a":1,"a":2}')
        with self.assertRaises(pc.CustodyError):pc.read_json(p)

    def test_nonfinite_json_rejected(self):
        p=self.eval/'nan.json';p.write_text('{"x":NaN}')
        with self.assertRaises(pc.CustodyError):pc.read_json(p)

    def test_no_overwrite(self):
        path=self.eval/'exists.json';pc.save_json(path,{"ok":True})
        with self.assertRaises(FileExistsError):pc.save_json(path,{"ok":False})

    def test_insecure_private_key_mode_rejected(self):
        self.private_key.chmod(0o644)
        with self.assertRaises(pc.CustodyError):pc.sign('precommit',{'a':1},self.private_key)

    def test_score_recheck_and_report_attestation(self):
        def fake_checked_scorer(bundle,sub,ref):
            self.assertEqual(ref['cases']['caseA']['expected_verdict'],'COMPLIANT')
            return {'study_id':bundle['study_id'],'study_scope':'SYNTHETIC_DEVELOPMENT_ONLY',
                    'check_status':'TEST_DOUBLE_ONLY'}
        report,score_sig=pc.score_locked_run(
            self.precommit,self.receipt,self.bundle_file,self.submission_file,
            self.reference_file,self.nonce_file,self.public_key,self.private_key,
            scorer=fake_checked_scorer)
        pc.verify_score_attestation(report,score_sig,self.precommit,self.receipt,self.public_key)
        self.assertFalse(report['public_custody_attestation']['independent_external_custodian'])

    def test_altered_score_report_detected(self):
        report,att=pc.score_locked_run(
            self.precommit,self.receipt,self.bundle_file,self.submission_file,
            self.reference_file,self.nonce_file,self.public_key,self.private_key,
            scorer=lambda b,s,r:{'study_id':b['study_id'],'status':'PASS'})
        report['status']='FAIL'
        with self.assertRaises(pc.CustodyError):pc.verify_score_attestation(
            report,att,self.precommit,self.receipt,self.public_key)

    def test_symlinked_submission_is_rejected(self):
        target=self.eval/'real_submission.json'
        target.write_text(json.dumps(self.submission))
        self.submission_file.unlink()
        self.submission_file.symlink_to(target)
        with self.assertRaises(OSError):
            pc.verify_locked_run(self.precommit,self.receipt,self.bundle_file,
                                 self.submission_file,self.public_key)

    def test_preexisting_key_is_not_overwritten(self):
        existing=self.private_key.read_bytes()
        with self.assertRaises(pc.CustodyError):
            pc.generate_key_pair(self.private_key,self.eval/'new.pub.pem')
        self.assertEqual(existing,self.private_key.read_bytes())

    def test_submission_schema_mismatch_is_rejected(self):
        self.submission['schema']='veap.r13.submission/obsolete'
        self.submission.pop('submission_sha256')
        self.submission['submission_sha256']=pc._sha(pc._canonical(self.submission))
        self.submission_file.write_text(json.dumps(self.submission))
        with self.assertRaises(pc.CustodyError):
            pc.make_receipt(self.precommit,self.bundle_file,self.submission_file,
                            self.private_key,self.public_key)

    def test_wrong_study_in_reference_rejected_at_precommit(self):
        self.reference['study_id']='different'
        self.reference_file.write_text(json.dumps(self.reference))
        with self.assertRaises(pc.CustodyError):
            pc.make_precommit(self.bundle_file,self.reference_file,self.private_key,
                              self.vault/'new_nonce.secret')

    def test_report_scoring_blocked_on_changed_reference(self):
        self.reference['cases']['caseB']['expected_verdict']='COMPLIANT'
        self.reference_file.write_text(json.dumps(self.reference))
        ran=[]
        with self.assertRaises(pc.CustodyError):
            pc.score_locked_run(self.precommit,self.receipt,self.bundle_file,
                                self.submission_file,self.reference_file,self.nonce_file,
                                self.public_key,self.private_key,
                                scorer=lambda b,s,r:ran.append(1))
        self.assertEqual(ran,[])

    def test_receipt_is_not_replayable_on_another_precommit(self):
        # Re-registration of the same inputs generates a distinct experiment ID.
        other=pc.make_precommit(self.bundle_file,self.reference_file,self.private_key,
                                self.vault/'other_nonce')
        with self.assertRaises(pc.CustodyError):
            pc.verify_locked_run(other,self.receipt,self.bundle_file,
                                 self.submission_file,self.public_key)

    def test_reference_label_leak_into_evaluator_bundle_rejected(self):
        self.bundle['cases'][0]['expected_verdict']='COMPLIANT'
        self.bundle_file.write_text(json.dumps(self.bundle))
        with self.assertRaises(pc.CustodyError):
            pc.make_precommit(self.bundle_file,self.reference_file,self.private_key,
                              self.vault/'bad_nonce')

    def test_condition_revealing_case_id_rejected(self):
        self.bundle['cases'][0]['case_id']='complete_safely'
        self.bundle_file.write_text(json.dumps(self.bundle))
        with self.assertRaises(pc.CustodyError):
            pc.make_precommit(self.bundle_file,self.reference_file,self.private_key,
                              self.vault/'bad_nonce')

    def test_extra_envelope_field_fails_closed(self):
        tampered=copy.deepcopy(self.precommit)
        tampered['approved_by_external_reviewer']=True
        with self.assertRaises(pc.CustodyError):pc.verify(tampered,'precommit',self.public_key)

    def test_cli_public_verify(self):
        prepath=self.eval/'precommit.json'; receiptpath=self.eval/'receipt.json'
        pc.save_json(prepath,self.precommit);pc.save_json(receiptpath,self.receipt)
        self.assertEqual(pc.main(['verify','--precommit',str(prepath),'--receipt',str(receiptpath),
                                  '--bundle',str(self.bundle_file),'--submission',str(self.submission_file),
                                  '--public',str(self.public_key)]),0)

if __name__=='__main__':unittest.main()
