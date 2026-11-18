"""Bounded recovery, with synthetic replies; never an LLM accuracy score."""
from copy import deepcopy
from types import SimpleNamespace
import json
import pytest
from test_user_workflow import automatic_fixture
from test_live_demo import fixture_review
from demo.backend import automatic_review as audit, engine as module
from demo.backend.engine import Engine, Run
from cfm_id_llm.providers.base import ProviderError

def truncated():
    return ProviderError('truncated',code='INCOMPLETE_COMPLETION',
                         diagnostics={'finish_reason':'length'})

def test_length_retry_keeps_all_evidence_and_valid_adverse_findings(tmp_path,monkeypatch):
    e,r,_=automatic_fixture(tmp_path,monkeypatch)
    request,fields,sources=audit.request(r)
    original=deepcopy(request);seen=[]
    rejected={'scientific_approval':False,'findings':[dict(field=next(iter(fields)),
        source_ids=[next(iter(sources))],reason='候选改变了原文明确的比较方向',
        kind='READING_ERROR',question=None)]}
    def reply(run,req,stage):
        seen.append((deepcopy(req),stage))
        if len(seen)==1:raise truncated()
        return rejected
    monkeypatch.setattr(e,'call',reply)
    result=e._call_audit(r,request,'reading_audit_1')
    assert result==rejected and audit.check(result,fields,sources)['verdict']=='READING_ERROR'
    assert request==original and seen[0][0]['user_prompt']==seen[1][0]['user_prompt']
    assert [x[1] for x in seen]==['reading_audit_1','reading_audit_1_length_retry']
    assert r.automatic_audit_length_retries=={'query'}
    assert not r.reviews and r.result is None and r.query_review is None

def test_two_truncations_stop_and_do_not_restart_the_reading(tmp_path,monkeypatch):
    e,r,_=automatic_fixture(tmp_path,monkeypatch);calls=[]
    original=deepcopy(r.intake)
    def fail(run,request,stage):
        calls.append(stage);raise truncated()
    monkeypatch.setattr(e,'call',fail)
    with pytest.raises(ProviderError):e._continue_automatically(r)
    assert len(calls)==2 and r.intake==original and r.submission is None
    assert r.query_review is None and not r.reviews
    # Even a later audit in this phase cannot acquire another automatic retry.
    with pytest.raises(ProviderError):e._call_audit(r,{},'reading_audit_9')
    assert len(calls)==3

@pytest.mark.parametrize('code,reason',[
    ('INCOMPLETE_COMPLETION','content_filter'),('INCOMPLETE_COMPLETION',None),
    ('MODEL_REFUSAL','stop'),('TIMEOUT',None),('HTTP_ERROR',None)])
def test_no_retry_for_refusal_missing_finish_reason_or_transport(tmp_path,monkeypatch,code,reason):
    e,r,_=automatic_fixture(tmp_path,monkeypatch);calls=[]
    def fail(*args):
        calls.append(1);raise ProviderError('not recoverable here',code=code,diagnostics={'finish_reason':reason})
    monkeypatch.setattr(e,'call',fail)
    with pytest.raises(ProviderError):e._call_audit(r,{},'reading_audit_1')
    assert len(calls)==1 and not r.automatic_audit_length_retries

def test_longcat_retry_budget_and_global_call_cap_still_apply(tmp_path,monkeypatch):
    sent=[]
    def factory(**options):
        sent.append(options['max_tokens'])
        return SimpleNamespace(api_key=None,last_diagnostics={})
    monkeypatch.setattr(module,'generate',lambda *a,**k:{})
    e=Engine(tmp_path,provider_factory=factory,max_api_calls=2)
    e.credential('offline','longcat','offline-placeholder')
    r=Run(owner='offline',provider='longcat')
    e.call(r,{},'reading_audit_1');e.call(r,{},'reading_audit_1_length_retry')
    assert sent==[16384,32768] and e.calls==2
    with pytest.raises(ValueError,match='LOCAL_API_CALL_LIMIT'):
        e.call(r,{},'reading_audit_2_length_retry')
    assert sent==[16384,32768]

