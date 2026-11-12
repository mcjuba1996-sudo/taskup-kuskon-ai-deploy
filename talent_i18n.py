"""Offline Talent UI translations. Database values and authored content stay intact."""
from functools import lru_cache
import json
from pathlib import Path
import re

import streamlit as st

LANGUAGES = {'kk': 'Қазақша', 'en': 'English', 'ru': 'Русский'}
LANGUAGE_KEY = '_talent_language'
ROOT = Path(__file__).resolve().parent


def language():
    selected = st.session_state.get(LANGUAGE_KEY, 'ru')
    return selected if selected in LANGUAGES else 'ru'


def language_picker():
    if st.session_state.get(LANGUAGE_KEY) not in LANGUAGES:
        st.session_state[LANGUAGE_KEY] = 'ru'
    st.selectbox('Қазақша / English / Русский', list(LANGUAGES),
                 format_func=LANGUAGES.get, key=LANGUAGE_KEY,
                 help=t('Перед сменой языка сохраните заполненную форму. Роль и текущая страница сохранятся.'))


@lru_cache(maxsize=1)
def catalogs():
    merged, demo = {}, {}
    for path in sorted((ROOT / 'locales').glob('talent_*.json')):
        entries = json.loads(path.read_text(encoding='utf-8'))
        for source, translations in entries.items():
            merged.setdefault(source, translations)
        if path.name == 'talent_demo.json':
            demo.update(entries)
    return merged, demo


def t(source, *, _lang=None, **values):
    if not isinstance(source, str):
        return str(source)
    lang = _lang or language()
    translated = source if lang == 'ru' else catalogs()[0].get(source, {}).get(lang, source)
    return translated.format(**values) if values else translated


def td(source, *, _lang=None):
    """Translate only exact, known demo text; never write a translation to storage."""
    if not isinstance(source, str):
        return source
    lang = _lang or language()
    if lang == 'ru':
        return source
    translated = catalogs()[1].get(source, {}).get(lang)
    if translated is not None:
        return translated
    parent = re.fullmatch(r'Родитель участника A-(\d+) · демо', source)
    if parent:
        return t('Родитель участника A-{pupil_id} · демо', _lang=lang, pupil_id=parent.group(1))
    return source


def error_text(message, *, _lang=None):
    """Localize known validation messages, including composed handoff errors."""
    lang = _lang or language()
    if lang == 'ru':
        return message
    direct = t(message, _lang=lang)
    if direct != message:
        return direct
    size = re.fullmatch(r'(.+): от (\d+) до (\d+) символов\.', message)
    if size:
        return t('{label}: от {minimum} до {maximum} символов.', _lang=lang,
                 label=t(size.group(1), _lang=lang), minimum=size.group(2), maximum=size.group(3))
    parts = re.split(r'(?<=\.)\s+', message)
    result = []
    for part in parts:
        missing = re.fullmatch(r'(.+): нужно не менее 20 символов перед отправкой\.', part)
        result.append(t('{label}: нужно не менее 20 символов перед отправкой.', _lang=lang,
                        label=t(missing.group(1), _lang=lang)) if missing else t(part, _lang=lang))
    return ' '.join(result)
