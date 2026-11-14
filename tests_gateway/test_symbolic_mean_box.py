"""Parametric bounds: actual business dispatch, independent replay, no fake b."""
from copy import deepcopy
from fractions import Fraction as F
from itertools import product
import pytest
from examples.finite_mean_box_reference import setup,approval_records
from cfm_id import business_dispatch as dispatch,network_contrast_dispatch as contrast
from cfm_id_bridge.scientific_binding import sha


def execute(design='D7',exposure='E4',single=False,symbolic=True,point=False):
    s,o,spec,data=setup(design,exposure,single=single,symbolic=symbolic,point=point)
    p=dispatch.inspect_methods(s,'q1',**o)
    assert p['state']=='REVIEW_REQUIRED',p
    r=dispatch.execute(s,'q1',**o,**approval_records(p))
    assert r['state'] in ('POINT','PARTIAL') and r['independent_replay'],r
    return s,o,p,r,spec,data


@pytest.mark.parametrize('design,exposure',list(product([f'D{i}' for i in range(1,9)],[f'E{i}' for i in range(1,6)])))
def test_all_combinations_symbolic_and_numeric_agree(design,exposure):
    for single in (True,False):
        _,_,_,r,_,data=execute(design,exposure,single)
        _,_,_,numeric,_,_=execute(design,exposure,single,symbolic=False)
        formula=r['mathematical_claim']['bound_formula']
        assert r['mathematical_claim']['representation']=='PARAMETRIC_IDENTIFIED_INTERVAL'
        values={tuple(v[k] for k in ('node','own','exposure')):F(v['value']) for v in data['cells']}
        params={p['symbol']:values[tuple(p['cell'])] for p in formula['parameters']}
        def eval_(e):return str(F(e['constant'])+sum((F(d)*params[s] for s,d in e['terms'].items()),F(0)))
        assert [eval_(formula[k]) for k in ('lower','upper')]==numeric['mathematical_claim']['interval']
        assert r['state']==numeric['state']


def test_symbolic_point_and_nonconstant_partial_with_guarded_substitution(monkeypatch):
    from cfm_id import bounded_finite_solver as solver,bounded_finite_verify as verify
    from cfm_id.bounded_mean_formula import evaluate_symbolic
    from pfn_pipeline._internal.identification.randomized_arm_family import SupportEngine
    s,o,_,_,spec,data=execute(point=True)
    # First policy unsupported, second a supported arrangement: bounds contain b.
    raw=deepcopy(o['candidate']);raw['target']['first']['assignment']=dict.fromkeys(spec['nodes'],1)
    opts=dict(o,candidate=raw);p=dispatch.inspect_methods(s,'q1',**opts)
    a=approval_records(p);row=p['methods'][0]
    records=contrast.native_reviews_from_json(p,a['native_reviews'])[row['method']]
    q,i=contrast._compile_pair(p,row,records,'SYNTHETIC_TEST')
    cert=solver.solve_contrast(q,i)
    assert cert['status']=='PARTIAL' and cert['formula_lower']['terms']
    monkeypatch.setattr(SupportEngine,'joint_support',lambda **kw:(_ for _ in ()).throw(AssertionError('producer called')))
    assert verify.replay_contrast(cert,inquiries=q,information=i)
    values={p['symbol']:'1/2' for p in cert['parameters']}
    result=evaluate_symbolic(cert,values,inquiries=q,information=i,mode='contrast')
    assert result['interval']==['-1/4','1/4'] and result['numeric_information_reviewed'] is False
    values[next(iter(values))]='2'
    with pytest.raises(ValueError,match='PARAMETER_OUTSIDE'):evaluate_symbolic(cert,values,inquiries=q,information=i,mode='contrast')
    for key in ('formula_lower','parameters','cells'):
        bad=deepcopy(cert)
        if key=='formula_lower':bad[key]['constant']='99'
        elif key=='parameters':bad[key][0]['upper']='99'
        else:bad[key][0]['lower_world']={'constant':'0'}
        bad.pop('certificate_sha256');bad['certificate_sha256']=sha(bad)
        assert not verify.replay_contrast(bad,inquiries=q,information=i)


def test_symbolic_does_not_fill_missing_numeric_or_admit_sample():
    for kind in ('missing_value','finite_sample','not_reviewed','extra_constraint'):
        s,o,_,_=setup('D7','E4',symbolic=True)
        if kind=='missing_value':o['candidate']['information'][0]['availability']='EXACT_POPULATION_VALUE'
        if kind=='finite_sample':
            o['candidate']['information'][0].update(operator='FINITE_SAMPLE',availability='FINITE_SAMPLE',signature_cells=[])
        if kind=='extra_constraint':o['candidate']['bounded_model']['no_additional_coupling_constraints']['value']=False
        p=dispatch.inspect_methods(s,'q1',**o)
        if kind=='not_reviewed':r=dispatch.execute(s,'q1',**o,research_protocol_selected=True)
        else:r=p
        assert r['state'] not in ('POINT','PARTIAL') and not r['backend_called'],r


