"""Exact signed-box bounds for finite D1-D8/E1-E5; policy mean is a one-sided objective.

No exposure/design override: the checked inquiry must itself declare finite D1-D8/E1-E5.
The public entry still requires the existing scientific reviews.
"""
from fractions import Fraction as F
from cfm_id_bridge.scientific_binding import sha
from pfn_pipeline._internal.identification.randomized_arm_family import (
    AssignmentSpec, ExposureSpec, SupportEngine,
)
from .bounded_policy_contract import fail
from .bounded_finite_contract import inputs, input_digest, VERSIONS, is_symbolic, version_for


def _analyze(inquiries, information, mode):
    st, targets, known, bounds, coordinates = inputs(inquiries, information, mode)
    neighbors = {n: set() for n in st.node_order}
    for a, b in st.undirected_edges:
        neighbors[a].add(b); neighbors[b].add(a)
    inquiry=inquiries if mode=='policy' else inquiries['first']
    signature=inquiry.r2_signature
    cores=dict(signature.core_collaborators) if signature.core_collaborators else None
    exposure=ExposureSpec(signature.grouping,cores)
    references={n:exposure.reference_nodes(st.network(),n) for n in st.node_order}
    peers={n:(references[n] if references[n] is not None else neighbors[n]) for n in st.node_order}
    cells=[(n,a,e) for n in st.node_order for a in (0,1)
           for e in sorted({exposure.classify(k,len(peers[n])) for k in range(len(peers[n])+1)})]
    assignment = AssignmentSpec(st.design())
    tables={n:SupportEngine.joint_support(network=st.network(),assignment=assignment,
                                        exposure=exposure,node_id=n) for n in st.node_order}
    probabilities={c:tables[c[0]].get((c[1],c[2]),F(0)) for c in cells}
    if not set(known) <= set(cells):
        fail('INCOMPATIBLE', 'A4_SIGNATURE_NOT_REALIZABLE')
    if any(probabilities[c] == 0 for c in known):
        fail('INCOMPATIBLE', 'A4_CONDITIONAL_EVENT_HAS_ZERO_PROBABILITY')
    coefficients = {c: F(0) for c in cells}
    for side, t in targets.items():
        sign = 1 if side == 'first' else -1
        policy = dict(zip(st.node_order, t.policy_assignment))
        for n, weight in zip(st.node_order, t.unit_weights):
            cell = n, policy[n], exposure.classify(sum(policy[j] for j in peers[n]),len(peers[n]))
            coefficients[cell] += sign * F(weight)
    if any(d and probabilities[c] > 0 and c not in known for c, d in coefficients.items()):
        fail('NEEDS_INPUT', 'SUPPORTED_TARGET_A4_MEAN_MISSING' if mode == 'policy'
             else 'SUPPORTED_NONZERO_CONTRAST_A4_MEAN_MISSING')
    return st, known, bounds, coordinates, cells, probabilities, coefficients


def analyze(inquiries, information):
    """Contrast compatibility/completeness before endpoint execution."""
    return _analyze(inquiries, information, 'contrast')


