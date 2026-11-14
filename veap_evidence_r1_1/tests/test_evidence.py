import copy
import hashlib
import json
import math
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from veap_evidence.baselines import grade
from veap_evidence.fixtures import cases,contract,trace
from veap_evidence.verdict import EvaluationError,canonical_hash,evaluate,load_record

ROOT=Path(__file__).resolve().parents[1]


class EvidenceR1Tests(unittest.TestCase):
    def test_all_hand_labeled_synthetic_oracles(self):
        for key,item in cases().items():
            with self.subTest(case=key):
                self.assertEqual(evaluate(item['contract'],item['trace'])['verdict'],item['oracle'])

    def test_missing_cannot_erase_conclusive_violation(self):
        r=evaluate(contract(),cases()['violation_plus_missing']['trace'])
        self.assertEqual(r['requirements']['keepout_continuous']['verdict'],'VIOLATING')
        self.assertTrue(r['confirmed_violations'])

    def test_missing_irrelevant_camera_still_compliant(self):
        r=evaluate(contract(),cases()['missing_irrelevant_camera']['trace'])
        self.assertEqual(r['verdict'],'COMPLIANT')

    def test_missing_relevant_odom_is_inconclusive(self):
        r=evaluate(contract(),cases()['missing_required_odom']['trace'])
        self.assertEqual(r['verdict'],'INCONCLUSIVE')
        self.assertTrue(any(e['type']=='missing_required_pose_channel' for e in r['missing_evidence_diagnostics']))

    def test_safe_interval_without_sample_still_compliant(self):
        item=cases()['missing_safe_interval']
        r=evaluate(item['contract'],item['trace'])
        self.assertEqual(r['verdict'],'COMPLIANT')
        self.assertTrue(any(d['type']=='nominal_recording_gap' for d in r['missing_evidence_diagnostics']))
        self.assertFalse(r['requirements']['keepout_continuous']['unresolved_intervals'])

    def test_critical_gap_has_explicit_intervals(self):
        r=evaluate(contract(),cases()['missing_critical_interval']['trace'])
        intervals=r['requirements']['keepout_continuous']['unresolved_intervals']
        self.assertTrue(intervals)
        self.assertTrue(all(0<=d['interval_s'][0]<d['interval_s'][1]<=2 for d in intervals))

    def test_keepout_violation_witness(self):
        r=evaluate(contract(),cases()['observed_violation']['trace'])
        self.assertEqual(r['confirmed_violations'][0]['evidence_ref'],'pose-2')

    def test_mission_end_not_derived_from_trace(self):
        r=evaluate(contract(),cases()['early_truncation']['trace'])
        self.assertEqual(r['requirements']['goal_at_deadline']['verdict'],'INCONCLUSIVE')

    def test_uncertain_motion_not_false_compliant(self):
        r=evaluate(contract(),cases()['uncertain_clearance']['trace'])
        self.assertEqual(r['verdict'],'INCONCLUSIVE')

    def test_goal_at_deadline_not_success_claim(self):
        for truth in (True,False):
            t=trace();t['agent_claimed_success']=truth
            self.assertEqual(evaluate(contract(),t)['verdict'],'COMPLIANT')

    def test_terminal_false_claim_does_not_hide_violation(self):
        t=cases()['observed_violation']['trace']
        t['agent_claimed_success']=False
        self.assertEqual(evaluate(contract(),t)['verdict'],'VIOLATING')

    def test_goal_false_at_deadline(self):
        self.assertEqual(evaluate(contract(),cases()['goal_unreached']['trace'])['requirements']['goal_at_deadline']['verdict'],'VIOLATING')

    def test_motion_speed_contradiction_fails_closed(self):
        t=trace();t['samples'][1]['x']=200.0
        r=evaluate(contract(),t)
        self.assertEqual(r['verdict'],'INCONCLUSIVE')
        self.assertTrue(any(d['type']=='inconsistent_motion_bound' for d in r['missing_evidence_diagnostics']))

    def test_reproducibility_same_inputs_identical(self):
        self.assertEqual(evaluate(contract(),trace()),evaluate(contract(),trace()))

    def test_contract_digest_changes_with_requirement(self):
        c1=contract(); c2=contract();c2['keepout'][3]+=.01
        self.assertNotEqual(evaluate(c1,trace())['contract_sha256'],evaluate(c2,trace())['contract_sha256'])

    def test_trace_hash_changes_after_edit(self):
        t1=trace();t2=trace();t2['samples'][2]['x']+=.05
        self.assertNotEqual(evaluate(contract(),t1)['trace_canonical_sha256'],evaluate(contract(),t2)['trace_canonical_sha256'])

    def test_certificate_self_digest(self):
        c=evaluate(contract(),trace());given=c.pop('certificate_sha256')
        self.assertEqual(canonical_hash(c),given)

    def test_provenance_unattested(self):
        c=evaluate(contract(),trace())
        self.assertEqual(c['source_authenticity'],'UNATTESTED')
        self.assertIn('no physical safety certification',c['scope'])

    def test_baselines_explicit(self):
        t=cases()['missing_critical_interval']['trace']
        self.assertEqual(grade(contract(),t,'goal_only'),'COMPLIANT')
        self.assertEqual(grade(contract(),t,'gap_aware'),'INCONCLUSIVE')

    def test_strong_comparator_fails_observed_violation(self):
        t=cases()['observed_violation']['trace']
        self.assertEqual(grade(contract(),t,'sampled_safety'),'VIOLATING')
        self.assertEqual(grade(contract(),t,'gap_aware'),'VIOLATING')

    def test_independent_monitor_import_isolation(self):
        src=(ROOT/'external_monitor'/'monitor.py').read_text()
        self.assertNotIn('import veap',src)
        self.assertNotIn('from veap',src)

    def test_independent_monitor_agrees_all_fixture_cases(self):
        from external_monitor.monitor import inspect
        for key,item in cases().items():
            with self.subTest(case=key):
                cert=evaluate(item['contract'],item['trace'])
                res=inspect(item['contract'],item['trace'],cert)
                self.assertEqual(res['certificate_check'],'PASS',res['errors'])

    def test_separate_process_verifies_positive_certificate(self):
        with tempfile.TemporaryDirectory() as d:
            base=Path(d);c=base/'contract.json';t=base/'trace.json';out=base/'cert.json'
            c.write_text(json.dumps(contract()));t.write_text(json.dumps(trace()))
            tr,rawhash=load_record(t)
            out.write_text(json.dumps(evaluate(contract(),tr,rawhash)))
            run=subprocess.run([sys.executable,str(ROOT/'external_monitor'/'monitor.py'),str(c),str(t),str(out)],capture_output=True,text=True)
            self.assertEqual(run.returncode,0,run.stdout+run.stderr)
            self.assertEqual(json.loads(run.stdout)['reference_verdict'],'COMPLIANT')

    def test_checker_rejects_tampered_certificate(self):
        from external_monitor.monitor import inspect
        cert=evaluate(contract(),trace());cert['verdict']='VIOLATING'
        self.assertEqual(inspect(contract(),trace(),cert)['certificate_check'],'FAIL')

    def test_checker_rejects_tampered_evidence(self):
        from external_monitor.monitor import inspect
        cert=evaluate(contract(),trace());t=trace();t['samples'][1]['y']=0
        self.assertEqual(inspect(contract(),t,cert)['certificate_check'],'FAIL')

    def test_checker_rejects_false_witness(self):
        from external_monitor.monitor import inspect
        cert=evaluate(contract(),trace());cert['evidence_witnesses'].append({'type':'terminal_goal','evidence_ref':'not-a-record'})
        cert['certificate_sha256']=canonical_hash({k:v for k,v in cert.items() if k!='certificate_sha256'})
        self.assertEqual(inspect(contract(),trace(),cert)['certificate_check'],'FAIL')

    def test_checker_rejects_claimed_attestation(self):
        from external_monitor.monitor import inspect
        cert=evaluate(contract(),trace());cert['source_authenticity']='TRUSTED'
        cert['certificate_sha256']=canonical_hash({k:v for k,v in cert.items() if k!='certificate_sha256'})
        self.assertEqual(inspect(contract(),trace(),cert)['certificate_check'],'FAIL')

    def test_cli_demo_runs(self):
        with tempfile.TemporaryDirectory() as d:
            path=Path(d)/'out.json'
            p=subprocess.run([sys.executable,'-m','veap_evidence','demo','--out',str(path)],cwd=ROOT,capture_output=True,text=True)
            self.assertEqual(p.returncode,0,p.stderr)
            r=json.loads(path.read_text())
            self.assertEqual(r['n'],len(cases()))
            self.assertEqual(r['reproduction']['upstream_EAI'],'NOT_RUN')

    def test_empty_trace_is_inconclusive(self):
        t=trace();t['samples']=[]
        self.assertEqual(evaluate(contract(),t)['verdict'],'INCONCLUSIVE')

    def test_input_schema_and_numeric_limits(self):
        for value in (math.nan,math.inf,-math.inf,True,'not-a-speed'):
            c=contract();c['max_speed_mps']=value
            with self.subTest(value=str(value)),self.assertRaises(EvaluationError):
                evaluate(c,trace())
        c=contract();c['goal']['tolerance_m']=-1
        with self.assertRaises(EvaluationError):evaluate(c,trace())
        t=trace();t['schema']='not-the-schema'
        with self.assertRaises(EvaluationError):evaluate(contract(),t)

    def test_file_parser_rejects_nonfinite_json(self):
        with tempfile.TemporaryDirectory() as d:
            file=Path(d)/'bad.json';file.write_text('{"x":NaN}')
            with self.assertRaises(EvaluationError):load_record(file)

    def test_input_bound(self):
        t=trace();t['samples']=t['samples']*100001
        with self.assertRaises(EvaluationError):evaluate(contract(),t)

    def test_short_observed_log_not_claimed_complete(self):
        t=trace();t['samples']=t['samples'][:2]
        self.assertNotEqual(evaluate(contract(),t)['verdict'],'COMPLIANT')

    def test_baseline_comparison_is_not_external_validation(self):
        report=json.loads((ROOT/'artifacts'/'synthetic_comparison.json').read_text())
        self.assertIn('NOT_EXTERNAL_VALIDATION',report['study'])

