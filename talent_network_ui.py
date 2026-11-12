"""Separate demo workspaces for sources, guardians, and issuer statements."""
import streamlit as st

import talent_network as network
from talent_i18n import error_text, t, td


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
        st.error(error_text(str(error)))
        return
    st.session_state['tt_flash'] = message
    st.rerun()


def record_details(record):
    st.subheader(td(record['title']))
    st.caption(t(RECORD_STATUS[record['status']]))
    st.write(t('Событие: {event}', event=td(record['event'])))
    st.markdown(t('**Что заявляет источник**'))
    st.write(td(record['result']))
    st.link_button(t('Основание записи №{record_id} ↗', record_id=record['id']), record['evidence_url'])
    st.markdown(t('**Как источник проверял сведения**'))
    st.write(td(record['check_method']))
    st.caption(t('{kind}: {name} · {date}', kind=t(SOURCE_KIND[record['issuer_kind']]),
                 name=td(record['issuer_name']), date=record['issued_at']))
    if record['limitations']:
        st.write(t('Ограничения: {limitations}', limitations=td(record['limitations'])))
    if record['status'] == 'revoked':
        st.warning(t('Причина отзыва: {reason}', reason=record['revocation_reason']))
    st.caption(t(record['demo_notice']))


def render_source(source_id):
    source = network.person(source_id)
    st.caption(t('ИСТОЧНИК СВЕДЕНИЙ · ДЕМО'))
    st.title(t('Реестр достижений'))
    st.write(t('{name}: передайте школьнику запись о конкретном событии и укажите основание. '
               'Школьник сам решает, включать ли её в свои достижения.', name=td(source['name'])))
    st.info(t('Школа и организатор работают только со своим демонстрационным списком участников. '
              'Запись источника не означает независимую проверку платформой и не подтверждает реальную личность.'))
    roster = network.source_students(source_id)
    st.subheader(t('Выдать запись участнику'))
    if not roster:
        st.info(t('В вашем демонстрационном списке пока нет участников.'))
    else:
        by_id = {p['id']: p for p in roster}
        with st.form(f'tt_source_issue_{source_id}'):
            student_id = st.selectbox(t('Участник из моего списка'), list(by_id),
                format_func=lambda pid: t('{name} · {grade} класс', name=td(by_id[pid]['name']), grade=by_id[pid]['grade']),
                key=f'tt_source_student_{source_id}')
            title = st.text_input(t('Название достижения'), max_chars=140, key=f'tt_source_title_{source_id}')
            event = st.text_input(t('Событие или программа'), max_chars=200, key=f'tt_source_event_{source_id}')
            result = st.text_area(t('Участие и результат, которые подтверждает источник'), max_chars=2000,
                                  key=f'tt_source_result_{source_id}')
            url = st.text_input(t('Ссылка на протокол или другое основание'), max_chars=2000,
                                key=f'tt_source_url_{source_id}')
            method = st.text_area(t('Как проверены сведения и кем'), max_chars=2000,
                                   placeholder=t('Например: сопоставили результат с тестовым протоколом события.'),
                                   key=f'tt_source_method_{source_id}')
            limits = st.text_area(t('Ограничения подтверждения'), max_chars=2000,
                                   key=f'tt_source_limits_{source_id}')
            issue = st.form_submit_button(t('Передать запись школьнику'), type='primary')
        if issue:
            act(lambda: network.issue_record(source_id, student_id, title, event, result, url, method, limits),
                t('Запись передана школьнику. До его решения она не появится в открытых достижениях.'))
    st.subheader(t('Мои выданные записи'))
    records = network.source_records(source_id)
    if not records:
        st.info(t('Вы ещё не выдавали записей. Все поля выше заполняются тестовыми данными.'))
    for record in records:
        with st.container(border=True):
            st.caption(t('Участник: {name}', name=td(record['student_name'])))
            record_details(record)
            if record['status'] in ('offered', 'accepted'):
                with st.expander(t('Отозвать запись')):
                    st.caption(t('Отзыв убирает запись из доступных покупателю достижений. Причина останется видна школьнику.'))
                    with st.form(f'tt_source_revoke_{record["id"]}'):
                        reason = st.text_area(t('Причина отзыва'), max_chars=2000,
                                              key=f'tt_source_revoke_reason_{record["id"]}')
                        revoke = st.form_submit_button(t('Отозвать запись источника'))
                    if revoke:
                        act(lambda: network.revoke_record(record['id'], source_id, reason), t('Запись отозвана источником.'))


