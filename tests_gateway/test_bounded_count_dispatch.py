"""E4 common-entry contracts. Fixtures are not LLM measurements."""
from copy import deepcopy
from itertools import combinations
import pytest
from examples.network_contrast_dispatch_reference import material,a0_reference,fact_reference,approval_records
from examples.business_dispatch_reference import approve
from cfm_id import business_intake as intake,business_dispatch as dispatch


def setup(*,single=False,point=False,missing=False,extra=False,reverse=False):
    case,data=material('partial',bounds=('1/4','3/4'),reverse=reverse)
    nodes=data['nodes']
    if point:data['first']=[1,1,0,0];data['second']=[0,0,1,1]
    data['cells']=[dict(node=n,own=a,exposure=2-a,value='1/2') for n in nodes for a in (0,1)]
    c=case.model_dump()
    for src in c['sources']:
        if src['source_id']=='exposure':src['text']='同伴状态是合作邻居中启用工具的准确人数。'
        if src['source_id']=='information':src['text']='以下为全部可用的精确总体条件均值，不是样本估计：\n'+'\n'.join(f"{v['node']}自身状态{v['own']}，启用邻居人数{v['exposure']}时，总体准时开门率为1/2。" for v in data['cells'])
    first='、'.join(n for n,a in zip(nodes,data['first']) if a) or '没有门店'
    second='、'.join(n for n,a in zip(nodes,data['second']) if a) or '没有门店'
    c['business_question']=f'同一考核周，在{first}启用、其他店不启用时，四店等权平均准时开门率是多少？' if single else f'同一考核周，从{second}启用改成{first}启用（各方案其余店均不启用），四店等权平均准时开门率提高多少？'
    case=type(case).model_validate(c)
    a0=a0_reference(case)
    if single:
        a0['queries'][0]['kind']='FIXED_POLICY_VALUE'
        a0['queries'][0]['semantics'].pop('comparator')
    s=intake.start(case);s=intake.receive_candidate(s,a0,request_sha256=s.request_sha256)
    review=approve(dispatch.prepare_reader(s,'q1')['query_worksheet'])
    entry=dispatch.prepare_reader(s,'q1',query_review=review)
    raw=fact_reference(entry,data);raw['exposure']['kind']='EXACT_TREATED_NEIGHBOR_COUNT'
    if single:
        raw['version']='network-policy-reading-1'
        raw['target']=dict(kind='FIXED_POLICY_MEAN',**raw['target']['first'])
    if missing:raw['bounded_model']['listed_means_are_complete_information']['value']=None
    if extra:raw['bounded_model']['no_additional_coupling_constraints']['value']=False
    options=dict(query_review=review,candidate=raw,request_sha256=entry['request_sha256'])
    return s,options


@pytest.mark.parametrize('single',[True,False])
@pytest.mark.parametrize('point',[True,False])
def test_common_entry_uses_count_support_and_independent_replay(single,point):
    s,o=setup(single=single,point=point);p=dispatch.inspect_methods(s,'q1',**o)
    assert p['state']=='REVIEW_REQUIRED',p
    r=dispatch.execute(s,'q1',**o,**approval_records(p))
    assert r['state']==('POINT' if point else 'PARTIAL'),r
    assert r['independent_replay'] and r['primary_method'].endswith('D2_E4')
    expected=(['1/2','1/2'] if single else ['0','0']) if point else (['1/4','3/4'] if single else ['-1/2','1/2'])
    assert r['mathematical_claim']['interval']==expected
    withheld=dispatch.execute(s,'q1',**o,research_protocol_selected=True)
    assert not withheld['backend_called']


@pytest.mark.parametrize('single',[True,False])
@pytest.mark.parametrize('missing,extra,state',[(True,False,'NEEDS_INPUT'),(False,True,'ADAPTER_NOT_CONNECTED')])
def test_missing_or_rejected_model_does_not_call_backend(single,missing,extra,state):
    s,o=setup(single=single,missing=missing,extra=extra)
    p=dispatch.inspect_methods(s,'q1',**o)
    assert p['state']==state,p
    assert not p['backend_called']


def test_exposure_schema_and_local_check_agree_on_weighted_only_fields():
    from cfm_id_llm.shared_fact_definitions import SharedExposure
    from jsonschema import Draft202012Validator
    from pydantic import ValidationError
    validator=Draft202012Validator(SharedExposure.model_json_schema())
    for kind in ('EXACT_TREATED_NEIGHBOR_COUNT','STRICT_MAJORITY_TIES_LOW','ANY_TREATED_NEIGHBOR'):
        good=dict(kind=kind,source_ids=['s1'],mode=None,weights=None)
        validator.validate(good);SharedExposure.model_validate(good)
        bad=dict(good,mode='sum')
        assert list(validator.iter_errors(bad))
        with pytest.raises(ValidationError,match='NONWEIGHTED_EXPOSURE'):
            SharedExposure.model_validate(bad)
    weighted=dict(kind='WEIGHTED_EXPOSURE',source_ids=['s1'],weights={'A':'1/2'},mode='sum')
    validator.validate(weighted);SharedExposure.model_validate(weighted)
