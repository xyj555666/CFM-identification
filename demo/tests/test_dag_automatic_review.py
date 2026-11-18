"""DAG reading automation keeps the original native gates and science approval."""
from copy import deepcopy
import json
import pytest
from test_web_capabilities import setup, approve
from demo.backend.engine import Engine, Run, project
from demo.backend import dag_reading_review as dag, automatic_review as audit

def fixture(tmp_path, name='dag_frontdoor'):
    intake,submission,plan=setup(name)
    from cfm_id.business_intake import configure_fact_format
    from examples.business_dispatch_reference import approve as query_approve
    from examples.business_case_reference import short_fixture
    native=submission['candidate']
    intake=configure_fact_format(intake,'short_refs')
    review=query_approve(project.prepare_reader(intake,'q1')['query_worksheet'])
    entry=project.prepare_reader(intake,'q1',query_review=review)
    submission=dict(query_review=review,request_sha256=entry['request_sha256'],candidate=short_fixture(entry,native,None))
    run=Run(owner='fixture',synthetic=True,automatic_review=True,intake=intake,
            query_id='q1',entry=entry,submission=submission,query_review=submission['query_review'])
    engine=Engine(tmp_path);engine._plan(run)
    return engine,run

def matching(fields,sources):
    return dict(scientific_approval=False,assessments=[dict(field=p,source_ids=list(sources),
        comparison='原材料与本字段、来源及投影逐项相符。',matches_source=True,question=None) for p in fields])

@pytest.mark.parametrize('name',['dag_backdoor','dag_adjustment','dag_frontdoor'])
def test_source_review_background_then_only_science_remains(tmp_path,monkeypatch,name):
    engine,run=fixture(tmp_path,name)
    assert run.review_kind=='dag_source' and run.result is None
    req,fields,sources=dag.request(run)
    body=json.loads(req['user_prompt'])
    assert body['candidate']==run.submission['candidate'] and body['source_catalog']
    assert len(body['method_projections'])==len(run.plan['methods'])
    monkeypatch.setattr(engine,'call',lambda r,q,s:matching(fields,sources))
    engine._continue_automatically(run)
    assert run.review_kind=='science' and run.result is None and dag.valid(run)
    assert run.review_sheets and all(k.endswith('.science_review') for k in run.review_sheets)
    assert 'plan' in run.dag_fact_audit['records']
    engine._review(run,approve(run))
    assert run.result['state']=='POINT' and run.result['independent_replay'] is True

def test_rejected_science_is_not_overridden(tmp_path,monkeypatch):
    engine,run=fixture(tmp_path)
    _,fields,sources=dag.request(run)
    monkeypatch.setattr(engine,'call',lambda *a:matching(fields,sources))
    engine._continue_automatically(run)
    record=approve(run)
    first=next(iter(record['records']))
    record['records'][first]['decisions']['recursive_scm_and_perfect_intervention']='REJECTED'
    engine._review(run,record)
    assert run.result['state']!='POINT' and not run.result.get('backend_called')

def test_stale_audit_never_unlocks_science(tmp_path,monkeypatch):
    engine,run=fixture(tmp_path)
    _,fields,sources=dag.request(run)
    monkeypatch.setattr(engine,'call',lambda *a:matching(fields,sources))
    engine._continue_automatically(run)
    run.submission['candidate']['target']['context']='changed scope'
    assert not dag.valid(run)
    with pytest.raises(ValueError,match='CURRENT_DAG_SOURCE_REVIEW_REQUIRED'):
        engine._review(run,approve(run))
    assert run.result is None

def test_incomplete_and_fabricated_source_audits_rejected(tmp_path):
    _,run=fixture(tmp_path)
    _,fields,sources=dag.request(run)
    raw=matching(fields,sources);raw['assessments'].pop()
    with pytest.raises(ValueError):audit.check_focused(raw,fields,sources)
    raw=matching(fields,sources);raw['assessments'][0]['source_ids']=['made_up']
    with pytest.raises(ValueError):audit.check_focused(raw,fields,sources)
    raw=matching(fields,sources);raw['scientific_approval']=True
    with pytest.raises(ValueError,match='PERMISSION'):audit.check_focused(raw,fields,sources)

def test_known_error_is_reread_with_original_evidence_and_not_approved(tmp_path,monkeypatch):
    engine,run=fixture(tmp_path)
    original=deepcopy(run.submission)
    _,fields,sources=dag.request(run)
    raw=matching(fields,sources)
    raw['assessments'][0].update(matches_source=False,comparison='候选目标与原文所给研究时期不一致。')
    result=audit.check_focused(raw,fields,sources)
    captured=[]
    monkeypatch.setattr(engine,'_recheck',lambda r,e,f:captured.append((e,f)))
    assert dag.reread(engine,run,result)
    entry,feedback=captured[0]
    assert entry['reading_revision']['steps'][-1]['candidate']==original['candidate']
    assert feedback['issues'][0]['field_path']=='' and feedback['issues'][0]['source_ids']
    assert not run.dag_fact_audit and not dag.reread(engine,run,result)

