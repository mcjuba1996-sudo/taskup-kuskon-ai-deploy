"""Evidence-based review and independent personal-project journeys."""
import personal_projects as projects
import talent_store as store
from talent_evidence_ui import passport_report
from test_talent_ui import TalentUIBase


class TalentV2UIFlowTests(TalentUIBase):
    def test_defense_answer_assessment_review_and_auditable_passport(self):
        self.enter('buyer', 201)
        work = next(w for w in store.submissions(student_id=105) if w['status'] == 'pending')
        wid = work['id']
        self.assertIn('Понимание решения не проверялось', self.rendered())
        question = 'Почему соседние интервалы без общей длительности не считаются конфликтом расписания?'
        change = 'Добавьте проверку кабинета: пересечения разных кабинетов не должны считаться конфликтами.'
        self.app.text_area(key=f'tt_question_{wid}').set_value(question)
        self.app.text_area(key=f'tt_change_request_{wid}').set_value(change)
        self.submit(f'tt_defense_request_{wid}_{work["version"]}', 'Запросить защиту работы')
        defense = store.defense_rounds(wid, 201)[0]
        self.assertEqual(defense['status'], 'requested')
        self.assertEqual(store.submissions(student_id=105)[0]['understanding_status'], 'requested')

        self.enter('student', 105)
        self.click('tt_nav_works')
        self.assertIn(question, self.rendered())
        did = defense['id']
        answer = 'Использовано строгое сравнение начала одного интервала с концом другого, поэтому общая граница не пересекается.'
        change_result = 'Добавлено сравнение кабинета перед проверкой интервалов. Проверены одинаковые интервалы в двух кабинетах; помощь не использовалась.'
        self.app.text_area(key=f'tt_defense_answer_{did}').set_value(answer)
        self.app.text_area(key=f'tt_defense_change_{did}').set_value(change_result)
        self.app.text_input(key=f'tt_defense_url_{did}').set_value('https://example.com/demo/room-conflicts')
        self.app.text_input(key=f'tt_defense_source_{did}').set_value('demo-commit-rooms-v2')
        self.submit(f'tt_defense_answer_{did}_{defense["version"]}', 'Отправить ответ проверяющему')
        defense = store.defense_rounds(wid, 105)[0]
        self.assertEqual(defense['status'], 'answered')
        self.assertEqual(store.submissions(student_id=105)[0]['understanding_status'], 'answered')
        self.assertNotIn('Понимание решения проверено', self.rendered())

        self.enter('buyer', 201)
        observations = ('В ответе корректно объяснена строгая граница интервала. В изменении добавлен фильтр кабинета; '
                        'на одинаковых интервалах разных кабинетов конфликта больше нет.')
        self.app.text_area(key=f'tt_defense_observation_{did}').set_value(observations)
        self.app.text_input(key=f'tt_defense_reviewer_{did}').set_value('Демо-эксперт В.')
        self.app.text_input(key=f'tt_defense_role_{did}').set_value('Наставник Python программы')
        self.app.text_area(key=f'tt_defense_limits_{did}').set_value('Не проверялись часовые пояса и происхождение исходного кода.')
        self.app.radio(key=f'tt_defense_verdict_{did}').set_value('Понимание показано')
        self.submit(f'tt_defense_assess_{did}_{defense["version"]}', 'Сохранить наблюдения')
        defense = store.defense_rounds(wid, 201)[0]
        self.assertEqual(defense['status'], 'confirmed')
        work = next(w for w in store.submissions(student_id=105) if w['id'] == wid)
        self.assertEqual(work['status'], 'pending', 'Defense does not grade the project automatically.')
        self.assertEqual(work['understanding_status'], 'confirmed')
        self.review(work, [3, 4, 3], True)
        accepted = next(w for w in store.submissions(student_id=105) if w['id'] == wid)
        self.assertEqual(accepted['status'], 'approved')
        self.assertEqual(accepted['total'], 83.75)
        self.assertEqual(len(accepted['criterion_evidence']), 3)

        self.enter('student', 105)
        self.click('tt_nav_portfolio')
        rendered = self.rendered()
        self.assertIn('Понимание решения проверено', rendered)
        self.assertIn('Демо-наставник А.', rendered)
        self.assertIn(observations, rendered)
        self.assertIn('История версий и решений', [e.label for e in self.app.expander])
        events = store.history(wid, 105)
        self.assertEqual([e['event'] for e in events][-4:],
                         ['defense_requested', 'defense_answered', 'defense_assessed', 'approved'])
        self.assertEqual(events[-1]['snapshot']['ratings'], [3, 4, 3])
        self.assertEqual(events[-4]['snapshot']['ratings'], [])
        report = passport_report(accepted, store.person(105), 105)
        for value in (question, answer, observations, 'Демо-наставник А.', '83.75', '40%',
                      'Личность автора', 'Понимание решения проверено'):
            self.assertIn(value, report)

    def test_personal_draft_self_report_edit_and_explicit_handoff(self):
        self.enter('student', 105)
        self.click('tt_nav_projects')
        before = len(store.submissions(student_id=105))
        self.app.text_input(key='tt_project_new_0_title').set_value('Мой учебный отчёт')
        self.submit('tt_project_new_0', 'Сохранить проект')
        project = projects.projects(105)[0]
        self.assertEqual(project['version'], 1)
        self.assertEqual(len(store.submissions(student_id=105)), before)
        report = projects.project_report(project)
        self.assertIn(projects.SELF_ASSESSMENT, report)
        self.assertIn('Черновик', report)
        self.assertIn('Скачать отчёт самооценки', [w.label for w in self.app.get('download_button')])
        self.assertNotIn(105, [p['id'] for p in store.discover(201)])

        prefix = f'tt_project_{project["id"]}_{project["version"]}'
        self.app.text_area(key=prefix + '_description').set_value(
            'Подготовлены расчёты и два графика по синтетическим посещениям. Проверка воспроизводится по инструкции.')
        self.app.text_input(key=prefix + '_url').set_value('https://example.com/demo/my-analysis')
        self.app.text_input(key=prefix + '_source').set_value('report-v2')
        self.app.text_area(key=prefix + '_contribution').set_value(
            'Самостоятельно рассчитаны показатели, построены графики и проверены основные контрольные суммы.')
        self.app.text_area(key=prefix + '_help').set_value('Использованы Python и подсказка наставника для оформления графика.')
        for check in projects.CHECKLIST:
            self.app.checkbox(key=prefix + '_' + check['id']).check()
        self.submit(prefix, 'Сохранить проект')
        project = projects.projects(105)[0]
        self.assertEqual(project['version'], 2)
        self.assertEqual(projects.completeness(project), [])
        self.assertEqual(len(store.submissions(student_id=105)), before)
        report = projects.project_report(project)
        self.assertIn(projects.SELF_ASSESSMENT, report)
        self.assertNotIn('Результат принят', report)

        pid = project['id']
        self.app.selectbox(key=f'tt_project_target_{pid}').set_value(1).run()
        self.healthy()
        self.submit(f'tt_project_transfer_{pid}_{project["version"]}_1', 'Передать на проверку')
        self.assertIn('Подтвердите передачу', self.rendered())
        self.assertEqual(len(store.submissions(student_id=105)), before)
        self.app.checkbox(key=f'tt_project_consent_{pid}_1').check()
        self.submit(f'tt_project_transfer_{pid}_{project["version"]}_1', 'Передать на проверку')
        work = next(w for w in store.submissions(student_id=105) if w['challenge_id'] == 1)
        self.assertEqual(work['status'], 'pending')
        self.assertEqual(work['source_version'], 'report-v2')
        self.assertIn('Мой учебный отчёт', work['description'])
        self.assertEqual(len(store.submissions(student_id=105)), before + 1)
        self.assertEqual(projects.projects(105)[0], project, 'Handoff leaves the private draft intact.')
        self.assertNotIn(105, [p['id'] for p in store.discover(201)])

    def test_stale_personal_project_form_does_not_overwrite_newer_edit(self):
        self.enter('student', 105)
        self.click('tt_nav_projects')
        self.app.text_input(key='tt_project_new_0_title').set_value('Проект до изменения')
        self.submit('tt_project_new_0', 'Сохранить проект')
        project = projects.projects(105)[0]
        prefix = f'tt_project_{project["id"]}_{project["version"]}'
        self.app.text_input(key=prefix + '_title').set_value('Заголовок из устаревшей вкладки')
        projects.save_project(105, 'Новая версия из другой вкладки', '', '', '', '', [],
                              project_id=project['id'], expected_version=project['version'])
        self.submit(prefix, 'Сохранить проект')
        latest = projects.projects(105)[0]
        self.assertEqual(latest['title'], 'Новая версия из другой вкладки')
        self.assertEqual(latest['version'], 2)
