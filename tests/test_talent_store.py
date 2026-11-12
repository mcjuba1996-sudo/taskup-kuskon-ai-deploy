"""Offline domain tests for consent, ownership, review state, and additive storage."""
import copy
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import database as db
import talent_store as talent


class TalentStoreTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix='taskup-talent-')
        self.addCleanup(temporary.cleanup)
        environment = patch.dict(os.environ, {'TASKUP_DB': str(Path(temporary.name) / 'test.db')})
        environment.start()
        self.addCleanup(environment.stop)
        talent.init()

    def review(self, *args, **kwargs):
        defaults = dict(criterion_evidence=[
            'Основной сценарий воспроизводится на приложенных примерах.',
            'В пояснении описан выбор алгоритма и граничные случаи.',
            'Рефлексия описывает собственные изменения и использованную помощь.',
        ], reviewer_name='Демо-проверяющий', reviewer_role='Наставник IT-программы')
        defaults.update(kwargs)
        return talent.review_work(*args, **defaults)

    def work(self, student=105, buyer=201):
        return next(work for work in talent.submissions(student_id=student, buyer_id=buyer)
                    if work['status'] == 'pending')

    def test_seed_is_idempotent_and_preserves_original_tables(self):
        db.init_db()
        with db.connect() as conn:
            conn.execute("INSERT INTO profiles VALUES(999, 'business', 'Original business', 'Keep me')")
            conn.execute("INSERT INTO meta VALUES('test_original', 'unchanged')")
        before = talent.stats()
        talent.init()
        self.assertEqual(talent.stats(), before)
        self.assertEqual(len(talent.people('student')), 5)
        self.assertEqual(len(talent.people('buyer')), 2)
        self.assertGreaterEqual(before['challenges'], 3)
        self.assertEqual(before['approved'], 4)
        self.assertEqual(before['pending'], 1)
        self.assertEqual(db.rows('SELECT name FROM profiles WHERE id=999')[0]['name'], 'Original business')
        self.assertEqual(db.rows("SELECT value FROM meta WHERE key='test_original'")[0]['value'], 'unchanged')

    def test_new_profile_defaults_private_and_discovery_hides_pending(self):
        with db.connect() as conn:
            conn.execute('''INSERT INTO talent_people(id,role,name,region,grade,focus)
                VALUES(106,'student','New demo','Актюбинская область',9,'Python')''')
        profile = talent.person(106)
        self.assertFalse(profile['share_profile'])
        self.assertFalse(profile['guardian_consent'])
        self.assertEqual({p['id'] for p in talent.discover(201)}, {101, 102, 103})
        talent.set_visibility(105, True, True)
        self.assertNotIn(105, {p['id'] for p in talent.discover(201)})
        for profile in talent.discover(201):
            self.assertNotIn('contact', profile)
            self.assertNotIn('school', profile)
            self.assertNotIn('age', profile)
            self.assertTrue(all(work['status'] == 'approved' for work in profile['works']))

    def test_both_consents_required_and_filters_match_confirmed_skills(self):
        talent.set_visibility(104, True, False)
        self.assertNotIn(104, {p['id'] for p in talent.discover(201)})
        talent.set_visibility(104, False, True)
        self.assertNotIn(104, {p['id'] for p in talent.discover(201)})
        talent.set_visibility(104, True, True)
        self.assertIn(104, {p['id'] for p in talent.discover(201)})
        self.assertEqual({p['id'] for p in talent.discover(201, skill='python')}, {102})
        self.assertEqual(talent.discover(201, region='несуществующий регион'), [])

    def test_withdrawal_removes_shortlist_discovery_and_pending_invitation(self):
        talent.save_candidate(201, 101, True)
        invitation_id = talent.invite(201, 101, 'Приглашаем в демонстрационный учебный проект.')
        self.assertTrue(next(p for p in talent.discover(201) if p['id'] == 101)['saved'])
        talent.set_visibility(101, False, True)
        self.assertNotIn(101, {p['id'] for p in talent.discover(201)})
        self.assertEqual(talent.invitations(buyer_id=201), [])
        self.assertEqual(talent.invitations(student_id=101)[0]['status'], 'withdrawn')
        self.assertEqual(db.rows('SELECT * FROM talent_saved WHERE student_id=101'), [])
        for action in [lambda: talent.save_candidate(201, 101, True),
                       lambda: talent.invite(201, 101, 'Приглашение после отзыва согласия запрещено.'),
                       lambda: talent.respond_invitation(invitation_id, 101, True)]:
            with self.assertRaises(ValueError):
                action()
        talent.set_visibility(101, True, True)
        self.assertFalse(next(p for p in talent.discover(201) if p['id'] == 101)['saved'])
        self.assertEqual(talent.invitations(student_id=101)[0]['status'], 'withdrawn')

    def test_owner_can_review_private_work_but_other_buyer_cannot(self):
        work = self.work()
        self.assertFalse(talent.person(105)['share_profile'])
        self.assertNotIn(work['id'], {w['id'] for w in talent.submissions(buyer_id=202)})
        with self.assertRaises(ValueError):
            self.review(work['id'], 202, work['version'], [3, 3, 3], 'Хорошая работа с примерами.', True)
        self.review(work['id'], 201, work['version'], [3, 3, 3], 'Хорошая работа с примерами.', True)
        approved = talent.submissions(student_id=105)[0]
        self.assertEqual(approved['status'], 'approved')
        self.assertEqual(approved['total'], 75)
        self.assertTrue(approved['reviewed_at'])
        self.assertNotIn(105, {p['id'] for p in talent.discover(201)})
        talent.set_visibility(105, True, True)
        self.assertEqual(next(p for p in talent.discover(201) if p['id'] == 105)['works'][0]['id'], work['id'])

    def test_change_request_resubmit_stale_review_and_immutable_approval(self):
        original = self.work()
        self.review(original['id'], 201, original['version'], [2, 2, 1],
                           'Добавьте проверки и подробнее опишите свой вклад.', False)
        revised_id = talent.submit_work(2, 105, 'https://example.com/revised',
            'Добавлены проверки пустого списка и граничных значений.',
            'Самостоятельно нашла и исправила ошибку на границе интервалов.')
        self.assertEqual(revised_id, original['id'])
        revised = self.work()
        self.assertEqual(revised['version'], original['version'] + 2)
        self.assertEqual(revised['ratings'], [])
        self.assertEqual(revised['feedback'], '')
        self.assertIsNone(revised['reviewed_at'])
        with self.assertRaises(ValueError):
            self.review(revised_id, 201, original['version'], [4, 4, 4], 'Все проверки пройдены.', True)
        self.review(revised_id, 201, revised['version'], [4, 2, 2], 'Основной сценарий и вклад подтверждены примерами.', True)
        approved = talent.submissions(student_id=105)[0]
        self.assertEqual(approved['total'], 70)
        with self.assertRaises(ValueError):
            self.review(revised_id, 201, approved['version'], [4, 4, 4], 'Повторная проверка работы.', True)
        with self.assertRaises(ValueError):
            talent.submit_work(2, 105, 'https://example.com/again', 'Повторная сдача принятой работы.', 'Повторная рефлексия принятой работы.')

    def test_review_threshold_and_rating_validation(self):
        work = self.work()
        for ratings in ([4, 4, 1], [2, 2, 2], [3, 3, 2], [5, 4, 4], [-1, 3, 3],
                        [True, 3, 3], [3.0, 3, 3], [3, 3], '333'):
            with self.subTest(ratings=ratings), self.assertRaises(ValueError):
                self.review(work['id'], 201, work['version'], ratings, 'Обоснованная обратная связь.', True)
        self.assertEqual(self.work()['version'], work['version'])

    def test_fractional_scores_match_rubric_and_migrate_old_demo_scores(self):
        seeded = talent.submissions(student_id=101)[0]
        self.assertEqual(seeded['ratings'], [4, 3, 4])
        self.assertEqual(seeded['total'], 91.25)
        work = self.work()
        self.review(work['id'], 201, work['version'], [3, 4, 3], 'Проверки выполнены, обоснование подробное.', True)
        self.assertEqual(talent.submissions(student_id=105)[0]['total'], 83.75)
        with db.connect() as conn:
            conn.execute('UPDATE talent_submissions SET total=91 WHERE id=?', (seeded['id'],))
            conn.execute("DELETE FROM talent_meta WHERE key='exact_scores_v1'")
        talent.init()
        self.assertEqual(talent.submissions(student_id=101)[0]['total'], 91.25)

    def test_seed_evidence_migration_preserves_user_changed_links(self):
        seeded = talent.submissions(student_id=101)[0]
        changed = talent.submissions(student_id=102)[0]
        with db.connect() as conn:
            conn.execute('UPDATE talent_submissions SET evidence_url=? WHERE id=?',
                         ('https://example.com/demo/talent/101/1', seeded['id']))
            conn.execute('UPDATE talent_submissions SET evidence_url=? WHERE id=?',
                         ('https://example.com/my-replacement', changed['id']))
            conn.execute("DELETE FROM talent_meta WHERE key='demo_evidence_v1'")
        talent.init()
        self.assertEqual(talent.submissions(student_id=101)[0]['evidence_url'], talent.DEMO_EVIDENCE_URLS[1])
        self.assertEqual(talent.submissions(student_id=102)[0]['evidence_url'], 'https://example.com/my-replacement')

    def test_create_challenge_fixed_weights_and_roles(self):
        kwargs = dict(title='Проверь данные учебного центра', brief='Найдите ошибки в синтетической таблице и объясните способ проверки.',
                      skill='Аналитика данных', duration='3 часа', deliverable='Таблица с исправлениями и пояснением.', criteria=copy.deepcopy(talent.CRITERIA))
        cid = talent.create_challenge(201, **kwargs)
        created = next(c for c in talent.challenges(201) if c['id'] == cid)
        self.assertEqual(created['criteria'], talent.CRITERIA)
        with self.assertRaises(ValueError):
            talent.create_challenge(101, **kwargs)
        kwargs['criteria'][0]['weight'] = 50
        with self.assertRaises(ValueError):
            talent.create_challenge(201, **kwargs)
        self.assertEqual(next(c for c in talent.challenges(201) if c['id'] == cid)['criteria'][0]['weight'], 40)

    def test_submission_links_required_fields_and_roles(self):
        for url in ('javascript:alert(1)', 'file:///tmp/private', 'https://', 'https://user:pass@example.com'):
            with self.subTest(url=url), self.assertRaises(ValueError):
                talent.submit_work(3, 105, url, 'Достаточно длинное описание результата.', 'Достаточно длинная рефлексия результата.')
        with self.assertRaises(ValueError):
            talent.submit_work(3, 105, 'https://example.com/demo', '', 'Достаточно длинная рефлексия результата.')
        with self.assertRaises(ValueError):
            talent.submit_work(3, 201, 'https://example.com/demo', 'Достаточно длинное описание результата.', 'Достаточно длинная рефлексия результата.')
        with self.assertRaises(ValueError):
            talent.set_visibility(201, True, True)
        with self.assertRaises(ValueError):
            talent.set_visibility(101, 'true', True)
        with self.assertRaises(ValueError):
            talent.discover(101)
        with self.assertRaises(ValueError):
            talent.save_candidate(201, 105, True)

    def test_invitation_duplicate_and_response_ownership(self):
        iid = talent.invite(201, 101, 'Приглашаем обсудить демонстрационный учебный проект.')
        with self.assertRaises(ValueError):
            talent.invite(201, 101, 'Повторное приглашение не должно создавать дубликат.')
        with self.assertRaises(ValueError):
            talent.respond_invitation(iid, 102, True)
        talent.respond_invitation(iid, 101, True)
        self.assertEqual(talent.invitations(buyer_id=201)[0]['status'], 'accepted')
        with self.assertRaises(ValueError):
            talent.respond_invitation(iid, 101, False)
        with self.assertRaises(ValueError):
            talent.invite(201, 101, 'Нельзя повторять уже принятое приглашение.')
        declined = talent.invite(202, 103, 'Приглашаем в демонстрационную программу наставничества.')
        talent.respond_invitation(declined, 103, False)
        self.assertEqual(talent.invitations(student_id=103)[0]['status'], 'declined')


if __name__ == '__main__':
    unittest.main()
