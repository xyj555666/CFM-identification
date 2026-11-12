import base64
from pathlib import Path
import pytest
from demo.backend.engine import Engine, Run, PROJECT_ROOT
from demo.backend.example_materials import selected_file


def test_n100_uses_real_files_in_preview_without_model_calls(tmp_path):
    engine=Engine(tmp_path/'runs'); example=next(e for e in engine.examples if e['id']=='n100')
    result=engine.preview_uploads('test',dict(example_id='n100',question=example['case']['business_question'],use_example_network=True))
    assert result['network']['nodes']==100 and result['network']['edges']==642
    assert engine.calls==0 and result['factual_data'] is None
    no_files=engine.preview_uploads('test',dict(example_id='n100',question='比较本店启用与不启用',use_example_network=False))
    assert no_files['network'] is None
    nodes,name=selected_file(PROJECT_ROOT,example,'network_nodes')
    with pytest.raises(ValueError,match='同时上传'):
        engine.preview_uploads('test',dict(example_id='n100',question='比较本店启用与不启用',
            use_example_network=True,files=[dict(role='network_nodes',name=name,content=base64.b64encode(nodes.read_bytes()).decode())]))
    with pytest.raises(ValueError,match='EXAMPLE_FILE_NOT_FOUND'):
        selected_file(PROJECT_ROOT,example,'../secrets')


def test_provider_settings_bind_request_and_output_limits(tmp_path):
    captured=[]
    class Client:
        api_key=None;last_diagnostics={}
        def generate_json(self,**kw):return {'ok':True}
    def factory(**kw):captured.append(kw);return Client()
    e=Engine(tmp_path/'runs',provider_factory=factory)
    e.credential('u','deepseek','fixture-key',settings={'model':'qwen3.8-27b'})
    r=Run(owner='u',provider='deepseek')
    e.call(r,dict(system_prompt='Return JSON',user_prompt='Test'),'a0')
    assert captured[0]['model']=='qwen3.8-27b' and 'thinking' not in captured[0]
    e.credential('u','deepseek','fixture-key',settings={'model':'deepseek-v4-flash'})
    with pytest.raises(ValueError,match='MODEL_SETTINGS_CHANGED'):
        e.call(r,dict(system_prompt='Return JSON',user_prompt='Test'),'a0')
    with pytest.raises(ValueError,match='PROVIDER_ENDPOINT_MISMATCH'):
        e.credential('u','longcat','fixture-key',settings={'base_url':'https://unrelated.invalid/v1'})
    e.credential('v','longcat','fixture-key')
    e.call(Run(owner='v'),dict(request={'system':'Return JSON','user':'Test'}),'facts')
    assert captured[-1]['max_tokens']==32768
