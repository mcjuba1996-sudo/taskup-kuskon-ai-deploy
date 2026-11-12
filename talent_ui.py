"""TaskUp Talent UI. Every identity and consent in this MVP is synthetic."""
from html import escape
from io import BytesIO
from pathlib import Path
from zipfile import ZipFile
import streamlit as st
import talent_store as store
import personal_projects
from personal_projects_ui import render as render_projects
from talent_evidence_ui import (
    evidence_summary, defense_record, history_panel, student_defense, buyer_defense, passport_report,
)

ROOT = Path(__file__).resolve().parent
STATUS = {'pending': 'Ожидает проверки', 'changes_requested': 'Нужны доработки', 'approved': 'Результат принят'}
INVITES = {'pending': 'Ждёт ответа', 'accepted': 'Принято', 'declined': 'Отклонено', 'withdrawn': 'Отозвано после закрытия профиля'}
RATINGS = {0: '0 — нет свидетельств', 1: '1 — частично, доказательств мало', 2: '2 — базовый результат подтверждён',
           3: '3 — выполнено с доказательствами', 4: '4 — выполнено и проверено'}


def html(value):
    st.markdown(value, unsafe_allow_html=True)


def brand():
    html('<div class="tt-brand"><span class="tt-mark">↗</span> TaskUp <b>Talent</b></div>')


def heading(kicker, title, description=''):
    html(f'<div class="tt-kicker">{escape(kicker)}</div><h1>{escape(title)}</h1><p class="tt-intro">{escape(description)}</p>')


def tag(text, good=False):
    html(f'<span class="tt-tag {"good" if good else ""}">{escape(text)}</span>')


def action(callback, message):
    try:
        callback()
    except ValueError as exc:
        st.error(str(exc))
        return
    st.session_state['tt_flash'] = message
    st.rerun()


def enter(role):
    for key in list(st.session_state):
        if key.startswith('tt_'):
            del st.session_state[key]
    st.session_state['tt_role'] = role


def navigate(page):
    st.session_state['tt_page'] = page


def landing():
    brand()
    st.caption('Kuskon AI · HackHub 2026 · Талант до вуза')
    left, right = st.columns([1.4, 1], gap='large')
    with left:
        html('<div class="tt-kicker">РЕАЛЬНАЯ РАБОТА → ДОВЕРИЕ</div><h1 class="tt-hero-title">Твой талант.<br>'
             '<em>Твои доказательства.</em></h1><p class="tt-lead">Сделай небольшой IT-проект. Получи разбор от компании. '
             'Покажи, что умеешь, через результат работы.</p>')
        tag('Для школьников 9–11 классов Актюбинской области')
    with right:
        html('<div class="tt-proof"><div class="tt-proof-top">ПАСПОРТ РАБОТЫ <span>ДЕМО</span></div>'
             '<h3>Дашборд школьного клуба</h3><p>Участник A-103 · Актобе · Аналитика</p>'
             '<div class="tt-proof-result">✓ Результат принят заказчиком</div>'
             '<div class="tt-proof-row"><span>Работа и исходники</span><b>Приложены</b></div>'
             '<div class="tt-proof-row"><span>Критерии и обратная связь</span><b>Открыты</b></div>'
             '<div class="tt-proof-row"><span>Публикация профиля</span><b>По согласию</b></div>'
             '<p class="tt-small">Иллюстрация паспорта. Проверяется конкретная работа, а не «рейтинг таланта» школьника.</p></div>')
    html('<div class="tt-steps"><div><b>01</b><strong>Выбери задание</strong><span>Критерии известны заранее</span></div>'
         '<div><b>02</b><strong>Покажи результат</strong><span>Ссылка, подход и личный вклад</span></div>'
         '<div><b>03</b><strong>Получи признание</strong><span>Разбор и паспорт принятой работы</span></div></div>')
    st.subheader('Попробуйте обе стороны')
    for col, role, title, text, button in zip(st.columns(2, gap='large'), ('student', 'buyer'),
            ('Я школьник', 'Я представляю компанию'),
            ('Практика, обратная связь и портфолио работ. Для школьника бесплатно.',
             'Задания для образовательной программы, проверка результатов и подбор участников по работам.'),
            ('Выбрать задание →', 'Открыть кабинет компании →')):
        with col, st.container(border=True):
            st.subheader(title)
            st.write(text)
            st.button(button, key=f'tt_enter_{role}', type='primary' if role == 'student' else 'secondary',
                      use_container_width=True, on_click=enter, args=(role,))
    st.info('Демонстрационный стенд: все профили и результаты вымышлены. Переключение роли — не авторизация. '
            'Используйте только тестовые данные и ссылки.')
    with st.expander('Как устроено доверие'):
        st.write('Компания оценивает работу по трём критериям и указывает основания каждой оценки. По запросу '
                 'школьник объясняет решение и вносит небольшое изменение. В паспорте видны доказательства, '
                 'наблюдения проверяющего и границы проверки. Оценка результата и проверка понимания показаны отдельно.')
        st.write('Без компании можно сохранить свой проект, описать вклад, пройти самопроверку и скачать отчёт. '
                 'Он обозначен как самооценка. Передача компании происходит отдельным действием.')