@pytest.mark.parametrize('network_matches',[True,False,None])
def test_graph_conflict_only_source_bound_error_can_trigger_reread(tmp_path,monkeypatch,network_matches):
    e,r,_=automatic_fixture(tmp_path,monkeypatch)
    # Isolate the dispatch-conflict branch; no fake mathematical acceptance.
    blocked=dict(state='ADAPTER_NOT_CONNECTED',reason_code='COMBINED_OR_AMBIGUOUS_GRAPH_REPRESENTATIONS',
                 backend_called=False,independent_replay=False)
    monkeypatch.setattr(module.business_field_review,'submit',lambda *a,**k:deepcopy(blocked))
    # Use the actual target contract field names and source catalog.
    request,fields,sources=audit.request(r)
    assert 'query:common.unit_network' in fields and 'query:common.variable_causal_graph' in fields
    before=deepcopy(r.intake);seen=[];rereads=[]
    def reply(run,req,stage):
        seen.append(stage);body=json.loads(req['user_prompt'])
        assert body['source_catalog']==json.loads(request['user_prompt'])['source_catalog']
        assert set(body['fields'])=={'query:common.unit_network','query:common.variable_causal_graph'}
        assert body['other_reading_context'] and body['graph_conflict_context']
        return dict(scientific_approval=False,assessments=[
            dict(field=p,source_ids=[next(iter(sources))],comparison='核对原文中的对象关系与变量箭头的字段归属',
                 matches_source=network_matches if p.endswith('unit_network') else True,
                 question='这些联系是门店之间的往来，还是变量之间的影响？' if p.endswith('unit_network') and network_matches is None else None)
            for p in body['fields']])
    monkeypatch.setattr(e,'call',reply)
    def reread(run,feedback):
        rereads.append(feedback);return True
    monkeypatch.setattr(e,'_reread_business',reread)
    e._review(r,fixture_review(r))
    assert r.intake==before and r.submission is None and r.query_review is None and not r.reviews
    assert seen==['graph_conflict_audit']
    if network_matches is True:
        assert r.result==blocked and not rereads  # Genuine mixed setting stays blocked.
    elif network_matches is False:
        assert len(rereads)==1 and rereads[0]['source_located_issues'][0]['kind']=='READING_ERROR'
        assert r.result is None  # Only a real new A0 can resolve it.
    else:
        assert not rereads and r.result['state']=='NEEDS_INPUT' and r.user_question
        assert r.result['backend_called'] is False

def test_graph_focus_requires_both_fields_and_cannot_approve_science(tmp_path,monkeypatch):
    e,r,_=automatic_fixture(tmp_path,monkeypatch)
    req,fields,sources=audit.graph_conflict_request(r)
    with pytest.raises(ValueError,match='EXACT_COVERAGE'):
        audit.check_focused(dict(scientific_approval=False,assessments=[]),fields,sources)
    with pytest.raises(ValueError,match='PERMISSION'):
        audit.check_focused(dict(scientific_approval=True,assessments=[]),fields,sources)

def test_target_meaning_reaches_operand_full_and_focused_review(tmp_path,monkeypatch):
    e,r,_=automatic_fixture(tmp_path,monkeypatch)
    # Isolate the worksheet contract, not a new business or mathematical claim.
    r.review_sheets['query']['fields']['queries.q1.kind']['candidate']='INTERVENTIONAL_DISTRIBUTION'
    req,fields,sources=audit.request(r)
    from cfm_id_llm.target_first_reading import NETWORK_TARGET_DEFINITIONS
    path='query:queries.q1.semantics.first_arrangement'
    local=fields[path]['target_contract']
    assert local['definition']==NETWORK_TARGET_DEFINITIONS['INTERVENTIONAL_DISTRIBUTION']
    assert '不要求原文写出字母x' in local['definition'] and '不得扩大或缩小' in local['boundary']
    focused,subset=audit.focused_request(req,fields,dict(issues=[dict(field=path,kind='READING_ERROR')]))
    assert subset[path]['target_contract']==local
    assert json.loads(focused['user_prompt'])['source_catalog']==json.loads(req['user_prompt'])['source_catalog']
    assert r.query_review is None and not r.reviews
