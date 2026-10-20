import io
import json
from pathlib import Path
import sys
import threading
import tempfile
import unittest
from unittest.mock import patch
import urllib.error
import urllib.request

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import ai_chat
import app
import setup_ai


class SetupTests(unittest.TestCase):
    def test_save_validates_and_keeps_existing_key(self):
        with tempfile.TemporaryDirectory() as folder, patch.object(setup_ai, 'ROOT', Path(folder)):
            setup_ai.save('test-secret', '')
            path = Path(folder) / 'ai_config.local.json'
            self.assertEqual(json.loads(path.read_text())['model'], 'gpt-5-mini')
            with self.assertRaises(ValueError):
                setup_ai.save('bad key', '')
            self.assertEqual(json.loads(path.read_text())['api_key'], 'test-secret')


class ChatTests(unittest.TestCase):
    def test_response_and_context_without_tools(self):
        answer = {'output': [
            {'type': 'reasoning', 'summary': []},
            {'type': 'message', 'content': [{'type': 'output_text', 'text': 'Бірінші жауап.'}]},
            {'type': 'message', 'content': [{'type': 'output_text', 'text': 'Екінші бөлік.'}]},
        ]}
        def fake(request, timeout):
            self.assertEqual(request.full_url, 'https://api.openai.com/v1/responses')
            data = json.loads(request.data)
            self.assertEqual(data['input'][-1]['content'], 'Жалғастыр')
            self.assertEqual(data['input'][0]['content'], 'Сәлем')
            self.assertFalse(data['store'])
            self.assertNotIn('tools', data)
            self.assertNotIn('test-secret', request.data.decode())
            return io.BytesIO(json.dumps(answer).encode())
        with patch.object(ai_chat, 'settings', return_value=('test-secret', 'gpt-5-mini')), patch.object(ai_chat.urllib.request, 'urlopen', side_effect=fake):
            result = ai_chat.ask('Жалғастыр', [{'role': 'user', 'content': 'Сәлем'}])
        self.assertEqual(result['message'], 'Бірінші жауап.\nЕкінші бөлік.')
        self.assertEqual(result['source'], 'ai')

    def test_prompt_uses_selected_conversation_language(self):
        for locale, name in [('kk-KZ', 'Kazakh'), ('ru-RU', 'Russian'), ('en-US', 'English')]:
            def fake(request, timeout):
                self.assertIn('Answer in ' + name, json.loads(request.data)['instructions'])
                return io.BytesIO(json.dumps({'output': [{'type': 'message', 'content': [{'type': 'output_text', 'text': 'answer'}]}]}).encode())
            with self.subTest(locale=locale), patch.object(ai_chat, 'settings', return_value=('test-secret', 'gpt-5-mini')), patch.object(ai_chat.urllib.request, 'urlopen', side_effect=fake):
                self.assertEqual(ai_chat.ask('question', language=locale)['language'], locale)

    def test_missing_key(self):
        with patch.object(ai_chat, 'settings', return_value=('', 'gpt-5-mini')):
            with self.assertRaisesRegex(ValueError, 'SETUP_AI'):
                ai_chat.ask('Сәлем')

    def test_invalid_history(self):
        for history in ([{'role': 'system', 'content': 'bad'}], 'not a list', [{'role': 'user', 'content': 'x'*10001}]):
            with self.subTest(history_type=type(history).__name__):
                with self.assertRaises(ValueError):
                    ai_chat.conversation(history)

    def test_errors_do_not_leak_upstream_details(self):
        for status in (400, 401, 403, 404, 429, 500):
            error = urllib.error.HTTPError('https://api.openai.com/v1/responses', status, 'secret-upstream-detail', {}, io.BytesIO(b'test-secret'))
            with self.subTest(status=status), patch.object(ai_chat, 'settings', return_value=('test-secret', 'gpt-5-mini')), patch.object(ai_chat.urllib.request, 'urlopen', side_effect=error):
                with self.assertRaises(RuntimeError) as result:
                    ai_chat.ask('Сұрақ')
                self.assertNotIn('test-secret', str(result.exception))
                self.assertNotIn('secret-upstream-detail', str(result.exception))

    def test_public_status_has_no_key(self):
        with patch.object(ai_chat, 'settings', return_value=('test-secret', 'gpt-5-mini')):
            self.assertEqual(ai_chat.public_status(), {'configured': True, 'model': 'gpt-5-mini'})


