import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
import urllib.error

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import ai_chat
import desktop
import setup_ai


def reply(provider, text='Answer'):
    if provider == 'gemini':
        return {'steps': [{'type': 'model_output', 'content': [{'type': 'text', 'text': text}]}]}
    return {'output': [{'type': 'message', 'content': [{'type': 'output_text', 'text': text}]}]}


class ProviderTests(unittest.TestCase):
    def test_legacy_keys_and_provider_keys_are_preserved(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'ai_config.local.json'
            path.write_text(json.dumps({'api_key': 'old-openai', 'model': 'old-model'}))
            with patch.object(setup_ai, 'ROOT', Path(folder)), patch.object(ai_chat, 'CONFIG_PATH', path), patch.dict(ai_chat.os.environ, {}, clear=True):
                setup_ai.save('gemini-secret', '', 'gemini')
                self.assertEqual(ai_chat.settings(), ('old-openai', 'old-model'))
                self.assertEqual(ai_chat.settings('gemini'), ('gemini-secret', 'gemini-3.8-flash'))
                setup_ai.save('', 'custom-gemini', 'gemini')
                self.assertEqual(ai_chat.settings('gemini'), ('gemini-secret', 'custom-gemini'))
                self.assertNotIn('gemini-secret', json.dumps(ai_chat.public_status('gemini')))
                before = path.read_text()
                with self.assertRaises(ValueError):
                    setup_ai.save('bad key', '', 'openai')
                self.assertEqual(path.read_text(), before)

    def test_provider_environment_keys_and_model(self):
        with patch.object(ai_chat, 'read_config', return_value={}), patch.dict(ai_chat.os.environ, {'GEMINI_API_KEY': 'env-gemini', 'GEMINI_MODEL': 'custom-model'}, clear=True):
            self.assertEqual(ai_chat.settings('gemini'), ('env-gemini', 'custom-model'))
            self.assertEqual(ai_chat.settings('openai')[0], '')

    def test_gemini_search_request_and_sources(self):
        response = {'steps': [
            {'type': 'thought', 'summary': [{'type': 'text', 'text': 'private reasoning'}]},
            {'type': 'google_search_call', 'arguments': {'queries': ['query']}},
            {'type': 'google_search_result', 'result': [{'search_suggestions': '<div>Google suggestions</div>'}]},
            {'type': 'model_output', 'content': [{'type': 'text', 'text': 'Answer', 'annotations': [{'type': 'url_citation', 'url': 'https://example.org/source', 'title': 'Source', 'start_index': 0, 'end_index': 6}]}]},
        ]}
        def fake(request, timeout):
            self.assertEqual(request.full_url, 'https://generativelanguage.googleapis.com/v1beta/interactions')
            self.assertEqual(request.get_header('X-goog-api-key'), 'test-secret')
            self.assertIsNone(request.get_header('Authorization'))
            payload = json.loads(request.data)
            self.assertFalse(payload['store'])
            self.assertEqual(payload['tools'], [{'type': 'google_search'}])
            self.assertIn('USER:\nEarlier', payload['input'])
            self.assertIn('USER:\nNow', payload['input'])
            self.assertEqual(payload['generation_config']['max_output_tokens'], 4000)
            return io.BytesIO(json.dumps(response).encode())
        with patch.object(ai_chat, 'settings', return_value=('test-secret', 'gemini-3.8-flash')), patch.object(ai_chat.urllib.request, 'urlopen', side_effect=fake):
            result = ai_chat.ask('Now', [{'role': 'user', 'content': 'Earlier'}], provider='gemini', web_search=True)
        self.assertEqual(result['message'], 'Answer')
        self.assertTrue(result['searched'])
        self.assertEqual(result['citations'][0]['url'], 'https://example.org/source')
        self.assertEqual(result['search_suggestions'], ['<div>Google suggestions</div>'])

    def test_perplexity_uses_agent_api(self):
        response = reply('perplexity')
        response['output'].insert(0, {'queries': ['q'], 'results': [{'url': 'https://example.org', 'title': 'Source'}], 'type': 'search_results'})
        def fake(request, timeout):
            self.assertEqual(request.full_url, 'https://api.perplexity.ai/v1/agent')
            self.assertEqual(request.get_header('Authorization'), 'Bearer test-secret')
            self.assertEqual(json.loads(request.data)['tools'], [{'type': 'web_search'}])
            return io.BytesIO(json.dumps(response).encode())
        with patch.object(ai_chat, 'settings', return_value=('test-secret', 'openai/gpt-5.6-sol')), patch.object(ai_chat.urllib.request, 'urlopen', side_effect=fake):
            result = ai_chat.ask('Question', provider='perplexity', web_search=True)
        self.assertTrue(result['searched'])
        self.assertEqual(len(result['citations']), 1)

    def test_search_disabled_does_not_attach_tools(self):
        for provider in ai_chat.PROVIDERS:
            def fake(request, timeout):
                payload = json.loads(request.data)
                self.assertNotIn('tools', payload)
                self.assertFalse(payload['store'])
                return io.BytesIO(json.dumps(reply(provider)).encode())
            with self.subTest(provider=provider), patch.object(ai_chat, 'settings', return_value=('test-secret', 'model')), patch.object(ai_chat.urllib.request, 'urlopen', side_effect=fake):
                result = ai_chat.ask('Question', provider=provider)
                self.assertFalse(result['search_requested'])
                self.assertFalse(result['searched'])

    def test_openai_inline_offsets_and_unsafe_sources(self):
        response = {'output': [
            {'type': 'web_search_call'},
            {'type': 'message', 'content': [
                {'type': 'output_text', 'text': 'First'},
                {'type': 'output_text', 'text': 'Second', 'annotations': [
                    {'type': 'url_citation', 'url': 'https://example.org', 'start_index': 0, 'end_index': 6},
                    {'type': 'url_citation', 'url': 'javascript:alert(1)'},
                    {'type': 'url_citation', 'url': 'https://user:password@example.org'},
                ]},
            ]},
        ]}
        answer, citations, _, searched = ai_chat.parse_answer(response, 'openai')
        self.assertEqual(answer, 'First\nSecond')
        self.assertEqual(len(citations), 1)
        self.assertEqual(citations[0]['end_index'], len(answer))
        self.assertTrue(searched)

    def test_invalid_provider_or_search_flag_never_sends_request(self):
        with patch.object(ai_chat.urllib.request, 'urlopen') as call:
            for args in ({'provider': 'unknown'}, {'web_search': 'yes'}, {'provider': None}):
                with self.assertRaises(ValueError):
                    ai_chat.ask('Question', **args)
            call.assert_not_called()

    def test_quota_error_has_no_secret_and_no_fallback(self):
        error = urllib.error.HTTPError('https://api.openai.com/v1/responses', 429, 'secret', {}, io.BytesIO(json.dumps({'error': {'code': 'insufficient_quota', 'message': 'test-secret'}}).encode()))
        with patch.object(ai_chat, 'settings', return_value=('test-secret', 'model')), patch.object(ai_chat.urllib.request, 'urlopen', side_effect=error) as call:
            with self.assertRaises(RuntimeError) as result:
                ai_chat.ask('Question')
            self.assertIn('балансы', str(result.exception))
            self.assertNotIn('test-secret', str(result.exception))
            self.assertEqual(call.call_count, 1)

    def test_oversized_response_is_rejected(self):
        with patch.object(ai_chat, 'settings', return_value=('test-secret', 'model')), patch.object(ai_chat, 'MAX_RESPONSE', 10), patch.object(ai_chat.urllib.request, 'urlopen', return_value=io.BytesIO(b'x' * 20)):
            with self.assertRaises(RuntimeError):
                ai_chat.ask('Question')

    def test_sites_open_fixed_urls_without_api(self):
        for site in desktop.AI_SITES:
            self.assertEqual(desktop.parse_command('Open ' + site)['action'], site)
            with patch.object(desktop.sys, 'platform', 'win32'), patch.object(desktop.webbrowser, 'open', return_value=True) as opened, patch.object(desktop.subprocess, 'Popen') as process:
                desktop.launch(site)
                opened.assert_called_once_with(desktop.AI_SITES[site][1])
                process.assert_not_called()


if __name__ == '__main__':
    unittest.main()
