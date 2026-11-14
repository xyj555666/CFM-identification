"""Independent finite D1-D8/E1-E5 replay by enumerating full binary assignments.

No imports from the producer, SupportEngine or exposure/assignment primitives.
Only typed input validation and binding are shared.
"""
from copy import deepcopy
from fractions import Fraction as F
from itertools import product, combinations
from math import comb
from functools import reduce
from operator import mul
from cfm_id_bridge.scientific_binding import sha
from .bounded_policy_contract import rational
from .bounded_finite_contract import inputs, input_digest, VERSIONS, is_symbolic, version_for


def _require(ok):
    if not ok:
        raise ValueError('FINITE_CERTIFICATE_INVALID')


def _check(certificate, inquiries, information, mode):
    st, targets, known, bounds, coordinates = inputs(inquiries, information, mode)
    _require(type(certificate) is dict)
    c = deepcopy(certificate); digest = c.pop('certificate_sha256')
    _require(sha(c) == digest)
    symbolic=is_symbolic(information,mode)
    numeric_keys={'version','theorem','mode','input_sha256','target_sha256','status',
        'lower','upper','width','logical_range','informative','sharp','model_scope',
        'cells','bound_terms','realization','production_admission','estimation_handoff_allowed'}
    symbolic_keys=(numeric_keys-{'lower','upper','logical_range','informative'})|{'parameters','formula_lower','formula_upper'}
    _require(set(c)==(symbolic_keys if symbolic else numeric_keys))
    _require(c['version'] == version_for(information,mode) and c['mode'] == mode
        and c['theorem'] == ('FINITE_SIGNATURE_MEAN_BOX_PARAMETRIC' if symbolic else 'FINITE_SIGNATURE_MEAN_BOX'))
    _require(c['input_sha256'] == input_digest(inquiries, information, mode)
        and c['target_sha256'] == sha(coordinates))
    _require(c['sharp'] is True and c['production_admission'] is False
        and c['estimation_handoff_allowed'] is False)
    _require(c['model_scope'] == 'SIGNATURE_MEANS_AND_NODE_BOUNDS_ONLY')
    nodes = st.node_order; positions = {n:i for i,n in enumerate(nodes)}
    adjacency = [[] for _ in nodes]
    for a,b in st.undirected_edges:
        adjacency[positions[a]].append(positions[b])
        adjacency[positions[b]].append(positions[a])
    inquiry=inquiries if mode=='policy' else inquiries['first']
    signature=inquiry.r2_signature
    kind=signature.grouping
    if kind=='pretreatment_core_collaborator_majority':
        core=dict(signature.core_collaborators)
        adjacency=[[positions[n] for n in core[node]] for node in nodes]
    def cell(i,z):
        k=sum(z[j] for j in adjacency[i]); d=len(adjacency[i])
        if kind in ('strict_majority_ties_low','pretreatment_core_collaborator_majority'):
            e=int(2*k>d)
        elif kind=='three_level_treated_neighbor_fraction':
            _require(d>0)
            e=0 if 3*k<d else 1 if 3*k<2*d else 2
        elif kind=='exact_treated_neighbor_count': e=k
        elif kind=='any_treated_neighbor': e=int(k>0)
        else: raise ValueError('UNSUPPORTED_EXPOSURE')
        return nodes[i],z[i],e
    vectors=list(product((0,1),repeat=len(nodes)))
    design=st.design()
    # Deliberately implement the full law separately from the production engine.
    name=type(design).__name__
    multiply=lambda values:reduce(mul,values,F(1))
    def group_law(z,groups,quotas):
        if any(sum(z[positions[n]] for n in g)!=q for g,q in zip(groups,quotas)):
            return F(0)
        return multiply(F(1,comb(len(g),q)) for g,q in zip(groups,quotas))
    def unequal_law(base,z):
        active=tuple(n for n,a in zip(nodes,z) if a)
        if len(active)!=base.m:return F(0)
        if base.unit_weights is not None:
            weights={n:F(base.unit_weights[n]) for n in nodes}
            den=sum((multiply(weights[n] for n in subset)
                     for subset in combinations(nodes,base.m)),F(0))
            _require(den>0)
            return multiply(weights[n] for n in active)/den
        return next((F(p) for subset,p in zip(base.treated_sets,base.set_probabilities)
                     if set(subset)==set(active)),F(0))
    def balanced(rule,z):
        active=[n for n,a in zip(nodes,z) if a]; other=[n for n,a in zip(nodes,z) if not a]
        if not active or not other:return False
        _require(all(set(row)==set(nodes) for row in rule.covariates.values()))
        return all(abs(sum((F(row[n]) for n in active),F(0))/len(active)-
                       sum((F(row[n]) for n in other),F(0))/len(other))<=F(rule.tolerance)
                   for row in rule.covariates.values())
    def probability(z):
        if name=='HeterogeneousBernoulliDesignV1':
            ps=design.propensities
            return multiply(F(ps[n]) if a else 1-F(ps[n]) for n,a in zip(nodes,z))
        if name=='CompleteRandomizationDesignV1':
            return F(1,comb(len(nodes),design.m)) if sum(z)==design.m else F(0)
        if name in ('TwoGroupFixedQuotaDesignV1','MultiGroupFixedQuotaDesignV25'):
            return group_law(z,design.groups,design.treated_quotas)
        if name=='ClusterBernoulliDesignV24':
            factors=[]
            for g,p in zip(design.clusters,design.cluster_probabilities):
                states={z[positions[n]] for n in g}
                if len(states)!=1:return F(0)
                factors.append(F(p) if next(iter(states)) else 1-F(p))
            return multiply(factors)
        if name=='TwoStageQuotaMixtureDesignV27':
            return sum((F(p)*group_law(z,design.groups,q) for q,p in
                        zip(design.quota_profiles,design.profile_probabilities)),F(0))
        if name=='UnequalProbabilityFixedQuotaDesignV1':return unequal_law(design,z)
        if name=='RerandomizedBalancedDesignV1':
            den=sum((unequal_law(design.base_design,v) for v in vectors
                     if balanced(design.balance_rule,v)),F(0))
            _require(den>0)
            return unequal_law(design.base_design,z)/den if balanced(design.balance_rule,z) else F(0)
        raise ValueError('UNSUPPORTED_DESIGN')
    observed=[(z,probability(z)) for z in vectors if probability(z)>0]
    _require(sum((q for z,q in observed),F(0))==1)
    cells={cell(i,z) for z in vectors for i in range(len(nodes))}
    ordered=sorted(cells,key=lambda x:(positions[x[0]],x[1],x[2]))
    mass={x:F(0) for x in cells}
    for z,q in observed:
        for i in range(len(nodes)):mass[cell(i,z)]+=q
    _require(bool(observed) and set(known)<=cells)
    _require(all(mass[x]>0 for x in known))
    coeff = {x:F(0) for x in cells}
    for side,t in targets.items():
        for i,w in enumerate(t.unit_weights):
            coeff[cell(i,t.policy_assignment)] += (1 if side == 'first' else -1)*F(w)
    _require(all(not d or mass[x] == 0 or x in known for x,d in coeff.items()))
    if symbolic:
        _check_symbolic(c,ordered,mass,coeff,known,bounds,st)
        return
    _require(type(c['cells']) is list and len(c['cells']) == len(cells))
    rows = {}
    for row in c['cells']:
        _require(type(row) is dict and set(row) == {'cell','support','a4_value','lower_world','upper_world'})
        x = row['cell']
        _require(type(x) is list and len(x) == 3 and type(x[0]) is str
            and type(x[1]) is int and type(x[2]) is int)
        x = tuple(x); _require(x in cells and x not in rows); rows[x] = row
        _require(rational(row['support']) == mass[x])
        _require(row['a4_value'] == (str(known[x]) if x in known else None))
        for side in ('lower_world','upper_world'):
            value = rational(row[side]); lo,hi = bounds[x[0]]
            _require(lo <= value <= hi and (x not in known or value == known[x]))
    # Rebuild observed conditional means in both full potential-mean worlds.
    for side in ('lower_world','upper_world'):
        sums = {x:F(0) for x in known}
        for z,q in observed:
            for i in range(len(nodes)):
                x = cell(i,z)
                if x in known:
                    sums[x] += q*rational(rows[x][side])
        _require(all(sums[x] == mass[x]*known[x] for x in known))
    terms,logical = [],[F(0),F(0)]
    for x in ordered:
        d=coeff[x];lo,hi=bounds[x[0]]
        logical[0]+=min(d*lo,d*hi);logical[1]+=max(d*lo,d*hi)
        a,b=(known[x],known[x]) if x in known else (lo,hi)
        if d:
            terms.append(dict(cell=list(x),coefficient=str(d),
                basis='A4_EQUALITY' if x in known else 'MEAN_BOUNDS',
                cell_lower=str(a),cell_upper=str(b),
                lower_contribution=str(min(d*a,d*b)),upper_contribution=str(max(d*a,d*b))))
    _require(sha(c['bound_terms']) == sha(terms))
    lower,upper=rational(c['lower']),rational(c['upper'])
    _require(lower == sum((F(t['lower_contribution']) for t in terms),F(0))
        and upper == sum((F(t['upper_contribution']) for t in terms),F(0)))
    for side,endpoint in (('lower_world',lower),('upper_world',upper)):
        _require(sum((coeff[x]*rational(rows[x][side]) for x in cells),F(0)) == endpoint)
    _require(lower <= upper and rational(c['width']) == upper-lower)
    _require(c['status'] == ('POINT' if lower == upper else 'PARTIAL'))
    _require(c['logical_range'] == list(map(str,logical)))
    _require(type(c['informative']) is bool and c['informative'] ==
        (lower > logical[0] or upper < logical[1]))
    _require(c['realization'] == ('BERNOULLI_PER_NODE_SIGNATURE'
        if st.outcome_kind == 'binary' else 'DETERMINISTIC_PER_NODE_SIGNATURE'))


