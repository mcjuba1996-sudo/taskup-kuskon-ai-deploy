"""Private drafts, explicit snapshot handoff and honest self-assessment exports."""
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import database as db
import personal_projects as personal
import talent_store as talent


class PersonalProjectTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix='taskup-projects-')
        self.addCleanup(temporary.cleanup)
        environment = patch.dict(os.environ, {'TASKUP_DB': str(Path(temporary.name) / 'test.db')})
        environment.start()
        self.addCleanup(environment.stop)
        talent.init()
        personal.init_projects()
        self.values = dict(title='Учебный анализ расписания',
            description='Проверяет пересечения занятий на синтетическом расписании.',
            evidence_url='https://example.com/synthetic-project',
            contribution='Сам написал проверку интервалов и разобрал граничные случаи.',
            tools_help='Использовал документацию Python и помощь наставника.',
            checks=['reproducible', 'personalcontribution'], source_version='demo-commit-v1')

    def create(self, student=105, **overrides):
        return personal.save_project(student, **{**self.values, **overrides})

    def get(self, project_id, student=105):
        return next(p for p in personal.projects(student) if p['id'] == project_id)

    def challenge(self):
        return talent.create_challenge(201, 'Отдельное задание для проекта',
            'Подготовьте учебный результат на синтетических данных и объясните решения.',
            'Python', '2 часа', 'Ссылка и описание учебного результата.', talent.CRITERIA)

    def test_empty_idempotent_namespace_and_private_listing(self):
        before = talent.stats()
        self.assertEqual(personal.projects(105), [])
        personal.init_projects()
        self.assertEqual(personal.projects(105), [])
        pid = self.create()
        self.assertEqual(self.get(pid)['checks'], self.values['checks'])
        self.assertEqual(personal.projects(101), [])
        with self.assertRaises(ValueError):
            personal.projects(201)
        self.assertEqual(talent.stats(), before)
        self.assertNotIn(105, {p['id'] for p in talent.discover(201)})

    def test_draft_needs_title_only_and_cannot_be_transferred(self):
        pid = self.create(description='', evidence_url='', contribution='', tools_help='', checks=[])
        draft = self.get(pid)
        self.assertEqual(len(personal.completeness(draft)), 3)
        self.assertIn('Черновик', personal.project_report(draft))
        with self.assertRaises(ValueError):
            personal.transfer_project(pid, 105, self.challenge(), 1)

    def test_owner_role_and_version_guards(self):
        pid = self.create()
        for student in (101, 201, 999):
            with self.subTest(student=student), self.assertRaises(ValueError):
                personal.save_project(student, **self.values, project_id=pid, expected_version=1)
        personal.save_project(105, **{**self.values, 'title': 'Обновлённый проект'},
                              project_id=pid, expected_version=1)
        self.assertEqual(self.get(pid)['version'], 2)
        for version in (None, 1, True, '2'):
            with self.subTest(version=version), self.assertRaises(ValueError):
                personal.save_project(105, **self.values, project_id=pid, expected_version=version)
        self.assertEqual(self.get(pid)['title'], 'Обновлённый проект')
        with self.assertRaises(ValueError):
            self.create(student=201)

    def test_validation_and_canonical_checklist(self):
        for changes in ({'title': 'ab'}, {'title': ' ' * 5}, {'description': 'x' * 5501},
                        {'evidence_url': 'javascript:alert(1)'}, {'contribution': None},
                        {'checks': ['verified']}, {'checks': ['tests', 'tests']},
                        {'checks': 'tests'}, {'checks': [True]}, {'source_version': 'x' * 201}):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                self.create(**changes)
        pid = self.create(checks=['limitations', 'reproducible'])
        self.assertEqual(self.get(pid)['checks'], ['reproducible', 'limitations'])
        with self.assertRaises(ValueError):
            personal.save_project(105, **self.values, expected_version=1)

    def test_report_ignores_forged_review_and_escapes_user_text(self):
        pid = self.create(title='<img src=x onerror=alert(1)>',
                          description='Текст\n# Подделанный системный заголовок')
        payload = {**self.get(pid), 'status': 'approved', 'reviewed_by': 'FORGED REVIEWER',
                   'ratings': [4, 4, 4], 'total': 100, 'verified': True}
        report = personal.project_report(payload)
        self.assertIn(personal.SELF_ASSESSMENT, report)
        self.assertIn('Отметки не проверены третьей стороной', report)
        self.assertNotIn('FORGED REVIEWER', report)
        self.assertNotIn('approved', report)
        self.assertNotIn('<img', report)
        self.assertNotIn('\n# Подделанный', report)
        self.assertIn('- [x] Я описал', report)
        self.assertIn('- [ ] Я проверил', report)

    def test_transfer_rejects_wrong_owner_stale_version_and_missing_challenge(self):
        pid = self.create()
        challenge_id = self.challenge()
        for student, version, cid in ((101, 1, challenge_id), (201, 1, challenge_id),
                                      (105, 0, challenge_id), (105, True, challenge_id), (105, 1, 999)):
            with self.subTest(student=student, version=version, cid=cid), self.assertRaises(ValueError):
                personal.transfer_project(pid, student, cid, version)
        self.assertEqual([s for s in talent.submissions(student_id=105)
                          if s['challenge_id'] == challenge_id], [])

    def test_transfer_snapshots_content_and_later_edits_do_not_mutate_submission(self):
        pid = self.create()
        cid = self.challenge()
        sid = personal.transfer_project(pid, 105, cid, 1)
        original = next(s for s in talent.submissions(student_id=105) if s['id'] == sid)
        self.assertEqual(original['source_version'], 'demo-commit-v1')
        self.assertEqual(original['status'], 'pending')
        self.assertIn(self.values['description'], original['description'])
        self.assertIn(self.values['contribution'], original['reflection'])
        self.assertIn('не внешняя оценка', original['reflection'])
        personal.save_project(105, **{**self.values, 'description': 'Совершенно новая версия описания результата.',
                                     'source_version': 'demo-commit-v2'},
                              project_id=pid, expected_version=1)
        unchanged = next(s for s in talent.submissions(student_id=105) if s['id'] == sid)
        self.assertEqual(unchanged, original)
        self.assertEqual(self.get(pid)['version'], 2)
        with self.assertRaises(ValueError):
            personal.transfer_project(pid, 105, cid, 2)

    def test_transfer_cannot_overwrite_existing_approved_or_pending_work(self):
        for student, cid in ((101, 1), (105, 2)):
            pid = self.create(student=student)
            before = talent.submissions(student_id=student)
            with self.subTest(student=student), self.assertRaises(ValueError):
                personal.transfer_project(pid, student, cid, 1)
            self.assertEqual(talent.submissions(student_id=student), before)

    def test_requested_revision_can_be_sent_without_rewriting_prior_history(self):
        pid = self.create()
        cid = self.challenge()
        sid = personal.transfer_project(pid, 105, cid, 1)
        initial = next(s for s in talent.submissions(student_id=105) if s['id'] == sid)
        first_snapshot = talent.history(sid, 105)[0]['snapshot']
        talent.review_work(sid, 201, initial['version'], [2, 2, 1],
            'Нужно подробнее объяснить проверки и полученную помощь.', False,
            criterion_evidence=['Основной сценарий описан, примеры требуют дополнения.',
                'Не хватает сравнения решения с альтернативным подходом.',
                'Полученная помощь указана, но личные изменения не раскрыты.'],
            reviewer_name='Демо проверяющий', reviewer_role='Наставник учебной программы')
        personal.save_project(105, **{**self.values, 'description': 'Добавлены воспроизводимые проверки и примеры результата.',
                                     'source_version': 'demo-commit-v2'},
                              project_id=pid, expected_version=1)
        self.assertEqual(personal.transfer_project(pid, 105, cid, 2), sid)
        revised = next(s for s in talent.submissions(student_id=105) if s['id'] == sid)
        self.assertEqual(revised['source_version'], 'demo-commit-v2')
        self.assertEqual(revised['status'], 'pending')
        self.assertEqual(revised['ratings'], [])
        self.assertEqual(talent.history(sid, 105)[0]['snapshot'], first_snapshot)

    def test_maximum_draft_fields_fit_submission_limits(self):
        pid = self.create(title='П' * 140, description='О' * 5500, contribution='В' * 2500,
                          tools_help='И' * 1000, checks=[c['id'] for c in personal.CHECKLIST])
        sid = personal.transfer_project(pid, 105, self.challenge(), 1)
        result = next(s for s in talent.submissions(student_id=105) if s['id'] == sid)
        self.assertLessEqual(len(result['description']), 6000)
        self.assertLessEqual(len(result['reflection']), 4000)

    def test_transfer_failure_rolls_back_without_mutating_project(self):
        pid = self.create()
        cid = self.challenge()
        before = self.get(pid)
        def fail(*args, _conn=None, **kwargs):
            _conn.execute('UPDATE talent_personal_projects SET title=? WHERE id=?', ('Should roll back', pid))
            raise ValueError('Submission failed')
        with patch.object(talent, 'submit_work', side_effect=fail), self.assertRaises(ValueError):
            personal.transfer_project(pid, 105, cid, 1)
        self.assertEqual(self.get(pid), before)


if __name__ == '__main__':
    unittest.main()
