"""Presentation of already replayed mean-box certificates; never grants review."""
from copy import deepcopy
from fractions import Fraction as F


def mathematical_claim(certificate,target):
    c=certificate
    common=dict(kind=c['status'],target=deepcopy(target),target_sha256=c['target_sha256'],
                width=c['width'],sharp=c['sharp'])
    if c['theorem']=='FINITE_SIGNATURE_MEAN_BOX_PARAMETRIC':
        return dict(common,representation='PARAMETRIC_IDENTIFIED_INTERVAL',numeric_value=None,
            bound_formula=dict(lower=deepcopy(c['formula_lower']),upper=deepcopy(c['formula_upper']),
                parameters=deepcopy(c['parameters']),
                validity='FOR_EVERY_PARAMETER_IN_DECLARED_DOMAIN'))
    # Do not re-solve or claim validity outside the original numeric model.
    # This is the arithmetic recipe of the independently replayed certificate.
    parameters=[];symbols={}
    for row in c['cells']:
        if row['a4_value'] is not None:
            key=tuple(row['cell']);symbol='b'+str(len(parameters)+1);symbols[key]=symbol
            parameters.append(dict(symbol=symbol,cell=deepcopy(row['cell']),value=row['a4_value']))
    linear={};lower=upper=F(0)
    for term in c['bound_terms']:
        d=F(term['coefficient'])
        if term['basis']=='A4_EQUALITY':linear[symbols[tuple(term['cell'])]]=str(d)
        else:
            lo=F(term.get('cell_lower',term.get('lower')))
            hi=F(term.get('cell_upper',term.get('upper')))
            lower+=min(d*lo,d*hi);upper+=max(d*lo,d*hi)
    supplied={p['symbol']:F(p['value']) for p in parameters}
    known=sum((F(d)*supplied[s] for s,d in linear.items()),F(0))
    if [str(known+lower),str(known+upper)]!=[c['lower'],c['upper']]:
        raise ValueError('BOUND_PRESENTATION_DOES_NOT_MATCH_CERTIFICATE')
    return dict(common,representation='EXACT_IDENTIFIED_INTERVAL',interval=[c['lower'],c['upper']],
        informative=c['informative'],logical_range=deepcopy(c['logical_range']),
        numeric_value=c['lower'] if c['status']=='POINT' else None,
        bound_formula=dict(lower=dict(constant=str(lower),terms=linear),
            upper=dict(constant=str(upper),terms=dict(linear)),parameters=parameters,
            validity='REPLAYED_NUMERIC_CERTIFICATE_RECIPE'))


def evaluate_symbolic(certificate,parameters,*,inquiries,information,mode):
    """Checked arithmetic only. New values do not inherit scientific approval.

    Actual numeric identification must enter the exact-population pathway with
    newly bound sources and reviews. Sample estimates cannot acquire that status
    by calling this convenience function.
    """
    from .bounded_policy_contract import rational
    from .bounded_finite_contract import is_symbolic
    from .bounded_finite_verify import replay_policy,replay_contrast
    if not is_symbolic(information,mode):raise ValueError('SYMBOLIC_INFORMATION_REQUIRED')
    valid=(replay_policy(certificate,inquiry=inquiries,information=information) if mode=='policy'
           else replay_contrast(certificate,inquiries=inquiries,information=information))
    if valid is not True:raise ValueError('INDEPENDENT_FORMULA_REPLAY_REQUIRED')
    domain={p['symbol']:p for p in certificate['parameters']}
    if type(parameters) is not dict or set(parameters)!=set(domain):
        raise ValueError('EXACT_PARAMETER_SET_REQUIRED')
    values={s:rational(v) for s,v in parameters.items()}
    if any(not F(domain[s]['lower'])<=v<=F(domain[s]['upper']) for s,v in values.items()):
        raise ValueError('PARAMETER_OUTSIDE_FEASIBLE_MODEL')
    def value(formula):
        return str(F(formula['constant'])+sum((F(d)*values[s] for s,d in formula['terms'].items()),F(0)))
    return dict(interval=[value(certificate['formula_lower']),value(certificate['formula_upper'])],
                diagnostic_only=True,numeric_information_reviewed=False,
                estimation_handoff_allowed=False)