def rubric(criteria):
    for item in criteria:
        st.markdown(f'**{item["label"]} · {item["weight"]}%**')
        st.write(item['description'])
    st.caption('Итог = сумма (оценка / 4 × вес). Принятие: итог не ниже 70 и каждая оценка не ниже 2. Это правило прототипа.')


def show_work(work, include_student=False):
    tag(STATUS[work['status']], work['status'] == 'approved')
    st.subheader(work['challenge_title'])
    if include_student:
        st.caption(f'{work["student_name"]} · {work["skill"]}')
    st.write(work['description'])
    st.link_button(f'Открыть результат работы №{work["id"]} ↗', work['evidence_url'])
    demo_prefix = 'https://github.com/mcjuba1996-sudo/taskup-kuskon-ai-deploy/blob/codex/hackhub-talent/demo_evidence/'
    reports = {'attendance.md', 'schedule.md', 'signup.md'}
    report_name = work['evidence_url'].removeprefix(demo_prefix)
    if work['evidence_url'].startswith(demo_prefix) and report_name in reports:
        with st.expander('Посмотреть демонстрационный образец здесь'):
            st.caption('Образец подготовлен командой с помощью Codex. Это не достижение реального школьника.')
            st.markdown((ROOT / 'demo_evidence' / report_name).read_text(encoding='utf-8'))
            archive = BytesIO()
            with ZipFile(archive, 'w') as bundle:
                for path in sorted((ROOT / 'demo_evidence').iterdir()):
                    if path.is_file() and path.suffix in ('.md', '.py', '.csv', '.html'):
                        bundle.write(path, path.name)
            st.download_button('Скачать образцы и исходники', archive.getvalue(), 'taskup-demo-evidence.zip',
                               mime='application/zip', key=f'tt_evidence_download_{work["id"]}')
    st.markdown('**Личный вклад и выводы**')
    st.write(work['reflection'])
    if work['status'] != 'pending':
        st.markdown(f'**Оценка этой работы: {work["total"]:g}/100**')
        for criterion, value in zip(work['criteria'], work['ratings']):
            st.write(f'{criterion["label"]}: {value}/4 · вес {criterion["weight"]}%')
        st.markdown('**Обратная связь заказчика**')
        st.write(work['feedback'])
        st.caption(f'Проверил: {work["buyer_name"]} · {work["reviewed_at"] or ""} · Демо-проверка')
    evidence_summary(work)
    viewer_id = st.session_state.get('tt_current_person')
    if viewer_id:
        if work['status'] != 'pending' or st.session_state.get('tt_role') == 'student':
            defense_record(work, viewer_id)
        history_panel(work, viewer_id)


