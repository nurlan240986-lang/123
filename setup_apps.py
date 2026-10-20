"""Register executable files explicitly selected by the local user."""
from pathlib import Path
import tkinter as tk
from tkinter import filedialog, messagebox
import desktop


def main():
    window = tk.Tk()
    window.title('JARVIS — бағдарламаларды қосу')
    window.geometry('660x500')
    frame = tk.Frame(window, padx=20, pady=15)
    frame.pack(fill='both', expand=True)
    tk.Label(frame, text='Жеке бағдарламаларды тіркеу', font=('Segoe UI', 14, 'bold')).pack(anchor='w')
    tk.Label(frame, text='Атауын жазыңыз, .exe файлын таңдаңыз және шақыру сөздерін енгізіңіз.\nМысалы: «Телеграм»; шақыру атаулары: телеграм, telegram.', justify='left').pack(anchor='w', pady=8)
    tk.Label(frame, text='Бағдарлама атауы').pack(anchor='w')
    name = tk.Entry(frame)
    name.pack(fill='x')
    tk.Label(frame, text='Осы компьютердегі .exe файлы').pack(anchor='w', pady=(7, 0))
    path = tk.Entry(frame)
    path.pack(fill='x')

    def browse():
        chosen = filedialog.askopenfilename(parent=window, title='Бағдарламаның .exe файлын таңдаңыз', filetypes=[('Windows бағдарламасы', '*.exe')])
        if chosen:
            path.delete(0, 'end')
            path.insert(0, chosen)
            if not name.get().strip():
                name.insert(0, Path(chosen).stem)

    tk.Button(frame, text='Файлды таңдау…', command=browse).pack(anchor='e', pady=4)
    tk.Label(frame, text='Пәрменде айтылатын атаулар (үтірмен бөліңіз, 1–5 атау)').pack(anchor='w')
    aliases = tk.Entry(frame)
    aliases.pack(fill='x')
    entries = tk.Listbox(frame, height=6)
    entries.pack(fill='both', expand=True, pady=10)
    items = []

    def refresh():
        nonlocal items
        items = desktop.read_apps()
        entries.delete(0, 'end')
        for item in items:
            entries.insert('end', item['name'] + ' — ' + ', '.join(item['aliases']))

    def add():
        try:
            desktop.register_app(name.get(), path.get(), aliases.get().split(','))
            refresh()
        except (OSError, ValueError) as exc:
            messagebox.showerror('Сақталмады', str(exc), parent=window)
            return
        name.delete(0, 'end')
        path.delete(0, 'end')
        aliases.delete(0, 'end')
        messagebox.showinfo('Дайын', 'Бағдарлама тіркелді. JARVIS бетіндегі «Тізімді жаңарту» батырмасын басыңыз.', parent=window)

    def remove():
        selected = entries.curselection()
        if not selected:
            return
        try:
            desktop.write_apps([item for i, item in enumerate(items) if i != selected[0]])
            refresh()
        except (OSError, ValueError) as exc:
            messagebox.showerror('Сақталмады', str(exc), parent=window)

    buttons = tk.Frame(frame)
    buttons.pack(fill='x')
    tk.Button(buttons, text='Таңдалған тіркеуді алып тастау', command=remove).pack(side='left')
    tk.Button(buttons, text='Бағдарламаны қосу', command=add).pack(side='right')
    try:
        refresh()
    except ValueError as exc:
        messagebox.showerror('Баптау оқылмады', str(exc), parent=window)
        window.destroy()
        return
    window.mainloop()


if __name__ == '__main__':
    main()
