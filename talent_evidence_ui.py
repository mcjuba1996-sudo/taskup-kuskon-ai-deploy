"""Evidence, defense and immutable history for the synthetic demonstration."""
import streamlit as st
import talent_store as store

UNDERSTANDING = {
    'not_requested': 'Понимание решения не проверялось',
    'requested': 'Ожидается ответ на вопросы',
    'answered': 'Ответ получен, оценка понимания ожидается',
    'confirmed': 'Понимание решения проверено',
    'needs_clarification': 'Понимание требует уточнения',
}
EVENTS = {'baseline_imported': 'Начальное состояние сохранённой работы',
          'submitted': 'Работа отправлена', 'resubmitted': 'Отправлена доработка',
          'reviewed': 'Решение проверяющего', 'approved': 'Работа принята',
          'changes_requested': 'Запрошена доработка', 'defense_requested': 'Запрошена защита',
          'defense_answered': 'Получен ответ школьника', 'defense_assessed': 'Оценено понимание'}


def act(callback, message):
    try:
        callback()
    except ValueError as error:
        st.error(str(error))
        return
    st.session_state['tt_flash'] = message
    st.rerun()


def evidence_summary(work):
    st.caption(f'Редакция работы {work.get("work_revision", 1)} · '
               f'Версия источника со слов автора: {work.get("source_version") or "не указана"}')
    status = work.get('understanding_status', 'not_requested')
    if status == 'confirmed':
        st.success(UNDERSTANDING[status])
    else:
        st.caption(UNDERSTANDING.get(status, status))
    st.caption('Эта отметка отражает наблюдения проверяющего по ответу и изменению решения. '
               'Она не удостоверяет личность или авторство всей работы.')
    if work['status'] != 'pending':
        st.markdown('**Основания оценок**')
        evidence = work.get('criterion_evidence', [])
        for i, criterion in enumerate(work['criteria']):
            if i < len(work['ratings']):
                points = criterion['weight'] * work['ratings'][i] / 4
                st.markdown(f'**{criterion["label"]}: {work["ratings"][i]}/4 × {criterion["weight"]}% = {points:g} балла**')
                st.write(evidence[i] if i < len(evidence) and evidence[i] else
                         'Подробное свидетельство не сохранено в ранней демонстрационной версии.')
        name = work.get('reviewer_name') or 'Индивидуальный проверяющий не указан'
        role = work.get('reviewer_role') or 'Роль не указана'
        st.caption(f'{name} · {role} · {work.get("reviewer_org") or work["buyer_name"]}')
        if work.get('review_limitations'):
            st.markdown('**Ограничения проверки**')
            st.write(work['review_limitations'])


def round_details(item):
    st.markdown('**Вопрос по решению**')
    st.write(item['question'])
    st.markdown('**Небольшое изменение**')
    st.write(item['change_request'])
    if item.get('answer'):
        st.markdown('**Ответ школьника**')
        st.write(item['answer'])
        st.markdown('**Что изменено и как проверено**')
        st.write(item['change_description'])
        st.link_button(f'Результат изменения · защита №{item["id"]}', item['evidence_url'])
        st.caption('Версия источника со слов автора: ' + (item.get('source_version') or 'не указана'))
    if item.get('observations'):
        st.markdown('**Наблюдения проверяющего**')
        st.write(item['observations'])
        st.caption(f'{item.get("reviewer_name", "")} · {item.get("reviewer_role", "")} · {item.get("assessed_at") or ""}')
        if item.get('limitations'):
            st.write('Ограничения: ' + item['limitations'])


def defense_record(work, viewer_id):
    rounds = store.defense_rounds(work['id'], viewer_id)
    if not rounds:
        return
    with st.expander('Вопросы, ответы и наблюдения проверки'):
        for item in rounds:
            st.caption(f'Защита №{item["id"]} · редакция работы {item["work_revision"]} · '
                       f'{UNDERSTANDING.get(item["status"], item["status"])}')
            round_details(item)
            st.divider()


