"""Source-bound automatic DAG reading review; scientific decisions remain separate."""
from copy import deepcopy
import json
from cfm_id import business_dispatch as dispatch, fact_reading_revision
from cfm_id_llm.fact_reading_contracts import contract_for_entry
from . import automatic_review as audit, capabilities

READING = {
    'target_meaning': '干预变量、结果、研究对象、时期、背景和干预取值必须与已审核原问一致。全部取值的分布函数允许自由参数，不是擅自指定单个值。',
    'variable_measurements_and_roles': '逐个核对变量、二元编码、观测或潜在状态。不能把未观测共同原因变成已观测变量。',
    'relations_and_omissions': '逐条核对直接因果边与方向、遗漏、完整性声明；对象间联系不等于变量因果边。',
    'source_entailment_and_scope': '核对每项实际引用及全部材料有无漏读；总体信息与样本、正支持、机制声明、未决定、不采用及真正额外限制必须保持原意。只确认如实记录，不批准科学有效性。',
    'requested_identification_roles': '保留指定、禁止、未决定或未指定调整集/前门变量的区别；不从方法名称自行添加角色。'
}
PLAN = {
    'selected_query_matches_native_target': '各方法的目标投影是否保持已审核的同一子问题。',
    'complete_model_and_constraints_preserved': '各投影是否保留全部共同因果图、潜在变量、科学声明及额外限制，没有为某个方法删除不利条件。',
    'method_requests_and_projections_preserved': '调整/前门角色与方法排除是否保持原声明；不检查定理是否成立。',
    'requested_intervention_values_and_kernel_view': '返回核函数的取值视图是否保持原问的指定取值或全部取值范围。'
}

def connected(run):
    return bool(run.automatic_review and run.entry and run.entry.get('reader_id')=='VARIABLE_DAG_FACTS'
                and run.entry.get('reference_format')=='short_refs' and run.submission)

def binding(run):
    return dispatch.sha(dict(entry=run.entry,candidate=run.submission['candidate'],plan=run.plan))

def valid(run):
    receipt=run.dag_fact_audit
    return bool(receipt and receipt.get('binding_sha256')==binding(run)
                and receipt.get('scientific_approval') is False)

def worksheet(run):
    contract=contract_for_entry(run.entry)
    if contract is None:raise ValueError('DAG_REGISTERED_READER_REQUIRED')
    refs=contract.reference_catalog(run.entry['bundle'],binding=run.entry['fact_binding_sha256'])
    return dict(version='web-dag-source-audit-1',binding_sha256=binding(run),
        source_catalog=deepcopy(refs['aliases']),decisions={},is_approval=False)

def request(run):
    if not connected(run) or run.review_kind!='dag_source':raise ValueError('DAG_SOURCE_STAGE_REQUIRED')
    contract=contract_for_entry(run.entry)
    sheet=worksheet(run);sources=sheet['source_catalog']
    candidate=run.submission['candidate']
    fields={key:dict(role=meaning,candidate=deepcopy(candidate),source_namespace='dag')
            for key,meaning in READING.items()}
    # Every requested native decision must be covered, not silently approved by
    # an incomplete reusable dictionary when a future method adds a new check.
    for row in run.plan.get('methods',[]):
        keys=(row.get('reading_worksheet') or {}).get('decisions',{})
        if not set(keys)<=READING.keys():raise ValueError('DAG_READING_DECISION_NOT_CONNECTED')
    if 'plan_worksheet' in run.plan:
        for key in run.plan['plan_worksheet']['decisions']:
            if key not in PLAN:raise ValueError('DAG_PLAN_DECISION_NOT_CONNECTED')
            fields['plan.'+key]=dict(role=PLAN[key],candidate=deepcopy(run.plan.get('query_scope')),
                                    source_namespace='dag')
    # Candidate once; all originals and method projections remain in context.
    for f in fields.values():f.pop('candidate',None)
    body=dict(stage='dag_source',fields=fields,source_catalog=sources,
        candidate=deepcopy(candidate),selected_query=deepcopy(run.entry['selected_query']),
        field_schema=contract.model.model_json_schema(),
        method_projections=[{k:deepcopy(row.get(k)) for k in ('method','projection','candidate','proposed_problem')}
                            for row in run.plan.get('methods',[])],
        query_scope=deepcopy(run.plan.get('query_scope')),
        exclusions=deepcopy(run.plan.get('exclusions',[])),
        definition_usage='字段定义与方法投影不是原文证据；核对来源是否支持拟采用条件，不要求此时已经科学批准。')
    base=dict(system_prompt=audit.SYSTEM,user_prompt=json.dumps(body,ensure_ascii=False))
    req,checked=audit.focused_request(base,fields,dict(issues=[dict(field=k,kind='READING_ERROR') for k in fields]))
    return req,checked,sources

