"""Clover's own model engine: talks straight to an AI provider with your API key, no CLI in between.

Providers (Settings → Intelligence → API key):
  anthropic  Claude API (api.anthropic.com), Messages API with prompt caching
  openai     OpenAI, or any OpenAI-style base URL you set
  azure      Azure OpenAI / Azure AI Foundry (classic deployments URL, or the v1 API)
  custom     any endpoint: OpenAI-compatible chat completions (Ollama, LM Studio, vLLM, OpenRouter, Groq…) or Anthropic Messages

Stdlib only. Messages use one neutral shape and are translated per provider:
  {'role': 'user', 'content': [{'type': 'text', 'text': …} | {'type': 'image', 'data': <base64 jpeg/png>, 'media': 'image/jpeg'}]}
  {'role': 'assistant', 'content': 'text', 'tool_calls': [{'id', 'name', 'args': {…}}]}
  {'role': 'tool', 'id': <tool call id>, 'name': …, 'content': 'text', 'images': [{'data', 'media'}]}
"""
import json
import os
import shutil
import ssl
import subprocess
import urllib.error
import urllib.parse
import urllib.request

PROVIDERS = ('anthropic', 'openai', 'azure', 'custom')
LABELS = {'anthropic': 'Claude API', 'openai': 'OpenAI', 'azure': 'Azure OpenAI', 'custom': 'Custom endpoint'}
DEFAULTS = {
    'anthropicModel': 'claude-haiku-5-5', 'anthropicWorkModel': 'claude-sonnet-5-5',
    'openaiBase': 'https://api.openai.com/v1', 'openaiModel': 'gpt-5-mini', 'openaiWorkModel': 'gpt-5',
    'azureApiVersion': '2024-10-21',
    'customFormat': 'openai',
}
ANTHROPIC_VERSION = '2023-06-01'
MAX_OUT = 4096


class ProviderError(Exception):
    """kind: auth | rate | offline | unavailable | too_long | bad_request | setup"""
    def __init__(self, kind, text, status=0):
        super().__init__(text)
        self.kind, self.text, self.status = kind, text, status


def _s(pref, key):
    value = pref(key, DEFAULTS.get(key, ''))
    return value.strip() if isinstance(value, str) else ''


def config(pref):
    """The saved provider settings, normalized. pref(key, default) reads settings.json."""
    provider = pref('provider', 'anthropic')
    provider = provider if provider in PROVIDERS else 'anthropic'
    if provider == 'anthropic':
        fast = _s(pref, 'anthropicModel') or DEFAULTS['anthropicModel']
        return {'provider': provider, 'format': 'anthropic', 'base': 'https://api.anthropic.com/v1', 'key': _s(pref, 'anthropicKey'),
                'fast': fast, 'work': _s(pref, 'anthropicWorkModel') or fast}
    if provider == 'openai':
        fast = _s(pref, 'openaiModel') or DEFAULTS['openaiModel']
        return {'provider': provider, 'format': 'openai', 'base': (_s(pref, 'openaiBase') or DEFAULTS['openaiBase']).rstrip('/'),
                'key': _s(pref, 'openaiKey'), 'fast': fast, 'work': _s(pref, 'openaiWorkModel') or fast}
    if provider == 'azure':
        fast = _s(pref, 'azureDeployment')
        return {'provider': provider, 'format': 'openai', 'base': _s(pref, 'azureEndpoint').rstrip('/'), 'key': _s(pref, 'azureKey'),
                'version': _s(pref, 'azureApiVersion') or DEFAULTS['azureApiVersion'], 'fast': fast, 'work': _s(pref, 'azureWorkDeployment') or fast}
    fmt = _s(pref, 'customFormat')
    fast = _s(pref, 'customModel')
    return {'provider': provider, 'format': fmt if fmt in ('openai', 'anthropic') else 'openai', 'base': _s(pref, 'customBase').rstrip('/'),
            'key': _s(pref, 'customKey'), 'fast': fast, 'work': _s(pref, 'customWorkModel') or fast}


