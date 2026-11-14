"""Auditable synthetic D1-D8/E1-E5 material and offline reviewed examples.

These are explicit test specifications, not saved LLM answers. The fixture
constructs the design law by drawing groups; replay independently sums laws.
Run: python -m examples.finite_mean_box_reference
"""
from copy import deepcopy
from fractions import Fraction as F
from itertools import combinations, product
from math import comb
from .network_contrast_dispatch_reference import material, a0_reference, fact_reference, approval_records
from .business_dispatch_reference import approve
from cfm_id import business_intake as intake, business_dispatch as dispatch


def specification(design, exposure, edges=None):
    nodes=['甲店','乙店','丙店','丁店']
    groups=[nodes[:2],nodes[2:]]
    edges=list(combinations(nodes,2)) if edges is None else list(edges)
    payloads={
        'D1':dict(kind='INDEPENDENT_BERNOULLI',probabilities=dict(zip(nodes,['0','1/3','1/2','2/3']))),
        'D2':dict(kind='UNIFORM_FIXED_QUOTA',fixed_count=2),
        'D3':dict(kind='TWO_GROUP_FIXED_QUOTA',groups=groups,treated_quotas=[1,1]),
        'D4':dict(kind='CLUSTER_BERNOULLI',clusters=groups,cluster_probabilities=['1/3','2/3']),
        'D5':dict(kind='MULTI_GROUP_FIXED_QUOTA',groups=[nodes[:2],[nodes[2]],[nodes[3]]],treated_quotas=[1,0,1]),
        'D6':dict(kind='TWO_STAGE_QUOTA_MIXTURE',groups=groups,quota_profiles=[[0,1],[1,2]],profile_probabilities=['1/3','2/3']),
        'D7':dict(kind='UNEQUAL_PROBABILITY_FIXED_QUOTA',fixed_count=2,unit_weights=dict(zip(nodes,['1','2','3','4']))),
        'D8':dict(kind='RERANDOMIZED_BALANCED',fixed_count=2,unit_weights=dict.fromkeys(nodes,'1'),balance_tolerance='0',balance_covariates={'规模':dict(zip(nodes,['0','0','1','1']))})}
    texts={
        'D1':'原试点甲店不启用；其余店各自独立抽签，乙店启用概率1/3、丙店1/2、丁店2/3。',
        'D2':'原试点每轮从四店均匀抽取恰好两家启用，其余不启用。',
        'D3':'原试点甲乙一组、丙丁一组，每组独立地均匀抽一家启用。',
        'D4':'原试点甲乙一起启用或不用，启用概率1/3；丙丁一起启用或不用，启用概率2/3。两组独立抽签。',
        'D5':'原试点分为甲乙、丙、丁三个组。各组独立均匀抽取，启用名额依次为1、0、1。',
        'D6':'原试点甲乙一组、丙丁一组。先抽取两组名额：以1/3概率抽到(0,1)，以2/3概率抽到(1,2)。给定名额后，两组分别独立、均匀抽取相应家数启用。',
        'D7':'每次启用两家店，甲乙丙丁的抽签权重分别为1、2、3、4；每对名单的概率按两店权重乘积占全部六对乘积之和计算。',
        'D8':'先从四店均匀抽取两家。甲乙的处理前规模记0，丙丁记1；只有启用组与未启用组的规模均值相等时接受，否则重新抽签。'}
    exposure_specs={
        'E1':('STRICT_MAJORITY_TIES_LOW','合作店中严格过半启用记1，其余记0。'),
        'E2':('THREE_LEVEL_TREATED_NEIGHBOR_FRACTION','合作店启用比例小于1/3记0，至少1/3但小于2/3记1，至少2/3记2。'),
        'E3':('PRETREATMENT_CORE_COLLABORATOR_MAJORITY','甲只以乙为核心合作店、乙只以甲为核心合作店、丙只以丁为核心合作店、丁只以丙为核心合作店。这些名单在试点前确定；核心合作店严格过半启用记1，否则记0。'),
        'E4':('EXACT_TREATED_NEIGHBOR_COUNT','同伴状态直接记录启用的合作邻居家数。'),
        'E5':('ANY_TREATED_NEIGHBOR','至少一家合作邻居启用记1，没有则记0。')}
    assignment=payloads[design]
    ex=dict(kind=exposure_specs[exposure][0])
    if exposure=='E3':ex['core_collaborators']=dict(zip(nodes,[[nodes[1]],[nodes[0]],[nodes[3]],[nodes[2]]]))
    # Generate elementary experimental draws, not exposure probabilities.
    law={}
    def add(active,p):
        z=tuple(int(n in active) for n in nodes)
        law[z]=law.get(z,F(0))+p
    def draws(parts,quotas,weight):
        options=[list(combinations(g,q)) for g,q in zip(parts,quotas)]
        den=1
        for opts in options:den*=len(opts)
        for selected in product(*options):add({n for group in selected for n in group},weight/den)
    if design=='D1':
        for z in product((0,1),repeat=4):
            p=F(1)
            for n,a in zip(nodes,z):
                q=F(assignment['probabilities'][n]);p*=q if a else 1-q
            if p:add({n for n,a in zip(nodes,z) if a},p)
    elif design=='D2':draws([nodes],[2],F(1))
    elif design in ('D3','D5'):draws(assignment['groups'],assignment['treated_quotas'],F(1))
    elif design=='D4':
        for states in product((0,1),repeat=2):
            p=F(1);active=set()
            for g,q,a in zip(groups,map(F,assignment['cluster_probabilities']),states):
                p*=q if a else 1-q
                if a:active.update(g)
            if p:add(active,p)
    elif design=='D6':
        for quotas,p in zip(assignment['quota_profiles'],assignment['profile_probabilities']):draws(groups,quotas,F(p))
    elif design=='D7':
        totals={}
        for pair in combinations(nodes,2):totals[pair]=F(assignment['unit_weights'][pair[0]])*F(assignment['unit_weights'][pair[1]])
        for pair,p in totals.items():add(set(pair),p/sum(totals.values()))
    elif design=='D8':
        # With two low and two high values, exactly one of each must be selected.
        draws(groups,[1,1],F(1))
    assert sum(law.values())==1
    def cell(node,z):
        peers=ex.get('core_collaborators',{}).get(node,[b if a==node else a for a,b in edges if node in (a,b)])
        k=sum(z[nodes.index(n)] for n in peers);d=len(peers)
        if exposure in ('E1','E3'):e=int(2*k>d)
        elif exposure=='E2':e=sum(F(k,d)>=t for t in (F(1,3),F(2,3)))
        elif exposure=='E4':e=k
        else:e=int(k>0)
        return node,z[nodes.index(node)],e
    support={}
    for z,p in law.items():
        for n in nodes:
            c=cell(n,z);support[c]=support.get(c,F(0))+p
    return dict(nodes=nodes,edges=edges,assignment=assignment,exposure=ex,assignment_text=texts[design],
                exposure_text=exposure_specs[exposure][1],law=law,support=support,cell=cell)


