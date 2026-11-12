"""Offline product flows with independent SQLite databases for each test."""
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from streamlit.testing.v1 import AppTest
import talent_store as store

ROOT = Path(__file__).resolve().parents[1]


class TalentUIFlowTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix='taskup-talent-ui-')
        self.addCleanup(temporary.cleanup)
        environment = patch.dict(os.environ, {
            'TASKUP_DB': str(Path(temporary.name) / 'test.db'),
            'OPENAI_API_KEY': '',
        })
        environment.start()
        self.addCleanup(environment.stop)
        self.app = AppTest.from_file(str(ROOT / 'app.py'), default_timeout=30).run()
        self.healthy()

    def healthy(self):
        self.assertFalse(self.app.exception, [item.message for item in self.app.exception])

    def click(self, key):
        self.app.button(key=key).click().run()
        self.healthy()

    def submit(self, form, label):
        buttons = [b for b in self.app.button
                   if b.label == label and str(b.key).startswith(f'FormSubmitter:{form}-')]
        self.assertEqual(len(buttons), 1, [(b.key, b.label) for b in self.app.button])
        buttons[0].click().run()
        self.healthy()

    def enter(self, role, person=None):
        if 'tt_role' in self.app.session_state and self.app.session_state['tt_role'] is not None:
            self.click('tt_change_role')
        self.click(f'tt_enter_{role}')
        if person is not None:
            self.app.selectbox(key=f'tt_person_{role}').set_value(person).run()
            self.healthy()

    def rendered(self):
        return '\n'.join(str(x.value) for kind in ('markdown', 'caption', 'subheader', 'info', 'warning', 'success', 'error')
                         for x in getattr(self.app, kind))

    def fill_work(self, challenge_id, description='Собраны расчёты, два графика и инструкция проверки на тестовой таблице.'):
        self.app.text_input(key=f'tt_url_{challenge_id}').set_value('https://example.com/talent-project')
        self.app.text_area(key=f'tt_description_{challenge_id}').set_value(description)
        self.app.text_area(key=f'tt_reflection_{challenge_id}').set_value(
            'Самостоятельно подготовлены расчёты и пояснения. С подсказкой проверены крайние случаи и исправлены ошибки.')

    def review(self, work, scores, approve):
        for index, score in enumerate(scores):
            self.app.select_slider(key=f'tt_score_{work["id"]}_{index}_{work["version"]}').set_value(score)
        self.app.text_area(key=f'tt_feedback_{work["id"]}_{work["version"]}').set_value(
            'Проверены расчёты и примеры результата. В пояснении видны подход и личный вклад; ограничения указаны.')
        self.app.checkbox(key=f'tt_checked_{work["id"]}_{work["version"]}').check()
        self.submit(f'tt_review_{work["id"]}_{work["version"]}', 'Принять работу' if approve else 'Вернуть на доработку')

    def test_all_pages_both_roles_and_identity_consent_isolation(self):
        self.assertIn('Твои доказательства', self.rendered())
        self.enter('student')
        for page in ('catalog', 'works', 'portfolio', 'invitations', 'about'):
            self.click(f'tt_nav_{page}')
            self.assertEqual(self.app.session_state['tt_page'], page)
        self.click('tt_nav_portfolio')
        self.assertTrue(self.app.checkbox(key='tt_share_profile').value)
        self.assertTrue(self.app.checkbox(key='tt_guardian_consent').value)
        self.app.selectbox(key='tt_person_student').set_value(104).run()
        self.healthy()
        self.assertFalse(self.app.checkbox(key='tt_share_profile').value)
        self.assertFalse(self.app.checkbox(key='tt_guardian_consent').value)
        self.assertIn(store.person(104)['name'], self.rendered())
        self.assertNotIn(store.person(101)['name'], self.rendered())
        self.enter('buyer')
        for page in ('review', 'challenges', 'discovery', 'invitations', 'about'):
            self.click(f'tt_nav_{page}')
            self.assertEqual(self.app.session_state['tt_page'], page)

    def test_submission_revision_review_visibility_invitation_full_cycle(self):
        self.enter('student', 105)
        self.fill_work(1)
        before = len(store.submissions(student_id=105))
        self.submit('tt_submit_1', 'Отправить на проверку')
        self.assertIn('Подтвердите передачу', self.rendered())
        self.assertEqual(len(store.submissions(student_id=105)), before)
        self.app.checkbox(key='tt_submit_consent_1').check()
        self.submit('tt_submit_1', 'Отправить на проверку')
        work = next(w for w in store.submissions(student_id=105) if w['challenge_id'] == 1)
        self.assertEqual(work['status'], 'pending')
        self.enter('buyer', 201)
        self.review(work, [0, 0, 0], True)
        self.assertTrue(self.app.error)
        work = next(w for w in store.submissions(student_id=105) if w['challenge_id'] == 1)
        self.assertEqual(work['status'], 'pending')
        self.review(work, [1, 2, 1], False)
        work = next(w for w in store.submissions(student_id=105) if w['challenge_id'] == 1)
        self.assertEqual(work['status'], 'changes_requested')
        self.enter('student', 105)
        self.fill_work(1, 'Исправлены расчёты, добавлены тестовые случаи и подробная инструкция воспроизведения результата.')
        self.app.checkbox(key='tt_submit_consent_1').check()
        self.submit('tt_submit_1', 'Отправить на проверку')
        revised = next(w for w in store.submissions(student_id=105) if w['challenge_id'] == 1)
        self.assertEqual(revised['id'], work['id'])
        self.assertGreater(revised['version'], work['version'])
        self.enter('buyer', 201)
        self.review(revised, [4, 3, 4], True)
        accepted = next(w for w in store.submissions(student_id=105) if w['challenge_id'] == 1)
        self.assertEqual(accepted['status'], 'approved')
        self.assertNotIn(105, [p['id'] for p in store.discover(201)])

        self.enter('student', 105)
        self.click('tt_nav_portfolio')
        self.assertIn('Результат принят', self.rendered())
        self.app.checkbox(key='tt_share_profile').check()
        self.submit('tt_visibility_105', 'Сохранить видимость')
        self.assertNotIn(105, [p['id'] for p in store.discover(201)])
        self.app.checkbox(key='tt_guardian_consent').check()
        self.submit('tt_visibility_105', 'Сохранить видимость')
        self.assertIn(105, [p['id'] for p in store.discover(201)])

        self.enter('buyer', 201)
        self.click('tt_nav_discovery')
        self.assertIn(store.person(105)['name'], self.rendered())
        self.click('tt_save_105')
        self.app.checkbox(key='tt_saved_only').check().run()
        self.healthy()
        self.assertIn(store.person(105)['name'], self.rendered())
        self.assertNotIn(store.person(101)['name'], self.rendered())
        self.app.text_area(key='tt_invite_message_105').set_value(
            'Приглашаем обсудить учебную программу. Следующий шаг — выбрать интересующее направление в демо.')
        self.submit('tt_invite_105', 'Отправить приглашение в демо')
        invitation = store.invitations(student_id=105)[0]
        self.assertEqual(invitation['status'], 'pending')
        self.enter('student', 105)
        self.click('tt_nav_invitations')
        self.click(f'tt_accept_{invitation["id"]}')
        self.assertEqual(store.invitations(student_id=105)[0]['status'], 'accepted')
        self.assertIn('Принято', self.rendered())

    def test_buyer_creates_challenge_and_student_can_find_it(self):
        self.enter('buyer', 202)
        self.click('tt_nav_challenges')
        self.app.text_input(key='tt_challenge_title').set_value('Прототип записи в школьный клуб')
        self.app.text_area(key='tt_challenge_brief').set_value(
            'Разработайте прототип понятной формы записи в школьный клуб на вымышленных данных для тестового сценария.')
        self.app.selectbox(key='tt_challenge_skill').set_value('UX/UI')
        self.app.text_area(key='tt_challenge_deliverable').set_value('Три экрана, сценарий проверки и описание решений.')
        self.submit('tt_create_challenge', 'Опубликовать задание')
        created = next(c for c in store.challenges(buyer_id=202) if c['title'] == 'Прототип записи в школьный клуб')
        self.assertEqual([c['weight'] for c in created['criteria']], [40, 35, 25])
        self.enter('student', 104)
        self.app.selectbox(key='tt_catalog_skill').set_value('UX/UI').run()
        self.healthy()
        self.assertIn(created['title'], self.rendered())
        self.assertEqual(len(self.app.text_input), 1)
        self.assertEqual(self.app.text_input[0].key, f'tt_url_{created["id"]}')


if __name__ == '__main__':
    unittest.main()
