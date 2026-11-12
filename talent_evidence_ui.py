"""Evidence, defense and immutable history for the synthetic demonstration."""
import streamlit as st
import talent_store as store
from talent_i18n import t, td, error_text

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
        st.error(error_text(str(error)))
        return
    st.session_state['tt_flash'] = t(message)
    st.rerun()


def evidence_summary(work):
    st.caption(t('Редакция работы {revision} · Версия источника со слов автора: {source_version}',
                 revision=work.get('work_revision', 1), source_version=td(work.get('source_version') or '') or t('не указана')))
    status = work.get('understanding_status', 'not_requested')
    if status == 'confirmed':
        st.success(t(UNDERSTANDING[status]))
    else:
        st.caption(t(UNDERSTANDING.get(status, status)))
    st.caption(t('Эта отметка отражает наблюдения проверяющего по ответу и изменению решения. '
                 'Она не удостоверяет личность или авторство всей работы.'))
    if work['status'] != 'pending':
        st.markdown(t('**Основания оценок**'))
        evidence = work.get('criterion_evidence', [])
        for i, criterion in enumerate(work['criteria']):
            if i < len(work['ratings']):
                points = criterion['weight'] * work['ratings'][i] / 4
                st.markdown(t('**{label}: {rating}/4 × {weight}% = {points:g} балла**', label=td(criterion['label']),
                              rating=work['ratings'][i], weight=criterion['weight'], points=points))
                st.write(td(evidence[i]) if i < len(evidence) and evidence[i] else
                         t('Подробное свидетельство не сохранено в ранней демонстрационной версии.'))
        name = td(work.get('reviewer_name') or '') or t('Индивидуальный проверяющий не указан')
        role = td(work.get('reviewer_role') or '') or t('Роль не указана')
        st.caption(f'{name} · {role} · {td(work.get("reviewer_org") or work["buyer_name"])}')
        if work.get('review_limitations'):
            st.markdown(t('**Ограничения проверки**'))
            st.write(td(work['review_limitations']))


def round_details(item):
    st.markdown(t('**Вопрос по решению**'))
    st.write(item['question'])
    st.markdown(t('**Небольшое изменение**'))
    st.write(item['change_request'])
    if item.get('answer'):
        st.markdown(t('**Ответ школьника**'))
        st.write(item['answer'])
        st.markdown(t('**Что изменено и как проверено**'))
        st.write(item['change_description'])
        st.link_button(t('Результат изменения · защита №{id}', id=item['id']), item['evidence_url'])
        st.caption(t('Версия источника со слов автора: {source_version}', source_version=td(item.get('source_version') or '') or t('не указана')))
    if item.get('observations'):
        st.markdown(t('**Наблюдения проверяющего**'))
        st.write(item['observations'])
        st.caption(f'{td(item.get("reviewer_name", ""))} · {td(item.get("reviewer_role", ""))} · {item.get("assessed_at") or ""}')
        if item.get('limitations'):
            st.write(t('Ограничения: {limitations}', limitations=item['limitations']))


def defense_record(work, viewer_id):
    rounds = store.defense_rounds(work['id'], viewer_id)
    if not rounds:
        return
    with st.expander(t('Вопросы, ответы и наблюдения проверки')):
        for item in rounds:
            st.caption(t('Защита №{id} · редакция работы {revision} · {status}', id=item['id'],
                         revision=item['work_revision'], status=t(UNDERSTANDING.get(item['status'], item['status']))))
            round_details(item)
            st.divider()