def challenge_catalog(student_id):
    heading('ПРАКТИКА', 'От задачи — к первой работе', 'Выберите мини-проект. Критерии открыты до начала работы.')
    items = store.challenges()
    selected = st.selectbox('Направление', ['Все направления', *sorted({c['skill'] for c in items})], key='tt_catalog_skill')
    my_works = {w['challenge_id']: w for w in store.submissions(student_id=student_id)}
    for challenge in items:
        if selected != 'Все направления' and challenge['skill'] != selected:
            continue
        with st.container(border=True):
            st.caption(f'{challenge["skill"]} · {challenge["duration"]} · {store.person(challenge["buyer_id"])["name"]}')
            st.subheader(challenge['title'])
            st.write(challenge['brief'])
            st.markdown('**Что нужно сдать**')
            st.write(challenge['deliverable'])
            with st.expander('Критерии приёмки и самопроверка'):
                rubric(challenge['criteria'])
            prior = my_works.get(challenge['id'])
            if prior and prior['status'] != 'changes_requested':
                tag(STATUS[prior['status']], prior['status'] == 'approved')
                st.caption('Результат и обратная связь — в разделе «Мои работы».')
                continue
            if prior:
                st.warning('Доработка: ' + prior['feedback'])
            with st.expander('Сдать доработку' if prior else 'Отправить работу на проверку'):
                st.caption('Работу увидит компания — автор задания, даже если портфолио закрыто. '
                           'Не добавляйте реальные ФИО, контакты или данные других школьников.')
                cid = challenge['id']
                with st.form(f'tt_submit_{cid}'):
                    url = st.text_input('Ссылка на репозиторий или прототип', value=prior['evidence_url'] if prior else '',
                                        placeholder='https://example.com/my-project', max_chars=2000, key=f'tt_url_{cid}')
                    description = st.text_area('Что сделано и как проверить', value=prior['description'] if prior else '',
                                               max_chars=6000, key=f'tt_description_{cid}')
                    reflection = st.text_area('Мой вклад, инструменты и чему я научился', value=prior['reflection'] if prior else '',
                                              max_chars=4000, key=f'tt_reflection_{cid}')
                    source_version = st.text_input('Коммит или версия результата', value=prior.get('source_version', '') if prior else '',
                                                   max_chars=200, key=f'tt_source_version_{cid}',
                                                   help='Укажите конкретную версию, которую передаёте на проверку. Это сведения автора; сервис не проверяет коммит автоматически.')
                    consent = st.checkbox('Отправляю тестовую работу этой компании для проверки', key=f'tt_submit_consent_{cid}')
                    send = st.form_submit_button('Отправить на проверку', type='primary')
                if send:
                    if not consent:
                        st.error('Подтвердите передачу тестовой работы компании.')
                    else:
                        action(lambda: store.submit_work(cid, student_id, url, description, reflection, source_version=source_version),
                               'Работа отправлена. Статус можно посмотреть в «Мои работы».')
    with st.expander('Начать самостоятельно: шаблон отчёта'):
        st.write('Опишите задачу, рабочий сценарий, личный вклад, инструменты, результаты проверки и ограничения.')
        template = '# Мой мини-проект\n\n## Задача\n\n## Что работает\n\n## Ссылка и инструкция\n\n## Мой вклад и инструменты\n\n## Проверка\n\n## Ограничения и выводы\n'
        st.download_button('Скачать шаблон отчёта', template, 'project-report.md', mime='text/markdown')


def student_works(student_id):
    heading('МОИ РАБОТЫ', 'Каждая попытка — шаг вперёд', 'Статусы, оценки и обратная связь по вашим результатам.')
    works = store.submissions(student_id=student_id)
    if not works:
        st.info('Пока нет работ. Выберите задание и отправьте первый результат.')
    for work in works:
        with st.container(border=True):
            show_work(work)
            student_defense(work, student_id)
            if work['status'] == 'changes_requested':
                st.button('Перейти к доработке', key=f'tt_revise_{work["id"]}', on_click=navigate, args=('catalog',))


