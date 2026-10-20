"""Local Windows assistant. Only explicit, predefined actions can run."""
import datetime
import json
import os
import re
from pathlib import Path
import secrets
import shutil
import subprocess
import sys
import tempfile
import threading
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import psutil
import ai_chat
import languages

ROOT = Path(__file__).resolve().parent
TOKEN = secrets.token_urlsafe(32)
VOICE_LOCK = threading.Lock()


def launch(name):
    if sys.platform != 'win32':
        raise RuntimeError('Бағдарламаларды ашу Windows жүйесінде жұмыс істейді.')
    if name in ('calculator', 'notepad'):
        exe = 'calc.exe' if name == 'calculator' else 'notepad.exe'
        subprocess.Popen([str(Path(os.environ['SystemRoot']) / 'System32' / exe)])
        return
    if name != 'word':
        raise ValueError('Белгісіз бағдарлама.')
    import winreg
    candidates = []
    for hive in (winreg.HKEY_CURRENT_USER, winreg.HKEY_LOCAL_MACHINE):
        for view in (winreg.KEY_WOW64_64KEY, winreg.KEY_WOW64_32KEY):
            try:
                with winreg.OpenKey(hive, r'SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths\WINWORD.EXE', 0, winreg.KEY_READ | view) as key:
                    candidates.append(winreg.QueryValueEx(key, None)[0].strip('"'))
            except OSError:
                pass
    found = shutil.which('WINWORD.EXE')
    if found:
        candidates.append(found)
    for env in ('ProgramFiles', 'ProgramFiles(x86)'):
        for office in ('root/Office16', 'Office16', 'Office15'):
            candidates.append(str(Path(os.environ.get(env, 'C:/Program Files')) / 'Microsoft Office' / office / 'WINWORD.EXE'))
    for candidate in candidates:
        if Path(candidate).is_file():
            subprocess.Popen([candidate])
            return
    raise RuntimeError('Word табылмады. Microsoft Word орнатылғанын тексеріңіз.')


def system_report():
    memory = psutil.virtual_memory()
    disk = psutil.disk_usage(Path(os.environ.get('SystemRoot', str(ROOT))).anchor or '/')
    return {
        'cpu': psutil.cpu_percent(interval=0.6),
        'memory_percent': memory.percent,
        'memory_used_gb': round((memory.total-memory.available)/1024**3, 1),
        'memory_total_gb': round(memory.total/1024**3, 1),
        'disk_percent': disk.percent,
        'disk_free_gb': round(disk.free/1024**3, 1),
    }


def resolve(text):
    text = text.lower().strip().rstrip('.!')
    if text in ('сағат қанша', 'сағат қанша?', 'уақытты айт', 'который час', 'который час?', 'what time is it', 'what time is it?', 'time'):
        return 'time'
    # Questions mentioning a program must not launch that program.
    if '?' in text or any(word in text for word in ('деген', 'қалай', 'түсіндір', 'почему', 'зачем', 'что такое', 'расскажи')) or re.search(r'\b(how|what|why|explain|describe)\b', text):
        return None
    opening = re.search(r'(^|\s)(аш\w*|откр\w*|запуст\w*|open|launch)(\s|$)', text)
    if opening and any(word in text for word in ('калькулятор', 'calculator')):
        return 'calculator'
    if opening and any(word in text for word in ('блокнот', 'notepad')):
        return 'notepad'
    if opening and any(word in text for word in ('word', 'ворд', 'уорд')):
        return 'word'
    if text in ('system check', 'check system', 'check the system') or (any(word in text for word in ('жүйе', 'систем', 'компьютер')) and any(word in text for word in ('тексер', 'провер'))):
        return 'system'
    if text in ('сәлем', 'сәлем, jarvis', 'привет', 'hello'):
        return 'hello'
    return None


def execute(action, language='kk-KZ'):
    language = languages.validate(language)
    if action in ('calculator', 'notepad', 'word'):
        launch(action)
        labels = {
            'kk-KZ': {'calculator': 'Калькулятор', 'notepad': 'Блокнот', 'word': 'Microsoft Word'},
            'ru-RU': {'calculator': 'Калькулятор', 'notepad': 'Блокнот', 'word': 'Microsoft Word'},
            'en-US': {'calculator': 'Calculator', 'notepad': 'Notepad', 'word': 'Microsoft Word'},
        }
        label = labels[language][action]
        templates = {'kk-KZ': '{} ашуға пәрмен жіберілді.', 'ru-RU': 'Отправлена команда на запуск: {}.', 'en-US': 'Sent a command to open {}.'}
        return {'message': templates[language].format(label)}
    if action == 'system':
        stats = system_report()
        templates = {
            'kk-KZ': 'Процессор жүктемесі {cpu} пайыз. Жедел жад {memory_percent} пайыз пайдаланылуда. Дискіде {disk_free_gb} гигабайт бос орын бар.',
            'ru-RU': 'Загрузка процессора: {cpu} процентов. Использование оперативной памяти: {memory_percent} процентов. Свободно на диске: {disk_free_gb} гигабайт.',
            'en-US': 'CPU usage is {cpu} percent. Memory usage is {memory_percent} percent. There are {disk_free_gb} gigabytes free on the disk.',
        }
        return {'message': templates[language].format(**stats), 'stats': stats}
    if action == 'time':
        prefix = {'kk-KZ': 'Қазір сағат ', 'ru-RU': 'Сейчас ', 'en-US': 'The time is '}
        return {'message': prefix[language] + datetime.datetime.now().strftime('%H:%M')}
    if action == 'hello':
        messages = {'kk-KZ': 'Сәлем! Мен сіздің JARVIS көмекшіңізбін. Пәрмен беріңіз.', 'ru-RU': 'Здравствуйте! Я ваш помощник JARVIS. Задайте вопрос или дайте команду.', 'en-US': 'Hello! I am JARVIS, your assistant. Ask a question or give me a command.'}
        return {'message': messages[language]}
    raise ValueError('Пәрмен түсініксіз. Экрандағы пәрмендердің бірін таңдаңыз.')


