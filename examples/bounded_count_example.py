"""D2/E4 synthetic, separately reviewed research examples; no LLM or API call.

The fixture states its mathematics independently of the reader. Its approvals
are hypothetical test assertions, never a way to approve real user materials.
Run: python -m examples.bounded_count_example
"""
from fractions import Fraction as F
from itertools import product
from types import SimpleNamespace

from examples import intent_routes_fixture as f
from examples.bounded_policy_intake_fixture import existing_reviews
from examples.bounded_contrast_fixture import reviews as endpoint_reviews
from cfm_id import bounded_policy, bounded_contrast
from cfm_id.bounded_count_contract import (
    CountMeanInformation, ReviewedCountContrast, POLICY_VERSION,
)
from cfm_id.question_bound_assignment import question_catalog
from cfm_id.source_locations import build_catalog


def make_case(nodes, edges, quota, first, second=None, population=None, *,
              continuous=False, mean_bounds=('0', '1')):
    """Generate exact count cells directly, without relabeling an E1 fixture."""
    nodes, edges, first = list(nodes), list(edges), list(first)
    population = nodes if population is None else list(population)
    policies = {'first': first}
    if second is not None:
        policies['second'] = list(second)
    if (not population or len(set(population)) != len(population)
            or not set(population) <= set(nodes)
            or any(len(z) != len(nodes) or any(type(a) is not int or a not in (0, 1) for a in z)
                   for z in policies.values())):
        raise ValueError('COMPLETE_POLICY_AND_EVALUATION_ROSTER_REQUIRED')
    treatment = '使用辅助系统'
    outcome = '当天任务得分' if continuous else '当天任务是否按时完成'
    claims = dict(
        analysis_unit='我们有'+str(len(nodes))+'个服务小组，编号是'+'、'.join(nodes)+'。',
        treatment=treatment, outcome=outcome,
        network='处理前确定的无向合作关系是'+('、'.join(a+'—'+b for a,b in edges) or '没有合作边')+'，本期保持不变。',
        assignment=f'原试点从全部小组中均匀随机抽取恰好{quota}组使用辅助系统，所有同人数名单的机会相同，其余不用。',
        exposure='同伴状态记录合作邻居中使用辅助系统的具体人数；没有合作邻居时记为0人。',
        information='业务结果是'+outcome+'。本例是合成研究，另行明确提供精确总体均值及科学条件；没有把有限样本均值当作总体均值。')
    def arrangement(z):
        names = [n for n,a in zip(nodes,z) if a]
        return ('所有小组都不用' if not names else '所有小组都用' if len(names)==len(nodes)
                else '、'.join(names)+'使用，其余不用')+'辅助系统'
    goal = '问题1：'
    if second is None:
        goal += '如果'+arrangement(first)+'，'
    else:
        goal += '方案甲是'+arrangement(first)+'，方案乙是'+arrangement(policies['second'])+'。甲减乙，'
    goal += '只评价'+'、'.join(population)+'，每组权重相同，'+outcome+'的平均值'+('是多少？' if second is None else '相差多少？')
    bundle = dict(case_id='COUNT_MEAN_RESEARCH', node_order=nodes,
        documents={'study.txt':'\n'.join(claims[k] for k in
            ('analysis_unit','network','assignment','exposure','information')), 'goal.txt':goal},
        question_slots={'q1':goal})
    source_ids = [sid for sid,row in build_catalog(bundle['documents']).items()
                  if row['text'].strip() == claims['assignment']]
    raw = dict(reading=dict(
        intents={'q1':dict(kind='水平' if second is None else '比较',
            question_id=question_catalog(bundle)['q1']['question_id'])},
        questions={'q1':dict(first=dict(zip(nodes,first)),
            second=None if second is None else dict(zip(nodes,policies['second'])),
            population=population, aggregation='等权平均')}),
        reported_assignment=dict(mechanism='FIXED_QUOTA_RANDOM', fixed_count=quota,
            maximum_count=None, uniform_subset_declared=True, reported_conflict=False, source_ids=source_ids))
    study = f.declare_network_study(network_id='COUNT_MEAN_NETWORK', node_order=tuple(nodes),
        undirected_edges=tuple(edges), treatment_variable='auxiliary',
        outcome_variable='score' if continuous else 'on_time',
        outcome_kind='continuous' if continuous else 'binary', context_reference='Same_context_W',
        observation_regime='experimental', assignment_design={'kind':'complete_randomization_binary_v1','m':quota},
        protocol_provenance='Explicit synthetic uniform fixed quota',
        network_provenance='Explicit synthetic fixed simple graph', graph_timing_claim='DECLARED_PRETREATMENT_FIXED')
    signature = f.declare_policy_signature(study, grouping='exact_treated_neighbor_count')
    suff = f.admit_mean_signature_sufficiency(study, signature, covered_nodes=tuple(nodes),
        assumption=f.Assumption(name='mean_signature_sufficiency', source='demo_specification',
            confirmed=True, status='ADMITTED', evidence=[
                'Separate synthetic scientific assumption: for every binary arrangement and every node, '
                'its conditional potential mean depends only on its own treatment and exact treated-neighbor count.']))
    friends = {n:{b if a==n else a for a,b in edges if n in (a,b)} for n in nodes}
    cells = set()
    for z in product((0,1),repeat=len(nodes)):
        if sum(z) != quota:
            continue
        v = dict(zip(nodes,z))
        cells.update((n,v[n],sum(v[j] for j in friends[n])) for n in nodes)
    source = f.declare_signature_population_source(study, signature, source_id='COUNT_EXACT_POPULATION',
        operator='NODE_SIGNATURE_MEANS', outcome_nodes=tuple(nodes), admission='ADMITTED',
        availability='EXACT_POPULATION_VALUE', provenance='All and only the exact synthetic cell means listed here',
        signature_cells=tuple(sorted(cells)))
    weights = tuple(str(F(1,len(population))) if n in population else '0' for n in nodes)
    inquiries, information = {}, {}
    for side,z in policies.items():
        target = f.fixed_policy_target_from_context(study, tuple(z), unit_weights=weights, authority='TRUSTED_FIXTURE')
        inquiry = f.FixedPolicyInquiryV21(study, target, f._assumptions(),
            r2_signature=signature, r2_sufficiency=suff, r2_sources=(source,))
        info = CountMeanInformation(version=POLICY_VERSION, inquiry_sha256=f.sha(inquiry),
            source_id=source.source_id, source_sha256=f.sha(source),
            information_scope='EXACT_LISTED_SIGNATURE_MEANS_ONLY',
            model_scope='SIGNATURE_MEANS_AND_NODE_BOUNDS_ONLY', availability='EXACT_POPULATION_VALUE',
            values=[dict(node=n,own=a,exposure=e,value='1/2') for n,a,e in sorted(cells)],
            bounds=[dict(node=n,lower=str(mean_bounds[0]),upper=str(mean_bounds[1])) for n in nodes],
            bounds_kind='CONDITIONAL_MEAN', bounds_scope='ALL_BINARY_ASSIGNMENTS_CONDITIONAL_ON_STUDY_CONTEXT',
            outcome_definition=outcome, outcome_unit='分' if continuous else '比例', outcome_period='当天',
            a4_provenance=source.provenance,
            bounds_provenance='Separate explicit mean bounds at every node and every binary arrangement; no other constraints')
        inquiries[side],information[side] = inquiry,info
    coordinates = dict(node_order=nodes, first=first, unit_weights=list(weights))
    if second is not None:
        coordinates.update(second=policies['second'],operation='first_minus_second')
    return dict(bundle=bundle,raw=raw,claims=claims,inquiries=inquiries,information=information,coordinates=coordinates)


