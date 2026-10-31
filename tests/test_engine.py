"""Clover's own provider engine against local mock servers: Claude API, OpenAI, Azure OpenAI and custom endpoints."""
import json
import os
import tempfile
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from unittest.mock import patch

import clover
import clover_engine as engine


class Mock(BaseHTTPRequestHandler):
    """Records every request; answers from the class-level script, one reply per POST."""
    seen, script = [], []

    def log_message(self, *_):
        pass

    def _reply(self, status, body, sse=False):
        self.send_response(status)
        self.send_header('content-type', 'text/event-stream' if sse else 'application/json')
        self.end_headers()
        self.wfile.write(body.encode())

    def do_GET(self):
        Mock.seen.append({'method': 'GET', 'path': self.path, 'headers': {k.lower(): v for k, v in self.headers.items()}})
        if self.path.endswith('/models') or '/models?' in self.path:
            return self._reply(200, json.dumps({'data': [{'id': 'gpt-5-mini'}, {'id': 'text-embedding-3'}, {'id': 'gpt-4.1'}, {'id': 'gpt-5'}]}))
        self._reply(404, '{}')

    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers['content-length'])))
        Mock.seen.append({'method': 'POST', 'path': self.path, 'headers': {k.lower(): v for k, v in self.headers.items()}, 'body': body})
        status, payload, sse = Mock.script.pop(0)
        self._reply(status, payload, sse)


def openai_sse(*chunks, usage=None):
    rows = [f'data: {json.dumps(c)}\n\n' for c in chunks]
    if usage: rows.append(f'data: {json.dumps({"choices": [], "usage": usage})}\n\n')
    return ''.join(rows) + 'data: [DONE]\n\n'


def anthropic_sse(*events):
    return ''.join(f'event: {e["type"]}\ndata: {json.dumps(e)}\n\n' for e in events)


class EngineTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = ThreadingHTTPServer(('127.0.0.1', 0), Mock)
        cls.base = f'http://127.0.0.1:{cls.server.server_address[1]}'
        threading.Thread(target=cls.server.serve_forever, daemon=True).start()
        cls.env = patch.dict(os.environ, {'NO_PROXY': '*', 'no_proxy': '*'})
        cls.env.start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.env.stop()

    def setUp(self):
        Mock.seen.clear(); Mock.script.clear()

    def prefs(self, **values):
        return lambda key, default=None: values.get(key, default)

    def test_config_defaults_and_problems(self):
        cfg = engine.config(self.prefs())
        self.assertEqual((cfg['provider'], cfg['fast'], cfg['work']), ('anthropic', 'claude-haiku-5-5', 'claude-sonnet-5-5'))
        self.assertIn('key', engine.problem(cfg))
        self.assertEqual(engine.problem(engine.config(self.prefs(anthropicKey='sk-ant'))), '')
        self.assertIn('address', engine.problem(engine.config(self.prefs(provider='azure', azureKey='k'))))
        self.assertIn('deployment', engine.problem(engine.config(self.prefs(provider='azure', azureKey='k', azureEndpoint='https://r.openai.azure.com'))))
        custom = engine.config(self.prefs(provider='custom', customBase='http://localhost:11434/v1/', customModel='llama3'))
        self.assertEqual((custom['base'], custom['format'], engine.problem(custom)), ('http://localhost:11434/v1', 'openai', ''))
        self.assertEqual(engine.config(self.prefs(provider='nope'))['provider'], 'anthropic')

    def test_well_known_presets(self):
        gem = engine.config(self.prefs(provider='gemini', geminiKey='g'))
        self.assertEqual((gem['base'], gem['fast'], gem['work'], engine.problem(gem)),
                         ('https://generativelanguage.googleapis.com/v1beta/openai', 'gemini-3.5-flash', 'gemini-3.1-pro', ''))
        self.assertEqual(engine.endpoint(gem, 'gemini-3.5-flash'), ('https://generativelanguage.googleapis.com/v1beta/openai/chat/completions',
                                                                     {'content-type': 'application/json', 'authorization': 'Bearer g'}))
        self.assertIn('Groq key', engine.problem(engine.config(self.prefs(provider='groq'))))
        for name in ('openrouter', 'groq', 'mistral', 'deepseek', 'xai'):
            cfg = engine.config(self.prefs(provider=name, **{name + 'Key': 'k', name + 'Model': 'mine'}))
            self.assertEqual((cfg['format'], cfg['fast'], engine.problem(cfg)), ('openai', 'mine', ''))
            self.assertTrue(cfg['base'].startswith('https://'))
        ollama = engine.config(self.prefs(provider='ollama', ollamaModel='llama3.2'))
        self.assertEqual((ollama['base'], ollama['key'], engine.problem(ollama)), ('http://localhost:11434/v1', '', ''))   # local: no key
        self.assertIn('model', engine.problem(engine.config(self.prefs(provider='ollama'))))
        self.assertEqual(engine.describe(ollama), 'Ollama · llama3.2 at localhost')
        self.assertEqual(set(engine.PROVIDERS), {'anthropic', 'openai', 'azure', 'gemini', 'openrouter', 'groq', 'mistral', 'deepseek', 'xai', 'ollama', 'custom'})

    def test_endpoints(self):
        az = engine.config(self.prefs(provider='azure', azureEndpoint='https://r.openai.azure.com/', azureKey='k', azureDeployment='mini'))
        url, headers = engine.endpoint(az, 'mini')
        self.assertEqual(url, 'https://r.openai.azure.com/openai/deployments/mini/chat/completions?api-version=2024-10-21')
        self.assertEqual(headers['api-key'], 'k')
        v1 = engine.config(self.prefs(provider='azure', azureEndpoint='https://r.services.ai.azure.com', azureKey='k', azureDeployment='mini', azureApiVersion='v1'))
        self.assertEqual(engine.endpoint(v1, 'mini')[0], 'https://r.services.ai.azure.com/openai/v1/chat/completions')
        ant = engine.config(self.prefs(anthropicKey='sk'))
        url, headers = engine.endpoint(ant, 'claude-haiku-5-5')
        self.assertEqual((url, headers['x-api-key'], headers['anthropic-version']), ('https://api.anthropic.com/v1/messages', 'sk', '2023-06-01'))
        custom = engine.config(self.prefs(provider='custom', customBase='http://h:1', customFormat='anthropic', customModel='m'))
        self.assertEqual(engine.endpoint(custom, 'm')[0], 'http://h:1/v1/messages')
        self.assertNotIn('authorization', engine.endpoint(custom, 'm')[1])   # keyless local server

    def test_openai_stream_with_tool_calls_and_usage(self):
        cfg = engine.config(self.prefs(provider='openai', openaiKey='sk-o', openaiBase=self.base + '/v1'))
        Mock.script.append((200, openai_sse(
            {'choices': [{'delta': {'content': 'Let me '}}]},
            {'choices': [{'delta': {'content': 'check.'}}]},
            {'choices': [{'delta': {'tool_calls': [{'index': 0, 'id': 'call_1', 'function': {'name': 'bash', 'arguments': '{"comm'}}]}}]},
            {'choices': [{'delta': {'tool_calls': [{'index': 0, 'function': {'arguments': 'and": "date"}'}}]}, 'finish_reason': 'tool_calls'}]},
            usage={'prompt_tokens': 12, 'completion_tokens': 5, 'prompt_tokens_details': {'cached_tokens': 4}}), True))
        streamed = []
        out = engine.chat(cfg, 'sys', [{'role': 'user', 'content': [{'type': 'text', 'text': 'hi'}, {'type': 'image', 'data': 'QUJD', 'media': 'image/png'}]}],
                          tools=[{'name': 'bash', 'description': 'd', 'schema': {'type': 'object'}}], on_text=streamed.append)
        self.assertEqual(out['text'], 'Let me check.')
        self.assertEqual(out['tool_calls'], [{'id': 'call_1', 'name': 'bash', 'args': {'command': 'date'}}])
        self.assertEqual(out['usage'], {'in': 12, 'out': 5, 'cached': 4})
        self.assertEqual(streamed, ['Let me ', 'Let me check.'])
        req = Mock.seen[-1]
        self.assertEqual(req['path'], '/v1/chat/completions')
        self.assertEqual(req['headers']['authorization'], 'Bearer sk-o')
        body = req['body']
        self.assertEqual((body['model'], body['max_completion_tokens'], body['messages'][0]), ('gpt-5-mini', 4096, {'role': 'system', 'content': 'sys'}))
        self.assertEqual(body['messages'][1]['content'][1]['image_url']['url'], 'data:image/png;base64,QUJD')
        self.assertEqual(body['tools'][0]['function']['name'], 'bash')

    def test_openai_tool_round_trip_shapes_and_tool_images(self):
        msgs = [{'role': 'user', 'content': 'look'},
                {'role': 'assistant', 'content': '', 'tool_calls': [{'id': 'c1', 'name': 'read_file', 'args': {'path': '/tmp/a.jpg'}}]},
                {'role': 'tool', 'id': 'c1', 'name': 'read_file', 'content': 'Picture: a.jpg', 'images': [{'data': 'WFla', 'media': 'image/jpeg'}]}]
        out = engine._openai_messages('s', msgs)
        self.assertEqual(out[2]['tool_calls'][0]['function'], {'name': 'read_file', 'arguments': '{"path": "/tmp/a.jpg"}'})
        self.assertEqual(out[3], {'role': 'tool', 'tool_call_id': 'c1', 'content': 'Picture: a.jpg'})
        self.assertEqual(out[4]['role'], 'user')
        self.assertEqual(out[4]['content'][1]['image_url']['url'], 'data:image/jpeg;base64,WFla')
        ant = engine._anthropic_messages(msgs)
        self.assertEqual(ant[1]['content'][0]['type'], 'tool_use')
        self.assertEqual(ant[2]['content'][0]['type'], 'tool_result')
        self.assertEqual(ant[2]['content'][0]['content'][1]['source']['data'], 'WFla')
        self.assertEqual(ant[-1]['content'][-1]['cache_control'], {'type': 'ephemeral'})

    def test_anthropic_stream_tool_use(self):
        cfg = engine.config(self.prefs(provider='custom', customBase=self.base, customFormat='anthropic', customModel='claude-haiku-5-5', customKey='k'))
        Mock.script.append((200, anthropic_sse(
            {'type': 'message_start', 'message': {'usage': {'input_tokens': 20, 'cache_read_input_tokens': 7}}},
            {'type': 'content_block_start', 'index': 0, 'content_block': {'type': 'text', 'text': ''}},
            {'type': 'content_block_delta', 'index': 0, 'delta': {'type': 'text_delta', 'text': 'Opening it'}},
            {'type': 'content_block_start', 'index': 1, 'content_block': {'type': 'tool_use', 'id': 'tu_1', 'name': 'bash', 'input': {}}},
            {'type': 'content_block_delta', 'index': 1, 'delta': {'type': 'input_json_delta', 'partial_json': '{"command": "open -a '}},
            {'type': 'content_block_delta', 'index': 1, 'delta': {'type': 'input_json_delta', 'partial_json': 'Safari"}'}},
            {'type': 'message_delta', 'delta': {'stop_reason': 'tool_use'}, 'usage': {'output_tokens': 9}},
            {'type': 'message_stop'}), True))
        out = engine.chat(cfg, 'system words', [{'role': 'user', 'content': 'open safari'}], tools=[{'name': 'bash', 'description': 'd', 'schema': {'type': 'object'}}])
        self.assertEqual(out['text'], 'Opening it')
        self.assertEqual(out['tool_calls'], [{'id': 'tu_1', 'name': 'bash', 'args': {'command': 'open -a Safari'}}])
        self.assertEqual((out['usage'], out['stop']), ({'in': 20, 'out': 9, 'cached': 7}, 'tool_use'))
        req = Mock.seen[-1]
        self.assertEqual(req['path'], '/v1/messages')
        self.assertEqual(req['body']['system'][0]['cache_control'], {'type': 'ephemeral'})
        self.assertEqual(req['body']['tools'][0]['input_schema'], {'type': 'object'})
        self.assertEqual(req['headers']['x-api-key'], 'k')

    def test_errors_are_classified(self):
        cfg = engine.config(self.prefs(provider='custom', customBase=self.base + '/v1', customModel='m'))
        for status, kind in ((401, 'auth'), (429, 'rate'), (503, 'unavailable'), (400, 'bad_request')):
            Mock.script.append((status, json.dumps({'error': {'message': f'nope {status}'}}), False))
            with self.assertRaises(engine.ProviderError) as caught:
                engine.chat(cfg, 's', [{'role': 'user', 'content': 'x'}])
            self.assertEqual((caught.exception.kind, caught.exception.text), (kind, f'nope {status}'))
        Mock.script.append((400, json.dumps({'error': {'message': "This model's maximum context length is 8192 tokens"}}), False))
        with self.assertRaises(engine.ProviderError) as caught:
            engine.chat(cfg, 's', [{'role': 'user', 'content': 'x'}])
        self.assertEqual(caught.exception.kind, 'too_long')
        dead = engine.config(self.prefs(provider='custom', customBase='http://127.0.0.1:9/v1', customModel='m'))
        with self.assertRaises(engine.ProviderError) as caught:
            engine.chat(dead, 's', [{'role': 'user', 'content': 'x'}], timeout=2)
        self.assertEqual(caught.exception.kind, 'offline')

    def test_token_field_fallback_and_unstreamed_reply(self):
        cfg = engine.config(self.prefs(provider='custom', customBase=self.base + '/v1', customModel='gpt-5-local'))
        Mock.script.append((400, json.dumps({'error': {'message': 'Unrecognized request argument supplied: max_completion_tokens'}}), False))
        Mock.script.append((200, json.dumps({'choices': [{'message': {'content': 'whole answer'}, 'finish_reason': 'stop'}], 'usage': {'prompt_tokens': 3, 'completion_tokens': 2}}), False))
        out = engine.chat(cfg, 's', [{'role': 'user', 'content': 'x'}])
        self.assertEqual((out['text'], out['usage']['in']), ('whole answer', 3))
        self.assertIn('max_completion_tokens', Mock.seen[-2]['body'])
        self.assertIn('max_tokens', Mock.seen[-1]['body'])
        self.assertNotIn('max_completion_tokens', Mock.seen[-1]['body'])

    def test_azure_classic_omits_model_and_lists_deployments(self):
        cfg = engine.config(self.prefs(provider='azure', azureEndpoint=self.base, azureKey='az', azureDeployment='mini', azureWorkDeployment='big'))
        Mock.script.append((200, openai_sse({'choices': [{'delta': {'content': 'ok'}, 'finish_reason': 'stop'}]}), True))
        self.assertEqual(engine.test(cfg)['ok'], True)
        req = Mock.seen[-1]
        self.assertEqual(req['path'], '/openai/deployments/mini/chat/completions?api-version=2024-10-21')
        self.assertNotIn('model', req['body'])
        self.assertEqual(req['headers']['api-key'], 'az')
        self.assertEqual(engine.models(cfg)[:2], ['mini', 'big'])

    def test_models_filters_openai_chat_models(self):
        cfg = engine.config(self.prefs(provider='openai', openaiKey='k', openaiBase=self.base + '/v1'))
        self.assertEqual(engine.models(cfg), ['gpt-5', 'gpt-5-mini', 'gpt-4.1'])
        self.assertEqual(Mock.seen[-1]['path'], '/v1/models')

    def test_test_reports_problems_without_calling(self):
        self.assertEqual(engine.test(engine.config(self.prefs())), {'ok': False, 'text': 'Add your Claude API key in Clover Settings → Intelligence.'})
        self.assertEqual(Mock.seen, [])


