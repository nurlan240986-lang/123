"""Explicit desktop commands, registered applications and local workspace tools."""
import datetime
import fnmatch
import json
import os
from pathlib import Path
import platform
import re
import secrets
import shutil
import subprocess
import sys
import time
import webbrowser

import languages

ROOT = Path(__file__).resolve().parent
WORKSPACE = ROOT / 'JARVIS_Workspace'
APPS_PATH = ROOT / 'apps.local.json'
PROGRAMS = {
    'calculator': ('Калькулятор', 'calc.exe', ('калькулятор', 'calculator')),
    'notepad': ('Блокнот', 'notepad.exe', ('блокнот', 'notepad')),
    'word': ('Microsoft Word', 'WINWORD.EXE', ('word', 'ворд', 'уорд')),
    'excel': ('Microsoft Excel', 'EXCEL.EXE', ('excel', 'эксель', 'ексель')),
    'powerpoint': ('Microsoft PowerPoint', 'POWERPNT.EXE', ('powerpoint', 'пауэрпоинт', 'презентациялар')),
    'paint': ('Paint', 'mspaint.exe', ('paint', 'пейнт')),
    'explorer': ('Файл менеджері', 'explorer.exe', ('проводник', 'file explorer', 'файл менеджер')),
    'taskmanager': ('Task Manager', 'Taskmgr.exe', ('task manager', 'диспетчер задач', 'тапсырмалар диспетчер')),
    'chrome': ('Google Chrome', 'chrome.exe', ('chrome', 'хром')),
    'edge': ('Microsoft Edge', 'msedge.exe', ('edge', 'эдж')),
    'browser': ('Браузер', None, ('браузер', 'browser')),
    'settings': ('Windows Settings', None, ('баптаулар', 'параметры', 'settings')),
}


def tr(language, kk, ru, en):
    return {'kk-KZ': kk, 'ru-RU': ru, 'en-US': en}[languages.validate(language)]


def read_apps():
    if not APPS_PATH.exists():
        return []
    try:
        data = json.loads(APPS_PATH.read_text(encoding='utf-8-sig'))
        if not isinstance(data, list) or len(data) > 20:
            raise ValueError
        ids, aliases = set(), set()
        for item in data:
            if not isinstance(item, dict) or not re.fullmatch(r'app_[a-f0-9]{16}', item.get('id', '')):
                raise ValueError
            if not isinstance(item.get('name'), str) or not 1 <= len(item['name']) <= 60:
                raise ValueError
            if not isinstance(item.get('path'), str) or not Path(item['path']).is_absolute() or Path(item['path']).suffix.casefold() != '.exe':
                raise ValueError
            if item['path'].startswith(('\\\\', '//')):
                raise ValueError
            names = item.get('aliases')
            if not isinstance(names, list) or not 1 <= len(names) <= 5 or any(not isinstance(x, str) or not 2 <= len(x.strip()) <= 40 for x in names):
                raise ValueError
            normalized = {x.casefold().strip() for x in names}
            if item['id'] in ids or aliases & normalized:
                raise ValueError
            ids.add(item['id'])
            aliases.update(normalized)
        return data
    except (ValueError, TypeError, OSError):
        raise ValueError('apps.local.json оқылмады. SETUP_APPS.bat арқылы баптауды тексеріңіз.') from None


def write_apps(items):
    if len(items) > 20:
        raise ValueError('Ең көбі 20 бағдарлама тіркеуге болады.')
    temporary = APPS_PATH.with_suffix('.tmp')
    temporary.write_text(json.dumps(items, ensure_ascii=False, indent=2), encoding='utf-8')
    temporary.replace(APPS_PATH)


def register_app(name, path, aliases):
    name = name.strip()
    path = Path(path).expanduser()
    aliases = list(dict.fromkeys(x.strip().casefold() for x in aliases if x.strip()))
    if not 1 <= len(name) <= 60 or not 1 <= len(aliases) <= 5 or any(not 2 <= len(x) <= 40 for x in aliases):
        raise ValueError('Атау 1–60 таңба, әр шақыру атауы 2–40 таңба болуы керек (1–5 атау).')
    if not path.is_absolute() or not path.is_file() or path.suffix.casefold() != '.exe' or str(path).startswith(('\\\\', '//')):
        raise ValueError('Осы компьютердегі .exe файлын таңдаңыз. Пәрмен не аргумент енгізілмейді.')
    existing = read_apps()
    used = {a.casefold() for _, _, names in PROGRAMS.values() for a in names}
    used.update(a.casefold() for item in existing for a in item['aliases'])
    if any(a in used for a in aliases):
        raise ValueError('Мұндай шақыру атауы бар. Басқа бірегей атауды таңдаңыз.')
    item = {'id': 'app_' + secrets.token_hex(8), 'name': name, 'path': str(path.resolve()), 'aliases': aliases}
    write_apps(existing + [item])
    return item


