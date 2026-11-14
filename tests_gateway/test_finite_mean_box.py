"""Cross-product acceptance with an explicit oracle; no LLM success claims."""
from copy import deepcopy
from fractions import Fraction as F
from itertools import product
import pytest
from examples.finite_mean_box_reference import setup,approval_records
from cfm_id import business_dispatch as dispatch
from cfm_id import network_bounded_dispatch as bounded,network_contrast_dispatch as contrast
from cfm_id.bounded_policy_contract import BoundedPolicyUnavailable
from cfm_id_bridge.scientific_binding import sha


def prepare(**kw):
    s,o,spec,data=setup(**kw)
    p=dispatch.inspect_methods(s,'q1',**o)
    assert p['state']=='REVIEW_REQUIRED',p
    return s,o,spec,data,p


def oracle(spec,data,single):
    known={(v['node'],v['own'],v['exposure']):F(v['value']) for v in data['cells']}
    coeff={}
    for side,sign in [('first',1)]+([] if single else [('second',-1)]):
        for n in spec['nodes']:
            c=spec['cell'](n,data[side]);coeff[c]=coeff.get(c,F(0))+F(sign,4)
    low=high=F(0)
    for c,w in coeff.items():
        lo,hi=(known[c],known[c]) if c in known else (F(1,4),F(3,4))
        low+=min(w*lo,w*hi);high+=max(w*lo,w*hi)
    return [str(low),str(high)]


@pytest.mark.parametrize('design,exposure',list(product([f'D{i}' for i in range(1,9)],[f'E{i}' for i in range(1,6)])))
def test_all_forty_combinations_mean_contrast_point_and_bounds(design,exposure):
    for single,point in product((True,False),(True,False)):
        s,o,spec,data,p=prepare(design=design,exposure=exposure,single=single,point=point)
        r=dispatch.execute(s,'q1',**o,**approval_records(p))
        expected=oracle(spec,data,single)
        assert r['state']==('POINT' if expected[0]==expected[1] else 'PARTIAL'),r
        assert r['mathematical_claim']['interval']==expected
        assert r['independent_replay'] is True
        if point:assert r['state']=='POINT'
        # Joint law must match independent experimental-draw probabilities.
        for cell in r['certificate']['cells']:
            assert F(cell['support'])==spec['support'].get(tuple(cell['cell']),F(0))


@pytest.mark.parametrize('design',[f'D{i}' for i in range(1,9)])
def test_missing_rejected_and_unreviewed_never_reach_backend(design):
    for single in (True,False):
        for missing,extra,state in [(True,False,'NEEDS_INPUT'),(False,True,'ADAPTER_NOT_CONNECTED')]:
            s,o,_,_=setup(design,'E4',single=single,missing=missing,extra=extra)
            p=dispatch.inspect_methods(s,'q1',**o)
            assert p['state']==state,p
            assert not p['backend_called']
        s,o,_,_,p=prepare(design=design,exposure='E4',single=single)
        r=dispatch.execute(s,'q1',**o,research_protocol_selected=True)
        assert r['state']=='REVIEW_REQUIRED' and not r['backend_called']
        approvals=approval_records(p)
        row=p['methods'][0]
        key=next(iter(row['science_worksheet']['decisions']))
        approvals['native_reviews'][row['method']]['science_review'].decisions[key]='REJECTED'
        r=dispatch.execute(s,'q1',**o,**approvals)
        assert not r['backend_called'] and r['state'] not in ('POINT','PARTIAL')


def native(design='D6',exposure='E4'):
    _,_,_,_,p=prepare(design=design,exposure=exposure)
    a=approval_records(p);row=p['methods'][0]
    records=contrast.native_reviews_from_json(p,a['native_reviews'])[row['method']]
    q,i=contrast._compile_pair(p,row,records,'SYNTHETIC_TEST')
    return p,q,i


def test_generic_replay_tamper_and_independence(monkeypatch):
    from cfm_id import bounded_finite_solver as solver,bounded_finite_verify as verify
    from pfn_pipeline._internal.identification.randomized_arm_family import SupportEngine
    _,q,i=native();cert=solver.solve_contrast(q,i)
    assert verify.replay_contrast(cert,inquiries=q,information=i)
    monkeypatch.setattr(SupportEngine,'evaluate',lambda **kw:(_ for _ in ()).throw(AssertionError('producer primitive called')))
    assert verify.replay_contrast(cert,inquiries=q,information=i)
    for field,value in [('upper','99'),('sharp',False),('mode','policy'),('informative',True)]:
        bad=deepcopy(cert);bad[field]=value;bad.pop('certificate_sha256')
        bad['certificate_sha256']=sha(bad)
        assert not verify.replay_contrast(bad,inquiries=q,information=i)
    bad=deepcopy(cert);bad['cells'][0]['support']='1';bad.pop('certificate_sha256');bad['certificate_sha256']=sha(bad)
    assert not verify.replay_contrast(bad,inquiries=q,information=i)


