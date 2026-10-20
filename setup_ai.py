"""Configure provider-specific keys locally without showing existing secrets."""
import getpass
import json
import os
from pathlib import Path
import sys
import webbrowser
import ai_chat

ROOT = Path(__file__).resolve().parent


def save(key, model, provider='openai'):
    provider = ai_chat.validate_provider(provider)
    path = ROOT / 'ai_config.local.json'
    config = {}
    if path.exists():
        try:
            config = json.loads(path.read_text(encoding='utf-8-sig'))
        except (ValueError, OSError):
            raise ValueError('Қазіргі баптау файлы оқылмады. Оның сақтық көшірмесін жасап, пішімін тексеріңіз.') from None
    if not isinstance(config, dict) or not isinstance(config.get('providers', {}), dict):
        raise ValueError('AI баптау пішімі жарамсыз.')
    entries = config.setdefault('providers', {})
    existing = entries.get(provider, {})
    if not isinstance(existing, dict):
        raise ValueError('Платформа баптауы жарамсыз.')
    previous = existing.get('api_key', config.get('api_key', '') if provider == 'openai' else '')
    key = key.strip() or previous
    model = model.strip() or ai_chat.PROVIDERS[provider]['model']
    if not isinstance(key, str) or not key or any(c.isspace() for c in key) or not key.isascii() or any(ord(c) < 32 for c in key):
        raise ValueError('Кілтті енгізіңіз. Кілт бос орын қамтымауы керек.')
    if len(model) > 150:
        raise ValueError('Модель атауы тым ұзын.')
    entries[provider] = {'api_key': key, 'model': model}
    if provider == 'openai':
        config.update(api_key=key, model=model)
    temporary = path.with_suffix('.tmp')
    temporary.write_text(json.dumps(config, ensure_ascii=False, indent=2), encoding='utf-8')
    try:
        os.chmod(temporary, 0o600)
    except OSError:
        pass
    temporary.replace(path)


def gui():
    import tkinter as tk
    from tkinter import ttk, messagebox
    window = tk.Tk()
    window.title('JARVIS — ЖИ платформаларын қосу')
    window.geometry('570x380')
    window.resizable(False, False)
    frame = tk.Frame(window, padx=22, pady=18)
    frame.pack(fill='both', expand=True)
    tk.Label(frame, text='OpenAI / Gemini / Perplexity', font=('Segoe UI', 14, 'bold')).pack(anchor='w')
    tk.Label(frame, text='Әр платформаның өз API кілті керек. Кілт осы компьютерде сақталады.\nAPI сұрақтары мен интернеттен іздеу қызмет шарттарына сай есептеледі.', justify='left', wraplength=520).pack(anchor='w', pady=(5, 10))
    provider = ttk.Combobox(frame, state='readonly', values=['OpenAI', 'Gemini', 'Perplexity'])
    provider.set('OpenAI')
    provider.pack(fill='x')
    tk.Label(frame, text='Жаңа API кілті (бар кілтті сақтасаңыз, бос қалдырыңыз)').pack(anchor='w', pady=(10, 2))
    key_entry = tk.Entry(frame, show='•')
    key_entry.pack(fill='x')
    tk.Label(frame, text='Модель атауы').pack(anchor='w', pady=(10, 2))
    model_entry = tk.Entry(frame)
    model_entry.pack(fill='x')
    status = tk.Label(frame, text='', anchor='w', justify='left')
    status.pack(anchor='w', pady=7)

    def refresh(event=None):
        current = provider.get().lower()
        key_entry.delete(0, 'end')
        try:
            key, model = ai_chat.settings(current)
            status.config(text='Кілт сақталған.' if key else 'Бұл платформаға кілт әлі енгізілмеген.')
        except ValueError:
            model = ai_chat.PROVIDERS[current]['model']
            status.config(text='Баптау файлын тексеріңіз.')
        model_entry.delete(0, 'end')
        model_entry.insert(0, model)

    def submit():
        try:
            save(key_entry.get(), model_entry.get(), provider.get().lower())
        except (ValueError, OSError) as exc:
            messagebox.showerror('Сақталмады', str(exc), parent=window)
            return
        refresh()
        messagebox.showinfo('Дайын', 'Баптау сақталды. JARVIS бетінен осы ЖИ платформасын таңдаңыз.\nБайланыс алғашқы сұрақта тексеріледі.', parent=window)

    row = tk.Frame(frame)
    row.pack(fill='x', pady=8)
    tk.Button(row, text='Кілт алу бетін ашу', command=lambda: webbrowser.open(ai_chat.PROVIDERS[provider.get().lower()]['key_url'])).pack(side='left')
    tk.Button(row, text='Баптауды сақтау', command=submit).pack(side='right')
    provider.bind('<<ComboboxSelected>>', refresh)
    refresh()
    window.mainloop()


def console():
    print('JARVIS AI setup: OpenAI / Gemini / Perplexity')
    provider = input('Provider [openai]: ').strip().lower() or 'openai'
    ai_chat.validate_provider(provider)
    print('Create a key at ' + ai_chat.PROVIDERS[provider]['key_url'])
    print('The key is hidden. Paste, then press Enter. A blank entry retains a saved key.')
    key = getpass.getpass('API key: ')
    model = input('Model [' + ai_chat.PROVIDERS[provider]['model'] + ']: ')
    save(key, model, provider)
    print('Saved. Select this provider in JARVIS. The first question tests the connection.')


if __name__ == '__main__':
    try:
        if sys.platform == 'win32':
            try:
                gui()
            except ImportError:
                console()
        else:
            console()
    except (KeyboardInterrupt, EOFError):
        print('\nSetup cancelled.')
    except ValueError as exc:
        print('Setup failed:', exc)
