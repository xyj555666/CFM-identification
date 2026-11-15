"""Coverage text describes the active registry; it grants no additional ability."""
from demo.backend.coverage import summary
from demo.backend.capabilities import inventory
from cfm_id.bounded_policy_contract import MAX_N
from cfm_id_llm.network_files import MAX_NODES, MAX_EDGES


def test_public_coverage_accounts_for_each_registered_method_once():
    page = summary()
    shown = [m['id'] for group in page['groups'] for m in group['methods']]
    registered = [m['id'] for row in inventory() for m in row['methods']]
    assert sorted(shown) == sorted(registered)
    assert len(shown) == len(set(shown))
    assert page['import_limits'] == dict(nodes=MAX_NODES, edges=MAX_EDGES)
    assert page['finite_partial']['max_nodes'] == MAX_N < MAX_NODES
    assert len(page['finite_partial']['designs']) == 8
    assert len(page['finite_partial']['exposures']) == 5
    assert any('尚未接入此网页' in note for note in page['notes'])


def test_unexplained_new_registration_cannot_silently_disappear(monkeypatch):
    from demo.backend import coverage
    import pytest
    monkeypatch.setattr(coverage, 'inventory', lambda: inventory()+[dict(methods=[dict(id='NEW_METHOD',label='待补解释')])])
    with pytest.raises(ValueError, match='WEB_COVERAGE_PRESENTATION_MISMATCH'):
        coverage.summary()