def _solve(inquiries, information, mode):
    st, known, bounds, coordinates, cells, probabilities, coefficients = _analyze(
        inquiries, information, mode)
    if is_symbolic(information,mode):
        return _symbolic(inquiries,information,mode,st,known,bounds,coordinates,cells,probabilities,coefficients)
    rows, terms, logical = [], [], [F(0), F(0)]
    for c in cells:
        d = coefficients[c]; lo, hi = bounds[c[0]]
        logical[0] += min(d * lo, d * hi)
        logical[1] += max(d * lo, d * hi)
        a, b = (known[c], known[c]) if c in known else (lo, hi)
        low, high = (a, b) if d > 0 else (b, a) if d < 0 else ((a+b)/2, (a+b)/2)
        rows.append(dict(cell=list(c), support=str(probabilities[c]),
            a4_value=str(known[c]) if c in known else None,
            lower_world=str(low), upper_world=str(high)))
        if d:
            terms.append(dict(cell=list(c), coefficient=str(d),
                basis='A4_EQUALITY' if c in known else 'MEAN_BOUNDS',
                cell_lower=str(a), cell_upper=str(b),
                lower_contribution=str(d*low), upper_contribution=str(d*high)))
    lower = sum((F(t['lower_contribution']) for t in terms), F(0))
    upper = sum((F(t['upper_contribution']) for t in terms), F(0))
    cert = dict(version=VERSIONS[mode], theorem='FINITE_SIGNATURE_MEAN_BOX',
        mode=mode, input_sha256=input_digest(inquiries, information, mode),
        target_sha256=sha(coordinates), status='POINT' if lower == upper else 'PARTIAL',
        lower=str(lower), upper=str(upper), width=str(upper-lower),
        logical_range=list(map(str, logical)),
        informative=lower > logical[0] or upper < logical[1], sharp=True,
        model_scope='SIGNATURE_MEANS_AND_NODE_BOUNDS_ONLY', cells=rows, bound_terms=terms,
        realization='BERNOULLI_PER_NODE_SIGNATURE' if st.outcome_kind == 'binary'
            else 'DETERMINISTIC_PER_NODE_SIGNATURE',
        production_admission=False, estimation_handoff_allowed=False)
    cert['certificate_sha256'] = sha(cert)
    return cert


def _symbolic(inquiries,information,mode,st,known,bounds,coordinates,cells,probabilities,coefficients):
    """For every feasible b, output an affine sharp interval and endpoint worlds.

    Parameter names are determined by formal coordinates, never guessed from
    free text. Values remain unknown, with feasibility bounds explicit.
    """
    symbols={c:'b'+str(k+1) for k,c in enumerate(c for c in cells if c in known)}
    parameters=[dict(symbol=symbols[c],cell=list(c),lower=str(bounds[c[0]][0]),
                     upper=str(bounds[c[0]][1])) for c in cells if c in known]
    rows=[];terms=[];linear={};lo=hi=F(0)
    for c in cells:
        d=coefficients[c];a,b=bounds[c[0]]
        if c in known:
            lower=upper=dict(parameter=symbols[c])
            if d:linear[symbols[c]]=str(d)
        else:
            low,high=(a,b) if d>0 else (b,a) if d<0 else ((a+b)/2,(a+b)/2)
            lower,upper=dict(constant=str(low)),dict(constant=str(high))
            lo+=d*low;hi+=d*high
        rows.append(dict(cell=list(c),support=str(probabilities[c]),
            parameter=symbols.get(c),lower_world=lower,upper_world=upper))
        if d:terms.append(dict(cell=list(c),coefficient=str(d),
            basis='A4_PARAMETER' if c in known else 'MEAN_BOUNDS',
            parameter=symbols.get(c),cell_lower=str(a),cell_upper=str(b)))
    cert=dict(version=version_for(information,mode),theorem='FINITE_SIGNATURE_MEAN_BOX_PARAMETRIC',
        mode=mode,input_sha256=input_digest(inquiries,information,mode),target_sha256=sha(coordinates),
        status='POINT' if lo==hi else 'PARTIAL',sharp=True,width=str(hi-lo),
        model_scope='SIGNATURE_MEANS_AND_NODE_BOUNDS_ONLY',parameters=parameters,
        formula_lower=dict(constant=str(lo),terms=linear),formula_upper=dict(constant=str(hi),terms=dict(linear)),
        cells=rows,bound_terms=terms,realization='BERNOULLI_PER_NODE_SIGNATURE' if st.outcome_kind=='binary'
        else 'DETERMINISTIC_PER_NODE_SIGNATURE',production_admission=False,estimation_handoff_allowed=False)
    cert['certificate_sha256']=sha(cert)
    return cert


def solve_policy(inquiry, information):
    return _solve(inquiry, information, 'policy')


def solve_contrast(inquiries, information):
    return _solve(inquiries, information, 'contrast')
