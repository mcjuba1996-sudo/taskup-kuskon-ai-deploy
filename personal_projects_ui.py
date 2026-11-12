"""Private self-assessment, useful before a buyer joins the demonstration."""
import streamlit as st
import personal_projects as projects
import talent_store as store
from talent_i18n import t, td, error_text, language


def act(callback, message):
    try:
        callback()
    except ValueError as error:
        st.error(error_text(str(error)))
        return
    st.session_state['tt_flash'] = t(message)
    st.rerun()


def project_form(student_id, project=None):
    item = project or {}
    pid = item.get('id', 'new')
    version = item.get('version', 0)
    prefix = f'tt_project_{pid}_{version}'
    with st.form(prefix):
        title = st.text_input(t('Название проекта'), value=item.get('title', ''), max_chars=140, key=prefix + '_title')
        description = st.text_area(t('Задача, результат и как его проверить'), value=item.get('description', ''), max_chars=5500, key=prefix + '_description')
        url = st.text_input(t('Ссылка на работу (можно добавить позже)'), value=item.get('evidence_url', ''), max_chars=2000, key=prefix + '_url')
        source = st.text_input(t('Коммит или версия файла'), value=item.get('source_version', ''), max_chars=200, key=prefix + '_source')
        contribution = st.text_area(t('Что именно сделал я'), value=item.get('contribution', ''), max_chars=2500, key=prefix + '_contribution')
        help_text = st.text_area(t('Инструменты, ИИ и помощь других людей'), value=item.get('tools_help', ''), max_chars=1000, key=prefix + '_help')
        st.caption(t('Самопроверка: ваши отметки помогают подготовить отчёт и не означают внешнюю проверку.'))
        selected = [c['id'] for c in projects.CHECKLIST if st.checkbox(t(c['label']), value=c['id'] in item.get('checks', []), key=prefix + '_' + c['id'])]
        save = st.form_submit_button(t('Сохранить проект'), type='primary')
    if save:
        act(lambda: projects.save_project(student_id, title, description, url, contribution, help_text, selected,
                                           source_version=source, project_id=item.get('id'), expected_version=item.get('version')),
            'Проект сохранён в личном пространстве. Внешняя проверка не проводилась.')


def render(student_id):
    st.caption(t('ЛИЧНОЕ ПРОСТРАНСТВО'))
    st.title(t('Мой проект — уже сегодня'))
    st.write(t('Оформите существующую работу, опишите свой вклад и получите отчёт для портфолио. '
               'Для этого не нужно ждать покупателя или выполнять новое задание.'))
    st.info(t('Самооценка. Внешняя проверка не проводилась. Проекты доступны только выбранному демопрофилю; '
              'передача организации выполняется отдельным действием. Все вводимые данные должны быть тестовыми.'))
    items = projects.projects(student_id)
    with st.expander(t('Добавить свой проект'), expanded=not items):
        project_form(student_id)
    for item in items:
        with st.container(border=True):
            st.subheader(item['title'])
            st.caption(t('Личный черновик · версия {version} · внешней проверки нет', version=item['version']))
            st.write(item['description'] or t('Описание пока не заполнено.'))
            missing = projects.completeness(item)
            if missing:
                st.caption(t('Чтобы передать на проверку, дополните: {missing}', missing=', '.join(error_text(message) for message in missing)))
            st.download_button(t('Скачать отчёт самооценки'), projects.project_report(item, lang=language()),
                               f'my-project-{item["id"]}.md', mime='text/markdown', key=f'tt_project_report_{item["id"]}')
            with st.expander(t('Редактировать проект')):
                project_form(student_id, item)
            with st.expander(t('Передать работу организации по заданию')):
                st.caption(t('Выберите задание, требованиям которого соответствует ваш проект. Организация получит копию текущей '
                             'версии и проверит её по своим критериям. Поздние изменения личного проекта не изменят отправленную работу.'))
                challenges = store.challenges()
                by_id = {c['id']: c for c in challenges}
                if not by_id:
                    st.info(t('Пока нет заданий организаций. Личный отчёт уже доступен без них.'))
                    continue
                pid = item['id']
                cid = st.selectbox(t('Задание для проверки'), list(by_id), format_func=lambda x: td(by_id[x]['title']), key=f'tt_project_target_{pid}')
                st.write(td(by_id[cid]['deliverable']))
                for criterion in by_id[cid]['criteria']:
                    st.caption(f'{td(criterion["label"])} · {criterion["weight"]}%: {td(criterion["description"])}')
                with st.form(f'tt_project_transfer_{pid}_{item["version"]}_{cid}'):
                    consent = st.checkbox(t('Согласен передать копию тестового проекта заказчику выбранного задания'), key=f'tt_project_consent_{pid}_{cid}')
                    send = st.form_submit_button(t('Передать на проверку'), disabled=bool(missing))
                if send:
                    if not consent:
                        st.error(t('Подтвердите передачу проекта выбранной организации.'))
                    else:
                        act(lambda: projects.transfer_project(pid, student_id, cid, item['version']),
                            'Копия передана организации. Ответы и проверка находятся в разделе «Мои работы».')