def history_panel(work, viewer_id):
    with st.expander(t('История версий и решений')):
        for item in store.history(work['id'], viewer_id):
            snapshot = item['snapshot']
            st.markdown(f'**{t(EVENTS.get(item["event"], item["event"]))}**')
            st.caption(f'{item["created"]} · {td(item.get("actor_name") or "") or t("Система")}')
            if item['event'] == 'baseline_imported':
                st.caption(t('Сохранено состояние на момент обновления приложения. Более ранние версии восстановить нельзя.'))
            st.caption(t('Редакция {revision} · версия состояния {version}', revision=snapshot.get('work_revision', 1),
                         version=snapshot.get('version', '—')))
            st.write(td(snapshot.get('description', '')))
            st.write(t('Личный вклад и выводы: {reflection}', reflection=td(snapshot.get('reflection', ''))))
            st.write(t('Источник: {url}', url=snapshot.get('evidence_url', '')))
            st.write(t('Версия источника: {source_version}', source_version=td(snapshot.get('source_version') or '') or t('не указана')))
            if snapshot.get('feedback'):
                st.write(t('Решение: {feedback}', feedback=td(snapshot['feedback'])))
                st.write(t('Оценки: {ratings} · итог {total:g}/100', ratings=snapshot.get('ratings', []), total=snapshot.get('total', 0)))
            for criterion, evidence in zip(snapshot.get('criteria', []), snapshot.get('criterion_evidence', [])):
                st.write(f'{td(criterion["label"])}: {td(evidence)}')
            if snapshot.get('reviewer_name'):
                st.write(t('Проверяющий: {name} · {role} · {organization}', name=td(snapshot['reviewer_name']),
                           role=td(snapshot.get('reviewer_role', '')), organization=td(snapshot.get('reviewer_org', ''))))
                st.write(t('Ограничения проверки: {limitations}', limitations=td(snapshot.get('review_limitations') or '') or t('не указаны')))
            st.divider()
        st.caption(t('История хранит введённые сведения и решения. Содержимое внешнего сайта по ссылке может измениться; '
                     'для точной привязки используйте ссылку на конкретный коммит или неизменяемую версию файла.'))


def student_defense(work, student_id):
    if work['status'] != 'pending':
        return
    current = [r for r in store.defense_rounds(work['id'], student_id)
               if r['work_revision'] == work['work_revision'] and r['status'] == 'requested']
    for item in current:
        did = item['id']
        st.subheader(t('Покажите понимание своего решения'))
        st.write(t('Вопрос: {question}', question=item['question']))
        st.write(t('Изменение: {change}', change=item['change_request']))
        st.caption(t('Ответ и результат увидит заказчик задания. Опишите помощь и инструменты, если использовали их.'))
        with st.form(f'tt_defense_answer_{did}_{item["version"]}'):
            answer = st.text_area(t('Объяснение решения'), max_chars=4000, key=f'tt_defense_answer_{did}')
            change = st.text_area(t('Что изменено, как проверено и какая помощь использовалась'), max_chars=4000, key=f'tt_defense_change_{did}')
            url = st.text_input(t('Ссылка на результат изменения'), max_chars=2000, key=f'tt_defense_url_{did}')
            source = st.text_input(t('Коммит или версия результата'), max_chars=200, key=f'tt_defense_source_{did}')
            send = st.form_submit_button(t('Отправить ответ проверяющему'), type='primary')
        if send:
            act(lambda: store.answer_defense(did, student_id, item['version'], answer, change, url, source_version=source),
                'Ответ отправлен. Отметка о понимании появится только после оценки проверяющего.')


def buyer_defense(work, buyer_id):
    rounds = [r for r in store.defense_rounds(work['id'], buyer_id) if r['work_revision'] == work['work_revision']]
    active = next((r for r in rounds if r['status'] in ('requested', 'answered')), None)
    with st.expander(t('Проверить понимание решения'), expanded=bool(active)):
        st.caption(t('Запросите объяснение и небольшое изменение по теме задания. Оценивайте наблюдаемый ответ; '
                     'использование ИИ или помощь наставника сами по себе не означают отсутствие понимания.'))
        if active:
            if active['status'] == 'requested':
                st.info(t('Вопрос отправлен. Ответить можно в роли школьника, в разделе «Мои работы».'))
                st.write(active['question'])
                st.write(active['change_request'])
            else:
                round_details(active)
                did = active['id']
                with st.form(f'tt_defense_assess_{did}_{active["version"]}'):
                    observations = st.text_area(t('Что конкретно показал ответ и результат изменения'), max_chars=4000,
                                                key=f'tt_defense_observation_{did}')
                    name = st.text_input(t('Имя проверяющего (демо)'), max_chars=120, key=f'tt_defense_reviewer_{did}')
                    role = st.text_input(t('Роль и компетенция проверяющего'), max_chars=120, key=f'tt_defense_role_{did}')
                    limits = st.text_area(t('Что осталось непроверенным'), max_chars=2000, key=f'tt_defense_limits_{did}')
                    understood = st.radio(t('Вывод по пониманию'), ['Нужно уточнение', 'Понимание показано'], format_func=t, key=f'tt_defense_verdict_{did}')
                    assess = st.form_submit_button(t('Сохранить наблюдения'), type='primary')
                if assess:
                    act(lambda: store.assess_defense(did, buyer_id, active['version'], understood == 'Понимание показано',
                                                     observations, name, role, limitations=limits),
                        'Наблюдения сохранены. Итоговую оценку работы выставьте отдельно по критериям.')
        else:
            if work.get('understanding_status') == 'confirmed':
                st.success(t('Понимание по текущей редакции уже оценено. При необходимости можно задать следующий вопрос.'))
            with st.form(f'tt_defense_request_{work["id"]}_{work["version"]}'):
                question = st.text_area(t('Вопрос по решению'), max_chars=2000,
                    placeholder=t('Почему соседние интервалы времени не считаются пересечением?'), key=f'tt_question_{work["id"]}')
                change = st.text_area(t('Небольшое изменение для проверки понимания'), max_chars=2000,
                    placeholder=t('Добавьте учёт кабинета: конфликт возможен только в одном кабинете.'), key=f'tt_change_request_{work["id"]}')
                request = st.form_submit_button(t('Запросить защиту работы'))
            if request:
                act(lambda: store.request_defense(work['id'], buyer_id, work['version'], question, change), 'Вопрос и изменение отправлены школьнику.')


