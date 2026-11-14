"""Independent D2/E4 replay by enumerating full binary assignments.

No imports from the producer, SupportEngine or exposure/assignment primitives.
Only typed input validation and binding are shared.
"""
from copy import deepcopy
from fractions import Fraction as F
from itertools import product
from cfm_id_bridge.scientific_binding import sha
from .bounded_policy_contract import rational
from .bounded_count_contract import inputs, input_digest, VERSIONS


def _require(ok):
    if not ok:
        raise ValueError('COUNT_CERTIFICATE_INVALID')


def _check(certificate, inquiries, information, mode):
    st, targets, known, bounds, coordinates = inputs(inquiries, information, mode)
    _require(type(certificate) is dict)
    c = deepcopy(certificate); digest = c.pop('certificate_sha256')
    _require(sha(c) == digest)
    _require(set(c) == {'version','theorem','mode','input_sha256','target_sha256','status',
        'lower','upper','width','logical_range','informative','sharp','model_scope',
        'cells','bound_terms','realization','production_admission','estimation_handoff_allowed'})
    _require(c['version'] == VERSIONS[mode] and c['mode'] == mode
        and c['theorem'] == 'FINITE_EXACT_COUNT_MEAN_BOX')
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
    def cell(i, z):
        return nodes[i], z[i], sum(z[j] for j in adjacency[i])
    vectors = list(product((0,1), repeat=len(nodes)))
    observed = [z for z in vectors if sum(z) == st.design().m]
    cells = {cell(i,z) for z in vectors for i in range(len(nodes))}
    ordered = sorted(cells, key=lambda x:(positions[x[0]],x[1],x[2]))
    counts = {x:0 for x in cells}
    for z in observed:
        for i in range(len(nodes)):
            counts[cell(i,z)] += 1
    _require(bool(observed) and set(known) <= cells)
    _require(all(counts[x] > 0 for x in known))
    coeff = {x:F(0) for x in cells}
    for side,t in targets.items():
        for i,w in enumerate(t.unit_weights):
            coeff[cell(i,t.policy_assignment)] += (1 if side == 'first' else -1)*F(w)
    _require(all(not d or counts[x] == 0 or x in known for x,d in coeff.items()))
    _require(type(c['cells']) is list and len(c['cells']) == len(cells))
    rows = {}
    for row in c['cells']:
        _require(type(row) is dict and set(row) == {'cell','support','a4_value','lower_world','upper_world'})
        x = row['cell']
        _require(type(x) is list and len(x) == 3 and type(x[0]) is str
            and type(x[1]) is int and type(x[2]) is int)
        x = tuple(x); _require(x in cells and x not in rows); rows[x] = row
        _require(rational(row['support']) == F(counts[x],len(observed)))
        _require(row['a4_value'] == (str(known[x]) if x in known else None))
        for side in ('lower_world','upper_world'):
            value = rational(row[side]); lo,hi = bounds[x[0]]
            _require(lo <= value <= hi and (x not in known or value == known[x]))
    # Rebuild observed conditional means in both full potential-mean worlds.
    for side in ('lower_world','upper_world'):
        sums = {x:F(0) for x in known}
        for z in observed:
            for i in range(len(nodes)):
                x = cell(i,z)
                if x in known:
                    sums[x] += rational(rows[x][side])
        _require(all(sums[x] == counts[x]*known[x] for x in known))
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