def problem(cfg):
    """'' when the settings can work, else one line saying what to fill in."""
    name = LABELS[cfg['provider']]
    if cfg['provider'] in ('anthropic', 'openai') and not cfg['key']:
        return f'Add your {name} key in Clover Settings → Intelligence.'
    if cfg['provider'] in ('azure', 'custom'):
        try: u = urllib.parse.urlparse(cfg['base'])
        except ValueError: u = None
        if not u or u.scheme not in ('http', 'https') or not u.hostname:
            return f'Enter your {name} address in Clover Settings → Intelligence.'
        if cfg['provider'] == 'azure' and not cfg['key']:
            return 'Add your Azure OpenAI key in Clover Settings → Intelligence.'
    if not cfg['fast']:
        return f'Pick a {"deployment" if cfg["provider"] == "azure" else "model"} for {name} in Clover Settings → Intelligence.'
    return ''


def describe(cfg):
    if cfg['provider'] in ('azure', 'custom'):
        host = urllib.parse.urlparse(cfg['base']).hostname or cfg['base']
        return f'{LABELS[cfg["provider"]]} · {cfg["fast"]} at {host}'
    return f'{LABELS[cfg["provider"]]} · {cfg["fast"]}'


# ---------------------------------------------------------------- HTTP

def _azure_v1(cfg):
    return cfg.get('version', '').lower() in ('v1', 'latest', 'preview') or '/openai/v1' in cfg['base']


def endpoint(cfg, model):
    """-> (url, headers) for one chat call with this model."""
    key, base = cfg['key'], cfg['base']
    if cfg['provider'] == 'azure':
        headers = {'api-key': key, 'content-type': 'application/json'}
        if _azure_v1(cfg):
            root = base.split('/openai/v1')[0]
            return root + '/openai/v1/chat/completions', headers
        query = urllib.parse.urlencode({'api-version': cfg.get('version') or DEFAULTS['azureApiVersion']})
        return f'{base}/openai/deployments/{urllib.parse.quote(model, safe="")}/chat/completions?{query}', headers
    if cfg['format'] == 'anthropic':
        headers = {'anthropic-version': ANTHROPIC_VERSION, 'content-type': 'application/json'}
        if key:
            headers['x-api-key'] = key
            if cfg['provider'] == 'custom': headers['authorization'] = 'Bearer ' + key
        url = base + '/messages' if base.endswith('/v1') else base + '/v1/messages'
        return url, headers
    headers = {'content-type': 'application/json'}
    if key: headers['authorization'] = 'Bearer ' + key
    return base + '/chat/completions', headers


def models_url(cfg):
    if cfg['provider'] == 'azure':
        if _azure_v1(cfg): return cfg['base'].split('/openai/v1')[0] + '/openai/v1/models', {'api-key': cfg['key']}
        return f"{cfg['base']}/openai/models?api-version={urllib.parse.quote(cfg.get('version') or DEFAULTS['azureApiVersion'])}", {'api-key': cfg['key']}
    headers = {'anthropic-version': ANTHROPIC_VERSION} if cfg['format'] == 'anthropic' else {}
    if cfg['key']: headers.update({'x-api-key': cfg['key'], 'authorization': 'Bearer ' + cfg['key']})
    base = cfg['base']
    if cfg['format'] == 'anthropic' and not base.endswith('/v1'): base += '/v1'
    return base + '/models', headers


def _kind(status, text):
    low = text.lower()
    if status in (401, 403): return 'auth'
    if status == 429: return 'rate'
    if status == 413 or 'context' in low and ('length' in low or 'limit' in low or 'window' in low) or 'too long' in low or 'maximum context' in low: return 'too_long'
    if status >= 500 or status == 529: return 'unavailable'
    return 'bad_request'


def _error_text(raw):
    try:
        data = json.loads(raw)
        error = data.get('error', data) if isinstance(data, dict) else {}
        if isinstance(error, dict): return str(error.get('message') or error.get('type') or raw)[:300]
        if isinstance(error, str): return error[:300]
    except ValueError:
        pass
    return raw.strip()[:300]


