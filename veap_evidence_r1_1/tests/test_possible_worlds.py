"""Constructive ambiguity, certificate falsification and correlation controls."""
import copy
import unittest
from pathlib import Path

from veap_evidence.fixtures import cases
from veap_evidence.possible_worlds import construct_gap_pair
from veap_evidence.verdict import EvaluationError, canonical_hash, evaluate
from external_monitor.possible_worlds_checker import verify_pair, check_world, segment_rect_distance
from scripts.run_r1_identifiability import run_study,translated_variant


class CounterfactualIdentifiabilityTests(unittest.TestCase):
    def setUp(self):
        item=cases()['missing_critical_interval']
        self.contract=item['contract']
        self.trace=item['trace']
        self.pair=construct_gap_pair(self.contract,self.trace)

    def test_pair_demonstrates_same_evidence_opposite_worlds(self):
        checked=verify_pair(self.contract,self.trace,self.pair)
        self.assertEqual(checked['status'],'PASS')
        self.assertEqual(checked['world_results']['candidate_compliant']['world_verdict'],'COMPLIANT')
        self.assertEqual(checked['world_results']['candidate_violating']['world_verdict'],'VIOLATING')
        self.assertEqual(evaluate(self.contract,self.trace)['verdict'],'INCONCLUSIVE')

    def test_independent_checker_no_veap_imports(self):
        source=(Path(__file__).parents[1]/'external_monitor'/'possible_worlds_checker.py').read_text()
        self.assertNotIn('from veap',source)
        self.assertNotIn('import veap',source)

    def test_pair_linked_to_inputs(self):
        altered=copy.deepcopy(self.pair)
        altered['contract_sha256']='0'*64
        self.assertEqual(verify_pair(self.contract,self.trace,altered)['status'],'FAIL')

    def test_rehashed_but_unphysical_violation_world_rejected(self):
        altered=copy.deepcopy(self.pair)
        altered['paths']['candidate_violating'][2]['y']=-100.0
        altered['pair_sha256']=canonical_hash({k:v for k,v in altered.items() if k!='pair_sha256'})
        checked=verify_pair(self.contract,self.trace,altered)
        self.assertEqual(checked['status'],'FAIL')
        self.assertTrue(any('speed' in e for e in checked['failures']))

    def test_rehashed_but_mismatched_observation_rejected(self):
        altered=copy.deepcopy(self.pair)
        altered['paths']['candidate_violating'][1]['x']+=0.3
        altered['pair_sha256']=canonical_hash({k:v for k,v in altered.items() if k!='pair_sha256'})
        self.assertEqual(verify_pair(self.contract,self.trace,altered)['status'],'FAIL')

    def test_rehashed_false_safe_world_rejected(self):
        altered=copy.deepcopy(self.pair)
        altered['paths']['candidate_compliant'][2]['y']=0.0
        altered['pair_sha256']=canonical_hash({k:v for k,v in altered.items() if k!='pair_sha256'})
        self.assertEqual(verify_pair(self.contract,self.trace,altered)['status'],'FAIL')

    def test_rehashed_false_terminal_goal_rejected(self):
        altered=copy.deepcopy(self.pair)
        altered['paths']['candidate_compliant'][-1]['x']=3.0
        altered['pair_sha256']=canonical_hash({k:v for k,v in altered.items() if k!='pair_sha256'})
        self.assertEqual(verify_pair(self.contract,self.trace,altered)['status'],'FAIL')

    def test_rehashed_false_missing_interval_is_rejected(self):
        altered=copy.deepcopy(self.pair)
        altered['missing_interval_s']=[0.0, 2.0]
        altered['pair_sha256']=canonical_hash({k:v for k,v in altered.items() if k!='pair_sha256'})
        self.assertEqual(verify_pair(self.contract,self.trace,altered)['status'],'FAIL')

    def test_rehashed_wrong_assumptions_rejected(self):
        altered=copy.deepcopy(self.pair)
        altered['assumptions']['max_speed_mps']=40.
        altered['pair_sha256']=canonical_hash({k:v for k,v in altered.items() if k!='pair_sha256'})
        self.assertEqual(verify_pair(self.contract,self.trace,altered)['status'],'FAIL')

    def test_rehashed_false_compliance_claim_rejected(self):
        altered=copy.deepcopy(self.pair)
        altered['required_joint_decision']='COMPLIANT'
        altered['pair_sha256']=canonical_hash({k:v for k,v in altered.items() if k!='pair_sha256'})
        self.assertEqual(verify_pair(self.contract,self.trace,altered)['status'],'FAIL')

    def test_pair_not_claimed_provenance(self):
        self.assertEqual(self.pair['source_authenticity'],'UNATTESTED')
        checked=verify_pair(self.contract,self.trace,self.pair)
        self.assertEqual(checked['ground_truth_independence'],'NOT_ESTABLISHED')

    def test_pair_generator_rejects_unsupported_gap(self):
        with self.assertRaises(EvaluationError):
            construct_gap_pair(self.contract,self.trace,at_time_s=-2.)

    def test_geometry_detects_segment_crossing_without_interior_samples(self):
        # Neither endpoint in rectangle, straight segment crosses it.
        rect=[0.8,-0.2,1.2,0.2]
        self.assertEqual(segment_rect_distance((0.,0.),(2.,0.),rect),0.)

    def test_harmless_missing_camera_retains_compliance(self):
        item=cases()['missing_irrelevant_camera']
        self.assertEqual(evaluate(item['contract'],item['trace'])['verdict'],'COMPLIANT')

    def test_observed_violation_survives_gap(self):
        item=cases()['violation_plus_missing']
        self.assertEqual(evaluate(item['contract'],item['trace'])['verdict'],'VIOLATING')

    def test_stress_study_clearly_declares_correlations(self):
        result=run_study(3)
        self.assertEqual(result['n_cases'],18)
        self.assertTrue(result['no_independent_scenes'])
        self.assertEqual(result['summary']['accepted_counterfactual_ambiguity_witnesses'],3)
        self.assertEqual(result['summary']['accepted_veap_certificates'],18)
        self.assertEqual(result['summary']['correct_by_method']['veap'],18)

if __name__=='__main__':unittest.main()
