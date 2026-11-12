"""Private self-assessment, useful before a buyer joins the demonstration."""
import streamlit as st
import personal_projects as projects
import talent_store as store


def act(callback, message):
    try:
        callback()
    except ValueError as error:
        st.error(str(error))
        return
    st.session_state['tt_flash'] = message
    st.rerun()


def project_form(student_id, project=None):
    item = project or {}
    pid = item.get('id', 'new')
    version = item.get('version', 0)
    prefix = f'tt_project_{pid}_{version}'
    with st.form(prefix):
        title = st.text_input('Название проекта', value=item.get('title', ''), max_chars=140, key=prefix + '_title')
        description = st.text_area('Задача, результат и как его проверить', value=item.get('description', ''), max_chars=5500, key=prefix + '_description')
        url = st.text_input('Ссылка на работу (можно добавить позже)', value=item.get('evidence_url', ''), max_chars=2000, key=prefix + '_url')
        source = st.text_input('Коммит или версия файла', value=item.get('source_version', ''), max_chars=200, key=prefix + '_source')
        contribution = st.text_area('Что именно сделал я', value=item.get('contribution', ''), max_chars=2500, key=prefix + '_contribution')
        help_text = st.text_area('Инструменты, ИИ и помощь других людей', value=item.get('tools_help', ''), max_chars=1000, key=prefix + '_help')
        st.caption('Самопроверка: ваши отметки помогают подготовить отчёт и не означают внешнюю проверку.')
        selected = [c['id'] for c in projects.CHECKLIST if st.checkbox(c['label'], value=c['id'] in item.get('checks', []), key=prefix + '_' + c['id'])]
        save = st.form_submit_button('Сохранить проект', type='primary')
    if save:
        act(lambda: projects.save_project(student_id, title, description, url, contribution, help_text, selected,
                                           source_version=source, project_id=item.get('id'), expected_version=item.get('version')),
            'Проект сохранён в личном пространстве. Внешняя проверка не проводилась.')


def render(student_id):
    st.caption('ЛИЧНОЕ ПРОСТРАНСТВО')
    st.title('Мой проект — уже сегодня')
    st.write('Оформите существующую работу, опишите свой вклад и получите отчёт для портфолио. '
             'Для этого не нужно ждать компанию или выполнять новое задание.')
    st.info('Самооценка. Внешняя проверка не проводилась. Проекты доступны только выбранному демопрофилю; '
            'передача компании выполняется отдельным действием. Все вводимые данные должны быть тестовыми.')
    items = projects.projects(student_id)
    with st.expander('Добавить свой проект', expanded=not items):
        project_form(student_id)
    for item in items:
        with st.container(border=True):
            st.subheader(item['title'])
            st.caption(f'Личный черновик · версия {item["version"]} · внешней проверки нет')
            st.write(item['description'] or 'Описание пока не заполнено.')
            missing = projects.completeness(item)
            if missing:
                st.caption('Чтобы передать на проверку, дополните: ' + ', '.join(missing))
            st.download_button('Скачать отчёт самооценки', projects.project_report(item),
                               f'my-project-{item["id"]}.md', mime='text/markdown', key=f'tt_project_report_{item["id"]}')
            with st.expander('Редактировать проект'):
                project_form(student_id, item)
            with st.expander('Передать работу компании по заданию'):
                st.caption('Выберите задание, требованиям которого соответствует ваш проект. Компания получит копию текущей '
                           'версии и проверит её по своим критериям. Поздние изменения личного проекта не изменят отправленную работу.')
                challenges = store.challenges()
                by_id = {c['id']: c for c in challenges}
                if not by_id:
                    st.info('Пока нет заданий компаний. Личный отчёт уже доступен без них.')
                    continue
                pid = item['id']
                cid = st.selectbox('Задание для проверки', list(by_id), format_func=lambda x: by_id[x]['title'], key=f'tt_project_target_{pid}')
                st.write(by_id[cid]['deliverable'])
                for criterion in by_id[cid]['criteria']:
                    st.caption(f'{criterion["label"]} · {criterion["weight"]}%: {criterion["description"]}')
                with st.form(f'tt_project_transfer_{pid}_{item["version"]}_{cid}'):
                    consent = st.checkbox('Согласен передать копию тестового проекта заказчику выбранного задания', key=f'tt_project_consent_{pid}_{cid}')
                    send = st.form_submit_button('Передать на проверку', disabled=bool(missing))
                if send:
                    if not consent:
                        st.error('Подтвердите передачу проекта выбранной компании.')
                    else:
                        act(lambda: projects.transfer_project(pid, student_id, cid, item['version']),
                            'Копия передана компании. Ответы и проверка находятся в разделе «Мои работы».')
