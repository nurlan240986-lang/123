# JARVIS Windows 3.1

Қазақша Windows көмекшісі: жергілікті пәрмендер, CPU/RAM/диск көрсеткіштері, дауысты тану және OpenAI Responses API арқылы сұхбат.

1. Python 3.11+ орнатыңыз.
2. START.bat іске қосыңыз.
3. AI үшін SETUP_AI.bat ашып, API кілтін тек өз компьютеріңізде енгізіңіз.
4. Сұрақ қойыңыз. API пайдалану шығыны болады.

Толық нұсқаулық: [README_KZ.txt](README_KZ.txt). GitHub: [GITHUB_KZ.txt](GITHUB_KZ.txt).

API кілтін GitHub-қа жүктемеңіз. ai_config.local.json және .env файлдары .gitignore ішінде шығарылған. Кілт интерфейске берілмейді. Сұрақтар мен қысқа контекст OpenAI-ға жіберіледі.

Авто, Тек AI сұхбат және Тек компьютер пәрмендері режимдері бар. AI өздігінен компьютерде әрекет орындамайды.

Сервер тек 127.0.0.1 мекенжайында жұмыс істейді. Жоба жергілікті Windows компьютеріне арналған; GitHub Pages-та орындалмайды.

Тест: python -m unittest discover -s tests -v

API тесттері жасанды жауаптармен орындалады. Нақты қосылым үшін жарамды кілт, қолжетімді модель және API балансы қажет. Микрофон, Windows SAPI және бағдарлама ашу нақты Windows компьютерінде тексеріледі.

## JARVIS 3.0: desktop tools

Adds Excel, PowerPoint, Paint, File Explorer, Task Manager, Chrome, Edge, default browser and Windows Settings. Register additional local executable files with `SETUP_APPS.bat`.

Use the desktop tools panel or commands such as `Open Word and browser`, `Find file: *.pdf`, `Create folder: Word lesson`, `Save note: Tomorrow plan`, `Create system report`, and `Prepare lesson`. Kazakh and Russian equivalents are listed in the app and README_KZ.txt. Local actions do not require an API key.

Files are created in `JARVIS_Workspace`; filename search is bounded to that workspace and the user's Documents, Downloads and Desktop folders. The AI chat does not execute arbitrary code or control other applications' interfaces.

Upgrade all program files after stopping the server, retaining local configuration and workspace files. Real application launching requires Windows and the corresponding installed applications.

## AI websites and provider APIs

Open Gemini, ChatGPT, Perplexity, Copilot or Claude in the default browser using a button or a command such as `Open Gemini`. These actions open the website; users sign in and enter questions there.

For in-app answers, choose OpenAI, Gemini or Perplexity. Configure each provider through SETUP_AI.bat; existing OpenAI settings are preserved. Enable the web search checkbox to make that provider's search tool available. Returned citations are clickable, and Gemini search suggestions are sandboxed. Changing providers clears the current conversation to avoid forwarding its history to another service.

Default endpoints and model names follow the linked official docs in README_KZ.txt. Models, quotas, regions and search billing are governed by each provider. No paid requests or Windows hardware checks are included in the simulated tests.
