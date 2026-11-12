"""Localization preserves canonical state, authored text and export safeguards."""
import copy
import json
from pathlib import Path
import string
import unittest
from unittest.mock import patch

import personal_projects as projects
from talent_evidence_ui import passport_report
import talent_i18n as i18n
import talent_store as store
from tests.test_talent_ui import TalentUIBase

ROOT = Path(__file__).resolve().parents[1]


class TalentTranslationTests(unittest.TestCase):
    def setUp(self):
        i18n.catalogs.cache_clear()

    def test_catalog_placeholders_and_explicit_language(self):
        formatter = string.Formatter()
        fields = lambda text: [(field, spec, conv) for _, field, spec, conv in formatter.parse(text)
                               if field is not None]
        merged = {}
        paths = sorted((ROOT / 'locales').glob('talent_*.json'))
        self.assertTrue(paths)
        for path in paths:
            catalog = json.loads(path.read_text(encoding='utf-8'))
            for source, translations in catalog.items():
                with self.subTest(catalog=path.name, source=source):
                    if source in merged:
                        self.assertEqual(translations, merged[source], 'Duplicate keys must have identical translations.')
                    merged[source] = translations
                for lang in ('en', 'kk'):
                    with self.subTest(catalog=path.name, source=source, lang=lang):
                        self.assertTrue(translations[lang])
                        self.assertCountEqual(fields(source), fields(translations[lang]))
        for lang, expected in (('ru', 'Сохранить проект'), ('en', 'Save project'), ('kk', 'Жобаны сақтау')):
            self.assertEqual(i18n.t('Сохранить проект', _lang=lang), expected)
        authored = 'Мой неизменённый текст — Қазақша / English {braces}'
        self.assertEqual(i18n.t('Ответ: {answer}', _lang='en', answer=authored), 'Answer: ' + authored)
        self.assertEqual(i18n.t('unknown {literal}', _lang='kk'), 'unknown {literal}')

    def test_demo_translation_does_not_translate_arbitrary_authored_content(self):
        source = 'Моё собственное описание, которое я хочу сохранить: Қазақша, English.'
        for lang in ('ru', 'en', 'kk'):
            self.assertEqual(i18n.td(source, _lang=lang), source)
            # A UI label is not automatically a known demo field.
            self.assertEqual(i18n.td('Сохранить проект', _lang=lang), 'Сохранить проект')

    def test_personal_export_localizes_labels_but_quotes_authored_text(self):
        project = {
            'title': '<img src=x onerror=alert(1)>',
            'description': 'Авторский текст на русском\n# Ложный заголовок\n[ссылка](javascript:alert(1))',
            'evidence_url': 'https://example.com/result',
            'contribution': 'Жеке үлес: мой неизменяемый рассказ об участии.',
            'tools_help': 'English tool name and русский комментарий',
            'checks': ['reproducible'], 'source_version': 'commit-{author-value}',
        }
        original = copy.deepcopy(project)
        for lang, heading, self_check in (
                ('ru', '# Мой проект', 'Самооценка. Внешняя проверка не проводилась'),
                ('en', '# My project', 'Self-assessment. No external review has taken place'),
                ('kk', '# Менің жобам', 'Өзін-өзі бағалау. Сыртқы тексеру жүргізілген жоқ')):
            report = projects.project_report(project, lang=lang)
            self.assertTrue(report.startswith(heading + '\n'))
            self.assertIn(self_check, report)
            self.assertIn('Авторский текст на русском', report)
            self.assertIn('English tool name and русский комментарий', report)
            self.assertNotIn('<img', report)
            self.assertNotIn('\n# Ложный', report)
            self.assertNotIn('[ссылка](javascript:', report)
            self.assertIn('> \\# Ложный заголовок', report)
        self.assertEqual(project, original)
        with patch.object(i18n, 'language', return_value='kk'):
            self.assertTrue(projects.project_report(project).startswith('# Мой проект\n'))

    def test_incomplete_export_uses_translated_requirements(self):
        draft = {'title': 'Авторский черновик'}
        for lang in ('en', 'kk'):
            report = projects.project_report(draft, lang=lang)
            self.assertIn('Авторский черновик', report)
            for message in projects.completeness(draft):
                self.assertNotIn(message, report)
                self.assertIn(i18n.t(message, _lang=lang), report)
            self.assertIn(projects._quoted('', lang=lang), report)

    def test_passport_labels_use_requested_language_without_rewriting_evidence(self):
        work = {
            'id': 7, 'challenge_title': 'Моё авторское задание', 'work_revision': 2,
            'evidence_url': 'https://example.com/work', 'source_version': 'immutable-commit',
            'description': 'Авторское описание без автоперевода.', 'reflection': 'Мой личный вклад остаётся моим текстом.',
            'total': 75, 'criteria': [{'label': 'Мой критерий', 'weight': 100}], 'ratings': [3],
            'criterion_evidence': ['Моё наблюдение по критерию.'], 'feedback': 'Комментарий автора проверки.',
            'reviewer_name': 'Тестовый проверяющий', 'reviewer_role': 'Моя указанная роль',
            'buyer_name': 'Моя организация', 'reviewed_at': 'demo-time', 'review_limitations': 'Мои ограничения.',
            'understanding_status': 'confirmed',
        }
        defense = {'work_revision': 2, 'question': 'Мой вопрос?', 'change_request': 'Моё изменение.',
                   'answer': 'Мой ответ.', 'evidence_url': 'https://example.com/change',
                   'observations': 'Мои наблюдения.', 'reviewer_name': 'Тестовый проверяющий',
                   'reviewer_role': 'Моя указанная роль', 'limitations': 'Мои ограничения.'}
        original = copy.deepcopy(work)
        with patch('talent_evidence_ui.store.defense_rounds', return_value=[defense]):
            for lang, heading in (('ru', '# Паспорт работы — ДЕМО'), ('en', '# Work passport — DEMO'),
                                  ('kk', '# Жұмыс паспорты — ДЕМО')):
                report = passport_report(work, {'name': 'Тестовый участник'}, 101, lang=lang)
                self.assertTrue(report.startswith(heading + '\n'))
                self.assertIn(i18n.t('Понимание решения проверено', _lang=lang), report)
                for value in ('Мой критерий', 'Моё наблюдение по критерию.', 'Мой вопрос?',
                              'Мой ответ.', 'Моя указанная роль', 'immutable-commit'):
                    self.assertIn(value, report)
            with patch.object(i18n, 'language', return_value='en'):
                self.assertTrue(passport_report(work, {'name': 'Участник'}, 101).startswith('# Паспорт работы'))
        self.assertEqual(work, original)