def review_case(p):
    """Explicit OFFLINE review assertions; changes in science need fresh reviews."""
    if 'second' in p['inquiries']:
        r = endpoint_reviews(p)
        r['joint_review'] = ReviewedCountContrast(**bounded_contrast.worksheet(
            p['bundle'],p['raw'],query_id='q1',packet=r['packet'],context=r['context'],information=p['information']),
            reviewer='Independent synthetic count-model reviewer',
            evidence='Both ordered policies, common exact means, all-arrangement count sufficiency and mean bounds reviewed',
            reviewed_direction_and_common_population=True,reviewed_complete_common_a4_model=True,
            reviewed_scientific_bounds_and_no_extra_constraints=True,synthetic_fixture=True)
        return r
    expected = dict(classification='FIXED_POLICY',node_order=p['coordinates']['node_order'],
        assignment=p['coordinates']['first'],unit_weights=p['coordinates']['unit_weights'])
    r = existing_reviews(p['bundle'],p['raw'],SimpleNamespace(
        inquiry=p['inquiries']['first'],information=p['information']['first']),p['claims'],expected)
    return dict(r,synthetic_protocol_selected=True)


def submit_case(p, reviews):
    if 'second' in p['inquiries']:
        return bounded_contrast.submit(p['bundle'],p['raw'],query_id='q1',information=p['information'],**reviews)
    return bounded_policy.submit(p['bundle'],p['raw'],query_id='q1',information=p['information']['first'],**reviews)


def main():
    import json
    nodes=list('ABCD'); edges=[('A','B'),('B','C'),('C','D')]
    examples = {
        'supported_policy_point':make_case(nodes,edges,2,[1,1,0,0]),
        'full_rollout_partial':make_case(nodes,edges,2,[1]*4),
        'ordered_difference_partial':make_case(nodes,edges,2,[1]*4,[0]*4),
    }
    rows={}
    for name,p in examples.items():
        result=submit_case(p,review_case(p)); cert=result.get('bounded_result',{})
        rows[name]=dict(state=result['state'],reason=result.get('reason_code'),
            interval=[cert.get('lower'),cert.get('upper')],replayed=result['bounded_certificate_replayed'])
    print(json.dumps(rows,ensure_ascii=False,indent=2))


if __name__=='__main__':
    main()