def test_actual_ambiguity_asks_without_reread_or_science(tmp_path,monkeypatch):
    engine,run=fixture(tmp_path)
    _,fields,sources=dag.request(run)
    raw=matching(fields,sources)
    raw['assessments'][0].update(matches_source=None,comparison='原文对这项时期仍未确定。',question='这次关注哪个随访时期？')
    monkeypatch.setattr(engine,'call',lambda *a:raw)
    monkeypatch.setattr(engine,'_recheck',lambda *a:pytest.fail('Ambiguity must not become a reading retry'))
    engine._continue_automatically(run)
    assert run.user_question['items'][0]['question']=='这次关注哪个随访时期？'
    assert run.result is None and not run.dag_fact_audit

def test_manual_workflow_still_requires_native_reading_reviews(tmp_path):
    intake,submission,plan=setup('dag_frontdoor')
    run=Run(owner='manual',synthetic=True,intake=intake,query_id='q1',submission=submission)
    engine=Engine(tmp_path);engine._plan(run)
    assert run.review_kind=='science' and 'plan' in run.review_sheets
    assert any(k.endswith('.reading_review') for k in run.review_sheets)

@pytest.mark.parametrize('kind',['FINITE_SAMPLE','MARGINALS_ONLY'])
def test_true_information_gap_still_stops_after_automatic_review(tmp_path,monkeypatch,kind):
    engine,run=fixture(tmp_path)
    run.submission['candidate']['information']['kind']=kind
    engine._plan(run)
    _,fields,sources=dag.request(run)
    monkeypatch.setattr(engine,'call',lambda *a:matching(fields,sources))
    engine._continue_automatically(run)
    assert run.result['state']=='NEEDS_INPUT'
    assert run.result['clarification_questions'] and not run.result['backend_called']
    assert run.review_kind is None and run.result.get('independent_replay') is False

def test_revised_a0_gets_one_new_focused_check(tmp_path,monkeypatch):
    from test_user_workflow import automatic_fixture
    engine,run,_=automatic_fixture(tmp_path,monkeypatch)
    run.automatic_focused_stages.add('query')
    run.artifacts['target_reread_prior']={'intake_candidate':{'test':'Different original candidate retained'}}
    request,fields,sources=audit.request(run);key=next(iter(fields))
    seen=[]
    def call(r,q,stage):
        seen.append(stage)
        if stage.startswith('focused_audit'):
            return matching({key:fields[key]},sources)
        return dict(scientific_approval=False,findings=[dict(field=key,source_ids=list(sources),
            reason='复核模型对新候选的原意仍有争议，需要定向核对。',kind='READING_ERROR',question=None)])
    monkeypatch.setattr(engine,'call',call)
    def reviewed(r,payload):r.review_kind='science'
    monkeypatch.setattr(engine,'_review',reviewed)
    engine._continue_automatically(run)
    assert len(seen)==2 and seen[1].startswith('focused_audit')
    assert run.automatic_focused_stages=={'query','query_reread'}

def test_active_target_profile_uses_shared_aggregation_contract(tmp_path,monkeypatch):
    from test_user_workflow import automatic_fixture
    from cfm_id_llm.business_field_contract import fields as business_fields
    from cfm_id_llm.target_first_skill import AGGREGATION
    shared=next(f for f in business_fields('semantics') if f.name=='aggregation')
    assert AGGREGATION==shared
    engine,run,_=automatic_fixture(tmp_path,monkeypatch)
    request,fields,sources=audit.request(run)
    actual=[f['definition'] for p,f in fields.items() if p.endswith('.semantics.aggregation')]
    assert actual and all(f['meaning']==shared.meaning and f['excludes']==shared.excludes for f in actual)


def test_located_business_reread_receives_previous_wire_output_without_approval(tmp_path,monkeypatch):
    from test_user_workflow import automatic_fixture
    engine,run,_=automatic_fixture(tmp_path,monkeypatch)
    original_case=deepcopy(run.case)
    previous={'queries':[{'kind':'INTERVENTIONAL_DISTRIBUTION',
        'semantics':{'first_arrangement':{'state':'STATED','value':'设定变量的各个取值','refs':['s0001']},
                     'standardization_distribution':{'state':'STATED','value':'可用联合分布','refs':['s0002']}}}]}
    run.artifacts['a0_candidate']=deepcopy(previous)
    feedback={'source_located_issues':[{'field':'query:queries.q1.semantics.standardization_distribution',
        'reason':'资料来源不等于目标的平均规则','source_ids':['query:s0002']}]}
    requests=[]
    class RequestCaptured(Exception):pass
    def call(r,request,stage):
        assert stage=='a0';requests.append(deepcopy(request));raise RequestCaptured()
    monkeypatch.setattr(engine,'call',call)
    with pytest.raises(RequestCaptured):engine._reread_business(run,feedback)
    block=json.loads(requests[0]['user_prompt'].split('\n\n')[-1])
    assert block['previous_candidate']==previous and block['reread_reason']==feedback
    assert run.case==original_case and run.query_review is None and not run.reviews
    assert run.artifacts['target_reread_prior']['artifacts']['a0_candidate']==previous
    assert not engine._reread_business(run,feedback) and len(requests)==1