def passport_report(work, pupil, viewer_id, lang='ru'):
    tr = lambda source, **values: t(source, _lang=lang, **values)
    demo = lambda value: td(value, _lang=lang)
    lines = [tr('# Паспорт работы — ДЕМО'), '', demo(work['challenge_title']), '',
             tr('Профиль: {name}', name=demo(pupil['name'])), tr('Редакция работы: {revision}', revision=work.get('work_revision', 1)),
             tr('Результат: {url}', url=work['evidence_url']),
             tr('Версия источника со слов автора: {source_version}', source_version=demo(work.get('source_version') or '') or tr('не указана')),
             '', demo(work['description']), '', tr('## Вклад и инструменты'), demo(work['reflection']), '',
             tr('## Оценка результата'), f'{work["total"]:g}/100', tr('Формула: сумма (оценка / 4 × вес).'), '']
    evidence = work.get('criterion_evidence', [])
    for i, (criterion, rating) in enumerate(zip(work['criteria'], work['ratings'])):
        lines += [f'- {demo(criterion["label"])}: {rating}/4 × {criterion["weight"]}% = {rating * criterion["weight"] / 4:g}',
                  tr('  Основание: {evidence}', evidence=demo(evidence[i]) if i < len(evidence) else tr('не сохранено в раннем демо'))]
    lines += ['', tr('Комментарий: {feedback}', feedback=demo(work['feedback'])),
              tr('Проверяющий: {name} · {role}', name=demo(work.get('reviewer_name') or '') or tr('не указан'),
                 role=demo(work.get('reviewer_role') or '') or tr('роль не указана')),
              tr('Организация: {organization}', organization=demo(work['buyer_name'])), tr('Дата: {date}', date=work['reviewed_at'] or ''),
              tr('Ограничения: {limitations}', limitations=demo(work.get('review_limitations') or '') or tr('не указаны')),
              '', tr('## Проверка понимания'), tr(UNDERSTANDING.get(work.get('understanding_status', 'not_requested')))]
    for item in store.defense_rounds(work['id'], viewer_id):
        if item['work_revision'] == work['work_revision']:
            lines += ['', tr('Вопрос: {question}', question=item['question']), tr('Изменение: {change}', change=item['change_request']),
                      tr('Ответ: {answer}', answer=item.get('answer') or tr('ожидается')),
                      tr('Результат изменения: {url}', url=item.get('evidence_url') or tr('нет')),
                      tr('Наблюдения: {observations}', observations=item.get('observations') or tr('проверка не завершена')),
                      tr('Проверяющий: {name} · {role}', name=demo(item.get('reviewer_name') or '') or tr('не указан'),
                         role=demo(item.get('reviewer_role') or '')),
                      tr('Ограничения: {limitations}', limitations=item.get('limitations') or tr('не указаны'))]
    lines += ['', tr('Все данные синтетические. Паспорт фиксирует оценку конкретной работы, не удостоверяет личность '
                    'или авторство всей работы. Содержимое внешней ссылки может измениться.')]
    return '\n'.join(lines) + '\n'