def _curl_lines(url, headers, body, timeout):
    """Fallback transport: macOS curl trusts the system keychain when this Python has no CA bundle."""
    curl = '/usr/bin/curl' if os.path.exists('/usr/bin/curl') else shutil.which('curl')
    if not curl: raise ProviderError('offline', 'Could not open a secure connection.')
    args = [curl, '-q', '-sS', '-N', '--max-time', str(int(timeout)), '-w', '\n__CLOVER_STATUS__%{http_code}', '-X', 'POST' if body is not None else 'GET', url]
    for k, v in headers.items(): args += ['-H', f'{k}: {v}']
    if body is not None: args += ['--data-binary', '@-']
    p = subprocess.Popen(args, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if body is not None: p.stdin.write(body)
    p.stdin.close()
    held = []
    for line in p.stdout:
        text = line.decode('utf-8', 'replace')
        if text.startswith('__CLOVER_STATUS__'):
            status = int(text[len('__CLOVER_STATUS__'):].strip() or 0)
            if status >= 400 or status == 0:
                raw = ''.join(held)
                raise ProviderError(_kind(status, raw) if status else 'offline', _error_text(raw) or f'HTTP {status}', status)
            break
        held.append(text) if len(held) < 200 else None
        yield text
    p.wait()
    if p.returncode:
        raise ProviderError('offline', (p.stderr.read().decode('utf-8', 'replace').strip() or 'Could not connect.')[:300])


def open_lines(url, headers, body=None, timeout=90):
    """POST (or GET) and yield the response line by line, so streams arrive as they are written."""
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, headers=headers, method='POST' if data is not None else 'GET')
    try:
        response = urllib.request.urlopen(req, timeout=timeout)
    except urllib.error.HTTPError as error:
        raw = error.read().decode('utf-8', 'replace')
        error.close()
        raise ProviderError(_kind(error.code, raw), _error_text(raw) or f'HTTP {error.code}', error.code) from None
    except urllib.error.URLError as error:
        if isinstance(error.reason, ssl.SSLCertVerificationError):
            yield from _curl_lines(url, headers, data, timeout)
            return
        raise ProviderError('offline', f'Could not reach {urllib.parse.urlparse(url).hostname}: {error.reason}') from None
    except (TimeoutError, OSError) as error:
        raise ProviderError('offline', f'Could not reach {urllib.parse.urlparse(url).hostname}: {error}') from None
    with response:
        for line in response:
            yield line.decode('utf-8', 'replace')


def get_json(url, headers, timeout=8):
    return json.loads(''.join(open_lines(url, headers, None, timeout)))


def sse(lines):
    """Server-sent events -> parsed JSON payloads. A plain JSON body (a server that ignored stream) comes back whole."""
    plain = []
    for line in lines:
        line = line.rstrip('\r\n')
        if line.startswith('data:'):
            data = line[5:].strip()
            if not data or data == '[DONE]': continue
            try: yield json.loads(data)
            except ValueError: continue
        elif line and not line.startswith(('event:', ':', 'id:', 'retry:')):
            plain.append(line)
    if plain:
        try: yield {'__whole__': json.loads('\n'.join(plain))}
        except ValueError: pass


# ---------------------------------------------------------------- formats

def _anthropic_messages(messages):
    out = []
    for m in messages:
        if m['role'] == 'user':
            blocks = []
            for b in m['content'] if isinstance(m['content'], list) else [{'type': 'text', 'text': m['content']}]:
                if b['type'] == 'image':
                    blocks.append({'type': 'image', 'source': {'type': 'base64', 'media_type': b.get('media', 'image/jpeg'), 'data': b['data']}})
                else:
                    blocks.append({'type': 'text', 'text': b['text']})
            out.append({'role': 'user', 'content': blocks})
        elif m['role'] == 'assistant':
            blocks = [{'type': 'text', 'text': m['content']}] if m.get('content') else []
            blocks += [{'type': 'tool_use', 'id': c['id'], 'name': c['name'], 'input': c['args']} for c in m.get('tool_calls', [])]
            out.append({'role': 'assistant', 'content': blocks or [{'type': 'text', 'text': '…'}]})
        else:
            inner = [{'type': 'text', 'text': m['content'] or '(no output)'}]
            inner += [{'type': 'image', 'source': {'type': 'base64', 'media_type': i.get('media', 'image/jpeg'), 'data': i['data']}} for i in m.get('images', [])]
            result = {'type': 'tool_result', 'tool_use_id': m['id'], 'content': inner}
            if out and out[-1]['role'] == 'user' and out[-1]['content'] and out[-1]['content'][0].get('type') == 'tool_result':
                out[-1]['content'].append(result)   # parallel tool results share one user turn
            else:
                out.append({'role': 'user', 'content': [result]})
    if out:   # cache the conversation so far: each tool round re-sends it
        last = out[-1]['content'][-1]
        last['cache_control'] = {'type': 'ephemeral'}
    return out