def _check_symbolic(c,ordered,mass,coeff,known,bounds,st):
    """Independently rebuild affine objectives and all parametric witness cells."""
    symbols={x:'b'+str(j+1) for j,x in enumerate(x for x in ordered if x in known)}
    _require(c['parameters']==[dict(symbol=symbols[x],cell=list(x),lower=str(bounds[x[0]][0]),
                                  upper=str(bounds[x[0]][1])) for x in ordered if x in known])
    expected_rows=[];expected_terms=[];polynomial={};lower=upper=F(0)
    for x in ordered:
        d=coeff[x];a,b=bounds[x[0]]
        if x in known:
            low=high={'parameter':symbols[x]}
            if d:polynomial[symbols[x]]=str(d)
        else:
            low={'constant':str(a if d>0 else b if d<0 else (a+b)/2)}
            high={'constant':str(b if d>0 else a if d<0 else (a+b)/2)}
            lower+=min(d*a,d*b);upper+=max(d*a,d*b)
        expected_rows.append(dict(cell=list(x),support=str(mass[x]),parameter=symbols.get(x),
                                  lower_world=low,upper_world=high))
        if d:expected_terms.append(dict(cell=list(x),coefficient=str(d),
            basis='A4_PARAMETER' if x in known else 'MEAN_BOUNDS',parameter=symbols.get(x),
            cell_lower=str(a),cell_upper=str(b)))
    _require(c['cells']==expected_rows and c['bound_terms']==expected_terms)
    _require(c['formula_lower']==dict(constant=str(lower),terms=polynomial))
    _require(c['formula_upper']==dict(constant=str(upper),terms=polynomial))
    _require(rational(c['width'])==upper-lower and lower<=upper)
    _require(c['status']==('POINT' if lower==upper else 'PARTIAL'))
    _require(c['realization']==('BERNOULLI_PER_NODE_SIGNATURE' if st.outcome_kind=='binary'
                                else 'DETERMINISTIC_PER_NODE_SIGNATURE'))
    # Each listed positive-support conditional mean is the same b coordinate
    # in every underlying arrangement of its event. Hence in both witnesses
    # its probability-weighted sum is mass[x]*b, without substituting numbers.
    # Bounds are asserted only on the explicit independent parameter domain.


def _replay(certificate, inquiries, information, mode):
    try:
        _check(certificate,inquiries,information,mode)
        return True
    except (ValueError,TypeError,KeyError,AttributeError,IndexError,ZeroDivisionError,OverflowError):
        return False


def replay_policy(certificate, *, inquiry, information):
    return _replay(certificate,inquiry,information,'policy')


def replay_contrast(certificate, *, inquiries, information):
    return _replay(certificate,inquiries,information,'contrast')
