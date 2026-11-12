"""Separate demo workspaces for sources, guardians, and issuer statements."""
import streamlit as st

import talent_network as network


RECORD_STATUS = {
    'offered': 'Ожидает решения школьника',
    'accepted': 'Школьник включил запись в достижения',
    'declined': 'Школьник отклонил запись',
    'revoked': 'Источник отозвал запись',
}
WORK_STATUS = {'pending': 'На проверке', 'changes_requested': 'Нужна доработка', 'approved': 'Результат принят'}
INVITATION_STATUS = {'pending': 'Ожидает ответа школьника', 'accepted': 'Принято школьником',
                     'declined': 'Отклонено школьником', 'withdrawn': 'Отозвано'}
SOURCE_KIND = {'school': 'Школа', 'organizer': 'Организатор конкурса'}


def act(callback, message):
    try:
        callback()
    except ValueError as error:
        st.error(str(error))
        return
    st.session_state['tt_flash'] = message
    st.rerun()


def record_details(record):
    st.subheader(record['title'])
    st.caption(RECORD_STATUS[record['status']])
    st.write('Событие: ' + record['event'])
    st.markdown('**Что заявляет источник**')
    st.write(record['result'])
    st.link_button(f'Основание записи №{record["id"]} ↗', record['evidence_url'])
    st.markdown('**Как источник проверял сведения**')
    st.write(record['check_method'])
    st.caption(f'{SOURCE_KIND[record["issuer_kind"]]}: {record["issuer_name"]} · {record["issued_at"]}')
    if record['limitations']:
        st.write('Ограничения: ' + record['limitations'])
    if record['status'] == 'revoked':
        st.warning('Причина отзыва: ' + record['revocation_reason'])
    st.caption(record['demo_notice'])


def render_source(source_id):
    source = network.person(source_id)
    st.caption('ИСТОЧНИК СВЕДЕНИЙ · ДЕМО')
    st.title('Реестр достижений')
    st.write(f'{source["name"]}: передайте школьнику запись о конкретном событии и укажите основание. '
             'Школьник сам решает, включать ли её в свои достижения.')
    st.info('Школа и организатор работают только со своим демонстрационным списком участников. '
            'Запись источника не означает независимую проверку платформой и не подтверждает реальную личность.')
    roster = network.source_students(source_id)
    st.subheader('Выдать запись участнику')
    if not roster:
        st.info('В вашем демонстрационном списке пока нет участников.')
    else:
        by_id = {p['id']: p for p in roster}
        with st.form(f'tt_source_issue_{source_id}'):
            student_id = st.selectbox('Участник из моего списка', list(by_id),
                format_func=lambda pid: f'{by_id[pid]["name"]} · {by_id[pid]["grade"]} класс',
                key=f'tt_source_student_{source_id}')
            title = st.text_input('Название достижения', max_chars=140, key=f'tt_source_title_{source_id}')
            event = st.text_input('Событие или программа', max_chars=200, key=f'tt_source_event_{source_id}')
            result = st.text_area('Участие и результат, которые подтверждает источник', max_chars=2000,
                                  key=f'tt_source_result_{source_id}')
            url = st.text_input('Ссылка на протокол или другое основание', max_chars=2000,
                                key=f'tt_source_url_{source_id}')
            method = st.text_area('Как проверены сведения и кем', max_chars=2000,
                                   placeholder='Например: сопоставили результат с тестовым протоколом события.',
                                   key=f'tt_source_method_{source_id}')
            limits = st.text_area('Ограничения подтверждения', max_chars=2000,
                                   key=f'tt_source_limits_{source_id}')
            issue = st.form_submit_button('Передать запись школьнику', type='primary')
        if issue:
            act(lambda: network.issue_record(source_id, student_id, title, event, result, url, method, limits),
                'Запись передана школьнику. До его решения она не появится в открытых достижениях.')
    st.subheader('Мои выданные записи')
    records = network.source_records(source_id)
    if not records:
        st.info('Вы ещё не выдавали записей. Все поля выше заполняются тестовыми данными.')
    for record in records:
        with st.container(border=True):
            st.caption('Участник: ' + record['student_name'])
            record_details(record)
            if record['status'] in ('offered', 'accepted'):
                with st.expander('Отозвать запись'):
                    st.caption('Отзыв убирает запись из доступных покупателю достижений. Причина останется видна школьнику.')
                    with st.form(f'tt_source_revoke_{record["id"]}'):
                        reason = st.text_area('Причина отзыва', max_chars=2000,
                                              key=f'tt_source_revoke_reason_{record["id"]}')
                        revoke = st.form_submit_button('Отозвать запись источника')
                    if revoke:
                        act(lambda: network.revoke_record(record['id'], source_id, reason), 'Запись отозвана источником.')