def test_d6_exclusion_needs_own_review_and_missing_never_inferred():
    s,o,_,_,p=prepare(design='D6',exposure='E4')
    key='first_stage_profile_no_direct_outcome_effect'
    row=p['methods'][0];assert key in row['science_worksheet']['decisions']
    a=approval_records(p);del a['native_reviews'][row['method']]['science_review'].decisions[key]
    r=dispatch.execute(s,'q1',**o,**a)
    assert not r['backend_called']
    for status in ('NOT_STATED','UNDECIDED','NOT_ADOPTED'):
        raw=deepcopy(o['candidate']);raw['first_stage_exclusion']['status']=status
        if status=='NOT_STATED':raw['first_stage_exclusion']['source_ids']=[]
        p=dispatch.inspect_methods(s,'q1',**dict(o,candidate=raw))
        assert p['state'] in ('NEEDS_INPUT','ADAPTER_NOT_CONNECTED') and not p['backend_called'],p
        if status in ('NOT_STATED','UNDECIDED'):
            questions=' '.join(p['clarification_questions'])
            assert '最终启用名单相同' in questions and '尚未决定' in questions
            assert 'first_stage_exclusion' not in questions


def test_direction_cancellation_and_bounds_ladder():
    for reverse in (False,True):
        s,o,spec,data,p=prepare(design='D1',exposure='E5',reverse=reverse)
        r=dispatch.execute(s,'q1',**o,**approval_records(p))
        assert r['mathematical_claim']['interval']==oracle(spec,data,False)
        if not reverse:first=r['mathematical_claim']['interval']
        else:assert list(map(F,r['mathematical_claim']['interval']))==[-F(first[1]),-F(first[0])]
    s,o,_,_,p=prepare(design='D3',exposure='E2')
    def solve(raw):
        opts=dict(o,candidate=raw);plan=dispatch.inspect_methods(s,'q1',**opts)
        return dispatch.execute(s,'q1',**opts,**approval_records(plan))
    narrow=solve(o['candidate'])
    wider=deepcopy(o['candidate'])
    for b in wider['bounded_model']['bounds']:b.update(lower='0',upper='1')
    wide=solve(wider)
    assert narrow['mathematical_claim']['interval']==['-1/2','1/2']
    assert wide['mathematical_claim']['interval']==['-1','1']
    # The same unsupported cell on both sides cancels before any bound.
    cancel=deepcopy(o['candidate']);cancel['target']['second']=deepcopy(cancel['target']['first'])
    assert solve(cancel)['mathematical_claim']['interval']==['0','0']


def test_native_contract_no_silent_a4_loss_or_full_law_downgrade():
    from cfm_id import bounded_finite_contract as contract,bounded_finite_solver as solver
    from dataclasses import replace
    _,q,i=native()
    bad=i['first'].model_copy(update={'values':i['first'].values[:-1]})
    with pytest.raises(BoundedPolicyUnavailable,match='COMPLETE_EXACT_A4_VALUE_LIST_REQUIRED'):
        solver.solve_policy(q['first'],bad)
    bad=i['first'].model_copy(update={'inquiry_sha256':'0'*64})
    with pytest.raises(BoundedPolicyUnavailable,match='STALE'):contract.validate_model(q['first'],bad)
    # Native backend registry must select the same finite implementation.
    from cfm_id.bounded_backends import policy_backend,contrast_backend
    assert policy_backend(i['first']).solve is solver.solve_policy
    assert contrast_backend(i).solve is solver.solve_contrast


@pytest.mark.parametrize('design,exposure',list(product(('D1','D4','D6'),('E1','E2','E3','E4','E5'))))
def test_irregular_chain_and_realisable_signature_states(design,exposure):
    edges=[('甲店','乙店'),('乙店','丙店'),('丙店','丁店')]
    s,o,spec,data,p=prepare(design=design,exposure=exposure,edges=edges)
    r=dispatch.execute(s,'q1',**o,**approval_records(p))
    assert r['mathematical_claim']['interval']==oracle(spec,data,False)
    assert r['independent_replay']
    for c in r['certificate']['cells']:
        assert F(c['support'])==spec['support'].get(tuple(c['cell']),F(0))


def test_newly_supported_design_still_requires_supported_target_information():
    from examples.network_bounded_dispatch_reference import setup as old_setup
    s,e,o,p=old_setup(n=7)
    c=o['candidate'];c['assignment'].update(kind='INDEPENDENT_BERNOULLI',fixed_count=None,
                                          probabilities={n:'1/2' for n in c['study']['nodes']})
    p=dispatch.inspect_methods(s,'q1',**o)
    assert p['state']=='REVIEW_REQUIRED',p
    r=dispatch.execute(s,'q1',**o,**approval_records(p))
    assert r['state']=='NEEDS_INPUT' and r['reason_code']=='SUPPORTED_TARGET_A4_MEAN_MISSING'
    assert not r['independent_replay']