def setup(design='D3',exposure='E2',*,single=False,point=False,reverse=False,
          missing=False,extra=False,profile=None,edges=None,symbolic=False):
    spec=specification(design,exposure,edges);nodes=spec['nodes']
    case,data=material('partial',bounds=('1/4','3/4'))
    data['edges']=[list(e) for e in spec['edges']]
    data['first']=list(next(iter(spec['law']))) if point else [1]*4
    data['second']=list(next(reversed(spec['law']))) if point else [0]*4
    if reverse:data['first'],data['second']=data['second'],data['first']
    data['cells']=[dict(node=n,own=a,exposure=e,value=str(F(1,4)+F(nodes.index(n)+a+e,32)))
                   for n,a,e in sorted(spec['support'])]
    # Different values expose reversed comparisons and incorrect averaging.
    c=case.model_dump()
    for src in c['sources']:
        if src['source_id']=='network':
            src['text']='处理前固定的简单无向合作网，完整关系为'+('、'.join(a+'—'+b for a,b in spec['edges']) or '没有边')+'。没有其他边；未与任何对象相连的店为孤立点。'
        if src['source_id']=='assignment':src['text']=spec['assignment_text']
        if src['source_id']=='exposure':src['text']=spec['exposure_text']
        if src['source_id']=='information':
            src['text']='本合成研究提供且只提供以下精确总体均值（不是四店的一次观测）：\n'+'\n'.join(
                f"{v['node']}自身状态{v['own']}、同伴状态{v['exposure']}，准时开门的总体平均值为{v['value']}。" for v in data['cells'])
        if src['source_id']=='information' and symbolic:
            src['text']=('本研究只允许使用下面列明各格子的总体条件平均值作为符号信息，只求计算公式，尚不代入数值；有限样本不能替代这些总体信息。格子为：'+
                '、'.join(f"{v['node']}自身{v['own']}同伴{v['exposure']}" for v in data['cells']))
        if src['source_id']=='science' and design=='D6':
            src['text']+='另行采用：最后启用名单相同时，第一步抽到哪个名额方案不会再影响各店结果。'
        if src['source_id']=='complete_model':
            if missing:src['text']='这些均值是否列尽全部信息，负责人尚未确定。'
            elif extra:src['text']+='还需额外要求甲乙两店在全启用时均值相等。'
    def arrangement(z):return '、'.join(n for n,a in zip(nodes,z) if a)+'启用，其余店不启用' if any(z) else '全部不启用'
    first,second=map(arrangement,(data['first'],data['second']))
    c['business_question']=(f'四店同一考核周，若{first}，平均准时开门率是多少？' if single else
        f'四店同一考核周，从{second}改为{first}，平均准时开门率提高多少？')+'四家店等权，采用附件研究条件。'
    case=type(case).model_validate(c);a0=a0_reference(case)
    if single:
        a0['queries'][0]['kind']='FIXED_POLICY_VALUE';a0['queries'][0]['semantics'].pop('comparator')
    s=intake.start(case,network_fact_contract=profile)
    s=intake.receive_candidate(s,a0,request_sha256=s.request_sha256)
    review=approve(dispatch.prepare_reader(s,'q1')['query_worksheet'])
    entry=dispatch.prepare_reader(s,'q1',query_review=review)
    raw=deepcopy(fact_reference(entry,data))
    raw['assignment']={'probabilities':None,'fixed_count':None,**spec['assignment'],
                       'source_ids':raw['assignment']['source_ids']}
    raw['exposure']=dict(spec['exposure'],source_ids=raw['exposure']['source_ids'])
    if design=='D6':raw['first_stage_exclusion']=dict(status='ADOPTED',source_ids=raw['assumptions']['consistency']['source_ids'] if 'assumptions' in raw else raw['scientific_statements']['consistency']['source_ids'])
    if symbolic:
        for item in raw['information']:
            item['availability']='SYMBOLIC_POPULATION_OPERATOR'
            for cell in item['signature_cells']:cell['value']=None
    if single:
        raw['version']='network-policy-reading-1';raw['target']=dict(kind='FIXED_POLICY_MEAN',**raw['target']['first'])
    if missing:raw['bounded_model']['listed_means_are_complete_information']['value']=None
    if extra:raw['bounded_model']['no_additional_coupling_constraints']['value']=False
    options=dict(query_review=review,candidate=raw,request_sha256=entry['request_sha256'])
    return s,options,spec,data


def main():
    import json
    results=[]
    for d,e in product(range(1,9),range(1,6)):
        for single in (True,False):
            s,o,_,_=setup(f'D{d}',f'E{e}',single=single)
            p=dispatch.inspect_methods(s,'q1',**o)
            r=dispatch.execute(s,'q1',**o,**approval_records(p)) if p['state']=='REVIEW_REQUIRED' else p
            results.append(dict(design=d,exposure=e,objective='mean' if single else 'contrast',
                state=r['state'],interval=(r.get('mathematical_claim') or {}).get('interval'),
                replay=r.get('independent_replay'),reason=r.get('reason_code')))
    print(json.dumps(results,ensure_ascii=False,indent=2))

if __name__=='__main__':main()