def render_parent(parent_id):
    st.caption('ЗАКОННЫЙ ПРЕДСТАВИТЕЛЬ · ДЕМО')
    st.title('Согласие и прогресс ребёнка')
    st.info('Показаны только связанные с этим демопрофилем дети. Связь и согласие моделируются: '
            'реальная личность и полномочия законного представителя здесь не удостоверяются.')
    children = network.guardian_children(parent_id)
    if not children:
        st.info('В демонстрации пока нет связанного ребёнка.')
        return
    by_id = {child['id']: child for child in children}
    child_id = st.selectbox('Связанный ребёнок', list(by_id), format_func=lambda pid: by_id[pid]['name'],
                            key=f'tt_guardian_child_{parent_id}')
    overview = network.guardian_overview(parent_id, child_id)
    child = overview['child']
    st.subheader(child['name'])
    st.caption(f'{child["region"]} · {child["grade"]} класс · {child["focus"]}')
    st.write('Выбор школьника: ' + ('разрешает показ профиля' if child['share_profile'] else 'профиль закрыт для каталога'))
    st.caption('Согласие представителя и решение школьника независимы. Для каталога нужны оба согласия '
               'и принятая работа. Представитель не может включить согласие за школьника.')
    st.caption('Покупателям станут доступны профиль, принятые работы, история прежних редакций и решений, '
               'материалы защиты и принятые школьником записи школы или организатора.')
    with st.form(f'tt_guardian_consent_{parent_id}_{child_id}'):
        granted = st.checkbox('Разрешаю показать организациям тестовый профиль, принятые работы, историю, материалы защиты и принятые ребёнком записи источников',
                              value=child['guardian_consent'], key=f'tt_guardian_granted_{parent_id}_{child_id}')
        save = st.form_submit_button('Сохранить согласие представителя', type='primary')
    if save:
        act(lambda: network.set_guardian_consent(parent_id, child_id, granted), 'Согласие представителя сохранено.')
    st.caption('Отзыв согласия скрывает профиль из каталога и избранного, отзывает ожидающие приглашения. '
               'Организации сохраняют доступ к работам, отправленным на их задания.')
    st.subheader('Работы, отправленные на проверку')
    if not overview['works']:
        st.info('Ребёнок ещё не отправлял работ на задания организаций.')
    for work in overview['works']:
        with st.container(border=True):
            st.subheader(work['title'])
            st.caption(WORK_STATUS[work['status']])
            if work['score'] is not None:
                st.write(f'Оценка конкретной работы: {work["score"]:g}/100')
            if work['feedback']:
                st.write(work['feedback'])
    st.caption('Личные черновики и проекты самооценки в кабинете представителя не показываются.')
    st.subheader('Приглашения ребёнку')
    if not overview['invitations']:
        st.info('Приглашений пока нет.')
    for invitation in overview['invitations']:
        with st.container(border=True):
            st.subheader(invitation['buyer_name'])
            st.caption(INVITATION_STATUS[invitation['status']])
            st.write(invitation['message'])
    st.caption('Ответ на приглашение даёт сам школьник. Здесь нет инструментов подбора кандидатов или рассылки.')


def render_student_records(student_id):
    st.caption('ДОСТИЖЕНИЯ · ЗАПИСИ ИСТОЧНИКОВ')
    st.title('Школа и организаторы о вашей работе')
    st.write('Проверьте запись и решите, включать ли её в свои достижения. Принятие записи не включает '
             'публичность профиля: настройки видимости находятся отдельно в портфолио.')
    st.caption('Одной записи источника недостаточно для каталога покупателей: нужны принятая работа, '
               'ваше согласие на видимость и согласие законного представителя.')
    records = network.student_records(student_id)
    if not records:
        st.info('Записей пока нет. В демонстрации школа или организатор могут передать сведения из своего реестра.')
    for record in records:
        with st.container(border=True):
            record_details(record)
            if record['status'] == 'offered':
                left, right = st.columns(2)
                if left.button('Включить в мои достижения', key=f'tt_record_accept_{record["id"]}', type='primary'):
                    act(lambda: network.respond_record(record['id'], student_id, True), 'Запись включена в достижения. Настройки публичности не изменены.')
                if right.button('Отклонить запись', key=f'tt_record_decline_{record["id"]}'):
                    act(lambda: network.respond_record(record['id'], student_id, False), 'Запись отклонена.')


def render_public_records(buyer_id, student_id):
    records = network.public_records(buyer_id, student_id)
    if not records:
        return
    with st.expander('Дополнительные сведения от школы и организаторов'):
        st.caption('Принятые школьником заявления источников дополняют работы. '
                   'Платформа не проводила независимую проверку этих сведений.')
        for record in records:
            record_details(record)
            st.divider()