def accept(run,answer):
    if answer['verdict']!='PASS' or answer['scientific_approval'] is not False:
        raise ValueError('DAG_SOURCE_APPROVAL_FORBIDDEN')
    req,fields,sources=request(run)
    confirmed=answer.get('confirmed',[])
    if len(confirmed)!=len(fields) or {x['field'] for x in confirmed}!=set(fields):
        raise ValueError('DAG_SOURCE_EXACT_COVERAGE_REQUIRED')
    evidence='后台独立对照原文逐项完成目标、变量、因果图、引用与投影核对；不批准科学条件。'
    records={}
    sheets={}
    if 'plan_worksheet' in run.plan:sheets['plan']=run.plan['plan_worksheet']
    for row in run.plan.get('methods',[]):
        if row.get('reading_worksheet'):sheets[row['method']+'.reading_review']=row['reading_worksheet']
    for name,sheet in sheets.items():
        if any(v not in ('PENDING','ACCEPTED') for v in sheet['decisions'].values()):
            raise ValueError('DAG_SOURCE_MUST_NOT_OVERRIDE_REJECTION')
        records[name]={**capabilities.identity(sheet), 'authority':run.authority,
            'reviewer':'Independent LLM DAG reading audit','evidence':evidence,
            'decisions':{k:'ACCEPTED' for k in sheet['decisions']}}
    return dict(binding_sha256=binding(run),scientific_approval=False,
                findings=deepcopy(confirmed),records=records)

def reread(engine,run,answer):
    """Existing revision protocol binds original candidate and located feedback."""
    if run.automatic_rechecks>=1:return False
    args={k:run.submission[k] for k in ('query_review','candidate','request_sha256','reading_revision') if k in run.submission}
    prepared=fact_reading_revision.prepare_recheck(run.intake,run.query_id,**args)
    sheet=prepared.get('feedback_worksheet')
    if not sheet:return False
    refs=worksheet(run)['source_catalog']
    issues=[]
    for item in answer['issues']:
        if item['kind']!='READING_ERROR':continue
        ids=list(dict.fromkeys(refs[s]['source_id'] for s in item['source_ids']))
        if not ids:return False
        # Native reading decisions cover several fields; root is the protocol's
        # existing whole-object pointer. Feedback supplies no replacement value.
        issues.append(dict(field_path='',kind='OMITTED_OR_MISREAD',source_ids=ids,
                           reason=item['field']+'：'+item['reason']))
    if not issues:return False
    # The protocol requires unique (path,kind); combine located issues without
    # removing any source or supplying a corrected candidate.
    issue=dict(field_path='',kind='OMITTED_OR_MISREAD',
        source_ids=list(dict.fromkeys(s for x in issues for s in x['source_ids'])),
        reason='；'.join(x['reason'] for x in issues))
    if len(issue['reason'])>1200:return False
    feedback=dict(version=sheet['version'],binding_sha256=sheet['binding_sha256'],authority=run.authority,
        reviewer='Background DAG reading recovery',evidence='后台复核定位到原材料与候选之间的具体差异；请求按原材料重读，不指定替换答案或授予科学批准。',
        issues=[issue])
    entry=fact_reading_revision.prepare_recheck(run.intake,run.query_id,**args,feedback=feedback)
    if entry.get('state')!='READY_TO_READ':return False
    run.automatic_rechecks+=1;engine._recheck(run,entry,feedback)
    return True
