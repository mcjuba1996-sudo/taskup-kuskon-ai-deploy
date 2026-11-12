"""Source acceptance, guardian scope, and public visibility through demo UI."""
import personal_projects as projects
import talent_network as network
import talent_store as store
from test_talent_ui import TalentUIBase


class TalentNetworkUIFlowTests(TalentUIBase):
    def issue(self, source_id, student_id, title):
        self.app.selectbox(key=f'tt_source_student_{source_id}').set_value(student_id)
        self.app.text_input(key=f'tt_source_title_{source_id}').set_value(title)
        self.app.text_input(key=f'tt_source_event_{source_id}').set_value('Учебная демонстрационная программа')
        self.app.text_area(key=f'tt_source_result_{source_id}').set_value('Участник представил учебный результат на разборе программы.')
        self.app.text_input(key=f'tt_source_url_{source_id}').set_value('https://example.com/demo/protocol')
        self.app.text_area(key=f'tt_source_method_{source_id}').set_value(
            'Демо-наставник сопоставил результат с вымышленным протоколом учебной программы и записью выступления.')
        self.app.text_area(key=f'tt_source_limits_{source_id}').set_value('Реальная личность и независимое авторство не проверялись.')
        self.submit(f'tt_source_issue_{source_id}', 'Передать запись школьнику')
        return network.source_records(source_id)[0]

    def assert_support_role_has_no_buyer_controls(self):
        keys = {button.key for button in self.app.button}
        for forbidden in ('tt_nav_discovery', 'tt_nav_review', 'tt_nav_challenges', 'tt_nav_projects'):
            self.assertNotIn(forbidden, keys)

    def test_school_record_requires_student_acceptance_and_visibility_then_can_be_revoked(self):
        ids = network.demo_ids()
        self.enter('school', ids['school'])
        self.assert_support_role_has_no_buyer_controls()
        self.assertEqual({p['id'] for p in network.source_students(ids['school'])}, {101, ids['student']})
        record = self.issue(ids['school'], 101, 'Учебный анализ данных школы')
        self.assertEqual(record['status'], 'offered')
        self.assertEqual(network.public_records(201, 101), [])

        self.enter('buyer', 201)
        self.click('tt_nav_discovery')
        self.assertNotIn(record['title'], self.rendered())
        self.enter('student', 101)
        self.click('tt_nav_achievements')
        self.assertIn(record['title'], self.rendered())
        self.click(f'tt_record_accept_{record["id"]}')
        self.assertEqual(network.student_records(101)[0]['status'], 'accepted')
        self.assertIn(record['id'], [r['id'] for r in network.public_records(201, 101)])
        self.enter('buyer', 201)
        self.click('tt_nav_discovery')
        self.assertIn(record['title'], self.rendered())
        self.assertIn('Платформа не проводила независимую проверку', self.rendered())

        self.enter('student', 101)
        self.click('tt_nav_portfolio')
        self.app.checkbox(key='tt_share_profile').uncheck()
        self.submit('tt_visibility_101', 'Сохранить видимость')
        self.assertEqual(network.public_records(201, 101), [])
        self.enter('buyer', 201)
        self.click('tt_nav_discovery')
        self.assertNotIn(record['title'], self.rendered())

        self.enter('school', ids['school'])
        reason = 'Источник обнаружил ошибку в тестовом протоколе, запись отзывается до исправления.'
        self.app.text_area(key=f'tt_source_revoke_reason_{record["id"]}').set_value(reason)
        self.submit(f'tt_source_revoke_{record["id"]}', 'Отозвать запись источника')
        self.assertEqual(network.source_records(ids['school'])[0]['status'], 'revoked')
        self.enter('student', 101)
        self.click('tt_nav_achievements')
        self.assertIn(reason, self.rendered())
        self.assertNotIn(f'tt_record_accept_{record["id"]}', [b.key for b in self.app.button])

    def test_organizer_roster_is_separate_and_pupil_can_decline(self):
        ids = network.demo_ids()
        self.enter('school', ids['school'])
        self.app.text_input(key=f'tt_source_title_{ids["school"]}').set_value('Незавершённый школьный черновик')
        self.enter('organizer', ids['organizer'])
        self.assert_support_role_has_no_buyer_controls()
        self.assertEqual({p['id'] for p in network.source_students(ids['organizer'])}, {102, 105})
        self.assertEqual(self.app.text_input(key=f'tt_source_title_{ids["organizer"]}').value, '')
        self.assertNotIn(store.person(101)['name'], self.app.selectbox(key=f'tt_source_student_{ids["organizer"]}').options)
        record = self.issue(ids['organizer'], 102, 'Участие в учебном конкурсе решений')
        self.enter('student', 102)
        self.click('tt_nav_achievements')
        self.click(f'tt_record_decline_{record["id"]}')
        self.assertEqual(network.student_records(102)[0]['status'], 'declined')
        self.assertEqual(network.public_records(201, 102), [])
        self.enter('organizer', ids['organizer'])
        self.assertIn('Школьник отклонил запись', self.rendered())
        self.assertNotIn(f'FormSubmitter:tt_source_revoke_{record["id"]}-Отозвать запись источника',
                         [button.key for button in self.app.button])

    def test_guardian_sees_only_linked_child_and_cannot_enable_pupil_sharing(self):
        ids = network.demo_ids()
        child_id = ids['student']
        private_title = 'Частная идея, недоступная законному представителю'
        projects.save_project(child_id, private_title, '', '', '', '', [])
        store.submit_work(1, child_id, 'https://example.com/demo/child-work',
                          'Тестовая работа школьника: расчёты и примеры результата с пояснением.',
                          'Самостоятельно подготовлены примеры и проверены контрольные расчёты.')
        self.enter('parent', ids['parent'])
        self.assert_support_role_has_no_buyer_controls()
        options = self.app.selectbox(key=f'tt_guardian_child_{ids["parent"]}').options
        self.assertEqual(options, [store.person(child_id)['name']])
        self.assertEqual([child['id'] for child in network.guardian_children(ids['parent'])], [child_id])
        self.assertIn(store.challenges()[-1]['title'], self.rendered())
        self.assertNotIn(private_title, self.rendered())
        self.assertNotIn('Оценка конкретной работы:', self.rendered())
        self.assertFalse(store.person(child_id)['share_profile'])
        self.app.checkbox(key=f'tt_guardian_granted_{ids["parent"]}_{child_id}').check()
        self.submit(f'tt_guardian_consent_{ids["parent"]}_{child_id}', 'Сохранить согласие представителя')
        self.assertTrue(store.person(child_id)['guardian_consent'])
        self.assertFalse(store.person(child_id)['share_profile'])
        self.assertEqual(store.person(101)['guardian_consent'], True, 'Unrelated pupils remain unchanged.')
        self.app.checkbox(key=f'tt_guardian_granted_{ids["parent"]}_{child_id}').uncheck()
        self.submit(f'tt_guardian_consent_{ids["parent"]}_{child_id}', 'Сохранить согласие представителя')
        self.assertFalse(store.person(child_id)['guardian_consent'])

    def test_open_pupil_portfolio_refreshes_guardian_changes_from_another_session(self):
        ids = network.demo_ids()
        child_id = ids['student']
        self.enter('student', child_id)
        self.click('tt_nav_portfolio')
        self.assertTrue(self.app.checkbox(key='tt_guardian_consent').disabled)
        self.assertFalse(self.app.checkbox(key='tt_guardian_consent').value)

        network.set_guardian_consent(ids['parent'], child_id, True)
        self.app.run()
        self.healthy()
        self.assertTrue(self.app.checkbox(key='tt_guardian_consent').disabled)
        self.assertTrue(self.app.checkbox(key='tt_guardian_consent').value)
        self.app.checkbox(key='tt_share_profile').check()
        self.submit(f'tt_visibility_{child_id}', 'Сохранить видимость')
        self.assertFalse(self.app.error)
        self.assertTrue(store.person(child_id)['share_profile'])
        self.assertTrue(store.person(child_id)['guardian_consent'])

        network.set_guardian_consent(ids['parent'], child_id, False)
        self.app.run()
        self.healthy()
        self.assertTrue(self.app.checkbox(key='tt_guardian_consent').disabled)
        self.assertFalse(self.app.checkbox(key='tt_guardian_consent').value)
        with self.assertRaisesRegex(ValueError, 'родительском'):
            store.set_visibility(child_id, True, True)
        self.assertFalse(store.person(child_id)['guardian_consent'])
        self.app.checkbox(key='tt_share_profile').uncheck()
        self.submit(f'tt_visibility_{child_id}', 'Сохранить видимость')
        self.assertFalse(self.app.error)
        self.assertFalse(store.person(child_id)['share_profile'])
        self.assertFalse(store.person(child_id)['guardian_consent'])