def history_panel(work, viewer_id):
    with st.expander('История версий и решений'):
        for item in store.history(work['id'], viewer_id):
            snapshot = item['snapshot']
            st.markdown(f'**{EVENTS.get(item["event"], item["event"])}**')
            st.caption(f'{item["created"]} · {item.get("actor_name") or "Система"}')
            if item['event'] == 'baseline_imported':
                st.caption('Сохранено состояние на момент обновления приложения. Более ранние версии восстановить нельзя.')
            st.caption(f'Редакция {snapshot.get("work_revision", 1)} · версия состояния {snapshot.get("version", "—")}')
            st.write(snapshot.get('description', ''))
            st.write('Личный вклад и выводы: ' + snapshot.get('reflection', ''))
            st.write('Источник: ' + snapshot.get('evidence_url', ''))
            st.write('Версия источника: ' + (snapshot.get('source_version') or 'не указана'))
            if snapshot.get('feedback'):
                st.write('Решение: ' + snapshot['feedback'])
                st.write(f'Оценки: {snapshot.get("ratings", [])} · итог {snapshot.get("total", 0):g}/100')
            for criterion, evidence in zip(snapshot.get('criteria', []), snapshot.get('criterion_evidence', [])):
                st.write(f'{criterion["label"]}: {evidence}')
            if snapshot.get('reviewer_name'):
                st.write('Проверяющий: ' + snapshot['reviewer_name'] + ' · ' + snapshot.get('reviewer_role', '')
                         + ' · ' + snapshot.get('reviewer_org', ''))
                st.write('Ограничения проверки: ' + (snapshot.get('review_limitations') or 'не указаны'))
            st.divider()
        st.caption('История хранит введённые сведения и решения. Содержимое внешнего сайта по ссылке может измениться; '
                   'для точной привязки используйте ссылку на конкретный коммит или неизменяемую версию файла.')


def student_defense(work, student_id):
    if work['status'] != 'pending':
        return
    current = [r for r in store.defense_rounds(work['id'], student_id)
               if r['work_revision'] == work['work_revision'] and r['status'] == 'requested']
    for item in current:
        did = item['id']
        st.subheader('Покажите понимание своего решения')
        st.write('Вопрос: ' + item['question'])
        st.write('Изменение: ' + item['change_request'])
        st.caption('Ответ и результат увидит заказчик задания. Опишите помощь и инструменты, если использовали их.')
        with st.form(f'tt_defense_answer_{did}_{item["version"]}'):
            answer = st.text_area('Объяснение решения', max_chars=4000, key=f'tt_defense_answer_{did}')
            change = st.text_area('Что изменено, как проверено и какая помощь использовалась', max_chars=4000, key=f'tt_defense_change_{did}')
            url = st.text_input('Ссылка на результат изменения', max_chars=2000, key=f'tt_defense_url_{did}')
            source = st.text_input('Коммит или версия результата', max_chars=200, key=f'tt_defense_source_{did}')
            send = st.form_submit_button('Отправить ответ проверяющему', type='primary')
        if send:
            act(lambda: store.answer_defense(did, student_id, item['version'], answer, change, url, source_version=source),
                'Ответ отправлен. Отметка о понимании появится только после оценки проверяющего.')