def _openai_messages(system, messages):
    out = [{'role': 'system', 'content': system}]
    for m in messages:
        if m['role'] == 'user':
            parts = []
            for b in m['content'] if isinstance(m['content'], list) else [{'type': 'text', 'text': m['content']}]:
                if b['type'] == 'image':
                    parts.append({'type': 'image_url', 'image_url': {'url': f"data:{b.get('media', 'image/jpeg')};base64,{b['data']}"}})
                else:
                    parts.append({'type': 'text', 'text': b['text']})
            out.append({'role': 'user', 'content': parts if any(p['type'] != 'text' for p in parts) else '\n\n'.join(p['text'] for p in parts)})
        elif m['role'] == 'assistant':
            row = {'role': 'assistant', 'content': m.get('content') or None}
            if m.get('tool_calls'):
                row['tool_calls'] = [{'id': c['id'], 'type': 'function', 'function': {'name': c['name'], 'arguments': json.dumps(c['args'])}} for c in m['tool_calls']]
            out.append(row)
        else:
            out.append({'role': 'tool', 'tool_call_id': m['id'], 'content': m['content'] or '(no output)'})
    # Chat completions take no images in tool results: show them in one user turn after the tool rows.
    pictures = []
    for m in messages:
        if m['role'] == 'tool' and m.get('images'):
            pictures.append(m)
    if pictures and messages[-1]['role'] == 'tool':
        parts = [{'type': 'text', 'text': 'Pictures from the tool results above:'}]
        for m in pictures[-2:]:
            parts += [{'type': 'image_url', 'image_url': {'url': f"data:{i.get('media', 'image/jpeg')};base64,{i['data']}"}} for i in m['images']]
        out.append({'role': 'user', 'content': parts})
    return out


def _anthropic_tools(tools):
    return [{'name': t['name'], 'description': t['description'], 'input_schema': t['schema']} for t in tools]


def _openai_tools(tools):
    return [{'type': 'function', 'function': {'name': t['name'], 'description': t['description'], 'parameters': t['schema']}} for t in tools]


def _uses_completion_tokens(cfg, model):
    """OpenAI's reasoning models (gpt-5, o-series) reject max_tokens; most compatible servers only know max_tokens."""
    if cfg['provider'] in ('openai', 'azure'): return True
    return model.lower().startswith(('gpt-5', 'o1', 'o3', 'o4'))


def chat(cfg, system, messages, model=None, tools=(), on_text=None, timeout=120, max_out=MAX_OUT):
    """One model turn. -> {'text', 'tool_calls': [{'id','name','args'}], 'usage': {'in','out','cached'}, 'stop'}.
    on_text(full_text_so_far) is called as text streams in."""
    model = model or cfg['fast']
    url, headers = endpoint(cfg, model)
    if cfg['format'] == 'anthropic':
        body = {'model': model, 'max_tokens': max_out, 'stream': True,
                'system': [{'type': 'text', 'text': system, 'cache_control': {'type': 'ephemeral'}}],
                'messages': _anthropic_messages(messages)}
        if tools: body['tools'] = _anthropic_tools(tools)
        return _anthropic_stream(open_lines(url, headers, body, timeout), on_text)
    body = {'messages': _openai_messages(system, messages), 'stream': True}
    if not (cfg['provider'] == 'azure' and not _azure_v1(cfg)): body['model'] = model
    body['max_completion_tokens' if _uses_completion_tokens(cfg, model) else 'max_tokens'] = max_out
    if cfg['provider'] == 'openai': body['stream_options'] = {'include_usage': True}
    if tools: body['tools'] = _openai_tools(tools)
    try:
        return _openai_stream(open_lines(url, headers, body, timeout), on_text)
    except ProviderError as error:
        # A server that knows only the other token field, or no stream_options: try once in its dialect.
        if error.kind != 'bad_request' or not any(w in error.text for w in ('max_tokens', 'max_completion_tokens', 'stream_options', 'Unrecognized', 'unsupported')): raise
        field = 'max_tokens' if 'max_completion_tokens' in body else 'max_completion_tokens'
        body.pop('max_completion_tokens', None); body.pop('max_tokens', None); body.pop('stream_options', None)
        body[field] = max_out
        return _openai_stream(open_lines(url, headers, body, timeout), on_text)