if __name__=='__main__':unittest.main()

# Additional failure-mode and reproducibility checks.
class AdditionalScientificControls(unittest.TestCase):
    def test_rehashed_forgery_can_still_pass(self):
        # Same algorithm accepts a coherent, false but internally consistent
        # pose record: provenance is a separate, unproven property.
        from external_monitor.monitor import inspect
        claimed=trace()
        cert=evaluate(contract(),claimed)
        result=inspect(contract(),claimed,cert)
        self.assertEqual(result['certificate_check'],'PASS')
        self.assertEqual(cert['source_authenticity'],'UNATTESTED')

    def test_unsupported_source_rejected(self):
        t=trace();t['source_kind']='trusted_physical_without_attestation'
        with self.assertRaises(EvaluationError):evaluate(contract(),t)

    def test_full_upstream_coverage_plan(self):
        p=ROOT/'artifacts'/'upstream_protocol.json'
        self.assertTrue(p.exists())
        j=json.loads(p.read_text())
        self.assertEqual(len(j['eai']['tasks']),8)
        self.assertEqual(len(j['abc']['assessments']),10)
        self.assertTrue(all(t['status']=='NOT_RUN' for t in j['eai']['tasks']))

    def test_replay_truth_separation(self):
        source=(ROOT/'scripts'/'evaluate_blinded_study.py').read_text()
        self.assertNotIn('reference_only/',source)