def speak_windows(text, language='kk-KZ'):
    language = languages.validate(language)
    if sys.platform != 'win32':
        raise RuntimeError('Жүйелік дыбыстау тек Windows-та қолжетімді.')
    # Native SAPI automation avoids starting the PowerShell/.NET host.
    # The utterance is UTF-8 data in a temporary file, never executable code.
    host = Path(os.environ.get('SystemRoot', r'C:\Windows')) / 'System32' / 'cscript.exe'
    if not host.is_file():
        raise RuntimeError('Windows дыбыстау құралы (cscript.exe) табылмады. «Дауыстық жауап» белгісін қолданып көріңіз.')
    with VOICE_LOCK:
        filename = None
        try:
            with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', suffix='.txt', delete=False) as handle:
                handle.write(text)
                filename = handle.name
            result = subprocess.run(
                [str(host), '//Nologo', '//U', str(ROOT / 'native_voice.vbs'), filename, language],
                capture_output=True, timeout=35, creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0),
            )
            if result.returncode:
                raw = result.stdout + result.stderr
                detail = raw.decode('utf-16-le', errors='replace').strip()[:700] or 'Windows дыбыс модулі жауап бермеді.'
                raise RuntimeError('Windows дауысы қолжетімсіз: ' + detail + ' Браузердегі «Дауыстық жауап» белгісін қолданып көріңіз.')
        except subprocess.TimeoutExpired:
            raise RuntimeError('Windows дыбыстауы белгіленген уақытта аяқталмады. Дыбыс құрылғысын тексеріңіз.') from None
        finally:
            if filename:
                Path(filename).unlink(missing_ok=True)


class Handler(BaseHTTPRequestHandler):
    def send_json(self, code, data):
        body = json.dumps(data, ensure_ascii=False).encode('utf-8')
        self.send_response(code)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Content-Length', str(len(body)))
        self.send_header('Cache-Control', 'no-store')
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.end_headers()
        self.wfile.write(body)

    def trusted(self):
        host = f'127.0.0.1:{self.server.server_port}'
        return self.headers.get('Host') == host and self.headers.get('Origin', 'http://' + host) == 'http://' + host

    def do_GET(self):
        if not self.trusted():
            return self.send_json(403, {'error': 'Forbidden'})
        if self.path not in ('/', '/index.html'):
            return self.send_json(404, {'error': 'Not found'})
        page = (ROOT / 'index.html').read_text(encoding='utf-8').replace('__SESSION_TOKEN__', TOKEN).encode('utf-8')
        self.send_response(200)
        self.send_header('Content-Type', 'text/html; charset=utf-8')
        self.send_header('Content-Length', str(len(page)))
        self.send_header('Cache-Control', 'no-store')
        self.send_header('X-Frame-Options', 'DENY')
        self.end_headers()
        self.wfile.write(page)

    def do_POST(self):
        if not self.trusted() or self.headers.get('X-Jarvis-Token') != TOKEN:
            return self.send_json(403, {'error': 'Forbidden'})
        if self.path not in ('/api/command', '/api/speak', '/api/status'):
            return self.send_json(404, {'error': 'Not found'})
        try:
            length = int(self.headers.get('Content-Length', '0'))
            if not 0 < length <= 131072:
                raise ValueError('Сұрау көлемі жарамсыз.')
            data = json.loads(self.rfile.read(length))
            if not isinstance(data, dict):
                raise ValueError('Сұрау пішімі жарамсыз.')
            if self.path == '/api/status':
                return self.send_json(200, ai_chat.public_status())
            language = languages.validate(data.get('language', 'kk-KZ'))
            if self.path == '/api/speak':
                message = data.get('text', '')
                if not isinstance(message, str) or not 0 < len(message) <= 1000:
                    raise ValueError('Дыбыстау мәтіні жарамсыз.')
                speak_windows(message, language)
                return self.send_json(200, {'ok': True})
            if 'action' in data:
                action = data['action']
                if not isinstance(action, str):
                    raise ValueError('Пәрмен пішімі жарамсыз.')
            else:
                text = data.get('text', '')
                if not isinstance(text, str) or not 0 < len(text.strip()) <= 4000:
                    raise ValueError('Мәтін жарамсыз.')
                mode = data.get('mode', 'auto')
                if mode not in ('auto', 'chat', 'command'):
                    raise ValueError('Режим жарамсыз.')
                action = resolve(text) if mode != 'chat' else None
                if action is None and mode != 'command':
                    return self.send_json(200, ai_chat.ask(text, data.get('history', []), language))
            result = execute(action, language)
            result['language'] = language
            result['source'] = 'local'
            self.send_json(200, result)
        except (ValueError, json.JSONDecodeError) as exc:
            self.send_json(400, {'error': str(exc)})
        except Exception as exc:
            self.send_json(500, {'error': str(exc)})

    def log_message(self, fmt, *args):
        print(datetime.datetime.now().strftime('%H:%M:%S'), fmt % args)


def main():
    server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
    url = f'http://127.0.0.1:{server.server_port}'
    print('JARVIS is running at ' + url)
    print('Keep this window open. Press Ctrl+C to stop.')
    threading.Timer(0.8, lambda: webbrowser.open(url)).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == '__main__':
    main()