class RunDirectTests(unittest.TestCase):
    """The whole tool loop: the model asks for bash, the gate approves, the result goes back, the answer streams out."""

    def setUp(self):
        self.dir = tempfile.mkdtemp()
        self.prefs = {'client': 'direct', 'provider': 'openai', 'openaiKey': 'k', 'safe': True}
        self.patches = [patch.object(clover, 'pref', lambda k, d=None: self.prefs.get(k, d)),
                        patch.object(clover, 'DIR', self.dir), patch.object(clover, 'say', lambda *a: self.said.append(a))]
        for p in self.patches: p.start()
        self.said = []

    def tearDown(self):
        for p in self.patches: p.stop()

    def test_tool_loop(self):
        turns = [{'text': 'Checking the date', 'tool_calls': [{'id': 'c1', 'name': 'bash', 'args': {'command': 'echo hi-from-tool'}}], 'usage': {'in': 5, 'out': 2, 'cached': 0}, 'stop': 'tool_calls'},
                 {'text': 'It printed hi.', 'tool_calls': [], 'usage': {'in': 7, 'out': 3, 'cached': 0}, 'stop': 'stop'}]
        sent = []
        def chat(cfg, system, messages, model=None, tools=(), on_text=None, **_):
            sent.append([dict(m) for m in messages])
            self.assertIn('Tools here: bash', system)
            self.assertEqual(model, 'gpt-5-mini')
            return turns.pop(0)
        with patch.object(clover.clover_engine, 'chat', chat), patch.object(clover, 'direct_gate', lambda ask, tool, inp: (True, '')):
            reply, cost, steps = clover.run_direct('say hi')
        self.assertEqual(reply, 'It printed hi.')
        self.assertTrue(clover.run.ok)
        self.assertEqual(clover.run.ran, ['echo hi-from-tool'])
        self.assertEqual(clover.run.tokens, {'in': 12, 'out': 5, 'cached': 0})
        self.assertIn(('·', 'Checking the date'), self.said)
        self.assertEqual(sent[1][-1]['role'], 'tool')
        self.assertIn('hi-from-tool', sent[1][-1]['content'])
        self.assertEqual(len(steps), 1)

    def test_blocked_tool_reaches_the_model_and_auth_error_opens_setup(self):
        turns = [{'text': '', 'tool_calls': [{'id': 'c1', 'name': 'bash', 'args': {'command': 'rm -rf ~'}}], 'usage': {}, 'stop': 'tool_calls'}]
        seen = []
        def chat(cfg, system, messages, **_):
            seen.append(messages[-1])
            if turns: return turns.pop(0)
            raise clover.clover_engine.ProviderError('auth', 'invalid x-api-key', 401)
        with patch.object(clover.clover_engine, 'chat', chat), patch.object(clover, 'direct_gate', lambda *a: (False, 'Clover always blocks this command.')):
            reply, _, _ = clover.run_direct('wipe it')
        self.assertEqual(seen[-1]['content'], 'Clover always blocks this command.')
        self.assertEqual(clover.run.why, 'signed_out')
        self.assertIn('refused the key', reply)
        self.assertIn(('!', 'setup'), self.said)
        self.assertEqual(clover.run.ran, [])

    def test_missing_key_asks_for_setup(self):
        self.prefs['openaiKey'] = ''
        reply, _, _ = clover.run_direct('hi')
        self.assertIn('Add your OpenAI key', reply)
        self.assertEqual(clover.run.why, 'setup_needed')

    def test_plan_and_main_model(self):
        self.assertEqual(clover.plan(), {'ok': True, 'need': '', 'text': 'Using OpenAI · gpt-5-mini with your key.', 'client': 'direct'})
        self.assertEqual(clover.main_model(), 'gpt-5-mini')
        self.prefs['routing'] = 'capable'
        self.assertEqual(clover.main_model(), 'gpt-5')

    def test_gate_treats_direct_like_main_asks(self):
        """Plain commands run without a card (like Claude main asks); hard denials stay denied."""
        import io, contextlib
        def gate(cmd):
            out = io.StringIO()
            with patch.dict(os.environ, {'CLOVER_CLIENT': 'direct', 'CLOVER_ASK': self.dir}), patch('sys.stdin', io.StringIO(json.dumps({'tool_name': 'exec', 'tool_input': {'command': cmd}}))), \
                 contextlib.redirect_stdout(out), patch.object(clover, 'preview_commands', lambda *a: None), patch.object(clover, 'ask_user', lambda *a: 'n'):
                clover.gate()
            return json.loads(out.getvalue().strip().splitlines()[-1])
        self.assertEqual(gate('echo hello')['decision'], 'approve')
        self.assertEqual(gate('sudo ls')['decision'], 'block')
        self.assertEqual(gate('rm -rf /tmp/x')['decision'], 'block')


if __name__ == '__main__':
    unittest.main()