def buyer_defense(work, buyer_id):
    rounds = [r for r in store.defense_rounds(work['id'], buyer_id) if r['work_revision'] == work['work_revision']]
    active = next((r for r in rounds if r['status'] in ('requested', 'answered')), None)
    with st.expander('Проверить понимание решения', expanded=bool(active)):
        st.caption('Запросите объяснение и небольшое изменение по теме задания. Оценивайте наблюдаемый ответ; '
                   'использование ИИ или помощь наставника сами по себе не означают отсутствие понимания.')
        if active:
            if active['status'] == 'requested':
                st.info('Вопрос отправлен. Ответить можно в роли школьника, в разделе «Мои работы».')
                st.write(active['question'])
                st.write(active['change_request'])
            else:
                round_details(active)
                did = active['id']
                with st.form(f'tt_defense_assess_{did}_{active["version"]}'):
                    observations = st.text_area('Что конкретно показал ответ и результат изменения', max_chars=4000,
                                                key=f'tt_defense_observation_{did}')
                    name = st.text_input('Имя проверяющего (демо)', max_chars=120, key=f'tt_defense_reviewer_{did}')
                    role = st.text_input('Роль и компетенция проверяющего', max_chars=120, key=f'tt_defense_role_{did}')
                    limits = st.text_area('Что осталось непроверенным', max_chars=2000, key=f'tt_defense_limits_{did}')
                    understood = st.radio('Вывод по пониманию', ['Нужно уточнение', 'Понимание показано'], key=f'tt_defense_verdict_{did}')
                    assess = st.form_submit_button('Сохранить наблюдения', type='primary')
                if assess:
                    act(lambda: store.assess_defense(did, buyer_id, active['version'], understood == 'Понимание показано',
                                                     observations, name, role, limitations=limits),
                        'Наблюдения сохранены. Итоговую оценку работы выставьте отдельно по критериям.')
        else:
            if work.get('understanding_status') == 'confirmed':
                st.success('Понимание по текущей редакции уже оценено. При необходимости можно задать следующий вопрос.')
            with st.form(f'tt_defense_request_{work["id"]}_{work["version"]}'):
                question = st.text_area('Вопрос по решению', max_chars=2000,
                    placeholder='Почему соседние интервалы времени не считаются пересечением?', key=f'tt_question_{work["id"]}')
                change = st.text_area('Небольшое изменение для проверки понимания', max_chars=2000,
                    placeholder='Добавьте учёт кабинета: конфликт возможен только в одном кабинете.', key=f'tt_change_request_{work["id"]}')
                request = st.form_submit_button('Запросить защиту работы')
            if request:
                act(lambda: store.request_defense(work['id'], buyer_id, work['version'], question, change), 'Вопрос и изменение отправлены школьнику.')


def passport_report(work, pupil, viewer_id):
    lines = ['# Паспорт работы — ДЕМО', '', work['challenge_title'], '',
             f'Профиль: {pupil["name"]}', f'Редакция работы: {work.get("work_revision", 1)}',
             f'Результат: {work["evidence_url"]}', f'Версия источника со слов автора: {work.get("source_version") or "не указана"}',
             '', work['description'], '', '## Вклад и инструменты', work['reflection'], '',
             '## Оценка результата', f'{work["total"]:g}/100', 'Формула: сумма (оценка / 4 × вес).', '']
    evidence = work.get('criterion_evidence', [])
    for i, (criterion, rating) in enumerate(zip(work['criteria'], work['ratings'])):
        lines += [f'- {criterion["label"]}: {rating}/4 × {criterion["weight"]}% = {rating * criterion["weight"] / 4:g}',
                  '  Основание: ' + (evidence[i] if i < len(evidence) else 'не сохранено в раннем демо')]
    lines += ['', 'Комментарий: ' + work['feedback'],
              'Проверяющий: ' + (work.get('reviewer_name') or 'не указан') + ' · ' + (work.get('reviewer_role') or 'роль не указана'),
              'Организация: ' + work['buyer_name'], 'Дата: ' + (work['reviewed_at'] or ''),
              'Ограничения: ' + (work.get('review_limitations') or 'не указаны'), '', '## Проверка понимания',
              UNDERSTANDING.get(work.get('understanding_status', 'not_requested'))]
    for item in store.defense_rounds(work['id'], viewer_id):
        if item['work_revision'] == work['work_revision']:
            lines += ['', f'Вопрос: {item["question"]}', f'Изменение: {item["change_request"]}',
                      f'Ответ: {item.get("answer") or "ожидается"}', f'Результат изменения: {item.get("evidence_url") or "нет"}',
                      f'Наблюдения: {item.get("observations") or "проверка не завершена"}',
                      f'Проверяющий: {item.get("reviewer_name") or "не указан"} · {item.get("reviewer_role") or ""}',
                      f'Ограничения: {item.get("limitations") or "не указаны"}']
    lines += ['', 'Все данные синтетические. Паспорт фиксирует оценку конкретной работы, не удостоверяет личность '
              'или авторство всей работы. Содержимое внешней ссылки может измениться.']
    return '\n'.join(lines) + '\n'
