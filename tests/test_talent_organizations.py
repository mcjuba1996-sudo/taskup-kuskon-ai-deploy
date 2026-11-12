"""Four buyer types share guarded workflows; additive demos preserve old state."""
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import database as db
import talent_store as talent


EVIDENCE = [
    'По приложенному примеру основной сценарий даёт ожидаемый результат.',
    'Обоснование связывает выбранный алгоритм с проверяемой задачей.',
    'В самоотчёте описаны собственные действия и использованная помощь.',
]


class TalentOrganizationTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix='taskup-organizations-')
        self.addCleanup(temporary.cleanup)
        self.base = Path(temporary.name)
        environment = patch.dict(os.environ, {'TASKUP_DB': str(self.base / 'test.db')})
        environment.start()
        self.addCleanup(environment.stop)
        talent.init()

    def review(self, submission_id, buyer_id, approve=True):
        work = next(w for w in talent.submissions(buyer_id=buyer_id) if w['id'] == submission_id)
        talent.review_work(submission_id, buyer_id, work['version'], [3, 3, 3],
            'Проверены примеры и объяснение решений; результат соответствует заданию.', approve,
            criterion_evidence=EVIDENCE, reviewer_name='Эксперт · демо', reviewer_role='Наставник программы')

    def test_taxonomy_and_fictional_examples_are_complete(self):
        self.assertEqual(set(talent.ORGANIZATION_KINDS), {'company', 'university', 'agency', 'fund'})
        self.assertEqual(len(talent.people('buyer')), 5)
        self.assertEqual(len(talent.organizations('company')), 2)
        self.assertEqual(talent.person(201)['organization_kind'], 'company')
        self.assertEqual(talent.person(202)['organization_kind'], 'company')
        ids = talent.ecosystem_demo_ids()
        self.assertEqual({key: ids[key] for key in ('student', 'university', 'agency', 'fund')},
                         {'student': 106, 'university': 203, 'agency': 204, 'fund': 205})
        pupil = talent.person(ids['student'])
        self.assertEqual(pupil['grade'], 8)
        self.assertFalse(pupil['share_profile'])
        self.assertFalse(pupil['guardian_consent'])
        for kind in ('university', 'agency', 'fund'):
            buyer = talent.organizations(kind)[0]
            self.assertEqual(buyer['organization_kind'], kind)
            self.assertTrue(buyer['organization_purpose'])
            self.assertIn('демо', buyer['name'])
            self.assertTrue(talent.challenges(buyer_id=buyer['id']))
        pending = talent.submissions(student_id=ids['student'])
        self.assertEqual(len(pending), 1)
        self.assertEqual(pending[0]['buyer_id'], ids['university'])
        self.assertEqual(pending[0]['status'], 'pending')
        self.assertEqual(pending[0]['understanding_status'], 'not_requested')
        self.assertEqual(pending[0]['evidence_url'], talent.DEMO_EVIDENCE_URLS[2])

    def test_legacy_buyer_without_metadata_falls_back_to_company(self):
        with db.connect() as conn:
            conn.execute('INSERT INTO talent_people VALUES(900,?,?,?,?,?,?,?)',
                         ('buyer', 'Manually added buyer', 'Region', None, 'Existing focus', 0, 0))
        profile = talent.person(900)
        self.assertEqual(profile['organization_kind'], 'company')
        self.assertEqual(profile['organization_purpose'], 'Existing focus')
        self.assertIn(900, {p['id'] for p in talent.people('buyer', organization_kind='company')})
        self.assertNotIn('organization_kind', talent.person(101))
        for operation in (lambda: talent.organizations('school'),
                          lambda: talent.people('student', organization_kind='company')):
            with self.assertRaises(ValueError):
                operation()

    def test_each_kind_can_create_review_find_and_invite_with_owner_guards(self):
        for kind in talent.ORGANIZATION_KINDS:
            with self.subTest(kind=kind):
                buyer_id = talent.organizations(kind)[0]['id']
                cid = talent.create_challenge(buyer_id, 'Учебное задание для проверки навыка',
                    'Подготовьте объяснимый результат на синтетических данных и покажите проверочные примеры.',
                    'Python', '3 часа', 'Код, инструкция запуска и объяснение личного вклада.', talent.CRITERIA)
                sid = talent.submit_work(cid, 105, 'https://example.com/demo-result',
                    'Подготовлен код и проверочные примеры на синтетических данных.',
                    'Я реализовала основной алгоритм и описала полученную помощь.', 'test-v1')
                other_buyer = 202 if buyer_id != 202 else 201
                with self.assertRaises(ValueError):
                    talent.review_work(sid, other_buyer, 1, [3, 3, 3], 'Чужой покупатель не может принять работу.', True,
                        criterion_evidence=EVIDENCE, reviewer_name='Чужой эксперт', reviewer_role='Наставник')
                self.review(sid, buyer_id)
                talent.set_visibility(105, True, True)
                self.assertIn(105, {p['id'] for p in talent.discover(buyer_id)})
                talent.save_candidate(buyer_id, 105, True)
                self.assertTrue(next(p for p in talent.discover(buyer_id) if p['id'] == 105)['saved'])
                iid = talent.invite(buyer_id, 105, 'Приглашаем обсудить участие в нашей демонстрационной программе.')
                talent.respond_invitation(iid, 105, True)
                self.assertEqual(talent.invitations(buyer_id=buyer_id)[0]['status'], 'accepted')
                self.assertEqual(talent.submissions(buyer_id=buyer_id)[0]['reviewer_org'], talent.person(buyer_id)['name'])

    def test_student_cannot_change_linked_guardian_value(self):
        pupil_id = talent.ecosystem_demo_ids()['student']
        with db.connect() as conn:
            conn.execute('CREATE TABLE talent_guardian_links(parent_id INTEGER,student_id INTEGER UNIQUE)')
            conn.execute('INSERT INTO talent_guardian_links VALUES(401,?)', (pupil_id,))
        with self.assertRaises(ValueError):
            talent.set_visibility(pupil_id, True, True)
        talent.set_visibility(pupil_id, True, False)
        self.assertTrue(talent.person(pupil_id)['share_profile'])
        self.assertFalse(talent.person(pupil_id)['guardian_consent'])
        # Emulate the separately permission-checked parent module, not a student bypass.
        with db.connect() as conn:
            conn.execute('UPDATE talent_people SET guardian_consent=1 WHERE id=?', (pupil_id,))
        talent.set_visibility(pupil_id, False, True)
        with self.assertRaises(ValueError):
            talent.set_visibility(pupil_id, False, False)
        talent.set_visibility(105, True, True)  # Legacy demo without a guardian link remains supported.

    def test_migration_is_idempotent_and_preserves_existing_history(self):
        history = talent.history(talent.submissions(student_id=101)[0]['id'], 101)
        before = {table: db.rows('SELECT * FROM ' + table) for table in
                  ('talent_people', 'talent_challenges', 'talent_submissions', 'talent_work_history', 'talent_organizations')}
        ids = talent.ecosystem_demo_ids()
        talent.init()
        talent.init()
        for table, rows in before.items():
            self.assertEqual(db.rows('SELECT * FROM ' + table), rows)
        self.assertEqual(talent.ecosystem_demo_ids(), ids)
        self.assertEqual(talent.history(talent.submissions(student_id=101)[0]['id'], 101), history)

    def test_manual_and_network_id_collisions_never_overwrite_old_rows(self):
        with patch.dict(os.environ, {'TASKUP_DB': str(self.base / 'legacy-collisions.db')}):
            with patch.object(talent, '_migrate_organizations', return_value=None):
                talent.init()
            with db.connect() as conn:
                conn.execute('INSERT INTO talent_people VALUES(106,?,?,?,?,?,?,?)',
                             ('student', 'Manual pupil 106', 'Region', 11, 'Manual focus', 0, 0))
                conn.execute('INSERT INTO talent_people VALUES(203,?,?,?,?,?,?,?)',
                             ('buyer', 'Manual organization 203', 'Region', None, 'Manual purpose', 0, 0))
                conn.execute('CREATE TABLE talent_network_actors(id INTEGER PRIMARY KEY,role TEXT)')
                conn.execute("INSERT INTO talent_network_actors VALUES(204,'parent')")
                conn.execute('''INSERT INTO talent_challenges VALUES(4,201,?,?,?,?,?,?,?)''',
                             ('Manual task 4', 'Manual context', 'Python', '1 hour', 'Report', '[]', 'old-date'))
            tables = ('talent_people', 'talent_challenges', 'talent_submissions', 'talent_work_history', 'talent_network_actors')
            original = {table: db.rows('SELECT * FROM ' + table) for table in tables}
            talent.init()
            ids = talent.ecosystem_demo_ids()
            self.assertNotEqual(ids['student'], 106)
            self.assertNotEqual(ids['university'], 203)
            self.assertNotIn(204, [ids[k] for k in ('student', 'university', 'agency', 'fund')])
            self.assertNotEqual(ids['university_challenge'], 4)
            for table, rows in original.items():
                actual = db.rows('SELECT * FROM ' + table)
                for row in rows:
                    self.assertIn(row, actual)
            count = talent.stats()
            talent.init()
            self.assertEqual(talent.stats(), count)
            self.assertEqual(talent.ecosystem_demo_ids(), ids)


if __name__ == '__main__':
    unittest.main()
