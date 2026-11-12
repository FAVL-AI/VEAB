import pytest
from veab.spec import Scenario, digest, canonical, list_scenarios, load_scenario


def test_five_scenarios_with_train_validation_test():
    cases=list_scenarios()
    assert len(cases)>=5
    assert set(s.split for s in cases)=={"train","validation","test"}
    assert all(load_scenario(s.id).id==s.id for s in cases)


@pytest.mark.parametrize('name',['../secret','FOO','bad/id',''])
def test_reject_unsafe_scenario_name(name):
    with pytest.raises(ValueError):load_scenario(name)


def test_deterministic_canonical_json():
    assert digest({'b':2,'a':1})==digest({'a':1,'b':2})
    with pytest.raises(ValueError):canonical({'x':float('nan')})


def test_reject_unknown_scenario_field():
    case=load_scenario('campus-patrol').model_dump()
    case['arbitrary_code']='__import__("os").system("rm -rf /")'
    with pytest.raises(Exception): Scenario.model_validate(case)
