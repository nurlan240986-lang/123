"""Supported conversation locales shared by commands, chat and Windows speech."""
SUPPORTED = {'kk-KZ': 'Kazakh', 'ru-RU': 'Russian', 'en-US': 'English'}


def validate(language):
    if not isinstance(language, str) or language not in SUPPORTED:
        raise ValueError('Тіл жарамсыз. Қазақша, орысша немесе ағылшынша таңдаңыз.')
    return language
