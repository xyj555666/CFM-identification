"""D2/E4 extension: reviewed entry, independent finite oracle and old boundaries."""
from copy import deepcopy
from dataclasses import replace
from fractions import Fraction as F
from itertools import product
import subprocess
import sys
import unittest
from unittest.mock import patch

from cfm_id_bridge.scientific_binding import sha
from cfm_id.bounded_count_contract import CountMeanInformation, validate_model
from cfm_id.bounded_count_solver import solve_policy, solve_contrast
from cfm_id.bounded_count_verify import replay_policy, replay_contrast
from cfm_id.bounded_policy_contract import BoundedPolicyUnavailable, BoundedMeanInformation
from cfm_id import bounded_contrast
from examples.bounded_count_example import make_case, review_case, submit_case
from pfn_pipeline._internal.identification.randomized_arm_family import SupportEngine, ExposureSpec


def fixture(first=None, second=None, population=None, **kw):
    return make_case(list('ABCD'), [('A','B'),('B','C'),('C','D')], 2,
        [1]*4 if first is None else first, second, population, **kw)


def vertex_oracle(p):
    """Independent endpoint evaluation on shared mean-box vertices, small graphs only."""
    q=p['inquiries']['first']; nodes=list(q.study.node_order)
    info=p['information']['first']
    known={(r.node,r.own,r.exposure):F(r.value) for r in info.values}
    bounds={r.node:(F(r.lower),F(r.upper)) for r in info.bounds}
    def cell(i,z):
        others=[nodes.index(b if a==nodes[i] else a) for a,b in q.study.undirected_edges if nodes[i] in (a,b)]
        return nodes[i],z[i],sum(z[j] for j in others)
    required={cell(i,t.target.policy_assignment) for t in p['inquiries'].values()
              for i,w in enumerate(t.target.unit_weights) if F(w)}
    free=sorted(required-set(known)); values=[]
    for endpoints in product(*(bounds[c[0]] for c in free)):
        world=dict(known);world.update(zip(free,endpoints)); arms={}
        for s,t in p['inquiries'].items():
            arms[s]=sum((F(w)*world[cell(i,t.target.policy_assignment)]
                for i,w in enumerate(t.target.unit_weights) if F(w)),F(0))
        values.append(arms['first']-arms.get('second',F(0)))
    return tuple(map(str,(min(values),max(values))))


def rehash(c):
    c.pop('certificate_sha256',None);c['certificate_sha256']=sha(c);return c


def remove_mean(p, cell):
    """Remove a declared A4 coordinate, updating its actual source bindings too."""
    for s,q in list(p['inquiries'].items()):
        source=replace(q.r2_sources[0],signature_cells=tuple(c for c in q.r2_sources[0].signature_cells if c!=cell))
        q=replace(q,r2_sources=(source,));p['inquiries'][s]=q
        info=p['information'][s]
        p['information'][s]=info.model_copy(update=dict(inquiry_sha256=sha(q),source_sha256=sha(source),
            values=[v for v in info.values if (v.node,v.own,v.exposure)!=cell]))


