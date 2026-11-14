"""Exact signed-box bounds for D2/E4; policy mean is a one-sided objective.

No exposure/design override: the checked inquiry must itself declare D2/E4.
The public entry still requires the existing scientific reviews.
"""
from fractions import Fraction as F
from cfm_id_bridge.scientific_binding import sha
from pfn_pipeline._internal.identification.randomized_arm_family import (
    AssignmentSpec, ExposureSpec, SupportEngine,
)
from .bounded_policy_contract import fail
from .bounded_count_contract import inputs, input_digest, VERSIONS


def _analyze(inquiries, information, mode):
    st, targets, known, bounds, coordinates = inputs(inquiries, information, mode)
    neighbors = {n: set() for n in st.node_order}
    for a, b in st.undirected_edges:
        neighbors[a].add(b); neighbors[b].add(a)
    cells = [(n, a, e) for n in st.node_order for a in (0, 1)
             for e in range(len(neighbors[n]) + 1)]
    exposure = ExposureSpec('exact_treated_neighbor_count')
    assignment = AssignmentSpec(st.design())
    probabilities = {c: SupportEngine.evaluate(network=st.network(), assignment=assignment,
        exposure=exposure, node_id=c[0], own_treatment_value=c[1],
        exposure_value=c[2]).joint_probability for c in cells}
    if not set(known) <= set(cells):
        fail('INCOMPATIBLE', 'A4_SIGNATURE_NOT_REALIZABLE')
    if any(probabilities[c] == 0 for c in known):
        fail('INCOMPATIBLE', 'A4_CONDITIONAL_EVENT_HAS_ZERO_PROBABILITY')
    coefficients = {c: F(0) for c in cells}
    for side, t in targets.items():
        sign = 1 if side == 'first' else -1
        policy = dict(zip(st.node_order, t.policy_assignment))
        for n, weight in zip(st.node_order, t.unit_weights):
            cell = n, policy[n], sum(policy[j] for j in neighbors[n])
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
    cert = dict(version=VERSIONS[mode], theorem='FINITE_EXACT_COUNT_MEAN_BOX',
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


def solve_policy(inquiry, information):
    return _solve(inquiry, information, 'policy')


def solve_contrast(inquiries, information):
    return _solve(inquiries, information, 'contrast')
