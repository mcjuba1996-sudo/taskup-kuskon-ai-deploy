"""Source provenance, pupil acceptance and strictly scoped demo guardians."""
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import database as db
import personal_projects
import talent_network as network
import talent_store as talent


class TalentNetworkTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix='taskup-network-')
        self.addCleanup(temporary.cleanup)
        environment = patch.dict(os.environ, {'TASKUP_DB': str(Path(temporary.name) / 'test.db')})
        environment.start()
        self.addCleanup(environment.stop)
        talent.init()
        network.init_network()
        self.ids = network.demo_ids()
        self.core_ids = talent.ecosystem_demo_ids()
        self.record_values = dict(title='Тестовая запись о проекте', event='Учебное событие (демо)',
            result='Участник показал синтетический учебный проект.',
            evidence_url='https://example.com/synthetic-protocol',
            check_method='Демонстрационное сопоставление работы с тестовым протоколом.',
            limitations='Только синтетические данные, реальной проверки нет.')

    def issue(self, student=101, source=None, **changes):
        return network.issue_record(source or self.ids['school'], student, **{**self.record_values, **changes})

    def record(self, rid, student=101):
        return next(r for r in network.student_records(student) if r['id'] == rid)

    def approve_child(self):
        work = next(s for s in talent.submissions(student_id=self.ids['student'])
                    if s['challenge_id'] == self.core_ids['university_challenge'])
        talent.review_work(work['id'], self.core_ids['university'], work['version'], [3, 3, 3],
            'Демонстрационная работа принята по учебным критериям.', True,
            criterion_evidence=['Базовый сценарий воспроизведён на синтетическом примере.',
                'В отчёте описаны решения и ограничения тестового материала.',
                'Вклад и помощь обозначены в демонстрационном описании.'],
            reviewer_name='Демо эксперт', reviewer_role='Наставник учебной программы')
        return work['id']

    def test_seed_idempotent_disjoint_and_rosters_minimal(self):
        before = talent.stats()
        self.assertEqual({p['id'] for p in network.source_students(self.ids['school'])}, {101, self.ids['student']})
        self.assertEqual({p['id'] for p in network.source_students(self.ids['organizer'])}, {102, 105})
        self.assertEqual(len(network.source_records(self.ids['school'])), 1)
        self.assertEqual(len(network.source_records(self.ids['organizer'])), 1)
        network.init_network()
        self.assertEqual(network.demo_ids(), self.ids)
        self.assertEqual(len(network.source_records(self.ids['school'])), 1)
        self.assertEqual(talent.stats(), before)
        for kind in network.KINDS:
            actor = network.people(kind)[0]
            self.assertEqual(network.person(actor['id']), actor)
            self.assertEqual(db.rows('SELECT id FROM talent_people WHERE id=?', (actor['id'],)), [])
        self.assertEqual(set(network.source_students(self.ids['school'])[0]), {'id', 'name', 'grade', 'region', 'focus'})
        self.assertFalse(network.has_guardian(101))
        self.assertTrue(network.has_guardian(self.ids['student']))

    def test_source_issues_only_own_roster_and_provenance_is_explicit(self):
        rid = self.issue()
        record = self.record(rid)
        self.assertEqual(record['status'], 'offered')
        self.assertEqual(record['source_id'], self.ids['school'])
        self.assertEqual(record['check_method'], self.record_values['check_method'])
        self.assertTrue(record['issued_at'])
        self.assertIn('Школа', record['issuer_name'])
        self.assertIn('не подтверждены', record['demo_notice'])
        self.assertNotIn('score', record)
        for actor, student in ((self.ids['school'], 102), (self.ids['organizer'], 101),
                               (self.ids['parent'], self.ids['student']), (201, 101)):
            with self.subTest(actor=actor, student=student), self.assertRaises(ValueError):
                self.issue(student=student, source=actor)
        with self.assertRaises(ValueError):
            network.source_students(self.ids['parent'])
        self.assertNotIn(rid, {r['id'] for r in network.source_records(self.ids['organizer'])})

    def test_acceptance_visibility_and_revocation_are_distinct(self):
        rid = self.issue()
        before = talent.stats()
        self.assertNotIn(rid, {r['id'] for r in network.public_records(201, 101)})
        network.respond_record(rid, 101, True)
        self.assertIn(rid, {r['id'] for r in network.public_records(201, 101)})
        self.assertEqual(talent.stats(), before)
        talent.set_visibility(101, False, True)
        self.assertEqual(network.public_records(201, 101), [])
        talent.set_visibility(101, True, False)
        self.assertEqual(network.public_records(201, 101), [])
        talent.set_visibility(101, True, True)
        network.revoke_record(rid, self.ids['school'], 'Отзываем ошибочно предложенную демозапись.')
        self.assertNotIn(rid, {r['id'] for r in network.public_records(201, 101)})
        record = self.record(rid)
        self.assertEqual(record['status'], 'revoked')
        self.assertTrue(record['revoked_at'])
        self.assertTrue(record['responded_at'])
        self.assertIn('ошибочно', record['revocation_reason'])

    def test_only_recipient_can_respond_and_terminal_states_cannot_be_reused(self):
        rid = self.issue()
        for student, accept in ((102, True), (self.ids['parent'], True), (101, 1)):
            with self.subTest(student=student, accept=accept), self.assertRaises(ValueError):
                network.respond_record(rid, student, accept)
        network.respond_record(rid, 101, False)
        self.assertEqual(self.record(rid)['status'], 'declined')
        with self.assertRaises(ValueError):
            network.respond_record(rid, 101, True)
        with self.assertRaises(ValueError):
            network.revoke_record(rid, self.ids['school'], 'Повторное изменение завершённой записи.')
        revoked = self.issue()
        with self.assertRaises(ValueError):
            network.revoke_record(revoked, self.ids['organizer'], 'Чужой источник не может отзывать запись.')
        network.revoke_record(revoked, self.ids['school'], 'Отзыв до ответа школьника в демонстрации.')
        with self.assertRaises(ValueError):
            network.respond_record(revoked, 101, True)
        with self.assertRaises(ValueError):
            network.revoke_record(revoked, self.ids['school'], 'Повторный отзыв не должен изменить дату.')

    def test_validation_rolls_back_and_nonbuyers_cannot_read_catalog(self):
        count = len(network.source_records(self.ids['school']))
        for changes in ({'evidence_url': 'javascript:alert(1)'}, {'evidence_url': 'https://user:pass@example.com'},
                        {'title': ''}, {'event': 'xy'}, {'check_method': 'Проверено'},
                        {'result': None}, {'limitations': 'x' * 2001}):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                self.issue(**changes)
        self.assertEqual(len(network.source_records(self.ids['school'])), count)
        for actor in (101, self.ids['school'], self.ids['organizer'], self.ids['parent']):
            with self.subTest(actor=actor), self.assertRaises(ValueError):
                network.public_records(actor, 101)
        for actor in (self.ids['school'], self.ids['organizer'], self.ids['parent']):
            with self.subTest(actor=actor), self.assertRaises(ValueError):
                talent.discover(actor)
        with self.assertRaises(ValueError):
            network.people('buyer')

    def test_source_record_alone_does_not_create_approved_work_or_discovery(self):
        pupil = self.ids['student']
        rid = self.issue(student=pupil)
        network.respond_record(rid, pupil, True)
        network.set_guardian_consent(self.ids['parent'], pupil, True)
        talent.set_visibility(pupil, True, True)
        self.assertEqual(network.public_records(201, pupil), [])
        self.assertNotIn(pupil, {p['id'] for p in talent.discover(201)})
        self.approve_child()
        self.assertIn(rid, {r['id'] for r in network.public_records(201, pupil)})

    def test_parent_scoped_overview_excludes_private_projects_and_work_content(self):
        pupil, parent = self.ids['student'], self.ids['parent']
        self.assertEqual([p['id'] for p in network.guardian_children(parent)], [pupil])
        personal_projects.init_projects()
        personal_projects.save_project(pupil, 'PRIVATE PROJECT SENTINEL', 'PRIVATE DESCRIPTION', '', '', '', [])
        overview = network.guardian_overview(parent, pupil)
        self.assertEqual(set(overview), {'child', 'works', 'invitations'})
        self.assertNotIn('PRIVATE', str(overview))
        for work in overview['works']:
            self.assertEqual(set(work), {'id', 'title', 'status', 'score', 'feedback'})
            self.assertIsNone(work['score'])
            self.assertEqual(work['feedback'], '')
        for actor, child in ((parent, 101), (self.ids['school'], pupil), (201, pupil)):
            with self.subTest(actor=actor, child=child), self.assertRaises(ValueError):
                network.guardian_overview(actor, child)
        with self.assertRaises(ValueError):
            network.guardian_children(self.ids['school'])
        self.approve_child()
        approved = next(w for w in network.guardian_overview(parent, pupil)['works'] if w['status'] == 'approved')
        self.assertEqual(approved['score'], 75)
        self.assertTrue(approved['feedback'])

    def test_guardian_consent_preserves_pupil_choice_and_student_cannot_forge_it(self):
        pupil, parent = self.ids['student'], self.ids['parent']
        with self.assertRaises(ValueError):
            talent.set_visibility(pupil, True, True)
        talent.set_visibility(pupil, True, False)
        network.set_guardian_consent(parent, pupil, True)
        self.assertTrue(talent.person(pupil)['share_profile'])
        self.assertTrue(talent.person(pupil)['guardian_consent'])
        talent.set_visibility(pupil, False, True)
        self.assertFalse(talent.person(pupil)['share_profile'])
        self.assertTrue(talent.person(pupil)['guardian_consent'])
        with self.assertRaises(ValueError):
            talent.set_visibility(pupil, False, False)
        for actor, child, value in ((parent, 101, True), (self.ids['school'], pupil, True),
                                    (201, pupil, True), (parent, pupil, 'yes')):
            with self.subTest(actor=actor, child=child, value=value), self.assertRaises(ValueError):
                network.set_guardian_consent(actor, child, value)

    def test_parent_revocation_hides_evidence_removes_shortlist_and_withdraws_pending(self):
        pupil, parent = self.ids['student'], self.ids['parent']
        self.approve_child()
        rid = self.issue(student=pupil)
        network.respond_record(rid, pupil, True)
        network.set_guardian_consent(parent, pupil, True)
        talent.set_visibility(pupil, True, True)
        talent.save_candidate(201, pupil, True)
        invitation = talent.invite(201, pupil, 'Приглашение в вымышленную учебную программу.')
        self.assertEqual(network.guardian_overview(parent, pupil)['invitations'][0]['id'], invitation)
        network.set_guardian_consent(parent, pupil, False)
        self.assertTrue(talent.person(pupil)['share_profile'])
        self.assertFalse(talent.person(pupil)['guardian_consent'])
        self.assertEqual(network.public_records(201, pupil), [])
        self.assertNotIn(pupil, {p['id'] for p in talent.discover(201)})
        self.assertEqual(db.rows('SELECT * FROM talent_saved WHERE student_id=?', (pupil,)), [])
        self.assertEqual(talent.invitations(student_id=pupil)[0]['status'], 'withdrawn')
        with self.assertRaises(ValueError):
            talent.respond_invitation(invitation, pupil, True)
        network.set_guardian_consent(parent, pupil, True)
        self.assertFalse(next(p for p in talent.discover(201) if p['id'] == pupil)['saved'])
        self.assertEqual(talent.invitations(student_id=pupil)[0]['status'], 'withdrawn')

    def test_network_seed_preserves_manual_collisions_and_modified_records(self):
        # A separate fresh DB allows collisions before this namespace is seeded.
        with tempfile.TemporaryDirectory(prefix='taskup-network-collision-') as folder:
            with patch.dict(os.environ, {'TASKUP_DB': str(Path(folder) / 'collision.db')}):
                talent.init()
                with db.connect() as conn:
                    conn.execute("INSERT INTO talent_people VALUES(301,'buyer','Keep core buyer','Demo',NULL,'IT',0,0)")
                    conn.execute('''CREATE TABLE talent_network_actors(id INTEGER PRIMARY KEY,
                        kind TEXT NOT NULL,name TEXT NOT NULL)''')
                    conn.execute("INSERT INTO talent_network_actors VALUES(302,'school','Keep manual school')")
                network.init_network()
                ids = network.demo_ids()
                self.assertNotIn(ids['school'], (301, 302))
                self.assertNotIn(ids['organizer'], (301, 302))
                self.assertEqual(talent.person(301)['name'], 'Keep core buyer')
                self.assertEqual(network.person(302)['name'], 'Keep manual school')
                rid = network.source_records(ids['school'])[0]['id']
                network.respond_record(rid, 101, False)
                network.init_network()
                self.assertEqual(network.demo_ids(), ids)
                self.assertEqual(network.source_records(ids['school'])[0]['status'], 'declined')

    def test_guardian_revocation_failure_rolls_back_all_related_changes(self):
        pupil, parent = self.ids['student'], self.ids['parent']
        self.approve_child()
        network.set_guardian_consent(parent, pupil, True)
        talent.set_visibility(pupil, True, True)
        talent.save_candidate(201, pupil, True)
        talent.invite(201, pupil, 'Тестовое приглашение для проверки атомарного отзыва.')
        with patch.object(db, 'now', side_effect=ValueError('Simulated failure')), self.assertRaises(ValueError):
            network.set_guardian_consent(parent, pupil, False)
        self.assertTrue(talent.person(pupil)['guardian_consent'])
        self.assertTrue(talent.person(pupil)['share_profile'])
        self.assertTrue(next(p for p in talent.discover(201) if p['id'] == pupil)['saved'])
        self.assertEqual(talent.invitations(student_id=pupil)[0]['status'], 'pending')


if __name__ == '__main__':
    unittest.main()