def portfolio(student_id):
    pupil = store.person(student_id)
    heading('ПОРТФОЛИО', 'Работы говорят за вас', 'Вы управляете тем, что доступно компаниям в каталоге.')
    st.subheader(pupil['name'])
    st.write(f'{pupil["region"]} · {pupil["grade"]} класс · {pupil["focus"]}')
    public = pupil['share_profile'] and pupil['guardian_consent']
    tag('Видно компаниям при наличии принятой работы' if public else 'Закрыто для каталога компаний', public)
    st.caption('В каталоге доступны псевдоним, регион, класс, направление, принятые работы и история их версий, '
               'включая прежние доработки, ответы на защиту и наблюдения проверяющего. Телефон, адрес, школа '
               'и контакты не собираются. Ссылки и текст работ тоже видны: используйте только тестовые данные.')
    with st.form(f'tt_visibility_{student_id}'):
        share = st.checkbox('Я согласен показать компаниям тестовый профиль, принятые работы, историю их версий и материалы защиты',
                            value=pupil['share_profile'], key='tt_share_profile')
        guardian = st.checkbox('Согласие законного представителя получено — моделирование для демо',
                               value=pupil['guardian_consent'], key='tt_guardian_consent')
        saved = st.form_submit_button('Сохранить видимость', type='primary')
    if saved:
        action(lambda: store.set_visibility(student_id, share, guardian), 'Настройки видимости сохранены.')
    st.caption('Снятие любого согласия убирает профиль из каталога и избранного, отзывает ожидающие приглашения. '
               'Заказчик сохраняет доступ к работам на своих заданиях. В реальном сервисе нужна отдельная проверка '
               'согласия; этот переключатель её не заменяет.')
    st.subheader('Паспорта принятых работ')
    works = [w for w in store.submissions(student_id=student_id) if w['status'] == 'approved']
    if not works:
        st.info('Паспорт появится после приёмки результата компанией.')
    for work in works:
        with st.container(border=True):
            show_work(work)
            report = passport_report(work, pupil, student_id)
            st.download_button('Скачать паспорт работы', report, f'work-{work["id"]}.md', mime='text/markdown', key=f'tt_download_{work["id"]}')


def invitations(person_id, role):
    heading('ПРИГЛАШЕНИЯ', 'Следующий шаг — по согласию', 'Приглашения остаются внутри демо. Внешние сообщения не отправляются.')
    items = store.invitations(**{f'{role}_id': person_id})
    if not items:
        st.info('Пока нет приглашений. Компания может пригласить участника из каталога принятых работ.')
    for item in items:
        with st.container(border=True):
            st.subheader(item['buyer_name'] if role == 'student' else item['student_name'])
            tag(INVITES[item['status']], item['status'] == 'accepted')
            st.write(item['message'])
            if role == 'student' and item['status'] == 'pending':
                a, b = st.columns(2)
                if a.button('Принять приглашение', key=f'tt_accept_{item["id"]}', type='primary'):
                    action(lambda: store.respond_invitation(item['id'], person_id, True), 'Приглашение принято внутри демо.')
                if b.button('Отклонить', key=f'tt_decline_{item["id"]}'):
                    action(lambda: store.respond_invitation(item['id'], person_id, False), 'Приглашение отклонено.')