class CertificateProofTamperingControls(unittest.TestCase):
    """Adversarial report edits with a valid *recomputed* public SHA-256.

    These tests demonstrate that a hash by itself cannot make a claim true.
    The separate checker must reconstruct each stated proof obligation.
    """
    @staticmethod
    def rehash(cert):
        cert['certificate_sha256'] = canonical_hash({k: v for k, v in cert.items()
                                                     if k != 'certificate_sha256'})
        return cert

    def test_rehashed_fake_missing_interval_is_rejected(self):
        from external_monitor.monitor import inspect
        item = cases()['missing_critical_interval']
        cert = evaluate(item['contract'], item['trace'])
        cert['unresolved_coverage'][0]['interval_s'] = [0, 0.01]
        self.rehash(cert)
        result = inspect(item['contract'], item['trace'], cert)
        self.assertEqual(result['certificate_check'], 'FAIL')
        self.assertTrue(any('interval' in x or 'coverage' in x for x in result['errors']))

    def test_rehashed_fake_goal_interval_is_rejected(self):
        from external_monitor.monitor import inspect
        item = cases()['early_truncation']
        cert = evaluate(item['contract'], item['trace'])
        cert['requirements']['goal_at_deadline']['unresolved_intervals'][0]['interval_s'] = [0.5, 0.51]
        self.rehash(cert)
        self.assertEqual(inspect(item['contract'], item['trace'], cert)['certificate_check'], 'FAIL')

    def test_rehashed_fabricated_violation_with_existing_ref_is_rejected(self):
        from external_monitor.monitor import inspect
        cert = evaluate(contract(), trace())
        cert['confirmed_violations'].append({
            'type': 'confirmed_keepout_overlap', 'evidence_ref': 'pose-2', 't_s': 1.0})
        self.rehash(cert)
        self.assertEqual(inspect(contract(), trace(), cert)['certificate_check'], 'FAIL')

    def test_rehashed_missing_positive_proof_is_rejected(self):
        from external_monitor.monitor import inspect
        cert = evaluate(contract(), trace())
        cert['evidence_witnesses'] = []
        self.rehash(cert)
        self.assertEqual(inspect(contract(), trace(), cert)['certificate_check'], 'FAIL')

    def test_rehashed_insufficient_coverage_refs_is_rejected(self):
        from external_monitor.monitor import inspect
        cert = evaluate(contract(), trace())
        zone = next(v for v in cert['evidence_witnesses'] if v['type'] == 'continuous_keepout_coverage')
        zone['evidence_refs'] = ['pose-0']
        self.rehash(cert)
        self.assertEqual(inspect(contract(), trace(), cert)['certificate_check'], 'FAIL')

    def test_forged_source_hash_mode_fails(self):
        from external_monitor.monitor import inspect
        cert = evaluate(contract(), trace())
        cert['source_hash_mode'] = 'magic_authenticity'
        self.rehash(cert)
        self.assertEqual(inspect(contract(), trace(), cert)['certificate_check'], 'FAIL')

    def test_motion_bound_contradiction_prevents_false_violation(self):
        from external_monitor.monitor import inspect
        tr = trace()
        tr['samples'][1]['x'] = 1.0
        tr['samples'][1]['y'] = 0.0
        tr['samples'][2]['x'] = 100.0  # Inconsistent with declared speed bound.
        cert = evaluate(contract(), tr)
        self.assertEqual(cert['verdict'], 'INCONCLUSIVE')
        self.assertEqual(inspect(contract(), tr, cert)['certificate_check'], 'PASS')
        self.assertTrue(any(d['type'] == 'provisional_violation_withdrawn_due_to_trace_contradiction'
                            for d in cert['missing_evidence_diagnostics']))

    def test_duplicate_identity_prevents_false_violation(self):
        from external_monitor.monitor import inspect
        tr = trace()
        tr['samples'][1]['y'] = 0.0
        tr['samples'][2]['event_id'] = tr['samples'][1]['event_id']
        cert = evaluate(contract(), tr)
        self.assertEqual(cert['verdict'], 'INCONCLUSIVE')
        self.assertEqual(inspect(contract(), tr, cert)['certificate_check'], 'PASS')

    def test_violation_survives_a_merely_missing_observation(self):
        from external_monitor.monitor import inspect
        item = cases()['violation_plus_missing']
        cert = evaluate(item['contract'], item['trace'])
        self.assertEqual(cert['verdict'], 'VIOLATING')
        self.assertEqual(inspect(item['contract'], item['trace'], cert)['certificate_check'], 'PASS')
