"""Configure a local API key without echoing it to the terminal."""
import getpass
import json
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent


def save(key, model):
    key = key.strip()
    model = model.strip() or 'gpt-5-mini'
    if not key or any(c.isspace() for c in key):
        raise ValueError('Кілт бос болмауы және бос орын қамтымауы керек.')
    path = ROOT / 'ai_config.local.json'
    temporary = path.with_suffix('.tmp')
    temporary.write_text(json.dumps({'api_key': key, 'model': model}, indent=2), encoding='utf-8')
    try:
        os.chmod(temporary, 0o600)
    except OSError:
        pass
    temporary.replace(path)


def gui():
    import tkinter as tk
    from tkinter import messagebox

    window = tk.Tk()
    window.title('JARVIS — AI қосу')
    window.geometry('470x255')
    window.resizable(False, False)
    frame = tk.Frame(window, padx=22, pady=18)
    frame.pack(fill='both', expand=True)
    tk.Label(frame, text='OpenAI API кілтін енгізіңіз', font=('Segoe UI', 13, 'bold')).pack(anchor='w')
    tk.Label(frame, text='Кілт тек осы компьютерде сақталады. GitHub-қа жібермеңіз.', wraplength=420).pack(anchor='w', pady=(5, 12))
    key_entry = tk.Entry(frame, show='•', width=54)
    key_entry.pack(fill='x')
    tk.Label(frame, text='Модель (әдепкі: gpt-5-mini)').pack(anchor='w', pady=(12, 2))
    model_entry = tk.Entry(frame)
    model_entry.insert(0, 'gpt-5-mini')
    model_entry.pack(fill='x')

    def submit():
        try:
            save(key_entry.get(), model_entry.get())
        except (ValueError, OSError) as exc:
            messagebox.showerror('Баптау сақталмады', str(exc), parent=window)
            return
        key_entry.delete(0, 'end')
        messagebox.showinfo('Дайын', 'Кілт сақталды. START.bat ашыңыз немесе JARVIS бетін жаңартыңыз.', parent=window)
        window.destroy()

    tk.Button(frame, text='Кілтті сақтау', command=submit).pack(anchor='e', pady=(15, 0))
    key_entry.focus_set()
    window.mainloop()


def console():
    print('JARVIS AI setup / OpenAI Responses API')
    print('Create a key at https://platform.openai.com/api-keys')
    print('The key will not appear. In Windows console, right-click to paste, then press Enter.')
    key = getpass.getpass('OpenAI API key: ')
    if not key.strip():
        print('No key entered. Existing settings were not changed.')
        return
    model = input('Model [gpt-5-mini]: ')
    save(key, model)
    print('Saved. Run START.bat, or refresh the open JARVIS page.')


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