def test_extended_assignment_empty_acceptance_and_weight_normalizer():
    for design in ('D7','D8'):
        s,o,_,_=setup(design,'E4')
        if design=='D7':o['candidate']['assignment']['unit_weights']={n:'0' for n in o['candidate']['study']['nodes']}
        else:o['candidate']['assignment']['balance_covariates']={'x':dict(zip(o['candidate']['study']['nodes'],['0','0','0','1']))}
        p=dispatch.inspect_methods(s,'q1',**o)
        r=dispatch.execute(s,'q1',**o,**approval_records(p)) if p['state']=='REVIEW_REQUIRED' else p
        assert r['state'] not in ('POINT','PARTIAL') and not r.get('independent_replay'),r


@pytest.mark.parametrize('single',(True,False))
def test_symbolic_table_provenance_requires_current_independent_review(single):
    from cfm_id import network_information_evidence as evidence
    s,o,_,_=setup('D7','E4',single=single,symbolic=True)
    entry=dispatch.prepare_reader(s,'q1',query_review=o['query_review'])
    o['candidate']['information'][0]['source_ids']+=o['candidate']['exposure']['source_ids']
    original=deepcopy(o['candidate'])
    assert dispatch.inspect_methods(s,'q1',**o)['reason_code']=='EXACT_SINGLE_SOURCE_TABLE_REQUIRED'
    w=evidence.prepare(entry,o['candidate'])
    table=[k for k,v in w['source_catalog'].items() if v['doc_id']=='information']
    record=dict(version=w['version'],binding_sha256=w['binding_sha256'],authority='SYNTHETIC_TEST',
        reviewer='Independent symbolic source reviewer',evidence='The table defines population mean coordinates without numeric values; the other source only defines exposure.',
        disposition='ACCEPTED',table_source_ids=table,supporting_source_ids=[k for k in w['source_catalog'] if k not in table])
    p=dispatch.inspect_methods(s,'q1',**o,information_evidence_review=record)
    assert p['state']=='REVIEW_REQUIRED',p
    r=dispatch.execute(s,'q1',**o,information_evidence_review=record,**approval_records(p))
    assert r['independent_replay'] and r['mathematical_claim']['representation']=='PARAMETRIC_IDENTIFIED_INTERVAL'
    assert o['candidate']==original
    for status in ('PENDING','REJECTED'):
        bad=dict(record,disposition=status)
        r=dispatch.execute(s,'q1',**o,information_evidence_review=bad,research_protocol_selected=True)
        assert not r['backend_called'] and not r['independent_replay']
    o['candidate']['information'][0]['availability']='EXACT_POPULATION_VALUE'
    r=dispatch.execute(s,'q1',**o,information_evidence_review=record,research_protocol_selected=True)
    assert not r['backend_called'] and not r['independent_replay']


@pytest.mark.parametrize('design',('D7','D8'))
def test_explicit_set_law_and_extended_size_boundary(design):
    from itertools import combinations
    from examples.network_bounded_dispatch_reference import setup as legacy_setup
    s,o,spec,_=setup(design,'E4',symbolic=True)
    a=o['candidate']['assignment'];nodes=spec['nodes']
    weights={n:F(v) for n,v in a.pop('unit_weights').items()}
    pairs=list(combinations(nodes,2));total=sum(weights[x]*weights[y] for x,y in pairs)
    a.update(treated_sets=[list(pair) for pair in pairs],
             set_probabilities=[str(weights[x]*weights[y]/total) for x,y in pairs])
    p=dispatch.inspect_methods(s,'q1',**o)
    assert p['state']=='REVIEW_REQUIRED',p
    r=dispatch.execute(s,'q1',**o,**approval_records(p))
    assert r['independent_replay'] and r['state']=='PARTIAL',r
    s,_,o,_=legacy_setup(n=9)
    a=o['candidate']['assignment']
    a.update(kind='UNEQUAL_PROBABILITY_FIXED_QUOTA',unit_weights=dict.fromkeys(o['candidate']['study']['nodes'],'1'))
    p=dispatch.inspect_methods(s,'q1',**o)
    assert p['reason_code']=='EXTENDED_DESIGN_EXACT_ENUMERATION_LIMIT_8' and not p['backend_called']
