"""Generate full EAI module/scene and ABC source-assessment coverage plan.
No upstream benchmark is executed or its results imputed.
"""
import json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
ENVIRONMENTS=['virtualhome','behavior']
MODULES=['goal_interpretation','subgoal_decomposition','action_sequencing','transition_modeling']
ABC_ASSESSMENTS=['bird-bench','cy-bench','gaia','kernel-bench','mle-bench','osworld',
                 'swe-bench','swe-lancer','tau-bench','webarena']
REPRO={'schema':'veap.upstream.reproduction/1','no_score_claims':True,
       'eai':{'repository':'https://github.com/embodied-agent-interface/embodied-agent-interface',
              'revision':'531c62f8df2cb392bdf1907923c76da41cad4fe6',
              'environment':'Python 3.8 separate environment, BEHAVIOR iGibson optional dependency',
              'tasks':[{'environment':env,'module':module,'status':'NOT_RUN',
                        'command':f'eai-eval --dataset {env} --eval-type {module} --mode evaluate_results'}
                       for env in ENVIRONMENTS for module in MODULES]},
       'abc':{'repository':'https://github.com/uiuc-kang-lab/agentic-benchmarks',
              'revision':'ae1124758098876db04336e1d8c6e419a139c6e3',
              'checklist':'ABC.md','checklist_sections':['Outcome Validity','Challenge Validity','Benchmark Reporting'],
              'assessments':[{'source':f'assessments/{a}.yaml','status':'NOT_RUN'} for a in ABC_ASSESSMENTS],
              'flaw_experiments':[{'name':n,'status':'NOT_RUN'} for n in ['tau-bench','kernel-bench','swe-lancer','webarena','osworld']]}}

out=ROOT/'artifacts'/'upstream_protocol.json';out.parent.mkdir(exist_ok=True,parents=True)
out.write_text(json.dumps(REPRO,indent=2,sort_keys=True)+'\n')
print(json.dumps({'output':str(out),'eai_cells':len(REPRO['eai']['tasks']),
                  'abc_assessments':len(REPRO['abc']['assessments']),
                  'status':'NOT_RUN'},indent=2))
