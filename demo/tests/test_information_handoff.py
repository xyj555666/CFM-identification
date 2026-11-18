"""Source-role clarification must be reachable from the ordinary web plan."""
from copy import deepcopy
from demo.backend.engine import Engine, Run
from tests_gateway.test_network_information_evidence import fixture
from tests_gateway.test_network_bounded_dispatch import partition_table


def test_web_asks_source_roles_before_science_for_partitioned_table(tmp_path):
    session,entry,options,record=fixture()
    partition_table(options['candidate'])
    before=deepcopy(options['candidate'])
    run=Run(owner='test',synthetic=True,intake=session,query_id='q1',entry=entry,
        query_review=options['query_review'],submission=options)
    engine=Engine(tmp_path)
    engine._plan(run)
    assert run.review_kind=='information' and run.result is None
    sheet=run.review_sheets['information']
    assert len(sheet['entry_source_ids'])==7
    assert run.review_templates['information']['disposition']=='PENDING'
    assert run.submission['candidate']==before
    assert not run.plan['backend_called']
    record['binding_sha256']=sheet['binding_sha256']
    engine._review(run,dict(kind='information',records={'information':record}))
    assert run.review_kind=='science' and run.result is None
    assert run.submission['candidate']==before