def buyer_review(buyer_id):
    heading('ПРОВЕРКА РАБОТ', 'За каждым решением — доказательства', 'Откройте результат, проверьте критерии и объясните оценку.')
    all_works = store.submissions(buyer_id=buyer_id)
    for col, status, label in zip(st.columns(3), ('pending', 'approved', 'changes_requested'), ('Ожидают проверки', 'Принятые работы', 'На доработке')):
        col.metric(label, sum(w['status'] == status for w in all_works))
    state = st.selectbox('Статус работы', ['Ожидают проверки', 'Все работы'], key='tt_review_filter')
    items = [w for w in all_works if state == 'Все работы' or w['status'] == 'pending']
    if not items:
        st.info('Новых работ пока нет. В роли школьника отправьте результат на одно из ваших заданий.')
    for work in items:
        with st.container(border=True):
            show_work(work, include_student=True)
            if work['status'] != 'pending':
                continue
            buyer_defense(work, buyer_id)
            st.caption('Оценивайте наблюдаемый результат. Личность и авторство этой проверкой не удостоверяются.')
            with st.expander('Критерии задания', expanded=True):
                rubric(work['criteria'])
            wid = work['id']
            with st.form(f'tt_review_{wid}_{work["version"]}'):
                ratings, evidence = [], []
                for i, c in enumerate(work['criteria']):
                    ratings.append(st.select_slider(c['label'], options=list(RATINGS), value=0, format_func=lambda n: RATINGS[n],
                                                     key=f'tt_score_{wid}_{i}_{work["version"]}'))
                    evidence.append(st.text_area('Свидетельство: ' + c['label'], max_chars=2000,
                                                  placeholder='Укажите фрагмент, тест, экран или ответ и объясните, что он показывает.',
                                                  key=f'tt_evidence_{wid}_{i}_{work["version"]}'))
                feedback = st.text_area('Обратная связь с примерами из работы', max_chars=4000, key=f'tt_feedback_{wid}_{work["version"]}')
                reviewer_name = st.text_input('Имя проверяющего (демо)', max_chars=120, key=f'tt_reviewer_name_{wid}_{work["version"]}')
                reviewer_role = st.text_input('Роль и компетенция проверяющего', max_chars=120, key=f'tt_reviewer_role_{wid}_{work["version"]}')
                limits = st.text_area('Ограничения проведённой проверки', max_chars=2000, key=f'tt_review_limits_{wid}_{work["version"]}')
                if work.get('understanding_status') in ('requested', 'answered', 'needs_clarification'):
                    st.caption('Защита ещё не завершена успешно: сначала получите и оцените ответ либо верните работу на доработку.')
                checked = st.checkbox('Я открыл результат и проверил его по критериям (демо)', key=f'tt_checked_{wid}_{work["version"]}')
                a, b = st.columns(2)
                approve = a.form_submit_button('Принять работу', type='primary')
                changes = b.form_submit_button('Вернуть на доработку')
            if approve or changes:
                if not checked:
                    st.error('Подтвердите проверку результата перед решением.')
                else:
                    action(lambda: store.review_work(wid, buyer_id, work['version'], ratings, feedback, approve,
                                                      criterion_evidence=evidence, reviewer_name=reviewer_name,
                                                      reviewer_role=reviewer_role, review_limits=limits),
                           'Результат принят. Паспорт доступен школьнику.' if approve else 'Обратная связь отправлена. Можно доработать результат.')


def buyer_challenges(buyer_id):
    heading('ЗАДАНИЯ КОМПАНИИ', 'Начните с конкретной задачи', 'Небольшой результат и прозрачные критерии помогают увидеть навыки.')
    with st.expander('Создать мини-задание'):
        with st.form('tt_create_challenge'):
            title = st.text_input('Название задания', max_chars=140, key='tt_challenge_title')
            brief = st.text_area('Контекст и задача', max_chars=6000, key='tt_challenge_brief')
            skill = st.selectbox('Навык', ['Python', 'Веб-разработка', 'Аналитика', 'UX/UI'], key='tt_challenge_skill')
            duration = st.text_input('Рекомендуемый срок', value='5–7 дней', max_chars=100, key='tt_challenge_duration')
            deliverable = st.text_area('Ожидаемый результат и способ проверки', max_chars=2000, key='tt_challenge_deliverable')
            st.caption('Критерии и веса фиксируются при публикации. Уточните, какие свидетельства будете проверять.')
            criteria = [dict(c, description=st.text_area(f'{c["label"]} · {c["weight"]}%', value=c['description'],
                         max_chars=1500, key=f'tt_criterion_{i}')) for i, c in enumerate(store.CRITERIA)]
            create = st.form_submit_button('Опубликовать задание', type='primary')
        if create:
            action(lambda: store.create_challenge(buyer_id, title, brief, skill, duration, deliverable, criteria), 'Задание опубликовано.')
    for item in store.challenges(buyer_id=buyer_id):
        with st.container(border=True):
            st.caption(f'{item["skill"]} · {item["duration"]}')
            st.subheader(item['title'])
            st.write(item['brief'])
            st.write(item['deliverable'])
            with st.expander('Показать критерии'):
                rubric(item['criteria'])


