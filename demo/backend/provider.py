"""One explicit model call with the tested JSON transport; no hidden retries."""
from urllib.parse import urlparse
import re
from .runtime import identification_modules

PROVIDERS = {
    'longcat': {'model': 'LongCat-2.5', 'base_url': 'https://api.longcat.chat/openai/v1', 'thinking': 'disabled'},
    'deepseek': {'model': 'deepseek-v4-flash', 'base_url': 'https://newapi.sufe.edu.cn/v1', 'thinking': 'enabled'},
}

# Stable aliases preserve saved runs; labels describe who receives the request.
PROVIDERS.update({
    'openai': dict(model='gpt-6.1-sol', base_url='https://api.openai.com/v1', output_token_parameter='max_completion_tokens'),
    'deepseek_official': dict(model='deepseek-flash', base_url='https://api.deepseek.com/v1'),
    'qwen': dict(model='', base_url='https://dashscope.aliyuncs.com/compatible-mode/v1'),
    'gemini': dict(model='', base_url='https://generativelanguage.googleapis.com/v1beta/openai'),
    'claude': dict(model='', base_url='https://api.anthropic.com/v1', json_mode=False),
    'kimi': dict(model='', base_url='https://api.moonshot.cn/v1'),
    'glm': dict(model='', base_url='https://open.bigmodel.cn/api/paas/v4'),
    'doubao': dict(model='', base_url='https://ark.cn-beijing.volces.com/api/v3'),
    'custom': dict(model='', base_url=''),
})
LABELS = {
    'longcat': 'LongCat 官方', 'deepseek': '上海财经大学 SUFE · 中转接口',
    'openai': 'OpenAI 官方', 'deepseek_official': 'DeepSeek 官方',
    'qwen': '阿里云百炼 · Qwen 官方', 'gemini': 'Google · Gemini 官方',
    'claude': 'Anthropic · Claude 官方', 'kimi': '月之暗面 · Kimi 官方',
    'glm': '智谱 · GLM 官方', 'doubao': '火山方舟 · 豆包官方',
    'custom': '其他 OpenAI 兼容服务',
}
DOCS = {
    'longcat': 'https://longcat.chat/platform/docs/zh/',
    'openai': 'https://developers.openai.com/api/reference/resources/chat/subresources/completions/methods/create',
    'deepseek_official': 'https://api-docs.deepseek.com/',
    'qwen': 'https://help.aliyun.com/zh/model-studio/base-url',
    'gemini': 'https://ai.google.dev/gemini-api/docs/openai',
    'claude': 'https://platform.claude.com/docs/en/cli-sdks-libraries/libraries/openai-sdk',
    'kimi': 'https://platform.kimi.com/docs/get-api-key',
    'glm': 'https://docs.bigmodel.cn/cn/guide/develop/openai/introduction',
    'doubao': 'https://docs.volcengine.com/docs/ark/base-url-and-authentication?lang=zh',
}
NOTES = {
    'deepseek': '请求发送到 newapi.sufe.edu.cn，不是 DeepSeek 官方。使用学校平台的密钥和模型 ID，也可填写该平台已开通的 Qwen 等模型。',
    'qwen': '填写百炼已开通的模型 ID；服务地域和密钥须对应。这里默认北京按量付费接口。',
    'claude': '使用 Anthropic 官方 API 密钥；如果账号要求指定工作空间，请填写对应 ID。',
    'doubao': '填写方舟控制台提供的模型 ID 或推理接入点 ID。',
    'custom': '填写完整 Base URL（不含 /chat/completions）。此处只支持 OpenAI Chat Completions 兼容协议。',
}
MODEL_CHOICES = {
    'longcat': ['LongCat-2.5'],
    'deepseek': ['deepseek-v4-flash', 'qwen3.8-27b'],
    'openai': ['gpt-6.1-sol', 'gpt-6.1-terra'],
    'deepseek_official': ['deepseek-flash', 'deepseek-v4-pro'],
    'qwen': ['qwen3.8-max', 'qwen3.8-flash'],
    'gemini': ['gemini-3.8-flash'],
    'claude': ['claude-opus-5-5', 'claude-sonnet-5-5'],
    'kimi': ['kimi-k3.1-pro'],
    'glm': ['glm-5.3'],
    'doubao': ['doubao-seed-2-1-pro-260915'],
    'custom': [],
}
for _name, _models in MODEL_CHOICES.items():
    if _models and not PROVIDERS[_name]['model']:
        PROVIDERS[_name]['model'] = _models[0]
WIRE_FIELDS = ('model', 'base_url', 'thinking', 'output_token_parameter', 'json_mode', 'workspace_id')


def provider_catalog():
    return {name: dict(config, label=LABELS.get(name, name), docs_url=DOCS.get(name, ''),
                       models=MODEL_CHOICES.get(name, [config['model']]),
                       note=NOTES.get(name, '使用本厂商 API 密钥；模型 ID 按账号权限填写。'),
                       verification='已有本项目真实调用记录，仍可能读取失败。' if name in ('longcat', 'deepseek')
                       else '已接入协议；尚未完成此入口的真实业务验收。')
            for name, config in PROVIDERS.items()}


