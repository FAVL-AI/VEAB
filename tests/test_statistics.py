from veap.statistics import group_metrics, paired_bootstrap


def test_paired_bootstrap_is_deterministic():
    records=[]
    for i in range(6):
        records.append({'scenario_id':'a','seed':i,'policy':'route','shield':True,'verified':True,'progress':1.,'safety_violations':0,'energy_proxy':10.})
        records.append({'scenario_id':'a','seed':i,'policy':'route','shield':False,'verified':i%2==0,'progress':.5,'safety_violations':1,'energy_proxy':8.})
    a=paired_bootstrap(records,('route',True),('route',False))
    assert a==paired_bootstrap(records,('route',True),('route',False))
    assert a['n_pairs']==6 and a['difference']==.5
    assert group_metrics(records)['route__shield_True']['verified_completion']==1