def discovery(buyer_id):
    heading('КАТАЛОГ РАБОТ', 'Ищите навыки. Смотрите доказательства.', 'Принятые результаты и профили с двумя демонстрационными согласиями.')
    pupils = store.discover(buyer_id)
    a, b, c = st.columns(3)
    region = a.selectbox('Регион', ['Все регионы', *sorted({p['region'] for p in pupils})], key='tt_filter_region')
    skill = b.selectbox('Навык', ['Все навыки', *sorted({w['skill'] for p in pupils for w in p['works']})], key='tt_filter_skill')
    saved_only = c.checkbox('Только избранные', key='tt_saved_only')
    visible = [p for p in pupils if (region == 'Все регионы' or p['region'] == region)
               and (skill == 'Все навыки' or any(w['skill'] == skill for w in p['works'])) and (not saved_only or p['saved'])]
    st.caption(f'Профилей найдено: {len(visible)}. Общего рейтинга школьников нет: оценка относится к отдельной работе.')
    if not visible:
        st.info('Нет подходящих профилей. Измените фильтры или дождитесь согласия и приёмки новых работ.')
    for pupil in visible:
        with st.container(border=True):
            a, b = st.columns([3, 1])
            a.subheader(pupil['name'])
            a.caption(f'{pupil["region"]} · {pupil["grade"]} класс · {pupil["focus"]}')
            pid = pupil['id']
            if b.button('Убрать из избранного' if pupil['saved'] else 'В избранное', key=f'tt_save_{pid}'):
                action(lambda: store.save_candidate(buyer_id, pid, not pupil['saved']), 'Избранное обновлено.')
            for work in pupil['works']:
                with st.expander(f'Паспорт: {work["challenge_title"]}'):
                    show_work(work)
            with st.expander('Пригласить в образовательную программу'):
                st.caption('Школьник сам выберет, отвечать ли на приглашение. Контакты не раскрываются.')
                with st.form(f'tt_invite_{pid}'):
                    message = st.text_area('Цель приглашения и следующий шаг', max_chars=1500, key=f'tt_invite_message_{pid}')
                    send = st.form_submit_button('Отправить приглашение в демо')
                if send:
                    action(lambda: store.invite(buyer_id, pid, message), 'Приглашение появилось в кабинете школьника.')


def about():
    heading('О ПРОЕКТЕ', 'Доверие через результат работы', 'Один фокус для HackHub: понять, что школьник умеет делать.')
    st.subheader('Кому и за что это нужно')
    st.write('Школьник 9–11 класса из Актюбинской области получает практику, обратную связь и портфолио. '
             'Компания — организатор образовательной или CSR-программы — получает задания, проверку результатов и подбор участников по работам.')
    st.info('Гипотеза цены: 100 000 ₸ за 30-дневный пилот для одной компании. Платят за рабочее пространство программы '
            'и отбор участников. Цена и спрос ещё не подтверждены интервью.')
    st.subheader('Как появляется паспорт работы')
    rubric(store.CRITERIA)
    st.write('Решение принимает заказчик вручную. Каждая оценка опирается на описанное свидетельство. '
             'Можно запросить объяснение и небольшое изменение решения, затем сохранить наблюдения проверяющего. '
             'Паспорт отдельно показывает оценку результата и статус проверки понимания; история сохраняет версии и решения.')
    st.subheader('Польза без компании')
    st.write('В разделе «Мой проект» школьник оформляет существующую работу, описывает вклад и помощь, '
             'проходит самопроверку и скачивает отчёт. Внешняя проверка такого отчёта не заявляется. '
             'Позже можно явно передать копию проекта компании по подходящему заданию.')
    with st.expander('Сценарий демонстрации для жюри'):
        st.write('1. Школьник → София Т. → «Мои работы»: исходная работа по расписанию уже ждёт проверки.\n\n'
                 '2. Компания → Qadam IT Education → «Проверка работ»: запросите объяснение границ интервалов и изменение с учётом кабинета.\n\n'
                 '3. Школьник → София Т. → «Мои работы»: отправьте ответ и тестовый результат изменения.\n\n'
                 '4. Компания → сохраните наблюдения, выставьте оценки со свидетельствами и примите работу.\n\n'
                 '5. Школьник → «Моё портфолио»: откройте паспорт и историю, включите оба демонстрационных согласия.\n\n'
                 '6. Компания → «Каталог работ»: отправьте приглашение; школьник отвечает в «Приглашениях».\n\n'
                 '7. Покажите «Мой проект»: частный отчёт самооценки доступен сразу, без проверки компанией.')
    st.subheader('Что предстоит проверить')
    st.write('15 ответов школьников и 2 интервью покупателей, готовность платить и каналы набора первых 100 участников. '
             'Демонстрационные данные не являются результатами исследования.')
    st.caption('Стек: Python, Streamlit, SQLite. Новый сценарий работает без API-ключей. Предыдущая версия сохранена '
               'в legacy_app.py. Реальная авторизация, проверка согласия законного представителя и постоянная серверная база '
               'нужны до работы с настоящими школьниками.')