def find_executable(exe):
    candidates = []
    if sys.platform == 'win32':
        import winreg
        for hive in (winreg.HKEY_CURRENT_USER, winreg.HKEY_LOCAL_MACHINE):
            for view in (winreg.KEY_WOW64_64KEY, winreg.KEY_WOW64_32KEY):
                try:
                    with winreg.OpenKey(hive, 'SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\App Paths\\' + exe, 0, winreg.KEY_READ | view) as key:
                        candidates.append(os.path.expandvars(winreg.QueryValueEx(key, None)[0].strip('"')))
                except OSError:
                    pass
    system = Path(os.environ.get('SystemRoot', r'C:\Windows'))
    candidates += [str(system / 'System32' / exe), str(system / exe)]
    found = shutil.which(exe)
    if found:
        candidates.append(found)
    for env in ('ProgramFiles', 'ProgramFiles(x86)', 'LOCALAPPDATA'):
        prefix = os.environ.get(env)
        if not prefix:
            continue
        for sub in ('Microsoft Office/root/Office16', 'Microsoft Office/Office16', 'Microsoft Office/Office15', 'Google/Chrome/Application', 'Microsoft/Edge/Application'):
            candidates.append(str(Path(prefix) / sub / exe))
    return next((str(Path(p)) for p in candidates if Path(p).is_file()), None)


def launch(name):
    if sys.platform != 'win32':
        raise RuntimeError('Бағдарламаларды ашу Windows жүйесінде жұмыс істейді.')
    if name == 'browser':
        if not webbrowser.open('https://www.google.com/'):
            raise RuntimeError('Әдепкі браузер ашылмады.')
        return
    if name == 'settings':
        os.startfile('ms-settings:')
        return
    if name in PROGRAMS:
        path = find_executable(PROGRAMS[name][1])
        label = PROGRAMS[name][0]
    else:
        item = next((x for x in read_apps() if x['id'] == name), None)
        if item is None:
            raise ValueError('Белгісіз бағдарлама.')
        path, label = item['path'], item['name']
    if not path or not Path(path).is_file():
        raise RuntimeError(label + ' табылмады. Бағдарлама орнатылғанын тексеріңіз немесе SETUP_APPS.bat арқылы тіркеңіз.')
    subprocess.Popen([path], shell=False)


def program_name(name):
    if name in PROGRAMS:
        return PROGRAMS[name][0]
    item = next((x for x in read_apps() if x['id'] == name), None)
    if item:
        return item['name']
    raise ValueError('Белгісіз бағдарлама.')


def catalog():
    result = [{'id': name, 'name': values[0], 'aliases': list(values[2])} for name, values in PROGRAMS.items()]
    result += [{'id': x['id'], 'name': x['name'], 'aliases': x['aliases']} for x in read_apps()]
    return {'programs': result, 'workspace': str(WORKSPACE)}