class CountBoundsTests(unittest.TestCase):
    def test_registry_reports_connected_common_reader(self):
        from cfm_id.capability_registry import inventory
        rows={r['entry_id']:r for r in inventory()['separate_native_entries']}
        for route in ('BOUNDED_POLICY_MEAN_D2_E4','BOUNDED_POLICY_CONTRAST_D2_E4'):
            self.assertEqual(rows[route]['native_only_routes'],[])
            self.assertEqual(rows[route]['common_business_routes'],[route])

    def test_reviewed_policy_and_contrast_reach_result_and_replay(self):
        for p,status,expected in (
            (fixture(first=[1,1,0,0]),'POINT',('1/2','1/2')),
            (fixture(),'PARTIAL',('1/4','3/4')),
            (fixture(second=[0]*4),'PARTIAL',('-1/2','1/2')),
            (fixture(first=[1,1,0,0],second=[0,0,1,1]),'POINT',('0','0')),
        ):
            with self.subTest(status=status,contrast='second' in p['inquiries']):
                r=submit_case(p,review_case(p));self.assertEqual(r['state'],status,r)
                c=r['bounded_result'];self.assertEqual((c['lower'],c['upper']),expected)
                self.assertEqual(expected,vertex_oracle(p));self.assertTrue(r['bounded_certificate_replayed'])
                self.assertTrue(all(v['route'].endswith('D2_E4') for v in r['query_views']))

    def test_independent_oracle_on_graphs_counts_and_continuous_outcomes(self):
        # Degree-three E4 state 2 must remain distinct from 1 and 3.
        graphs=[[],[('A','B')],[('A',n) for n in 'BCD'],
                [(a,b) for i,a in enumerate('ABCD') for b in 'ABCD'[i+1:]]]
        for edges,quota,continuous in product(graphs,(1,2,3),(False,True)):
            p=make_case(list('ABCD'),edges,quota,[1]*4,[0]*4,['A','C'],continuous=continuous,
                mean_bounds=('-2','3') if continuous else ('0','1'))
            with self.subTest(edges=edges,quota=quota,continuous=continuous):
                c=solve_contrast(p['inquiries'],p['information'])
                self.assertEqual((c['lower'],c['upper']),vertex_oracle(p))
                self.assertTrue(replay_contrast(c,inquiries=p['inquiries'],information=p['information']))

    def test_single_mean_is_not_contrast_against_all_untreated(self):
        p=fixture(first=[0]*4)
        c=solve_policy(p['inquiries']['first'],p['information']['first'])
        self.assertEqual((c['lower'],c['upper']),('1/4','3/4'))

    def test_common_unknown_cancels_and_direction_reverses(self):
        p=fixture(second=[1]*4)
        c=solve_contrast(p['inquiries'],p['information'])
        self.assertEqual((c['lower'],c['upper']),('0','0'))
        self.assertEqual(c['bound_terms'],[])
        p=fixture(second=[1,1,0,0]);qs=p['inquiries'];infos=p['information']
        # Unequal known means make the interval asymmetric: direction matters
        # numerically, not merely in the target hash.
        for s,info in list(infos.items()):
            infos[s]=info.model_copy(update={'values':[v.model_copy(update={
                'value':str(F(1+2*v.own+v.exposure,6))}) for v in info.values]})
        c=solve_contrast(qs,infos)
        self.assertEqual((c['lower'],c['upper']),vertex_oracle(p))
        self.assertNotEqual(F(c['lower']),-F(c['upper']))
        reverse_q=dict(first=qs['second'],second=qs['first'])
        reverse_i=dict(first=infos['second'],second=infos['first'])
        reverse=solve_contrast(reverse_q,reverse_i)
        self.assertEqual((F(reverse['lower']),F(reverse['upper'])),(-F(c['upper']),-F(c['lower'])))
        self.assertFalse(replay_contrast(c,inquiries=reverse_q,information=reverse_i))

    def test_unequal_node_bounds_and_nonuniform_weights(self):
        from pfn_pipeline.network_inquiry_shadow import fixed_policy_target_from_context
        p=fixture(second=[0]*4,continuous=True)
        for s,q in list(p['inquiries'].items()):
            target=fixed_policy_target_from_context(q.study,q.target.policy_assignment,
                unit_weights=('1/2','1/3','1/6','0'),authority='TRUSTED_FIXTURE')
            q=replace(q,target=target);p['inquiries'][s]=q
            info=p['information'][s]
            p['information'][s]=info.model_copy(update={'inquiry_sha256':sha(q),
                'bounds':[r.model_copy(update={'lower':str(-i-1),'upper':str(i+2)})
                          for i,r in enumerate(info.bounds)],
                'values':[v.model_copy(update={'value':str(F(1+v.own+v.exposure,5))}) for v in info.values]})
        c=solve_contrast(p['inquiries'],p['information'])
        self.assertEqual((c['lower'],c['upper']),vertex_oracle(p))
        self.assertTrue(replay_contrast(c,inquiries=p['inquiries'],information=p['information']))

    def test_missing_supported_a4_blocked_but_canceled_coordinate_not_required(self):
        p=fixture(first=[1,1,0,0],second=[0,0,1,1])
        remove_mean(p,('A',1,1))
        with self.assertRaisesRegex(BoundedPolicyUnavailable,'SUPPORTED_NONZERO_CONTRAST_A4_MEAN_MISSING'):
            solve_contrast(p['inquiries'],p['information'])
        r=submit_case(p,review_case(p));self.assertEqual(r['state'],'NEEDS_INPUT')
        self.assertFalse(r['bounded_backend_called'])
        p=fixture(first=[1,1,0,0],second=[1,1,0,0]);remove_mean(p,('A',1,1))
        c=solve_contrast(p['inquiries'],p['information'])
        self.assertEqual(c['status'],'POINT');self.assertEqual(c['lower'],'0')
        self.assertTrue(replay_contrast(c,inquiries=p['inquiries'],information=p['information']))

    def test_complete_a4_list_and_binary_bound_semantics(self):
        p=fixture();q=p['inquiries']['first'];info=p['information']['first']
        with self.assertRaisesRegex(BoundedPolicyUnavailable,'COMPLETE_EXACT_A4_VALUE_LIST_REQUIRED'):
            solve_policy(q,info.model_copy(update={'values':info.values[:-1]}))
        narrow=fixture(mean_bounds=('1/4','3/4'))
        i=narrow['information']['first'];q=narrow['inquiries']['first']
        self.assertEqual(solve_policy(q,i)['status'],'PARTIAL')
        with self.assertRaisesRegex(BoundedPolicyUnavailable,'EMPTY_BINARY_OUTCOME_SUPPORT'):
            solve_policy(q,i.model_copy(update={'bounds_kind':'ALMOST_SURE_OUTCOME'}))

    def test_zero_support_a4_and_impossible_neighbor_count_are_rejected(self):
        for extra,reason in ((('B',1,2),'A4_CONDITIONAL_EVENT_HAS_ZERO_PROBABILITY'),
                             (('A',1,2),'A4_SIGNATURE_NOT_REALIZABLE')):
            p=fixture();q=p['inquiries']['first'];i=p['information']['first']
            source=replace(q.r2_sources[0],signature_cells=q.r2_sources[0].signature_cells+(extra,))
            q=replace(q,r2_sources=(source,));data=i.model_dump()
            data.update(inquiry_sha256=sha(q),source_sha256=sha(source))
            data['values'].append(dict(node=extra[0],own=extra[1],exposure=extra[2],value='1/2'))
            with self.subTest(extra=extra),self.assertRaisesRegex(BoundedPolicyUnavailable,reason):
                solve_policy(q,CountMeanInformation.model_validate(data))

    def test_zero_and_full_quota_boundaries(self):
        for quota in (0,4):
            p=make_case(list('ABCD'),[('A','B'),('B','C'),('C','D')],quota,[1]*4,[0]*4)
            c=solve_contrast(p['inquiries'],p['information'])
            self.assertEqual((c['lower'],c['upper']),vertex_oracle(p))
            self.assertTrue(replay_contrast(c,inquiries=p['inquiries'],information=p['information']))

    def test_rename_and_reorder_preserves_exact_set_but_not_certificate_binding(self):
        p=fixture(second=[0]*4);c=solve_contrast(p['inquiries'],p['information'])
        q=make_case(['丁','乙','甲','丙'],[('甲','乙'),('乙','丙'),('丙','丁')],2,[1]*4,[0]*4)
        other=solve_contrast(q['inquiries'],q['information'])
        self.assertEqual((other['lower'],other['upper']),(c['lower'],c['upper']))
        self.assertTrue(replay_contrast(other,inquiries=q['inquiries'],information=q['information']))
        self.assertFalse(replay_contrast(c,inquiries=q['inquiries'],information=q['information']))

    def test_other_design_exposure_and_extra_constraints_not_silently_accepted(self):
        from examples.bounded_policy_intake_fixture import make_case as old_case, declaration_review
        from cfm_id.bounded_policy_intake import compile_reviewed
        b,r,d,claims,coords=old_case(list('ABCD'),[('A','B')],2,[1]*4,list('ABCD'))
        compiled=compile_reviewed(b,r,query_id='q1',declaration=d,
            review=declaration_review(b,r,d,coords),synthetic_protocol_selected=True)
        old=compiled.information.model_dump();old['version']='bounded-count-policy-1'
        with self.assertRaisesRegex(BoundedPolicyUnavailable,'BOUNDED_D2_E4_FINITE_DOMAIN_REQUIRED'):
            solve_policy(compiled.inquiry,CountMeanInformation.model_validate(old))
        p=fixture();q=p['inquiries']['first'];info=p['information']['first']
        self.assertTrue(any(v.exposure==2 for v in info.values))
        old=info.model_dump();old['version']='bounded-policy-mean-1'
        with self.assertRaises(ValueError):BoundedMeanInformation.model_validate(old)
        q=replace(q,assumptions=q.assumptions+(q.assumptions[0],))
        with self.assertRaisesRegex(BoundedPolicyUnavailable,'ADDITIONAL_A5_REQUIRES_JOINT_CONSTRAINT_SOLVER'):
            solve_policy(q,info.model_copy(update={'inquiry_sha256':sha(q)}))

    def test_no_finite_sample_upgrade_or_full_law_downgrade(self):
        p=fixture();q=p['inquiries']['first'];info=p['information']['first']
        for field,value in (('availability','FINITE_SAMPLE_ONLY'),('model_scope','FULL_JOINT_LAW')):
            with self.subTest(field=field),self.assertRaises(ValueError):
                solve_policy(q,info.model_copy(update={field:value}))
        # Mutating even a non-target A4 value beyond the admitted bounds is rejected.
        values=list(info.values);values[-1]=values[-1].model_copy(update={'value':'2'})
        with self.assertRaisesRegex(BoundedPolicyUnavailable,'A4_MEAN_OUTSIDE_SCIENTIFIC_BOUNDS'):
            solve_policy(q,info.model_copy(update={'values':values}))

    def test_shared_population_and_numeric_model_required(self):
        p=fixture(second=[0]*4)
        different=fixture(first=[0]*4,population=['A'])
        p['inquiries']['second']=different['inquiries']['first']
        p['information']['second']=different['information']['first']
        with self.assertRaisesRegex(BoundedPolicyUnavailable,'COMMON_CONTRAST_POPULATION_AND_WEIGHTS_REQUIRED'):
            solve_contrast(p['inquiries'],p['information'])
        p=fixture(second=[0]*4);info=p['information']['second'];values=list(info.values)
        values[0]=values[0].model_copy(update={'value':'1/3'})
        p['information']['second']=info.model_copy(update={'values':values})
        with self.assertRaisesRegex(BoundedPolicyUnavailable,'COMMON_COMPLETE_NUMERIC_INFORMATION_REQUIRED'):
            solve_contrast(p['inquiries'],p['information'])

    def test_review_absence_rejection_and_changed_input_never_run_solver(self):
        for contrast in (False,True):
            p=fixture(second=[0]*4 if contrast else None);r=review_case(p)
            review_key='joint_review' if contrast else 'bounded_review'
            for key in (review_key,'assignment_review','context'):
                with self.subTest(contrast=contrast,missing=key):
                    rr=dict(r);rr[key]=None;out=submit_case(p,rr)
                    self.assertIn(out['state'],('REVIEW_REQUIRED','CHECK_BLOCKED'))
                    self.assertFalse(out['bounded_backend_called'])
            rr=dict(r);rr[review_key]=r[review_key].model_copy(update={'information_sha256':'0'*64})
            out=submit_case(p,rr);self.assertEqual(out['state'],'CHECK_BLOCKED')
            self.assertFalse(out['bounded_backend_called'])
            rr=dict(r);flag='reviewed_complete_common_a4_model' if contrast else 'reviewed_complete_a4_information'
            rr[review_key]=r[review_key].model_copy(update={flag:False})
            out=submit_case(p,rr);self.assertEqual(out['state'],'CHECK_BLOCKED')
            self.assertFalse(out['bounded_backend_called'])
            changed=deepcopy(p);changed['raw']['reading']['questions']['q1']['first']['A']=None
            out=submit_case(changed,r);self.assertEqual(out['state'],'NEEDS_INPUT')
            self.assertFalse(out['bounded_backend_called'])

    def test_missing_independent_scientific_review_still_blocks(self):
        p=fixture(second=[0]*4);r=review_case(p)
        b=r['context']['second'].core_port.bindings['q1']
        r['context']['second'].core_port.bindings['q1']=replace(b,
            admission=b.admission.model_copy(update={'approved_scientific_binding':None}))
        # Rebind the outer worksheet; this cannot restore the missing inner review.
        sheet=bounded_contrast.worksheet(p['bundle'],p['raw'],query_id='q1',packet=r['packet'],
            context=r['context'],information=p['information'])
        r['joint_review']=r['joint_review'].model_copy(update=sheet)
        out=submit_case(p,r);self.assertEqual(out['state'],'CHECK_BLOCKED')
        self.assertFalse(out['bounded_backend_called'])

    def test_mean_bounds_ladder_and_stale_approval(self):
        nodes=list('ABCD');edges=[(a,b) for i,a in enumerate(nodes) for b in nodes[i+1:]]
        previous=None
        for bounds,expected in ((('1/2','1/2'),('0','0')),(('1/4','3/4'),('-1/2','1/2')),(('0','1'),('-1','1'))):
            p=make_case(nodes,edges,2,[1]*4,[0]*4,mean_bounds=bounds)
            r=review_case(p);result=submit_case(p,r);c=result['bounded_result']
            self.assertEqual((c['lower'],c['upper']),expected)
            self.assertEqual(result['state'],'POINT' if expected==('0','0') else 'PARTIAL')
            self.assertTrue(result['bounded_certificate_replayed'])
            if previous is not None:
                result=submit_case(p,previous);self.assertEqual(result['state'],'CHECK_BLOCKED')
            previous=r

    def test_replay_does_not_call_producer_or_support_engine(self):
        p=fixture(second=[0]*4);c=solve_contrast(p['inquiries'],p['information'])
        with patch('cfm_id.bounded_count_solver._solve',side_effect=AssertionError('producer')), \
             patch.object(SupportEngine,'evaluate',side_effect=AssertionError('support')), \
             patch.object(ExposureSpec,'classify',side_effect=AssertionError('exposure')):
            self.assertTrue(replay_contrast(c,inquiries=p['inquiries'],information=p['information']))

    def test_rehashed_certificate_tampering_rejected(self):
        p=fixture(second=[0]*4);c=solve_contrast(p['inquiries'],p['information'])
        mutations=[lambda x:x.update(lower='-1',upper='1',width='2'),
            lambda x:x.update(mode='policy'),lambda x:x.update(version='bounded-policy-contrast-1'),
            lambda x:x.update(production_admission=True),lambda x:x.update(sharp=False),
            lambda x:x['cells'].pop(),lambda x:x['cells'][0].update(support='0'),
            lambda x:x['cells'][0].update(lower_world='-1'),
            lambda x:x['bound_terms'][0].update(coefficient='99'),
            lambda x:x.update(input_sha256='0'*64)]
        for i,mutate in enumerate(mutations):
            with self.subTest(tamper=i):
                forged=deepcopy(c);mutate(forged)
                self.assertFalse(replay_contrast(rehash(forged),inquiries=p['inquiries'],information=p['information']))
        single=fixture();cert=solve_policy(single['inquiries']['first'],single['information']['first'])
        cert['lower']='0'
        self.assertFalse(replay_policy(rehash(cert),inquiry=single['inquiries']['first'],information=single['information']['first']))

    def test_replay_checks_survive_python_optimization(self):
        code="""
from examples.bounded_count_example import make_case
from cfm_id.bounded_count_solver import solve_policy
from cfm_id.bounded_count_verify import replay_policy
from cfm_id_bridge.scientific_binding import sha
p=make_case(list('ABC'),[('A','B'),('B','C')],1,[1]*3)
q=p['inquiries']['first'];i=p['information']['first'];c=solve_policy(q,i)
if not replay_policy(c,inquiry=q,information=i):raise RuntimeError('valid rejected')
c['lower']='99';c.pop('certificate_sha256');c['certificate_sha256']=sha(c)
if replay_policy(c,inquiry=q,information=i):raise RuntimeError('forgery accepted')
"""
        r=subprocess.run([sys.executable,'-B','-O','-c',code],capture_output=True,text=True)
        self.assertEqual(r.returncode,0,r.stdout+r.stderr)


if __name__=='__main__':unittest.main()