def main():
    st.set_page_config(page_title='TaskUp Talent · Талант до вуза', page_icon='↗', layout='wide')
    html(f'<style>{(ROOT / "assets" / "talent.css").read_text(encoding="utf-8")}</style>')
    try:
        store.init()
        personal_projects.init_projects()
    except (OSError, store.db.sqlite3.Error):
        st.error('Не удалось открыть демонстрационную базу. Проверьте доступ к каталогу data.')
        st.stop()
    role = st.session_state.get('tt_role')
    if role not in ('student', 'buyer'):
        landing()
        return
    by_id = {p['id']: p for p in store.people(role)}
    pages = ({'catalog': 'Задания', 'projects': 'Мой проект', 'works': 'Мои работы', 'portfolio': 'Моё портфолио', 'invitations': 'Приглашения', 'about': 'О проекте'}
             if role == 'student' else {'review': 'Проверка работ', 'challenges': 'Мои задания', 'discovery': 'Каталог работ',
                                        'invitations': 'Приглашения', 'about': 'О проекте'})
    with st.sidebar:
        brand()
        st.caption('Кабинет школьника' if role == 'student' else 'Кабинет компании')
        person_id = st.selectbox('Демонстрационный профиль', list(by_id), format_func=lambda i: by_id[i]['name'], key=f'tt_person_{role}')
        if st.session_state.get('tt_current_person') != person_id:
            for key in list(st.session_state):
                if key.startswith('tt_') and key not in ('tt_role', f'tt_person_{role}', 'tt_page'):
                    del st.session_state[key]
            st.session_state['tt_current_person'] = person_id
        st.divider()
        current = st.session_state.setdefault('tt_page', next(iter(pages)))
        for page, label in pages.items():
            st.button(label, key=f'tt_nav_{page}', type='primary' if page == current else 'secondary', use_container_width=True,
                      on_click=navigate, args=(page,))
        st.divider()
        st.button('Сменить роль', key='tt_change_role', use_container_width=True, on_click=enter, args=(None,))
        st.caption('HackHub · Талант до вуза\n\nВсе данные вымышлены. Выбор профиля — демонстрация, не вход в аккаунт.')
    if message := st.session_state.pop('tt_flash', None):
        st.success(message)
    st.caption('ДЕМО · Тестовые профили и работы · Без реальных персональных данных')
    page = st.session_state['tt_page']
    if page == 'about':
        about()
    elif page == 'invitations':
        invitations(person_id, role)
    elif role == 'student':
        {'catalog': challenge_catalog, 'projects': render_projects, 'works': student_works, 'portfolio': portfolio}.get(page, challenge_catalog)(person_id)
    else:
        {'review': buyer_review, 'challenges': buyer_challenges, 'discovery': discovery}.get(page, buyer_review)(person_id)
