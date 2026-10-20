import getpass
import json
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def main():
    print('JARVIS AI setup / OpenAI Responses API')
    print('Create a key at https://platform.openai.com/api-keys')
    print('API usage may incur charges. Never upload your key to GitHub.')
    print('The key stays in ai_config.local.json on this computer.')
    print('The key will not appear while you type or paste it. Press Enter after pasting.')
    key = getpass.getpass('OpenAI API key: ').strip()
    if not key:
        print('No key entered. Existing settings were not changed.')
        return
    if any(c.isspace() for c in key):
        print('Invalid key: whitespace is not allowed. Run setup again.')
        return
    model = input('Model [gpt-5-mini]: ').strip() or 'gpt-5-mini'
    path = ROOT / 'ai_config.local.json'
    # Temporary file prevents an interrupted write from corrupting existing settings.
    temporary = path.with_suffix('.tmp')
    temporary.write_text(json.dumps({'api_key': key, 'model': model}, indent=2), encoding='utf-8')
    try:
        os.chmod(temporary, 0o600)
    except OSError:
        pass
    temporary.replace(path)
    print('Saved. Run START.bat, or refresh the open JARVIS page.')
    print('The connection will be tested when you send your first AI question.')


if __name__ == '__main__':
    try:
        main()
    except (KeyboardInterrupt, EOFError):
        print('\nSetup cancelled.')
