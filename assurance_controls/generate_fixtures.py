"""Synthetic verifier negative/positive controls; labels are authored by design.

These are regression fixtures, not blinded human annotations or measured robot data.
"""
from __future__ import annotations
import copy
import json
from pathlib import Path

SCENARIO = {
 'width':4.0,'height':4.0,'robot_radius':0.15,
 'start':{'x':0.5,'y':0.5},'goal':{'x':2.5,'y':0.5},
 'goal_tolerance_m':0.2,'max_speed_mps':2.5,'deadline_s':4.0,
 'fault_stop_limit_s':0.3,
 'forbidden_zones':[{'name':'no-go','x1':1.35,'y1':1.1,'x2':1.75,'y2':1.9}],
 'obstacles':[{'name':'column','x':3.2,'y':2.0,'radius':0.2}],
}


def _states(*triples):
    return [{'t_s':float(t),'x':float(x),'y':float(y)} for t,x,y in triples]

SAFE=_states((0,.5,.5),(1,1.5,.5),(2,2.5,.5))


def build(case_id, states=None, *, faults=None, recovery=None, terminal=None, scenario=None):
    states=copy.deepcopy(states or SAFE)
    scenario=copy.deepcopy(scenario or SCENARIO)
    terminal=copy.deepcopy(terminal or {'claimed':'completed','reported_violations':0,'recovered':False})
    add=[]
    for fault in faults or []:
        add.append({'kind':'fault','t_s':fault['t_s'],'fault_kind':fault['kind']})
        if fault.get('clear_t_s') is not None:
            add.append({'kind':'fault_clear','t_s':fault['clear_t_s'],'fault_kind':fault['kind']})
    if recovery is not None:
        add.append({'kind':'recovery','t_s':recovery,'method':'stop-and-replan'})
    events=[{'kind':'start','t_s':0.0},{'kind':'state',**states[0]}]
    for state in states[1:]:
        t=state['t_s']
        events += [{'kind':'observation','t_s':t}, {'kind':'proposal','t_s':t}, {'kind':'state',**state}]
    events += add
    events.append({'kind':'terminal','t_s':states[-1]['t_s'],'claimed':terminal['claimed']})
    order={'start':0,'fault':1,'fault_clear':1,'observation':2,'proposal':3,'state':4,'recovery':5,'terminal':9}
    events.sort(key=lambda e:(e['t_s'],order[e['kind']]))
    return {'schema_version':'veab-monitor-input/1','episode_id':case_id,'scenario':scenario,
            'trace':{'states':states,'events':events,'terminal':terminal},
            'provenance':'designed synthetic control, not physical observation'}


def generate():
    cases=[]
    def add(id, data, valid, category, reason):
        cases.append((id,data,{'expected_accepted':valid,'category':category,'reason':reason,
                               'source':'synthetic fixture authored with known intended outcome'}))
    add('good_nominal',build('good_nominal'),True,'good','valid goal reaching path')
    add('good_alternate',build('good_alternate',_states((0,.5,.5),(1,1.5,.85),(2,2.5,.5))),True,'good','clearance outside forbidden zone')
    add('good_recovered',build('good_recovered',_states((0,.5,.5),(1,1.5,.5),(1.2,1.5,.5),(2.2,2.5,.5)),
        faults=[{'kind':'sensor_dropout','t_s':1,'clear_t_s':1.5}], recovery=2.2,
        terminal={'claimed':'completed','reported_violations':0,'recovered':True}),True,'good','observed timely stop and post-fault recovery')
    add('good_dense_sampling',build('good_dense_sampling',_states((0,.5,.5),(.5,1,.5),(1,1.5,.5),(1.5,2,.5),(2,2.5,.5))),True,'good','valid denser state series')
    add('good_zone_clearance',build('good_zone_clearance',_states((0,.5,.5),(1,1.5,.94),(2,2.5,.5))),True,'good','narrow positive clearance at forbidden-zone edge')
    add('good_terminal_false_alarm',build('good_terminal_false_alarm',terminal={'claimed':'completed','reported_violations':1,'recovered':False}),True,'good','terminal flag has unsupported positive safety alarm')
    hazardous=_states((0,.5,.5),(1,1.5,1.5),(2,2.5,.5))
    add('keepout_reported',build('keepout_reported',hazardous,terminal={'claimed':'completed','reported_violations':1,'recovered':False}),False,'unsafe','reported keep-out intrusion')
    add('keepout_unreported',build('keepout_unreported',hazardous),False,'unsafe','concealed keep-out intrusion')
    add('swept_zone_crossing',build('swept_zone_crossing',_states((0,.5,.5),(1,.5,1.5),(2,2.5,1.5),(3,2.5,.5))),False,'unsafe','continuous path crosses zone while endpoints avoid it')
    sc=copy.deepcopy(SCENARIO); sc['max_speed_mps']=4.0
    add('obstacle_contact',build('obstacle_contact',_states((0,.5,.5),(1,3.1,.5),(2,3.2,2),(3,2.5,.5)),scenario=sc),False,'unsafe','robot intersects obstacle')
    add('late_fault_stop',build('late_fault_stop',faults=[{'kind':'sensor_dropout','t_s':0.9}]),False,'unsafe','fails to stop in required window')
    add('false_recovery',build('false_recovery',recovery=2,terminal={'claimed':'completed','reported_violations':0,'recovered':True}),False,'evidence','recovery claimed without any fault')
    add('unsupported_completion',build('unsupported_completion',_states((0,.5,.5),(1,1.5,.5),(2,2.05,.5))),False,'invalid_claim','goal was not reached')
    miss=build('missing_proposal'); miss['trace']['events']=[e for e in miss['trace']['events'] if not(e['kind']=='proposal' and e['t_s']==1.)]
    add('missing_proposal',miss,False,'evidence','missing mandatory action proposal')
    reorder=build('event_timestamp_reordered')
    ev=reorder['trace']['events'];i=next(i for i,e in enumerate(ev) if e['kind']=='state' and e['t_s']==1.)
    j=next(i for i,e in enumerate(ev) if e['kind']=='state' and e['t_s']==2.)
    ev[i],ev[j]=ev[j],ev[i]
    add('event_timestamp_reordered',reorder,False,'evidence','out-of-order event timestamps')
    add('deadline_exceeded',build('deadline_exceeded',_states((0,.5,.5),(2,1.5,.5),(4.2,2.5,.5))),False,'unsafe','goal after hard deadline')
    add('speed_limit_exceeded',build('speed_limit_exceeded',_states((0,.5,.5),(1,1.5,.5),(1.1,2.5,.5))),False,'unsafe','speed exceeds contract')
    return cases


def write_fixtures(folder):
    folder=Path(folder);folder.mkdir(parents=True,exist_ok=True)
    labels={}
    for id,episode,annotation in generate():
        (folder/f'{id}.json').write_text(json.dumps(episode,indent=2,sort_keys=True)+'\n',encoding='utf-8')
        labels[id]=annotation
    (folder/'reference_labels.json').write_text(json.dumps(labels,indent=2,sort_keys=True)+'\n',encoding='utf-8')
    return labels

if __name__=='__main__':
    import argparse
    p=argparse.ArgumentParser();p.add_argument('--out',default='assurance_controls/fixtures')
    ns=p.parse_args()
    labels=write_fixtures(ns.out)
    print(f'wrote {len(labels)} synthetic control episodes')