def parse_command(text):
    raw = text.strip()
    if ':' not in raw and not raw.casefold().startswith(('сағат қанша', 'который час', 'what time is it')) and ('?' in raw or any(x in raw.casefold() for x in ('деген', 'қалай', 'что такое', 'почему', 'зачем')) or re.search(r'\b(how|what|why|explain|describe)\b', raw, re.I)):
        return None
    # Content after an explicit note/search/folder prefix is data, including punctuation.
    patterns = [
        ('find_files', r'^(?:файл(?:ды)?\s+ізде|найди\s+файл|найти\s+файл|find\s+files?|search\s+files?)\s*[:\-]?\s*(.+)$'),
        ('make_folder', r'^(?:бума\s+жаса|создай\s+папку|создать\s+папку|create\s+folder)\s*[:\-]?\s*(.+)$'),
        ('save_note', r'^(?:жазба\s+сақта|сохрани\s+заметку|сохранить\s+заметку|save\s+note)\s*[:\-]?\s*(.+)$'),
    ]
    for action, pattern in patterns:
        found = re.match(pattern, raw, re.I | re.S)
        if found:
            return {'action': action, 'argument': found.group(1).strip()}
    text = raw.casefold().rstrip('.!')
    if text in ('сағат қанша', 'сағат қанша?', 'уақытты айт', 'который час', 'который час?', 'what time is it', 'what time is it?', 'time'):
        return {'action': 'time'}
    if '?' in text or any(x in text for x in ('деген', 'қалай', 'түсіндір', 'почему', 'зачем', 'что такое', 'расскажи')) or re.search(r'\b(how|what|why|explain|describe)\b', text):
        return None
    fixed = {
        'workspace': ('жұмыс бумасын аш', 'открой рабочую папку', 'open workspace'),
        'documents': ('құжаттарды аш', 'открой документы', 'open documents'),
        'downloads': ('жүктеулерді аш', 'открой загрузки', 'open downloads'),
        'full_report': ('толық есеп жаса', 'жүйе туралы есеп жаса', 'создай отчет системы', 'полный отчет', 'create system report', 'full system report'),
        'lesson_workspace': ('сабаққа дайындал', 'подготовь урок', 'prepare lesson'),
        'hello': ('сәлем', 'сәлем, jarvis', 'привет', 'hello'),
    }
    for action, words in fixed.items():
        if text in words:
            return {'action': action}
    if text in ('system check', 'check system', 'check the system') or (any(x in text for x in ('жүйе', 'систем', 'компьютер')) and any(x in text for x in ('тексер', 'провер'))):
        return {'action': 'system'}
    if not re.search(r'(^|\s)(аш\w*|откр\w*|запуст\w*|open|launch)(\s|$)', text):
        return None
    apps = catalog()['programs']
    matches = [item['id'] for item in apps if any(re.search(r'(?<!\w)' + re.escape(alias.casefold()) + r'(?:ды|ді|ты|ті|ны|ні|ын|ін|сын|сін)?(?!\w)', text) for alias in item['aliases'])]
    if any(x in matches for x in ('chrome', 'edge')) and 'browser' in matches:
        matches.remove('browser')
    if len(matches) == 1:
        return {'action': matches[0]}
    if 1 < len(matches) <= 5:
        return {'action': 'launch_many', 'argument': ','.join(matches)}
    return None


def known_folder(name):
    fallback = Path.home() / {'documents': 'Documents', 'downloads': 'Downloads', 'desktop': 'Desktop'}[name]
    if sys.platform == 'win32':
        import winreg
        key_name = {'documents': 'Personal', 'downloads': '{374DE290-123F-4565-9164-39C4925E467B}', 'desktop': 'Desktop'}[name]
        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r'Software\Microsoft\Windows\CurrentVersion\Explorer\User Shell Folders') as key:
                return Path(os.path.expandvars(winreg.QueryValueEx(key, key_name)[0]))
        except OSError:
            pass
    return fallback


def search_roots():
    roots = [WORKSPACE, known_folder('documents'), known_folder('downloads'), known_folder('desktop')]
    unique = []
    for root in roots:
        if str(root).startswith(('\\\\', '//')):
            continue
        try:
            resolved = root.resolve()
            if resolved.is_dir() and resolved not in unique:
                unique.append(resolved)
        except OSError:
            pass
    return unique


def open_directory(path):
    if sys.platform != 'win32':
        raise RuntimeError('Буманы ашу Windows-та жұмыс істейді.')
    path = Path(path).resolve()
    if not path.is_dir():
        raise ValueError('Бума табылмады.')
    os.startfile(str(path))


def open_search_folder(path):
    resolved = Path(path).resolve()
    if not any(resolved.is_relative_to(root) for root in search_roots()):
        raise ValueError('Іздеу аймағынан тыс буманы ашуға болмайды.')
    open_directory(resolved)


def workspace_folder(name):
    if not isinstance(name, str) or not 1 <= len(name.strip()) <= 80:
        raise ValueError('Бума атауы 1–80 таңба болуы керек.')
    name = name.strip()
    if name in ('.', '..') or re.search(r'[<>:"/\\|?*\x00-\x1f]', name) or name.endswith(('.', ' ')) or re.match(r'^(CON|PRN|AUX|NUL|COM[0-9]|LPT[0-9])(?:\.|$)', name, re.I):
        raise ValueError('Бумаға жарамды қарапайым атау беріңіз; жол енгізілмейді.')
    WORKSPACE.mkdir(parents=True, exist_ok=True)
    path = WORKSPACE / name
    if not path.resolve().is_relative_to(WORKSPACE.resolve()):
        raise ValueError('Жұмыс бумасынан тыс жолға рұқсат жоқ.')
    path.mkdir(exist_ok=False)
    return path


