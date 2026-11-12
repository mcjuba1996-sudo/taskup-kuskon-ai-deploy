"""Typed buyer entrypoints and a university-to-pupil consent journey."""
import talent_network as network
import talent_store as store
from test_talent_ui import TalentUIBase


class TalentOrganizationUIFlowTests(TalentUIBase):
    def enter_organization(self, kind):
        if 'tt_role' in self.app.session_state and self.app.session_state['tt_role'] is not None:
            self.click('tt_change_role')
        self.click(f'tt_enter_{kind}')
        self.assertEqual(self.app.session_state['tt_role'], 'buyer')
        self.assertEqual(self.app.session_state['tt_buyer_kind'], kind)

    def test_each_buyer_entry_filters_identity_and_student_catalog(self):
        for kind in ('university', 'agency', 'fund'):
            with self.subTest(kind=kind):
                self.enter_organization(kind)
                expected = store.people('buyer', organization_kind=kind)
                selector = self.app.selectbox(key='tt_person_buyer')
                self.assertEqual(selector.options, [person['name'] for person in expected])
                self.assertEqual(store.person(selector.value)['organization_kind'], kind)
                for page in ('review', 'challenges', 'discovery', 'invitations', 'about'):
                    self.click(f'tt_nav_{page}')
                    self.assertEqual(self.app.session_state['tt_page'], page)
        self.enter('student', 105)
        for kind in store.ORGANIZATION_KINDS:
            with self.subTest(catalog_kind=kind):
                self.app.selectbox(key='tt_catalog_kind').set_value(kind).run()
                self.healthy()
                expected_titles = {task['title'] for task in store.challenges()
                                   if store.person(task['buyer_id'])['organization_kind'] == kind}
                self.assertEqual({element.value for element in self.app.subheader}, expected_titles)

    def test_university_review_parent_consent_pupil_visibility_and_invitation(self):
        ids = store.ecosystem_demo_ids()
        actors = network.demo_ids()
        child_id = ids['student']
        university_id = ids['university']
        self.assertEqual(actors['student'], child_id)
        self.enter_organization('university')
        work = next(work for work in store.submissions(buyer_id=university_id)
                    if work['id'] == ids['university_submission'])
        self.assertEqual(work['status'], 'pending')
        self.review(work, [3, 3, 3], True)
        approved = next(work for work in store.submissions(student_id=child_id)
                        if work['id'] == ids['university_submission'])
        self.assertEqual(approved['status'], 'approved')
        self.assertNotIn(child_id, [p['id'] for p in store.discover(university_id)])

        self.enter('parent', actors['parent'])
        self.assertIn('Оценка конкретной работы: 75/100', self.rendered())
        self.app.checkbox(key=f'tt_guardian_granted_{actors["parent"]}_{child_id}').check()
        self.submit(f'tt_guardian_consent_{actors["parent"]}_{child_id}', 'Сохранить согласие представителя')
        self.assertTrue(store.person(child_id)['guardian_consent'])
        self.assertFalse(store.person(child_id)['share_profile'])
        self.assertNotIn(child_id, [p['id'] for p in store.discover(university_id)])

        self.enter('student', child_id)
        self.click('tt_nav_portfolio')
        self.assertTrue(self.app.checkbox(key='tt_guardian_consent').disabled)
        self.assertTrue(self.app.checkbox(key='tt_guardian_consent').value)
        self.app.checkbox(key='tt_share_profile').check()
        self.submit(f'tt_visibility_{child_id}', 'Сохранить видимость')
        self.assertIn(child_id, [p['id'] for p in store.discover(university_id)])

        self.enter_organization('university')
        self.click('tt_nav_discovery')
        self.assertIn(store.person(child_id)['name'], self.rendered())
        message = 'Приглашаем обсудить участие в демонстрационном IT-интенсиве. Это учебная программа, а не решение о зачислении.'
        self.app.text_area(key=f'tt_invite_message_{child_id}').set_value(message)
        self.submit(f'tt_invite_{child_id}', 'Отправить приглашение в демо')
        invitation = store.invitations(student_id=child_id)[0]
        self.assertEqual(invitation['buyer_id'], university_id)
        self.assertEqual(invitation['status'], 'pending')
        self.enter('student', child_id)
        self.click('tt_nav_invitations')
        self.assertIn(message, self.rendered())
        self.click(f'tt_accept_{invitation["id"]}')
        self.assertEqual(store.invitations(student_id=child_id)[0]['status'], 'accepted')
        self.enter('parent', actors['parent'])
        self.assertIn(message, self.rendered())
        self.assertIn('Принято школьником', self.rendered())
        self.assertNotIn(f'tt_accept_{invitation["id"]}', [button.key for button in self.app.button])