def connection_options(provider, settings=None):
    if provider not in PROVIDERS: raise ValueError('UNKNOWN_PROVIDER')
    settings = {} if settings is None else settings
    if not isinstance(settings, dict) or set(settings) - {'model', 'base_url', 'workspace_id', 'output_token_parameter', 'json_mode'}:
        raise ValueError('MODEL_SETTINGS_INVALID')
    config = {k: v for k, v in PROVIDERS[provider].items() if k in WIRE_FIELDS}
    config.update(settings)
    model = config.get('model')
    if not isinstance(model, str) or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9._:/+\-]{0,199}', model.strip()):
        raise ValueError('MODEL_ID_REQUIRED')
    config['model'] = model.strip()
    if provider == 'deepseek' and not config['model'].startswith('deepseek'):
        config.pop('thinking', None)
    url = config.get('base_url')
    if not isinstance(url, str) or len(url)>500 or any(c.isspace() for c in url):
        raise ValueError('MODEL_BASE_URL_INVALID')
    try:
        parsed = urlparse(url)
        port = parsed.port
    except ValueError:
        raise ValueError('MODEL_BASE_URL_INVALID') from None
    if (parsed.scheme != 'https' or not parsed.hostname or parsed.username or parsed.password or
            parsed.query or parsed.fragment or any(c in url for c in '{}\\') or
            parsed.path.rstrip('/').endswith('/chat/completions')):
        raise ValueError('MODEL_BASE_URL_INVALID')
    expected = urlparse(PROVIDERS[provider]['base_url']).hostname
    allowed = parsed.hostname == expected
    if provider == 'qwen':
        allowed = parsed.hostname in {'dashscope.aliyuncs.com', 'dashscope-intl.aliyuncs.com', 'dashscope-us.aliyuncs.com', 'cn-hongkong.dashscope.aliyuncs.com'} or parsed.hostname.endswith('.maas.aliyuncs.com')
    if provider != 'custom' and (not allowed or port not in (None,443)):
        raise ValueError('PROVIDER_ENDPOINT_MISMATCH')
    config['base_url'] = url.rstrip('/')
    for key in ('json_mode', 'output_token_parameter'):
        default = PROVIDERS[provider].get(key, True if key=='json_mode' else 'max_tokens')
        if provider != 'custom' and config.get(key, default) != default:
            raise ValueError('PROVIDER_PROTOCOL_MISMATCH')
    if config.get('output_token_parameter', 'max_tokens') not in ('max_tokens', 'max_completion_tokens') or type(config.get('json_mode', True)) is not bool:
        raise ValueError('MODEL_SETTINGS_INVALID')
    workspace = config.get('workspace_id', '')
    if not isinstance(workspace, str) or (workspace and (provider != 'claude' or not re.fullmatch(r'[A-Za-z0-9_-]{1,160}', workspace))):
        raise ValueError('MODEL_WORKSPACE_INVALID')
    if not workspace: config.pop('workspace_id', None)
    return config


def public_connection(provider, options):
    return dict(provider=provider, label=LABELS.get(provider, provider),
                **{k: options[k] for k in ('model', 'base_url') if k in options})


def make_provider(*, model, base_url, api_key=None, timeout=300, thinking=None,
                  max_tokens=16384, observer=None, output_token_parameter='max_tokens',
                  json_mode=True, workspace_id=None):
    identification_modules()
    if thinking is None and urlparse(base_url).hostname == 'api.longcat.chat':
        thinking = 'disabled'
    from cfm_id_llm.providers.final_content_observer import FinalContentObservedChatProvider
    if output_token_parameter not in ('max_tokens', 'max_completion_tokens'):
        raise ValueError('MODEL_SETTINGS_INVALID')
    client = FinalContentObservedChatProvider(model=model, base_url=base_url, api_key=api_key,
        timeout=timeout, max_stream_seconds=timeout, **{output_token_parameter: max_tokens},
        stream=False, thinking=thinking, json_mode=json_mode, allow_json_fence=False,
        require_finish_reason=True, final_content_observer=observer or (lambda text: None))
    if workspace_id:
        if urlparse(base_url).hostname != 'api.anthropic.com' or not re.fullmatch(r'[A-Za-z0-9_-]{1,160}', workspace_id):
            raise ValueError('MODEL_WORKSPACE_INVALID')
        send = client._transport
        def with_workspace(request, *, timeout):
            request.add_header('anthropic-workspace-id', workspace_id)
            return send(request, timeout=timeout)
        client._transport = with_workspace
    return client


def generate(provider, request, *, fact=False):
    prompt = request['request'] if fact else request
    return provider.generate_json(system_prompt=prompt['system' if fact else 'system_prompt'],
                                  user_prompt=prompt['user' if fact else 'user_prompt'])