def save_text(prefix, text):
    WORKSPACE.mkdir(parents=True, exist_ok=True)
    path = WORKSPACE / (prefix + '_' + datetime.datetime.now().strftime('%Y%m%d_%H%M%S') + '_' + secrets.token_hex(3) + '.txt')
    with path.open('x', encoding='utf-8') as handle:
        handle.write(text)
    return path


def find_files(query):
    if not isinstance(query, str) or not 1 <= len(query.strip()) <= 100 or any(x in query for x in ('/', '\\', '\0')):
        raise ValueError('Файл атауы не *.pdf сияқты үлгі енгізіңіз (1–100 таңба).')
    query = query.strip().casefold()
    wildcard = any(x in query for x in '*?[')
    results, seen, scanned, limited = [], set(), 0, False
    started = time.monotonic()
    examined = 0
    for root in search_roots():
        for directory, dirs, files in os.walk(root, followlinks=False):
            scanned += 1
            if scanned > 5000 or time.monotonic() - started > 3:
                return results, True
            current = Path(directory)
            if not current.resolve().is_relative_to(root):
                dirs[:] = []
                continue
            if len(current.relative_to(root).parts) >= 5:
                limited |= bool(dirs)
                dirs[:] = []
            else:
                dirs[:] = [x for x in dirs if not x.startswith('.') and x not in ('node_modules', 'AppData') and not (current / x).is_symlink()]
            for name in files:
                examined += 1
                if examined > 50000 or (examined % 128 == 0 and time.monotonic() - started > 3):
                    return results, True
                if (fnmatch.fnmatchcase(name.casefold(), query) if wildcard else query in name.casefold()):
                    path = current / name
                    if path.is_symlink():
                        continue
                    value = str(path)
                    if value not in seen:
                        seen.add(value)
                        results.append({'name': name, 'path': value, 'folder': str(current)})
                    if len(results) >= 30:
                        return results, True
    return results, limited


def full_report(language):
    import psutil
    mem = psutil.virtual_memory()
    title = tr(language, 'JARVIS: жүйе туралы толық есеп', 'JARVIS: полный отчет о системе', 'JARVIS: detailed system report')
    rows = [title, datetime.datetime.now().isoformat(timespec='seconds'), '', 'OS: ' + platform.platform(), 'Architecture: ' + platform.machine(), 'CPU logical cores: ' + str(psutil.cpu_count()), 'CPU usage (%): ' + str(psutil.cpu_percent(interval=0.5)), 'RAM total (GiB): ' + str(round(mem.total / 1024**3, 2)), 'RAM used (%): ' + str(mem.percent), 'Last boot: ' + datetime.datetime.fromtimestamp(psutil.boot_time()).isoformat(timespec='seconds'), '', 'Disks:']
    for disk in psutil.disk_partitions():
        try:
            usage = psutil.disk_usage(disk.mountpoint)
            rows.append(f'{disk.mountpoint}: free {usage.free / 1024**3:.1f} GiB, used {usage.percent}%')
        except (OSError, PermissionError):
            continue
    processes = []
    for proc in psutil.process_iter(['pid', 'name', 'memory_info']):
        try:
            info = proc.info
            if info['memory_info']:
                processes.append((info['memory_info'].rss, info['pid'], info['name']))
        except (psutil.Error, OSError):
            continue
    rows += ['', 'Top 10 processes by RAM (MiB):']
    rows += [f'{pid} | {name} | {rss / 1024**2:.1f}' for rss, pid, name in sorted(processes, reverse=True)[:10]]
    rows += ['', tr(language, 'Бұл есеп ағымдағы көрсеткіштерді сипаттайды; аппараттық ақауды өздігінен анықтамайды.', 'Отчет показывает текущие показатели и не является полной аппаратной диагностикой.', 'This report describes current metrics; it is not a complete hardware diagnosis.')]
    return save_text('System_report', '\n'.join(rows))