class RoutingTests(unittest.TestCase):
    def test_questions_never_launch_programs(self):
        for question in ('Word деген не?', 'Калькулятор қалай жұмыс істейді?', 'Что такое блокнот?', 'Word бағдарламасын түсіндір', 'How to open Word', 'Explain notepad'):
            self.assertIsNone(app.resolve(question))

    def test_supported_commands(self):
        for text, action in [('Калькуляторды аш', 'calculator'), ('Открой ворд', 'word'), ('Блокнотты аш', 'notepad'), ('Жүйені тексер', 'system'), ('Сағат қанша?', 'time')]:
            self.assertEqual(app.resolve(text), action)


class ServerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = app.ThreadingHTTPServer(('127.0.0.1', 0), app.Handler)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        cls.base = 'http://127.0.0.1:' + str(cls.server.server_port)

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join()

    def post(self, data, path='/api/command', token=app.TOKEN, origin=None):
        headers = {'Content-Type': 'application/json', 'X-Jarvis-Token': token}
        if origin:
            headers['Origin'] = origin
        request = urllib.request.Request(self.base + path, data=json.dumps(data).encode(), headers=headers)
        try:
            with urllib.request.urlopen(request) as response:
                return response.status, json.load(response)
        except urllib.error.HTTPError as exc:
            return exc.code, json.load(exc)

    def test_ai_question_and_history(self):
        with patch.object(app.ai_chat, 'ask', return_value={'message': 'AI answer', 'source': 'ai'}) as ask, patch.object(app, 'launch') as launch:
            code, data = self.post({'text': 'Word деген не?', 'history': [], 'mode': 'auto'})
            self.assertEqual(code, 200)
            self.assertEqual(data['source'], 'ai')
            ask.assert_called_once_with('Word деген не?', [], 'kk-KZ')
            launch.assert_not_called()

    def test_chat_mode_never_launches(self):
        with patch.object(app.ai_chat, 'ask', return_value={'message': 'AI answer', 'source': 'ai'}), patch.object(app, 'launch') as launch:
            self.assertEqual(self.post({'text': 'Word аш', 'mode': 'chat'})[0], 200)
            launch.assert_not_called()

    def test_command_mode_does_not_use_ai(self):
        with patch.object(app.ai_chat, 'ask') as ask:
            self.assertEqual(self.post({'text': 'Нейрожелі деген не?', 'mode': 'command'})[0], 400)
            ask.assert_not_called()

    def test_local_button_and_metrics(self):
        self.assertEqual(self.post({'action': 'time'})[1]['source'], 'local')
        code, result = self.post({'action': 'system'})
        self.assertEqual(code, 200)
        self.assertGreater(result['stats']['memory_total_gb'], 0)

    def test_selected_languages_reach_commands_and_chat(self):
        for language, greeting in [('kk-KZ', 'Сәлем'), ('ru-RU', 'Здравствуйте'), ('en-US', 'Hello')]:
            with self.subTest(language=language):
                code, result = self.post({'action': 'hello', 'language': language})
                self.assertEqual(code, 200)
                self.assertIn(greeting, result['message'])
                self.assertEqual(result['language'], language)
                with patch.object(app.ai_chat, 'ask', return_value={'message': 'answer'}) as ask:
                    self.assertEqual(self.post({'text': 'Explain Word', 'language': language})[0], 200)
                    ask.assert_called_once_with('Explain Word', [], language)

    def test_invalid_language_is_rejected_before_action(self):
        for language in ('fr-FR', None, {}, 12):
            with self.subTest(language=language), patch.object(app, 'launch') as launch, patch.object(app.ai_chat, 'ask') as ask:
                self.assertEqual(self.post({'action': 'word', 'language': language})[0], 400)
                launch.assert_not_called()
                ask.assert_not_called()

    def test_speech_receives_selected_locale(self):
        with patch.object(app, 'speak_windows') as speak:
            self.assertEqual(self.post({'text': 'Hello', 'language': 'en-US'}, path='/api/speak')[0], 200)
            speak.assert_called_once_with('Hello', 'en-US')

    def test_auth_and_origin(self):
        self.assertEqual(self.post({'action': 'time'}, token='invalid')[0], 403)
        self.assertEqual(self.post({'action': 'time'}, origin='https://untrusted.example')[0], 403)

    def test_secrets_are_not_served(self):
        for path in ('/ai_config.local.json', '/.env', '/app.py'):
            with self.assertRaises(urllib.error.HTTPError) as result:
                urllib.request.urlopen(self.base + path)
            self.assertEqual(result.exception.code, 404)


if __name__ == '__main__':
    unittest.main()