def render_parent(parent_id):
    st.caption(t('ЗАКОННЫЙ ПРЕДСТАВИТЕЛЬ · ДЕМО'))
    st.title(t('Согласие и прогресс ребёнка'))
    st.info(t('Показаны только связанные с этим демопрофилем дети. Связь и согласие моделируются: '
              'реальная личность и полномочия законного представителя здесь не удостоверяются.'))
    children = network.guardian_children(parent_id)
    if not children:
        st.info(t('В демонстрации пока нет связанного ребёнка.'))
        return
    by_id = {child['id']: child for child in children}
    child_id = st.selectbox(t('Связанный ребёнок'), list(by_id), format_func=lambda pid: td(by_id[pid]['name']),
                            key=f'tt_guardian_child_{parent_id}')
    overview = network.guardian_overview(parent_id, child_id)
    child = overview['child']
    st.subheader(td(child['name']))
    st.caption(t('{region} · {grade} класс · {focus}', region=td(child['region']), grade=child['grade'], focus=td(child['focus'])))
    st.write(t('Выбор школьника: {choice}', choice=t('разрешает показ профиля' if child['share_profile'] else 'профиль закрыт для каталога')))
    st.caption(t('Согласие представителя и решение школьника независимы. Для каталога нужны оба согласия '
                 'и принятая работа. Представитель не может включить согласие за школьника.'))
    st.caption(t('Покупателям станут доступны профиль, принятые работы, история прежних редакций и решений, '
                 'материалы защиты и принятые школьником записи школы или организатора.'))
    with st.form(f'tt_guardian_consent_{parent_id}_{child_id}'):
        granted = st.checkbox(t('Разрешаю показать организациям тестовый профиль, принятые работы, историю, материалы защиты и принятые ребёнком записи источников'),
                              value=child['guardian_consent'], key=f'tt_guardian_granted_{parent_id}_{child_id}')
        save = st.form_submit_button(t('Сохранить согласие представителя'), type='primary')
    if save:
        act(lambda: network.set_guardian_consent(parent_id, child_id, granted), t('Согласие представителя сохранено.'))
    st.caption(t('Отзыв согласия скрывает профиль из каталога и избранного, отзывает ожидающие приглашения. '
                 'Организации сохраняют доступ к работам, отправленным на их задания.'))
    st.subheader(t('Работы, отправленные на проверку'))
    if not overview['works']:
        st.info(t('Ребёнок ещё не отправлял работ на задания организаций.'))
    for work in overview['works']:
        with st.container(border=True):
            st.subheader(td(work['title']))
            st.caption(t(WORK_STATUS[work['status']]))
            if work['score'] is not None:
                st.write(t('Оценка конкретной работы: {score:g}/100', score=work['score']))
            if work['feedback']:
                st.write(td(work['feedback']))
    st.caption(t('Личные черновики и проекты самооценки в кабинете представителя не показываются.'))
    st.subheader(t('Приглашения ребёнку'))
    if not overview['invitations']:
        st.info(t('Приглашений пока нет.'))
    for invitation in overview['invitations']:
        with st.container(border=True):
            st.subheader(td(invitation['buyer_name']))
            st.caption(t(INVITATION_STATUS[invitation['status']]))
            st.write(invitation['message'])
    st.caption(t('Ответ на приглашение даёт сам школьник. Здесь нет инструментов подбора кандидатов или рассылки.'))


def render_student_records(student_id):
    st.caption(t('ДОСТИЖЕНИЯ · ЗАПИСИ ИСТОЧНИКОВ'))
    st.title(t('Школа и организаторы о вашей работе'))
    st.write(t('Проверьте запись и решите, включать ли её в свои достижения. Принятие записи не включает '
               'публичность профиля: настройки видимости находятся отдельно в портфолио.'))
    st.caption(t('Одной записи источника недостаточно для каталога покупателей: нужны принятая работа, '
                 'ваше согласие на видимость и согласие законного представителя.'))
    records = network.student_records(student_id)
    if not records:
        st.info(t('Записей пока нет. В демонстрации школа или организатор могут передать сведения из своего реестра.'))
    for record in records:
        with st.container(border=True):
            record_details(record)
            if record['status'] == 'offered':
                left, right = st.columns(2)
                if left.button(t('Включить в мои достижения'), key=f'tt_record_accept_{record["id"]}', type='primary'):
                    act(lambda: network.respond_record(record['id'], student_id, True), t('Запись включена в достижения. Настройки публичности не изменены.'))
                if right.button(t('Отклонить запись'), key=f'tt_record_decline_{record["id"]}'):
                    act(lambda: network.respond_record(record['id'], student_id, False), t('Запись отклонена.'))


def render_public_records(buyer_id, student_id):
    records = network.public_records(buyer_id, student_id)
    if not records:
        return
    with st.expander(t('Дополнительные сведения от школы и организаторов')):
        st.caption(t('Принятые школьником заявления источников дополняют работы. '
                     'Платформа не проводила независимую проверку этих сведений.'))
        for record in records:
            record_details(record)
            st.divider()