def _anthropic_stream(lines, on_text):
    text, calls, usage, stop, current = '', [], {'in': 0, 'out': 0, 'cached': 0}, '', None
    for event in sse(lines):
        if '__whole__' in event:   # not streamed
            whole = event['__whole__']
            if whole.get('type') == 'error': raise ProviderError(_kind(0, json.dumps(whole)), _error_text(json.dumps(whole)))
            for b in whole.get('content', []):
                if b.get('type') == 'text': text += b.get('text', '')
                if b.get('type') == 'tool_use': calls.append({'id': b['id'], 'name': b['name'], 'args': b.get('input') or {}})
            u = whole.get('usage', {})
            usage = {'in': u.get('input_tokens', 0), 'out': u.get('output_tokens', 0), 'cached': u.get('cache_read_input_tokens', 0)}
            if text and on_text: on_text(text)
            return {'text': text, 'tool_calls': calls, 'usage': usage, 'stop': whole.get('stop_reason', '')}
        kind = event.get('type')
        if kind == 'error':
            err = event.get('error', {})
            raise ProviderError('unavailable' if err.get('type') == 'overloaded_error' else 'bad_request', err.get('message', 'Stream error'))
        if kind == 'message_start':
            u = event.get('message', {}).get('usage', {})
            usage['in'] += u.get('input_tokens', 0) + u.get('cache_creation_input_tokens', 0)
            usage['cached'] += u.get('cache_read_input_tokens', 0)
        elif kind == 'content_block_start':
            block = event.get('content_block', {})
            if block.get('type') == 'tool_use':
                current = {'id': block.get('id'), 'name': block.get('name'), 'json': ''}
                calls.append(current)
            else:
                current = None
        elif kind == 'content_block_delta':
            delta = event.get('delta', {})
            if delta.get('type') == 'text_delta':
                text += delta.get('text', '')
                if on_text: on_text(text)
            elif delta.get('type') == 'input_json_delta' and current is not None:
                current['json'] += delta.get('partial_json', '')
        elif kind == 'message_delta':
            stop = event.get('delta', {}).get('stop_reason') or stop
            usage['out'] += event.get('usage', {}).get('output_tokens', 0)
    for call in calls:
        raw = call.pop('json', '')
        try: call['args'] = json.loads(raw) if raw.strip() else {}
        except ValueError: call['args'] = {}
    return {'text': text, 'tool_calls': calls, 'usage': usage, 'stop': stop}