class TalentLanguageStateTests(TalentUIBase):
    def setUp(self):
        super().setUp()
        # AppTest serializes format_func outside ScriptRunContext, where the
        # global Streamlit proxy has no app session. Bind it to this test's
        # real session; the browser and the app runner already have that context.
        current = lambda: self.app.session_state[i18n.LANGUAGE_KEY]
        override = patch.object(i18n, 'language', side_effect=current)
        override.start()
        self.addCleanup(override.stop)

    def switch(self, lang):
        self.app.selectbox(key=i18n.LANGUAGE_KEY).set_value(lang).run()
        self.healthy()
        self.assertEqual(self.app.session_state[i18n.LANGUAGE_KEY], lang)

    def test_canonical_filters_identity_and_page_survive_language_switch(self):
        self.enter('student', 104)
        self.app.selectbox(key='tt_catalog_skill').set_value('Python и автоматизация').run()
        self.app.selectbox(key='tt_catalog_kind').set_value('agency').run()
        for lang in ('en', 'kk', 'ru'):
            self.switch(lang)
            self.assertEqual(self.app.session_state['tt_role'], 'student')
            self.assertEqual(self.app.session_state['tt_page'], 'catalog')
            self.assertEqual(self.app.selectbox(key='tt_person_student').value, 104)
            self.assertEqual(self.app.selectbox(key='tt_catalog_skill').value, 'Python и автоматизация')
            self.assertEqual(self.app.selectbox(key='tt_catalog_kind').value, 'agency')
        self.switch('kk')
        self.enter('buyer', 202)
        self.assertEqual(self.app.session_state[i18n.LANGUAGE_KEY], 'kk')
        self.app.selectbox(key='tt_review_filter').set_value('Все работы').run()
        self.switch('en')
        self.assertEqual(self.app.selectbox(key='tt_review_filter').value, 'Все работы')
        self.assertEqual(self.app.selectbox(key='tt_person_buyer').value, 202)

    def test_personal_form_values_and_saved_text_survive_switch(self):
        self.enter('student', 105)
        self.click('tt_nav_projects')
        title = 'Мой текст / Қазақша / English'
        description = 'Это введённое автором описание, которое нельзя переводить.'
        self.app.text_input(key='tt_project_new_0_title').set_value(title)
        self.app.text_area(key='tt_project_new_0_description').set_value(description)
        self.app.checkbox(key='tt_project_new_0_reproducible').check()
        self.submit('tt_project_new_0', 'Сохранить проект')
        saved = projects.projects(105)[0]
        prefix = f'tt_project_{saved["id"]}_1'
        for lang in ('en', 'kk', 'ru', 'en'):
            self.switch(lang)
            self.assertEqual(self.app.session_state['tt_page'], 'projects')
            self.assertEqual(self.app.text_input(key=prefix + '_title').value, title)
            self.assertEqual(self.app.text_area(key=prefix + '_description').value, description)
            self.assertTrue(self.app.checkbox(key=prefix + '_reproducible').value)
            self.assertEqual(projects.projects(105)[0], saved)
        self.assertEqual((saved['title'], saved['description']), (title, description))
        self.assertEqual(saved['checks'], ['reproducible'])
        self.switch('kk')
        self.assertEqual(projects.projects(105)[0], saved)
        self.assertEqual(self.app.text_input(key=f'tt_project_{saved["id"]}_1_title').value, title)

    def test_defense_verdict_remains_canonical_and_submits_in_english(self):
        work = next(w for w in store.submissions(student_id=105) if w['status'] == 'pending')
        did = store.request_defense(work['id'], 201, work['version'],
            'Почему в вашем решении соседние интервалы не пересекаются?',
            'Добавьте отдельную проверку для разных кабинетов.')
        store.answer_defense(did, 105, 1, 'Время окончания одного интервала равно началу другого.',
            'Добавлена проверка кабинета и воспроизводимый пример результата.', 'https://example.com/defense')
        self.enter('buyer', 201)
        observations = 'Автор объяснил границу интервала и показал результат отдельной проверки кабинета.'
        for lang in ('kk', 'en'):
            self.switch(lang)
            self.assertEqual(self.app.radio(key=f'tt_defense_verdict_{did}').value, 'Нужно уточнение')
            self.assertIn(i18n.t('Понимание показано', _lang=lang), self.app.radio(key=f'tt_defense_verdict_{did}').options)
        self.app.text_area(key=f'tt_defense_observation_{did}').set_value(observations)
        self.app.text_input(key=f'tt_defense_reviewer_{did}').set_value('Демо эксперт')
        self.app.text_input(key=f'tt_defense_role_{did}').set_value('Наставник Python')
        self.app.radio(key=f'tt_defense_verdict_{did}').set_value('Понимание показано')
        self.submit(f'tt_defense_assess_{did}_2', 'Save observations')
        result = store.defense_rounds(work['id'], 201)[0]
        self.assertEqual(result['status'], 'confirmed')
        self.assertEqual(result['observations'], observations)
        self.assertEqual(result['reviewer_name'], 'Демо эксперт')


if __name__ == '__main__':
    unittest.main()
