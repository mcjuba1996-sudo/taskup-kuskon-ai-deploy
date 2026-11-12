"""Evidence review, observed defense, immutable chronology, and access tests."""
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import database as db
import talent_store as talent


REVIEW = dict(
    criterion_evidence=[
        'В report.md показан запуск пяти сценариев; вывод совпал с ожиданием.',
        'В README описаны сравнение границ интервалов и ограничение формата.',
        'В рефлексии перечислены личные изменения, ошибки и полученная помощь.',
    ],
    reviewer_name='Алия · демо', reviewer_role='Наставник Python-программы',
    review_limits='Наблюдения по предоставленным материалам; личность не проверялась.',
)
QUESTION = 'Почему граница конца одного занятия не конфликтует с началом следующего?'
CHANGE = 'Добавьте пример пустого расписания и покажите результат запуска проверки.'
ANSWER = 'Интервалы полуоткрытые, поэтому общая граница не является пересечением.'
CHANGE_DESCRIPTION = 'Добавлен тест пустого расписания. Выполнен запуск, получен пустой список конфликтов.'
OBSERVATIONS = 'Участник объяснил полуоткрытые интервалы и показал запуск нового теста с пустым расписанием.'


class TalentDefenseTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix='taskup-defense-')
        self.addCleanup(temporary.cleanup)
        environment = patch.dict(os.environ, {'TASKUP_DB': str(Path(temporary.name) / 'test.db')})
        environment.start()
        self.addCleanup(environment.stop)
        talent.init()
        self.submission_id = next(w['id'] for w in talent.submissions(student_id=105) if w['status'] == 'pending')

    def work(self):
        return next(w for w in talent.submissions(student_id=105) if w['id'] == self.submission_id)

    def request(self):
        return talent.request_defense(self.submission_id, 201, self.work()['version'], QUESTION, CHANGE)

    def round(self, defense_id):
        return next(r for r in talent.defense_rounds(self.submission_id, 105) if r['id'] == defense_id)

    def answer(self, defense_id, **overrides):
        args = dict(defense_id=defense_id, student_id=105, expected_version=self.round(defense_id)['version'],
                    answer=ANSWER, change_description=CHANGE_DESCRIPTION,
                    evidence_url='https://example.com/repo/commit/abc123', source_version='abc123')
        args.update(overrides)
        talent.answer_defense(**args)

    def assess(self, defense_id, understood=True, **overrides):
        args = dict(defense_id=defense_id, buyer_id=201, expected_version=self.round(defense_id)['version'],
                    understood=understood, observations=OBSERVATIONS,
                    reviewer_name=REVIEW['reviewer_name'], reviewer_role=REVIEW['reviewer_role'],
                    limitations=REVIEW['review_limits'])
        args.update(overrides)
        talent.assess_defense(**args)

    def review(self, approve=True, **overrides):
        args = dict(submission_id=self.submission_id, buyer_id=201, expected_version=self.work()['version'],
                    ratings=[3, 3, 3], feedback='Результат воспроизведён, по критериям достаточно свидетельств.',
                    approve=approve, **REVIEW)
        args.update(overrides)
        talent.review_work(**args)

    def test_existing_seed_gets_honest_baseline_without_fabricated_defense(self):
        approved = talent.submissions(student_id=101)[0]
        self.assertEqual(approved['status'], 'approved')
        self.assertEqual(approved['understanding_status'], 'not_requested')
        self.assertEqual(approved['criterion_evidence'], [])
        self.assertEqual(approved['reviewer_name'], '')
        self.assertEqual(talent.defense_rounds(approved['id'], 101), [])
        initial = talent.history(approved['id'], 101)
        self.assertEqual(len(initial), 1)
        self.assertEqual(initial[0]['event'], 'baseline_imported')
        self.assertIn('не восстановлены', initial[0]['snapshot']['history_note'])
        talent.init()
        self.assertEqual(talent.history(approved['id'], 101), initial)

    def test_upgrade_old_database_preserves_result_and_does_not_invent_old_revisions(self):
        old_path = str(Path(os.environ['TASKUP_DB']).with_name('pre-upgrade.db'))
        with patch.dict(os.environ, {'TASKUP_DB': old_path}):
            with db.connect() as conn:
                conn.executescript('''
                    CREATE TABLE talent_people(id INTEGER PRIMARY KEY,role TEXT,name TEXT,region TEXT,
                        grade INTEGER,focus TEXT,share_profile INTEGER DEFAULT 0,guardian_consent INTEGER DEFAULT 0);
                    CREATE TABLE talent_challenges(id INTEGER PRIMARY KEY,buyer_id INTEGER,title TEXT,brief TEXT,
                        skill TEXT,duration TEXT,deliverable TEXT,criteria TEXT,created TEXT);
                    CREATE TABLE talent_submissions(id INTEGER PRIMARY KEY,challenge_id INTEGER,student_id INTEGER,
                        evidence_url TEXT,description TEXT,reflection TEXT,status TEXT,ratings TEXT,feedback TEXT,
                        total REAL,version INTEGER,reviewed_at TEXT,created TEXT,updated TEXT,
                        UNIQUE(challenge_id,student_id));
                    CREATE TABLE talent_meta(key TEXT PRIMARY KEY,value TEXT);
                    INSERT INTO talent_meta VALUES('seed_v1','done'),('exact_scores_v1','done'),('demo_evidence_v1','done');
                    INSERT INTO talent_people VALUES(105,'student','Existing pupil','Region',11,'Python',0,0);
                    INSERT INTO talent_people VALUES(201,'buyer','Existing buyer','Region',NULL,'Program',0,0);
                ''')
                conn.execute('INSERT INTO talent_challenges VALUES(1,201,?,?,?,?,?,?,?)',
                             ('Existing task', 'Existing brief', 'Python', '5 hours', 'Report', json.dumps(talent.CRITERIA), '2026-01-01'))
                conn.execute('INSERT INTO talent_submissions VALUES(1,1,105,?,?,?,?,?,?,?,?,?,?,?)',
                             ('https://example.com/original', 'Original description', 'Original reflection',
                              'approved', '[3,3,3]', 'Original review', 75, 7, '2026-01-03', '2026-01-01', '2026-01-03'))
                before = dict(conn.execute('SELECT * FROM talent_submissions WHERE id=1').fetchone())
            talent.init()
            work = talent.submissions(student_id=105)[0]
            for key, value in before.items():
                self.assertEqual(work[key], json.loads(value) if key == 'ratings' else value)
            self.assertEqual(work['reviewer_name'], '')
            self.assertEqual(work['understanding_status'], 'not_requested')
            events = talent.history(1, 105)
            self.assertEqual(len(events), 1)
            self.assertEqual(events[0]['event'], 'baseline_imported')
            self.assertIn('не восстановлены', events[0]['snapshot']['history_note'])

    def test_new_submission_snapshots_source_and_result_only_review(self):
        sid = talent.submit_work(1, 105, 'https://example.com/commit/v1',
            'Сохранён отчёт, расчёты и две диаграммы на тестовых данных.',
            'Я собрала таблицу, проверила суммы и описала используемые инструменты.', 'release-v1')
        self.submission_id = sid
        self.assertEqual(self.work()['source_version'], 'release-v1')
        self.assertEqual(talent.history(sid, 105)[0]['event'], 'submitted')
        self.review()
        work = self.work()
        self.assertEqual(work['understanding_status'], 'not_requested')
        self.assertEqual(work['criterion_evidence'], REVIEW['criterion_evidence'])
        self.assertEqual(work['reviewer_name'], REVIEW['reviewer_name'])
        self.assertEqual(work['reviewer_org'], talent.person(201)['name'])
        self.assertEqual(work['review_limitations'], REVIEW['review_limits'])

    def test_review_requires_evidence_and_identity_not_just_scores(self):
        for changes in ({'criterion_evidence': []}, {'criterion_evidence': [''] * 3},
                        {'criterion_evidence': ['есть'] * 3}, {'reviewer_name': ''}, {'reviewer_role': ''},
                        {'criterion_evidence': [123, 'a' * 30, 'b' * 30]}):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                self.review(**changes)
        self.assertEqual(self.work()['status'], 'pending')
        self.assertEqual(len(talent.history(self.submission_id, 105)), 1)

    def test_full_defense_records_observations_versions_and_traceable_approval(self):
        original = self.work()
        did = self.request()
        self.assertEqual(self.round(did)['version'], 1)
        self.assertEqual(self.work()['version'], original['version'] + 1)
        self.assertEqual(self.work()['understanding_status'], 'requested')
        with self.assertRaises(ValueError):
            self.review()
        self.answer(did)
        self.assertEqual(self.round(did)['version'], 2)
        self.assertEqual(self.work()['understanding_status'], 'answered')
        with self.assertRaises(ValueError):
            self.review()
        self.assess(did)
        self.assertEqual(self.round(did)['version'], 3)
        self.assertEqual(self.work()['understanding_status'], 'confirmed')
        self.assertEqual(self.round(did)['observations'], OBSERVATIONS)
        self.assertEqual(self.round(did)['source_version'], 'abc123')
        self.review()
        self.assertEqual(self.work()['status'], 'approved')
        self.assertEqual([e['event'] for e in talent.history(self.submission_id, 105)],
                         ['baseline_imported', 'defense_requested', 'defense_answered', 'defense_assessed', 'approved'])

    def test_wrong_roles_owners_and_stale_review_are_rejected(self):
        original = self.work()
        for buyer in (202, 105, 101):
            with self.subTest(buyer=buyer), self.assertRaises(ValueError):
                talent.request_defense(self.submission_id, buyer, original['version'], QUESTION, CHANGE)
        did = self.request()
        with self.assertRaises(ValueError):
            self.review(expected_version=original['version'])
        with self.assertRaises(ValueError):
            self.answer(did, student_id=104)
        with self.assertRaises(ValueError):
            self.answer(did, expected_version=0)
        self.answer(did)
        with self.assertRaises(ValueError):
            self.assess(did, buyer_id=202)
        with self.assertRaises(ValueError):
            self.assess(did, expected_version=1)
        self.assertEqual(self.round(did)['status'], 'answered')

    def test_questions_answers_and_final_assessment_cannot_be_overwritten(self):
        did = self.request()
        with self.assertRaises(ValueError):
            self.request()
        self.answer(did)
        original_answer = self.round(did)
        with self.assertRaises(ValueError):
            self.answer(did, answer='Заменить уже зафиксированный ответ участника нельзя.')
        self.assertEqual(self.round(did), original_answer)
        self.assess(did)
        assessed = self.round(did)
        with self.assertRaises(ValueError):
            self.assess(did, understood=False)
        self.assertEqual(self.round(did), assessed)

    def test_clarification_needs_new_round_and_does_not_count_as_confirmed(self):
        first = self.request()
        self.answer(first)
        self.assess(first, understood=False, observations='Ответ описывает границы, но запуск пустого списка не показан; нужно уточнение.')
        self.assertEqual(self.work()['understanding_status'], 'needs_clarification')
        with self.assertRaises(ValueError):
            self.review()
        second = self.request()
        self.assertNotEqual(first, second)
        self.answer(second)
        self.assess(second)
        self.review()
        self.assertEqual([r['status'] for r in talent.defense_rounds(self.submission_id, 105)],
                         ['needs_clarification', 'confirmed'])

    def test_resubmission_invalidates_old_confirmation_without_deleting_evidence(self):
        did = self.request()
        self.answer(did)
        self.assess(did)
        self.review(approve=False, feedback='Понимание показано, но основную работу нужно дополнить проверкой форматов.')
        old_history = talent.history(self.submission_id, 105)
        old_round = self.round(did)
        talent.submit_work(2, 105, 'https://example.com/revised-v2',
            'Добавлены проверки неправильного формата и отрицательной длительности.',
            'Самостоятельно разобрала неверный формат и дополнила обработку ошибок.', 'release-v2')
        work = self.work()
        self.assertEqual(work['work_revision'], 2)
        self.assertEqual(work['understanding_status'], 'not_requested')
        self.assertEqual(work['criterion_evidence'], [])
        self.assertEqual(work['reviewer_name'], '')
        self.assertEqual(self.round(did), old_round)
        self.assertEqual(talent.history(self.submission_id, 105)[:-1], old_history)
        self.assertEqual(talent.history(self.submission_id, 105)[-1]['event'], 'resubmitted')

    def test_active_old_round_cannot_be_answered_after_requesting_revision(self):
        did = self.request()
        self.review(approve=False)
        talent.submit_work(2, 105, 'https://example.com/revised-v2',
            'Добавлены проверки неправильного формата и отрицательной длительности.',
            'Самостоятельно разобрала неверный формат и дополнила обработку ошибок.')
        with self.assertRaises(ValueError):
            self.answer(did)
        self.assertEqual(self.work()['understanding_status'], 'not_requested')
        self.assertNotEqual(self.request(), did)

    def test_approval_freezes_work_and_defense(self):
        self.review()
        with self.assertRaises(ValueError):
            self.request()
        with self.assertRaises(ValueError):
            self.review()
        with self.assertRaises(ValueError):
            talent.submit_work(2, 105, 'https://example.com/rewrite',
                'Нельзя заменить результат уже принятой работы.', 'Рефлексия после принятия не переписывается.')

    def test_history_and_defense_follow_work_visibility_and_consent(self):
        did = self.request()
        self.answer(did)
        self.assess(did)
        for viewer in (104, 202, 999):
            for read in (talent.history, talent.defense_rounds):
                with self.subTest(viewer=viewer, read=read.__name__), self.assertRaises(ValueError):
                    read(self.submission_id, viewer)
        self.review()
        with self.assertRaises(ValueError):
            talent.history(self.submission_id, 202)
        talent.set_visibility(105, True, True)
        self.assertTrue(talent.history(self.submission_id, 202))
        self.assertEqual(talent.defense_rounds(self.submission_id, 202)[0]['status'], 'confirmed')
        talent.set_visibility(105, False, True)
        for read in (talent.history, talent.defense_rounds):
            with self.assertRaises(ValueError):
                read(self.submission_id, 202)
            self.assertTrue(read(self.submission_id, 201))
            self.assertTrue(read(self.submission_id, 105))

    def test_another_visible_work_does_not_expose_pending_work_history(self):
        public = talent.submissions(student_id=101)[0]
        sid = talent.submit_work(2, 101, 'https://example.com/private-pending',
            'Новая работа ожидает проверки и не открыта другим компаниям.',
            'В этой работе ещё не завершены все проверочные примеры.')
        self.assertTrue(talent.history(public['id'], 202))
        with self.assertRaises(ValueError):
            talent.history(sid, 202)
        with self.assertRaises(ValueError):
            talent.defense_rounds(sid, 202)

    def test_history_snapshots_are_database_immutable_and_returned_as_copies(self):
        original = talent.history(self.submission_id, 105)
        returned = talent.history(self.submission_id, 105)
        returned[0]['snapshot']['description'] = 'tampered'
        self.assertEqual(talent.history(self.submission_id, 105), original)
        with self.assertRaises(db.sqlite3.IntegrityError):
            with db.connect() as conn:
                conn.execute("UPDATE talent_work_history SET snapshot='{}' WHERE submission_id=?", (self.submission_id,))
        with self.assertRaises(db.sqlite3.IntegrityError):
            with db.connect() as conn:
                conn.execute('DELETE FROM talent_work_history WHERE submission_id=?', (self.submission_id,))
        self.assertEqual(talent.history(self.submission_id, 105), original)

    def test_transactional_submit_rolls_back_with_parent_operation(self):
        before = talent.stats()['submissions']
        with self.assertRaises(RuntimeError):
            with db.connect() as conn:
                conn.execute('BEGIN IMMEDIATE')
                talent.submit_work(1, 105, 'https://example.com/rollback',
                    'Этот результат должен откатиться вместе с проектом.',
                    'Проверяется атомарная передача проекта в задание.', 'test-release', _conn=conn)
                raise RuntimeError('Parent operation failed')
        self.assertEqual(talent.stats()['submissions'], before)

    def test_no_confirmation_without_answer_observations_and_reviewer(self):
        did = self.request()
        with self.assertRaises(ValueError):
            self.assess(did)
        with self.assertRaises(ValueError):
            self.answer(did, evidence_url='javascript:alert(1)')
        with self.assertRaises(ValueError):
            self.answer(did, change_description='')
        self.answer(did)
        for kwargs in ({'observations': ''}, {'observations': 'Да, понял'}, {'reviewer_name': ''},
                       {'reviewer_role': ''}, {'understood': 1}):
            with self.subTest(kwargs=kwargs), self.assertRaises(ValueError):
                self.assess(did, **kwargs)
        self.assertEqual(self.work()['understanding_status'], 'answered')


if __name__ == '__main__':
    unittest.main()
