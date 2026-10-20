"""OpenAI Responses API adapter. Credentials stay in the local Python process."""
import json
import languages
import os
from pathlib import Path
import socket
import urllib.error
import urllib.request

ROOT = Path(__file__).resolve().parent
CONFIG_PATH = ROOT / 'ai_config.local.json'
DEFAULT_MODEL = 'gpt-5-mini'


def settings():
    config = {}
    if CONFIG_PATH.exists():
        try:
            config = json.loads(CONFIG_PATH.read_text(encoding='utf-8-sig'))
        except (OSError, ValueError):
            raise ValueError('AI баптау файлы оқылмады. SETUP_AI.bat арқылы қайта баптаңыз.') from None
        if not isinstance(config, dict):
            raise ValueError('AI баптау пішімі жарамсыз. SETUP_AI.bat арқылы қайта баптаңыз.')
    key = os.environ.get('OPENAI_API_KEY') or config.get('api_key', '')
    model = os.environ.get('OPENAI_MODEL') or config.get('model', DEFAULT_MODEL)
    if not isinstance(key, str) or not isinstance(model, str) or not model.strip():
        raise ValueError('AI баптауы жарамсыз. SETUP_AI.bat іске қосыңыз.')
    if any(c.isspace() for c in key.strip()):
        raise ValueError('API кілтінің пішімі жарамсыз. SETUP_AI.bat арқылы қайта енгізіңіз.')
    return key.strip(), model.strip()


def public_status():
    key, model = settings()
    return {'configured': bool(key), 'model': model}


def conversation(history):
    if not isinstance(history, list) or len(history) > 12:
        raise ValueError('Сөйлесу тарихы тым ұзын. «Жаңа әңгіме» басыңыз.')
    result = []
    total = 0
    for item in history:
        if not isinstance(item, dict) or item.get('role') not in ('user', 'assistant'):
            raise ValueError('Сөйлесу тарихының пішімі жарамсыз.')
        content = item.get('content')
        if not isinstance(content, str) or not 0 < len(content) <= 10000:
            raise ValueError('Сөйлесу хабарламасының ұзындығы жарамсыз.')
        total += len(content)
        if total > 24000:
            raise ValueError('Сөйлесу тарихы тым ұзын. «Жаңа әңгіме» басыңыз.')
        result.append({'role': item['role'], 'content': content})
    return result


def ask(question, history=None, language='kk-KZ'):
    language = languages.validate(language)
    if not isinstance(question, str) or not 0 < len(question.strip()) <= 4000:
        raise ValueError('Сұрақ 1–4000 таңбадан тұруы керек.')
    key, model = settings()
    if not key:
        raise ValueError('AI әлі бапталмаған. Бумадан SETUP_AI.bat ашып, OpenAI API кілтін енгізіңіз.')
    messages = conversation(history or [])
    messages.append({'role': 'user', 'content': question.strip()})
    payload = {
        'model': model,
        'instructions': (
            'You are JARVIS, a helpful desktop companion for a college teacher in Kazakhstan. '
            f'Answer in {languages.SUPPORTED[language]}, the selected conversation language. '
            'Follow an explicit request to translate or quote another language when relevant. Be clear and practical. '
            'You can explain, write lessons, help with IT, programming and general questions. '
            'You have no computer control or live web access in this chat. Do not claim to have '
            'opened programs, read local files, checked hardware or browsed websites. '
            'When relevant, explain that the user can use the separate local command buttons. '
            'Do not invent current facts. Keep answers concise unless detail is requested.'
        ),
        'input': messages,
        'max_output_tokens': 4000,
        'store': False,
    }
    if model.startswith('gpt-5'):
        payload['reasoning'] = {'effort': 'low'}
    request = urllib.request.Request(
        'https://api.openai.com/v1/responses',
        data=json.dumps(payload, ensure_ascii=False).encode('utf-8'),
        headers={'Authorization': 'Bearer ' + key, 'Content-Type': 'application/json'},
        method='POST',
    )
    try:
        with urllib.request.urlopen(request, timeout=90) as response:
            data = json.load(response)
    except urllib.error.HTTPError as exc:
        # Do not pass upstream bodies, request headers or credentials into the UI.
        messages = {
            401: 'API кілті қабылданбады. SETUP_AI.bat арқылы кілтті тексеріңіз.',
            403: 'Бұл API сұрауына рұқсат жоқ. OpenAI жоба рұқсаттары мен қолжетімділігін тексеріңіз.',
            404: 'AI моделі табылмады немесе қолжетімсіз. SETUP_AI.bat арқылы модельді тексеріңіз.',
            429: 'API лимиті немесе баланс шектеуі. OpenAI API балансын, пайдалану лимитін тексеріп, кейін қайталаңыз.',
            400: 'AI сұрауы қабылданбады. Модель баптауын тексеріңіз немесе жаңа әңгіме бастаңыз.',
        }
        raise RuntimeError(messages.get(exc.code, 'AI сервисі уақытша жауап бермеді. Кейін қайталаңыз.')) from None
    except (urllib.error.URLError, TimeoutError, socket.timeout):
        raise RuntimeError('AI сервисімен байланыс орнамады. Интернетті тексеріп, қайта жіберіңіз.') from None
    except (ValueError, OSError):
        raise RuntimeError('AI сервисінің жауабы оқылмады. Қайта жіберіңіз.') from None
    parts = []
    for item in data.get('output', []):
        if item.get('type') == 'message':
            for content in item.get('content', []):
                if content.get('type') == 'output_text' and isinstance(content.get('text'), str):
                    parts.append(content['text'])
                elif content.get('type') == 'refusal' and isinstance(content.get('refusal'), str):
                    parts.append(content['refusal'])
    answer = '\n'.join(parts).strip()
    if not answer:
        raise RuntimeError('AI мәтіндік жауап бермеді. Сұрақты қысқартып, қайта жіберіңіз.')
    return {'message': answer, 'source': 'ai', 'model': model, 'language': language}