def _openai_stream(lines, on_text):
    text, calls, usage, stop = '', {}, {'in': 0, 'out': 0, 'cached': 0}, ''
    for event in sse(lines):
        if '__whole__' in event:
            whole = event['__whole__']
            if 'error' in whole: raise ProviderError('bad_request', _error_text(json.dumps(whole)))
            choice = (whole.get('choices') or [{}])[0]
            message = choice.get('message', {})
            text = message.get('content') or ''
            for i, c in enumerate(message.get('tool_calls') or []):
                calls[i] = {'id': c.get('id') or f'call_{i}', 'name': c['function']['name'], 'json': c['function'].get('arguments') or ''}
            u = whole.get('usage') or {}
            usage = {'in': u.get('prompt_tokens', 0), 'out': u.get('completion_tokens', 0), 'cached': (u.get('prompt_tokens_details') or {}).get('cached_tokens', 0)}
            stop = choice.get('finish_reason') or ''
            if text and on_text: on_text(text)
            break
        if 'error' in event:
            raise ProviderError('bad_request', _error_text(json.dumps(event)))
        if event.get('usage'):
            u = event['usage']
            usage = {'in': u.get('prompt_tokens', 0), 'out': u.get('completion_tokens', 0), 'cached': (u.get('prompt_tokens_details') or {}).get('cached_tokens', 0)}
        for choice in event.get('choices') or []:
            delta = choice.get('delta') or {}
            if delta.get('content'):
                text += delta['content']
                if on_text: on_text(text)
            for c in delta.get('tool_calls') or []:
                row = calls.setdefault(c.get('index', len(calls)), {'id': '', 'name': '', 'json': ''})
                if c.get('id'): row['id'] = c['id']
                fn = c.get('function') or {}
                if fn.get('name'): row['name'] += fn['name']
                if fn.get('arguments'): row['json'] += fn['arguments']
            stop = choice.get('finish_reason') or stop
    out = []
    for i in sorted(calls):
        row = calls[i]
        try: args = json.loads(row['json']) if row['json'].strip() else {}
        except ValueError: args = {}
        out.append({'id': row['id'] or f'call_{i}', 'name': row['name'], 'args': args if isinstance(args, dict) else {}})
    return {'text': text, 'tool_calls': out, 'usage': usage, 'stop': stop}


# ---------------------------------------------------------------- helpers for Settings

def complete(cfg, system, text, model=None, image=None, timeout=45, max_out=1024, on_text=None):
    """A single tool-free answer (meeting answers, dictation cleanup)."""
    content = ([{'type': 'image', 'data': image, 'media': 'image/jpeg'}] if image else []) + [{'type': 'text', 'text': text}]
    return chat(cfg, system, [{'role': 'user', 'content': content}], model=model, timeout=timeout, max_out=max_out, on_text=on_text)


def models(cfg):
    """Model (or deployment) names the provider offers, best first; [] when it can't say."""
    if cfg['provider'] == 'azure' and not _azure_v1(cfg):
        found = [d for d in (cfg['fast'], cfg['work']) if d]
        try:
            url, headers = models_url(cfg)
            data = get_json(url, headers)
            found += [m['id'] for m in data.get('data', []) if isinstance(m, dict) and isinstance(m.get('id'), str)]
        except (ProviderError, ValueError, AttributeError):
            pass
        return list(dict.fromkeys(found))
    url, headers = models_url(cfg)
    try:
        data = get_json(url, headers)
    except (ProviderError, ValueError):
        return []
    rows = data.get('data', []) if isinstance(data, dict) else []
    ids = [m['id'] for m in rows if isinstance(m, dict) and isinstance(m.get('id'), str) and m['id']]
    if cfg['provider'] == 'openai':   # chat models only, newest families first
        ids = [i for i in ids if i.startswith(('gpt-', 'o1', 'o3', 'o4', 'chatgpt')) and not any(x in i for x in ('audio', 'realtime', 'transcribe', 'tts', 'image', 'embedding', 'search'))]
        ids.sort(key=lambda i: (not i.startswith('gpt-5'), not i.startswith('gpt-4.1'), i))
    return ids


def test(cfg):
    """{'ok', 'text'}: one tiny real call with the saved settings."""
    issue = problem(cfg)
    if issue: return {'ok': False, 'text': issue}
    try:
        reply = complete(cfg, 'You are a connection check. Reply with exactly: ok', 'ping', timeout=30, max_out=16)
    except ProviderError as error:
        hint = {'auth': 'The key was refused.', 'rate': 'Rate limited; the key works but try again shortly.', 'offline': 'Could not connect.',
                'unavailable': 'The provider is busy right now.', 'too_long': '', 'bad_request': 'The provider refused the request.'}.get(error.kind, '')
        return {'ok': error.kind == 'rate', 'text': f'{hint} {error.text}'.strip()}
    return {'ok': True, 'text': f'Connected to {describe(cfg)}.' + ('' if reply['text'].strip() else ' (empty reply)')}