def execute(action, argument='', language='kk-KZ'):
    languages.validate(language)
    if not isinstance(action, str):
        raise ValueError('Пәрмен жарамсыз.')
    if not isinstance(argument, str) or len(argument) > 4000:
        raise ValueError('Пәрмен аргументі жарамсыз.')
    if action in PROGRAMS or action.startswith('app_'):
        label = program_name(action)
        launch(action)
        return {'message': tr(language, label + ' ашуға пәрмен жіберілді.', 'Отправлена команда на запуск: ' + label + '.', 'Sent a command to open ' + label + '.')}
    if action == 'launch_many':
        names = list(dict.fromkeys(argument.split(',')))
        allowed = {x['id'] for x in catalog()['programs']}
        if not 1 <= len(names) <= 5 or any(x not in allowed for x in names):
            raise ValueError('Тек тіркелген 1–5 бағдарлама таңдалады.')
        results = []
        for name in names:
            try:
                launch(name)
                results.append(program_name(name) + ': ' + tr(language, 'ашуға жіберілді', 'команда отправлена', 'launch requested'))
            except (OSError, RuntimeError) as exc:
                results.append(program_name(name) + ': ' + str(exc))
        return {'message': '\n'.join(results)}
    if action in ('workspace', 'documents', 'downloads'):
        path = WORKSPACE if action == 'workspace' else known_folder(action)
        if action == 'workspace':
            path.mkdir(parents=True, exist_ok=True)
        open_directory(path)
        return {'message': tr(language, 'Бума ашуға жіберілді: ', 'Команда на открытие папки: ', 'Requested folder opening: ') + str(path)}
    if action == 'open_search_folder':
        open_search_folder(argument)
        return {'message': tr(language, 'Бума ашуға жіберілді.', 'Команда на открытие папки отправлена.', 'Requested folder opening.')}
    if action == 'make_folder':
        try:
            path = workspace_folder(argument)
        except FileExistsError:
            raise ValueError('Мұндай бума бар. Басқа атау беріңіз.') from None
        return {'message': tr(language, 'Бума жасалды: ', 'Создана папка: ', 'Created folder: ') + str(path), 'saved_path': str(path)}
    if action == 'save_note':
        if not argument.strip():
            raise ValueError('Жазба мәтінін енгізіңіз.')
        path = save_text('Note', argument)
        return {'message': tr(language, 'Жазба сақталды: ', 'Заметка сохранена: ', 'Saved note: ') + str(path), 'saved_path': str(path)}
    if action == 'full_report':
        path = full_report(language)
        return {'message': tr(language, 'Жүйе есебі дайын: ', 'Системный отчет готов: ', 'System report saved: ') + str(path), 'saved_path': str(path)}
    if action == 'find_files':
        files, limited = find_files(argument)
        message = tr(language, 'Табылған файл саны: ', 'Найдено файлов: ', 'Files found: ') + str(len(files))
        if limited:
            message += tr(language, '. Іздеу көлемі шектелді; нәтижелер толық болмауы мүмкін.', '. Поиск ограничен; список может быть неполным.', '. Search was bounded; results may be incomplete.')
        return {'message': message, 'files': files, 'limited': limited}
    if action == 'lesson_workspace':
        path = workspace_folder('Lesson_' + datetime.datetime.now().strftime('%Y%m%d_%H%M%S') + '_' + secrets.token_hex(2))
        for name in ('Materials', 'Tasks', 'Results'):
            (path / name).mkdir()
        (path / 'Lesson_notes.txt').write_text(tr(language, 'Сабақ тақырыбы:\nМақсаты:\nТапсырмалар:\nБағалау:\n', 'Тема урока:\nЦель:\nЗадания:\nОценивание:\n', 'Lesson topic:\nObjective:\nTasks:\nAssessment:\n'), encoding='utf-8')
        messages = [tr(language, 'Сабақ бумасы мен жазба үлгісі жасалды: ', 'Созданы папки урока и шаблон заметок: ', 'Created lesson folders and notes template: ') + str(path)]
        for name in ('word', 'browser'):
            try:
                launch(name)
                messages.append(program_name(name) + ': ' + tr(language, 'ашуға жіберілді', 'команда отправлена', 'launch requested'))
            except (RuntimeError, OSError) as exc:
                messages.append(program_name(name) + ': ' + str(exc))
        return {'message': '\n'.join(messages), 'saved_path': str(path)}
    raise ValueError('Белгісіз пәрмен. Пәрмендер тізімін қараңыз.')
