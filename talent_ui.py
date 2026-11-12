"""TaskUp Talent UI. Every identity and consent in this MVP is synthetic."""
from html import escape
from io import BytesIO
from pathlib import Path
from zipfile import ZipFile
from talent_i18n import t, td, error_text, language, language_picker
import streamlit as st
import talent_store as store
import talent_network as network
import personal_projects
from personal_projects_ui import render as render_projects
from talent_evidence_ui import evidence_summary, defense_record, history_panel, student_defense, buyer_defense, passport_report
from talent_network_ui import render_source, render_parent, render_student_records, render_public_records
ROOT = Path(__file__).resolve().parent
STATUS = {'pending': 'Ожидает проверки', 'changes_requested': 'Нужны доработки', 'approved': 'Результат принят'}
INVITES = {'pending': 'Ждёт ответа', 'accepted': 'Принято', 'declined': 'Отклонено', 'withdrawn': 'Отозвано после закрытия профиля'}
RATINGS = {0: '0 — нет свидетельств', 1: '1 — частично, доказательств мало', 2: '2 — базовый результат подтверждён', 3: '3 — выполнено с доказательствами', 4: '4 — выполнено и проверено'}
BUYER_CABINETS = {'company': 'Кабинет компании', 'university': 'Кабинет вуза', 'agency': 'Кабинет образовательного агентства', 'fund': 'Кабинет фонда'}
BUYER_INVITES = {'company': 'в образовательную или CSR-программу', 'university': 'в проектную школу или программу для абитуриентов', 'agency': 'на консультацию по образовательной траектории', 'fund': 'на отбор в грантовую программу'}
ROLE_ICONS = {'student': '<circle cx="12" cy="7" r="3"/><path d="M5 21v-3a7 7 0 0 1 14 0v3"/>', 'parent': '<circle cx="8" cy="8" r="3"/><circle cx="17" cy="10" r="2"/><path d="M2 21v-2a6 6 0 0 1 12 0v2m1-6a5 5 0 0 1 7 5v1"/>', 'university': '<path d="m3 8 9-5 9 5H3Zm0 13h18M5 18v-7m7 7v-7m7 7v-7"/>', 'buyer': '<rect x="3" y="7" width="18" height="14" rx="2"/><path d="M8 7V4h8v3M3 12l9 4 9-4m-9 2v4"/>', 'fund': '<path d="M12 21 4 13C-1 8 6 1 12 7c6-6 13 1 8 6l-8 8Z"/>', 'agency': '<circle cx="12" cy="12" r="9"/><path d="m16 8-2 6-6 2 2-6 6-2Z"/>', 'school': '<path d="M12 6C9 3 5 3 2 4v15c3-1 7-1 10 2 3-3 7-3 10-2V4c-3-1-7-1-10 2Zm0 0v15"/>', 'organizer': '<circle cx="12" cy="8" r="5"/><path d="m8 12-2 10 6-3 6 3-2-10"/>'}

def role_visual(key):
    category, style = (t('ТАЛАНТ И СЕМЬЯ'), 'family') if key in ('student', 'parent') else (t('ИСТОЧНИК СВЕДЕНИЙ'), 'source') if key in ('school', 'organizer') else (t('ПОКУПАТЕЛЬ'), 'buyer')
    html(f'<div class="tt-role-meta {style}"><span class="tt-role-icon"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">{ROLE_ICONS[key]}</svg></span>{category}</div>')

def html(value):
    st.markdown(value, unsafe_allow_html=True)

def brand():
    html('<div class="tt-brand"><span class="tt-mark">↗</span> TaskUp <b>Talent</b></div>')

def heading(kicker, title, description=''):
    html(f'<div class="tt-kicker">{escape(t(kicker))}</div><h1>{escape(t(title))}</h1><p class="tt-intro">{escape(td(description))}</p>')

def tag(text, good=False):
    html(f"""<span class="tt-tag {('good' if good else '')}">{escape(t(text))}</span>""")

def action(callback, message):
    try:
        callback()
    except ValueError as exc:
        st.error(error_text(str(exc)))
        return
    st.session_state['tt_flash'] = message
    st.rerun()

def enter(role, organization_kind=None):
    for key in list(st.session_state):
        if key.startswith('tt_'):
            del st.session_state[key]
    st.session_state['tt_role'] = role
    if role == 'buyer':
        st.session_state['tt_buyer_kind'] = organization_kind or 'company'

def navigate(page):
    st.session_state['tt_page'] = page

def landing():
    brand()
    st.caption(t('Kuskon AI · HackHub 2026 · Талант до вуза'))
    left, right = st.columns([1.4, 1], gap='large')
    with left:
        html(t('<div class="tt-kicker tt-hero-kicker">РЕАЛЬНАЯ РАБОТА → ДОВЕРИЕ</div><h1 class="tt-hero-title">Твой талант.<br><em>Твои доказательства.</em></h1><p class="tt-lead">Сделай небольшой IT-проект. Получи разбор от вуза или другой организации. Покажи, что умеешь, через результат работы.</p>'))
        tag(t('Для школьников 8–11 классов Актюбинской области'))
        html(t('<a class="tt-hero-cta" href="#vyberite-svoy-kabinet">Найти свой кабинет <span>→</span></a>'))
    with right:
        html(t('<div class="tt-proof"><div class="tt-proof-top">ПАСПОРТ РАБОТЫ <span>ДЕМО</span></div><h3>Учебный анализ данных</h3><p>Участник A-101 · Актобе · Аналитика</p><div class="tt-proof-result">✓ Результат принят заказчиком</div><div class="tt-proof-row"><span>Работа и исходники</span><b>Приложены</b></div><div class="tt-proof-row"><span>Критерии и обратная связь</span><b>Открыты</b></div><div class="tt-proof-row"><span>Публикация профиля</span><b>По согласию</b></div><p class="tt-small">Иллюстрация паспорта. Проверяется конкретная работа, а не «рейтинг таланта» школьника.</p></div>'))
    html(t('<div class="tt-steps"><div><b>01</b><strong>Выбери задание</strong><span>Критерии известны заранее</span></div><div><b>02</b><strong>Покажи результат</strong><span>Ссылка, подход и личный вклад</span></div><div><b>03</b><strong>Получи признание</strong><span>Разбор и паспорт принятой работы</span></div></div>'))
    st.subheader(t('Выберите свой кабинет'), anchor='vyberite-svoy-kabinet')
    st.caption(t('Практика, поддержка и новые возможности — у каждого участника своя роль.'))
    cards = [('student', None, 'student', t('Я школьник'), t('Практика, личные проекты, обратная связь и портфолио. Бесплатно.'), t('Выбрать задание →')), ('parent', None, 'parent', t('Я родитель'), t('Результаты ребёнка, следующий шаг и согласие на показ профиля.'), t('Открыть кабинет родителя →')), ('buyer', 'university', 'university', t('Я представляю вуз'), t('Проектные задания, знакомство с абитуриентами и приглашения в программы.'), t('Открыть кабинет вуза →')), ('buyer', 'company', 'buyer', t('Я представляю компанию'), t('Задания, проверка навыков и отбор в образовательные и CSR-программы.'), t('Открыть кабинет компании →')), ('buyer', 'fund', 'fund', t('Я представляю фонд'), t('Доказательства достижений региональных школьников и приглашения на отбор.'), t('Открыть кабинет фонда →')), ('buyer', 'agency', 'agency', t('Я представляю агентство'), t('Портфолио мотивированных школьников и приглашения на консультацию.'), t('Открыть кабинет агентства →')), ('school', None, 'school', t('Я представляю школу'), t('Подтверждение результатов своих учеников с указанием источника и способа проверки.'), t('Открыть кабинет школы →')), ('organizer', None, 'organizer', t('Я организатор конкурса'), t('Выдача записей о результатах участникам и управление собственным реестром.'), t('Открыть кабинет организатора →'))]
    for start in range(0, len(cards), 2):
        for col, (role, kind, key, title, description, button) in zip(st.columns(2, gap='large'), cards[start:start + 2]):
            with col, st.container(border=True, key=f'tt_role_card_{key}'):
                role_visual(key)
                st.subheader(title)
                st.write(description)
                st.button(button, key=f'tt_enter_{key}', type='primary' if role == 'student' else 'secondary', use_container_width=True, on_click=enter, args=(role, kind))
    st.info(t('Демонстрационный стенд: все профили и результаты вымышлены. Переключение роли — не авторизация. Используйте только тестовые данные и ссылки.'))
    with st.expander(t('Как устроено доверие')):
        st.write(t('Организация оценивает работу по трём критериям и указывает основания каждой оценки. По запросу школьник объясняет решение и вносит небольшое изменение. В паспорте видны доказательства, наблюдения проверяющего и границы проверки. Оценка результата и проверка понимания показаны отдельно.'))
        st.write(t('Без покупателя можно сохранить свой проект, описать вклад, пройти самопроверку и скачать отчёт. Он обозначен как самооценка. Передача организации происходит отдельным действием.'))
        st.write(t('Школы и организаторы выступают источниками сведений о достижениях. Школьник решает, добавлять ли полученную запись в портфолио. Такая запись показывает заявление источника и способ проверки, а не независимую сертификацию платформой.'))

def rubric(criteria):
    for item in criteria:
        st.markdown(f"**{td(item['label'])} · {item['weight']}%**")
        st.write(td(item['description']))
    st.caption(t('Итог = сумма (оценка / 4 × вес). Принятие: итог не ниже 70 и каждая оценка не ниже 2. Это правило прототипа.'))

def show_work(work, include_student=False):
    tag(STATUS[work['status']], work['status'] == 'approved')
    st.subheader(td(work['challenge_title']))
    if include_student:
        st.caption(f"{td(work['student_name'])} · {td(work['skill'])}")
    st.write(td(work['description']))
    st.link_button(t('Открыть результат работы №{p0} ↗', p0=work['id']), work['evidence_url'])
    demo_prefix = 'https://github.com/mcjuba1996-sudo/taskup-kuskon-ai-deploy/blob/codex/hackhub-talent/demo_evidence/'
    reports = {'attendance.md', 'schedule.md', 'signup.md'}
    report_name = work['evidence_url'].removeprefix(demo_prefix)
    if work['evidence_url'].startswith(demo_prefix) and report_name in reports:
        with st.expander(t('Посмотреть демонстрационный образец здесь')):
            st.caption(t('Образец подготовлен командой с помощью Codex. Это не достижение реального школьника.'))
            localized_report = ROOT / 'demo_evidence' / (Path(report_name).stem + '.' + language() + '.md')
            report_path = localized_report if language() != 'ru' and localized_report.exists() else ROOT / 'demo_evidence' / report_name
            st.markdown(report_path.read_text(encoding='utf-8'))
            archive = BytesIO()
            with ZipFile(archive, 'w') as bundle:
                for path in sorted((ROOT / 'demo_evidence').iterdir()):
                    if path.is_file() and path.suffix in ('.md', '.py', '.csv', '.html'):
                        bundle.write(path, path.name)
            st.download_button(t('Скачать образцы и исходники'), archive.getvalue(), 'taskup-demo-evidence.zip', mime='application/zip', key=f"tt_evidence_download_{work['id']}")
    st.markdown(t('**Личный вклад и выводы**'))
    st.write(td(work['reflection']))
    if work['status'] != 'pending':
        st.markdown(t('**Оценка этой работы: {p0:g}/100**', p0=work['total']))
        for criterion, value in zip(work['criteria'], work['ratings']):
            st.write(t('{p0}: {p1}/4 · вес {p2}%', p0=td(criterion['label']), p1=value, p2=criterion['weight']))
        st.markdown(t('**Обратная связь заказчика**'))
        st.write(td(work['feedback']))
        st.caption(t('Проверил: {p0} · {p1} · Демо-проверка', p0=td(work['buyer_name']), p1=work['reviewed_at'] or ''))
    evidence_summary(work)
    viewer_id = st.session_state.get('tt_current_person')
    if viewer_id:
        if work['status'] != 'pending' or st.session_state.get('tt_role') == 'student':
            defense_record(work, viewer_id)
        history_panel(work, viewer_id)

def challenge_catalog(student_id):
    heading(t('ПРАКТИКА'), t('От задачи — к первой работе'), t('Выберите мини-проект. Критерии открыты до начала работы.'))
    items = store.challenges()
    directions, organizations = st.columns(2)
    selected = directions.selectbox(t('Направление'), ['Все направления', *sorted({c['skill'] for c in items})], key='tt_catalog_skill', format_func=t)
    selected_kind = organizations.selectbox(t('Кто предлагает задание'), ['all', *store.ORGANIZATION_KINDS], format_func=lambda k: t(t('Все организации') if k == 'all' else store.ORGANIZATION_KINDS[k]), key='tt_catalog_kind')
    my_works = {w['challenge_id']: w for w in store.submissions(student_id=student_id)}
    for challenge in items:
        owner = store.person(challenge['buyer_id'])
        if selected != 'Все направления' and challenge['skill'] != selected:
            continue
        if selected_kind != 'all' and owner['organization_kind'] != selected_kind:
            continue
        with st.container(border=True):
            st.caption(f"{td(challenge['skill'])} · {td(challenge['duration'])} · {td(owner['name'])} · {t(store.ORGANIZATION_KINDS[owner['organization_kind']])}")
            st.subheader(td(challenge['title']))
            st.write(td(challenge['brief']))
            st.markdown(t('**Что нужно сдать**'))
            st.write(td(challenge['deliverable']))
            with st.expander(t('Критерии приёмки и самопроверка')):
                rubric(challenge['criteria'])
            prior = my_works.get(challenge['id'])
            if prior and prior['status'] != 'changes_requested':
                tag(STATUS[prior['status']], prior['status'] == 'approved')
                st.caption(t('Результат и обратная связь — в разделе «Мои работы».'))
                continue
            if prior:
                st.warning(t('Доработка: ') + td(prior['feedback']))
            with st.expander(t('Сдать доработку') if prior else t('Отправить работу на проверку')):
                st.caption(t('Работу увидит организация — автор задания, даже если портфолио закрыто. Не добавляйте реальные ФИО, контакты или данные других школьников.'))
                cid = challenge['id']
                with st.form(f'tt_submit_{cid}'):
                    url = st.text_input(t('Ссылка на репозиторий или прототип'), value=prior['evidence_url'] if prior else '', placeholder='https://example.com/my-project', max_chars=2000, key=f'tt_url_{cid}')
                    description = st.text_area(t('Что сделано и как проверить'), value=prior['description'] if prior else '', max_chars=6000, key=f'tt_description_{cid}')
                    reflection = st.text_area(t('Мой вклад, инструменты и чему я научился'), value=prior['reflection'] if prior else '', max_chars=4000, key=f'tt_reflection_{cid}')
                    source_version = st.text_input(t('Коммит или версия результата'), value=prior.get('source_version', '') if prior else '', max_chars=200, key=f'tt_source_version_{cid}', help=t('Укажите конкретную версию, которую передаёте на проверку. Это сведения автора; сервис не проверяет коммит автоматически.'))
                    consent = st.checkbox(t('Отправляю тестовую работу этой организации для проверки'), key=f'tt_submit_consent_{cid}')
                    send = st.form_submit_button(t('Отправить на проверку'), type='primary')
                if send:
                    if not consent:
                        st.error(t('Подтвердите передачу тестовой работы организации.'))
                    else:
                        action(lambda: store.submit_work(cid, student_id, url, description, reflection, source_version=source_version), t('Работа отправлена. Статус можно посмотреть в «Мои работы».'))
    with st.expander(t('Начать самостоятельно: шаблон отчёта')):
        st.write(t('Опишите задачу, рабочий сценарий, личный вклад, инструменты, результаты проверки и ограничения.'))
        template = t('# Мой мини-проект\n\n## Задача\n\n## Что работает\n\n## Ссылка и инструкция\n\n## Мой вклад и инструменты\n\n## Проверка\n\n## Ограничения и выводы\n')
        st.download_button(t('Скачать шаблон отчёта'), template, 'project-report.md', mime='text/markdown')

def student_works(student_id):
    heading(t('МОИ РАБОТЫ'), t('Каждая попытка — шаг вперёд'), t('Статусы, оценки и обратная связь по вашим результатам.'))
    works = store.submissions(student_id=student_id)
    if not works:
        st.info(t('Пока нет работ. Выберите задание и отправьте первый результат.'))
    for work in works:
        with st.container(border=True):
            show_work(work)
            student_defense(work, student_id)
            if work['status'] == 'changes_requested':
                st.button(t('Перейти к доработке'), key=f"tt_revise_{work['id']}", on_click=navigate, args=('catalog',))

def portfolio(student_id):
    pupil = store.person(student_id)
    heading(t('ПОРТФОЛИО'), t('Работы говорят за вас'), t('Вы управляете тем, что доступно вузам, агентствам, компаниям и фондам.'))
    st.subheader(td(pupil['name']))
    st.write(t('{p0} · {p1} класс · {p2}', p0=td(pupil['region']), p1=pupil['grade'], p2=td(pupil['focus'])))
    public = pupil['share_profile'] and pupil['guardian_consent']
    tag(t('Видно покупателям при наличии принятой работы') if public else t('Закрыто для каталога покупателей'), public)
    st.caption(t('В каталоге доступны псевдоним, регион, класс, направление, принятые работы и история их версий, включая прежние доработки, ответы на защиту, наблюдения проверяющего и принятые вами записи источников. Телефон, адрес и контакты не собираются. Ссылки и текст работ тоже видны: используйте только тестовые данные.'))
    linked_guardian = network.has_guardian(student_id)
    if linked_guardian:
        st.session_state['tt_guardian_consent'] = pupil['guardian_consent']
        st.caption(t('Для этого демопрофиля согласие представителя меняется в кабинете родителя. Ваше собственное согласие остаётся отдельным: для показа нужны оба.'))
    with st.form(f'tt_visibility_{student_id}'):
        share = st.checkbox(t('Я согласен показать вузам, агентствам, компаниям и фондам тестовый профиль, принятые работы, историю, материалы защиты и принятые записи источников'), value=pupil['share_profile'], key='tt_share_profile')
        guardian = st.checkbox(t('Согласие законного представителя получено — моделирование для демо'), value=False if linked_guardian else pupil['guardian_consent'], key='tt_guardian_consent', disabled=linked_guardian)
        saved = st.form_submit_button(t('Сохранить видимость'), type='primary')
    if saved:
        action(lambda: store.set_visibility(student_id, share, guardian), t('Настройки видимости сохранены.'))
    st.caption(t('Снятие любого согласия убирает профиль из каталога и избранного, отзывает ожидающие приглашения. Заказчик сохраняет доступ к работам на своих заданиях. В реальном сервисе нужна отдельная проверка согласия; этот переключатель её не заменяет.'))
    st.subheader(t('Паспорта принятых работ'))
    works = [w for w in store.submissions(student_id=student_id) if w['status'] == 'approved']
    if not works:
        st.info(t('Паспорт появится после приёмки результата организацией — автором задания.'))
    for work in works:
        with st.container(border=True):
            show_work(work)
            report = passport_report(work, pupil, student_id, lang=language())
            st.download_button(t('Скачать паспорт работы'), report, f"work-{work['id']}.md", mime='text/markdown', key=f"tt_download_{work['id']}")
    st.button(t('Достижения от школы и организаторов'), key='tt_open_achievements', on_click=navigate, args=('achievements',))

def invitations(person_id, role):
    heading(t('ПРИГЛАШЕНИЯ'), t('Следующий шаг — по согласию'), t('Приглашения остаются внутри демо. Внешние сообщения не отправляются.'))
    items = store.invitations(**{f'{role}_id': person_id})
    if not items:
        st.info(t('Пока нет приглашений. Компания может пригласить участника из каталога принятых работ.'))
    for item in items:
        with st.container(border=True):
            st.subheader(td(item['buyer_name']) if role == 'student' else td(item['student_name']))
            tag(INVITES[item['status']], item['status'] == 'accepted')
            st.write(item['message'])
            if role == 'student' and item['status'] == 'pending':
                a, b = st.columns(2)
                if a.button(t('Принять приглашение'), key=f"tt_accept_{item['id']}", type='primary'):
                    action(lambda: store.respond_invitation(item['id'], person_id, True), t('Приглашение принято внутри демо.'))
                if b.button(t('Отклонить'), key=f"tt_decline_{item['id']}"):
                    action(lambda: store.respond_invitation(item['id'], person_id, False), t('Приглашение отклонено.'))

def buyer_review(buyer_id):
    heading(t('ПРОВЕРКА РАБОТ'), t('За каждым решением — доказательства'), t('Откройте результат, проверьте критерии и объясните оценку.'))
    all_works = store.submissions(buyer_id=buyer_id)
    for col, status, label in zip(st.columns(3), ('pending', 'approved', 'changes_requested'), (t('Ожидают проверки'), t('Принятые работы'), t('На доработке'))):
        col.metric(label, sum((w['status'] == status for w in all_works)))
    state = st.selectbox(t('Статус работы'), ['Ожидают проверки', 'Все работы'], key='tt_review_filter', format_func=t)
    items = [w for w in all_works if state == 'Все работы' or w['status'] == 'pending']
    if not items:
        st.info(t('Новых работ пока нет. В роли школьника отправьте результат на одно из ваших заданий.'))
    for work in items:
        with st.container(border=True):
            show_work(work, include_student=True)
            if work['status'] != 'pending':
                continue
            buyer_defense(work, buyer_id)
            st.caption(t('Оценивайте наблюдаемый результат. Личность и авторство этой проверкой не удостоверяются.'))
            with st.expander(t('Критерии задания'), expanded=True):
                rubric(work['criteria'])
            wid = work['id']
            with st.form(f"tt_review_{wid}_{work['version']}"):
                ratings, evidence = ([], [])
                for i, c in enumerate(work['criteria']):
                    ratings.append(st.select_slider(td(c['label']), options=list(RATINGS), value=0, format_func=lambda n: t(RATINGS[n]), key=f"tt_score_{wid}_{i}_{work['version']}"))
                    evidence.append(st.text_area(t('Свидетельство: ') + td(c['label']), max_chars=2000, placeholder=t('Укажите фрагмент, тест, экран или ответ и объясните, что он показывает.'), key=f"tt_evidence_{wid}_{i}_{work['version']}"))
                feedback = st.text_area(t('Обратная связь с примерами из работы'), max_chars=4000, key=f"tt_feedback_{wid}_{work['version']}")
                reviewer_name = st.text_input(t('Имя проверяющего (демо)'), max_chars=120, key=f"tt_reviewer_name_{wid}_{work['version']}")
                reviewer_role = st.text_input(t('Роль и компетенция проверяющего'), max_chars=120, key=f"tt_reviewer_role_{wid}_{work['version']}")
                limits = st.text_area(t('Ограничения проведённой проверки'), max_chars=2000, key=f"tt_review_limits_{wid}_{work['version']}")
                if work.get('understanding_status') in ('requested', 'answered', 'needs_clarification'):
                    st.caption(t('Защита ещё не завершена успешно: сначала получите и оцените ответ либо верните работу на доработку.'))
                checked = st.checkbox(t('Я открыл результат и проверил его по критериям (демо)'), key=f"tt_checked_{wid}_{work['version']}")
                a, b = st.columns(2)
                approve = a.form_submit_button(t('Принять работу'), type='primary')
                changes = b.form_submit_button(t('Вернуть на доработку'))
            if approve or changes:
                if not checked:
                    st.error(t('Подтвердите проверку результата перед решением.'))
                else:
                    action(lambda: store.review_work(wid, buyer_id, work['version'], ratings, feedback, approve, criterion_evidence=evidence, reviewer_name=reviewer_name, reviewer_role=reviewer_role, review_limits=limits), t('Результат принят. Паспорт доступен школьнику.') if approve else t('Обратная связь отправлена. Можно доработать результат.'))

def buyer_challenges(buyer_id):
    owner = store.person(buyer_id)
    heading(t('ЗАДАНИЯ ОРГАНИЗАЦИИ'), t('Начните с конкретной задачи'), owner['organization_purpose'])
    with st.expander(t('Создать мини-задание')):
        with st.form('tt_create_challenge'):
            title = st.text_input(t('Название задания'), max_chars=140, key='tt_challenge_title')
            brief = st.text_area(t('Контекст и задача'), max_chars=6000, key='tt_challenge_brief')
            skill = st.selectbox(t('Навык'), ['Python', 'Веб-разработка', 'Аналитика', 'UX/UI'], key='tt_challenge_skill', format_func=t)
            duration = st.text_input(t('Рекомендуемый срок'), value=t('5–7 дней'), max_chars=100, key='tt_challenge_duration')
            deliverable = st.text_area(t('Ожидаемый результат и способ проверки'), max_chars=2000, key='tt_challenge_deliverable')
            st.caption(t('Критерии и веса фиксируются при публикации. Уточните, какие свидетельства будете проверять.'))
            criteria = [dict(c, description=st.text_area(f"{td(c['label'])} · {c['weight']}%", value=td(c['description']), max_chars=1500, key=f'tt_criterion_{i}')) for i, c in enumerate(store.CRITERIA)]
            create = st.form_submit_button(t('Опубликовать задание'), type='primary')
        if create:
            action(lambda: store.create_challenge(buyer_id, title, brief, skill, duration, deliverable, criteria), t('Задание опубликовано.'))
    for item in store.challenges(buyer_id=buyer_id):
        with st.container(border=True):
            st.caption(f"{td(item['skill'])} · {td(item['duration'])}")
            st.subheader(td(item['title']))
            st.write(td(item['brief']))
            st.write(td(item['deliverable']))
            with st.expander(t('Показать критерии')):
                rubric(item['criteria'])

def discovery(buyer_id):
    heading(t('КАТАЛОГ РАБОТ'), t('Ищите навыки. Смотрите доказательства.'), t('Принятые результаты и профили с двумя демонстрационными согласиями.'))
    owner = store.person(buyer_id)
    st.info(td(owner['organization_purpose']))
    pupils = store.discover(buyer_id)
    a, b, c = st.columns(3)
    region = a.selectbox(t('Регион'), ['Все регионы', *sorted({p['region'] for p in pupils})], key='tt_filter_region', format_func=t)
    skill = b.selectbox(t('Навык'), ['Все навыки', *sorted({w['skill'] for p in pupils for w in p['works']})], key='tt_filter_skill', format_func=t)
    saved_only = c.checkbox(t('Только избранные'), key='tt_saved_only')
    visible = [p for p in pupils if (region == 'Все регионы' or p['region'] == region) and (skill == 'Все навыки' or any((w['skill'] == skill for w in p['works']))) and (not saved_only or p['saved'])]
    st.caption(t('Профилей найдено: {p0}. Общего рейтинга школьников нет: оценка относится к отдельной работе.', p0=len(visible)))
    if not visible:
        st.info(t('Нет подходящих профилей. Измените фильтры или дождитесь согласия и приёмки новых работ.'))
    for pupil in visible:
        with st.container(border=True):
            a, b = st.columns([3, 1])
            a.subheader(td(pupil['name']))
            a.caption(t('{p0} · {p1} класс · {p2}', p0=td(pupil['region']), p1=pupil['grade'], p2=td(pupil['focus'])))
            pid = pupil['id']
            if b.button(t('Убрать из избранного') if pupil['saved'] else t('В избранное'), key=f'tt_save_{pid}'):
                action(lambda: store.save_candidate(buyer_id, pid, not pupil['saved']), t('Избранное обновлено.'))
            for work in pupil['works']:
                with st.expander(t('Паспорт: {p0}', p0=td(work['challenge_title']))):
                    show_work(work)
            render_public_records(buyer_id, pid)
            with st.expander(t('Пригласить {purpose}', purpose=t(BUYER_INVITES[owner['organization_kind']]))):
                st.caption(t('Школьник сам выберет, отвечать ли на приглашение. Контакты не раскрываются.'))
                with st.form(f'tt_invite_{pid}'):
                    message = st.text_area(t('Цель приглашения и следующий шаг'), max_chars=1500, key=f'tt_invite_message_{pid}')
                    send = st.form_submit_button(t('Отправить приглашение в демо'))
                if send:
                    action(lambda: store.invite(buyer_id, pid, message), t('Приглашение появилось в кабинете школьника.'))

def research_overview():
    st.subheader(t('Проблема и исследование'))
    st.info(t('Статус: гипотеза. Реальные интервью ещё не проведены.'))
    st.write(t('При конкурсном отборе в IT-программу готовый командный проект может не показывать, что конкретный школьник сделал и понимает самостоятельно. Координатору приходится запрашивать пояснения, а участнику — заново объяснять свой вклад. Проверяем, насколько часто это происходит и мешает ли принять решение.'))
    st.write(t('**Первый сегмент для проверки:** школьники 9–11 классов Актюбинской области и координаторы корпоративных проектных IT-программ с конкурсным отбором.'))
    st.write(t('**Почему личный вклад:** работа показывает общий результат, а пояснение и короткая защита могут помочь понять действия и решения конкретного участника. Пользу такого процесса ещё нужно проверить.'))
    st.caption(t('Смоделированные сценарии: примеры ниже вымышлены и не являются ответами участников исследования.'))
    scenarios = ((t('Школьник: общий проект, неясный личный вклад'), t('Команда отправляет сайт школьного клуба. Проверяющий просит участника показать, какие страницы и функции он сделал сам. Описание своей части и короткая защита могут помочь объяснить вклад.'), t('Что проверяем: какие уточнения действительно запрашивали при прошлой подаче и что произошло дальше.')), (t('Покупатель: пояснения приходят в разных форматах'), t('Координатор получает командные проекты и отдельно уточняет вклад кандидатов. Ответы приходят в разных форматах, поэтому основания решений сложно сопоставить.'), t('Что проверяем: конкретный случай, действия проверяющего, затраты времени и влияние на решение.')), (t('Покупатель: существующая проверка уже работает'), t('В другой программе есть стандартное задание, короткая защита и общая таблица решений. Такого процесса может быть достаточно; новая платформа способна добавить лишний ввод данных.'), t('Что может опровергнуть гипотезу: нынешний процесс устраивает координатора, а TaskUp не добавляет полезных сведений.')))
    for title, situation, question in scenarios:
        with st.expander(title):
            st.caption(t('Смоделированный сценарий'))
            st.write(situation)
            st.write(question)
    st.link_button(t('Полный учебный пример ↗'), 'https://github.com/mcjuba1996-sudo/taskup-kuskon-ai-deploy/blob/main/docs/research/synthetic-example.txt')
    st.caption(t('Подтверждение проблемы остаётся открытым: нужны реальные ответы школьников и покупателей, включая случаи, в которых гипотеза не подтверждается.'))

def about():
    heading(t('О ПРОЕКТЕ'), t('Доверие через результат работы'), t('Один фокус для HackHub: понять, что школьник умеет делать.'))
    research_overview()
    st.subheader(t('Кому и за что это нужно'))
    st.write(t('Школьник 8–11 класса из Актюбинской области получает практику, обратную связь и портфолио. Вузы, образовательные агентства, компании и фонды создают задания, проверяют результаты и приглашают участников. Школы и организаторы конкурсов дают сведения о достижениях, а родители видят результаты своего ребёнка и управляют согласием.'))
    st.info(t('Гипотеза цены: 100 000 ₸ за одну 30-дневную кампанию компании: одно задание, до 100 регистраций и до 25 работ на проверке. Экспертов предоставляет покупатель. Платят за организацию процесса отбора; число участников и приглашений не гарантируется. Цена, спрос и окупаемость ещё не подтверждены интервью.'))
    st.subheader(t('Как появляется паспорт работы'))
    rubric(store.CRITERIA)
    st.write(t('Решение принимает заказчик вручную. Каждая оценка опирается на описанное свидетельство. Можно запросить объяснение и небольшое изменение решения, затем сохранить наблюдения проверяющего. Паспорт отдельно показывает оценку результата и статус проверки понимания; история сохраняет версии и решения.'))
    st.caption(t('Первый проверяемый коммерческий сегмент — корпоративная проектная IT-программа для 9–11 классов. Другие кабинеты расширяют сценарии прототипа; спрос и готовность платить у каждого сегмента ещё предстоит проверить.'))
    st.subheader(t('Польза без покупателя'))
    st.write(t('В разделе «Мой проект» школьник оформляет существующую работу, описывает вклад и помощь, проходит самопроверку и скачивает отчёт. Внешняя проверка такого отчёта не заявляется. Позже можно явно передать копию проекта организации по подходящему заданию.'))
    st.subheader(t('Роли и доступ к данным'))
    st.write(t('Покупателям доступны профили с принятой работой и двумя согласиями. Школа или организатор работает со своим демонстрационным списком участников и собственными записями. Школьник принимает или отклоняет запись источника. Родитель видит только привязанный профиль и сводку результатов; личные черновики остаются у школьника.'))
    st.caption(t('В демонстрации родитель привязан к участнику A-106. В остальных ранних профилях согласие представителя по-прежнему моделируется переключателем. Все связи, организации и записи вымышлены.'))
    with st.expander(t('Сценарий демонстрации для жюри')):
        st.write(t('1. Школьник → София Т. → «Мои работы»: исходная работа по расписанию уже ждёт проверки.\n\n2. Компания → Qadam IT Education → «Проверка работ»: запросите объяснение границ интервалов и изменение с учётом кабинета.\n\n3. Школьник → София Т. → «Мои работы»: отправьте ответ и тестовый результат изменения.\n\n4. Компания → сохраните наблюдения, выставьте оценки со свидетельствами и примите работу.\n\n5. Школьник → «Моё портфолио»: откройте паспорт и историю, включите оба демонстрационных согласия.\n\n6. Компания → «Каталог работ»: отправьте приглашение; школьник отвечает в «Приглашениях».\n\n7. Покажите «Мой проект»: частный отчёт самооценки доступен сразу, без проверки компанией.'))
    st.subheader(t('Что предстоит проверить'))
    st.write(t('15 ответов школьников и 2 интервью покупателей, готовность платить и каналы набора первых 100 участников. Демонстрационные данные не являются результатами исследования.'))
    st.caption(t('Стек: Python, Streamlit, SQLite. Новый сценарий работает без API-ключей. Предыдущая версия сохранена в legacy_app.py. Реальная авторизация, проверка согласия законного представителя и постоянная серверная база нужны до работы с настоящими школьниками.'))

def main():
    st.set_page_config(page_title=t('TaskUp Talent · Талант до вуза'), page_icon='↗', layout='wide')
    with st.container(key='talent_language_bar'):
        _, language_column = st.columns([3, 1])
        with language_column:
            language_picker()
    html(f"<style>{(ROOT / 'assets' / 'talent.css').read_text(encoding='utf-8')}</style>")
    try:
        store.init()
        personal_projects.init_projects()
        network.init_network()
    except (OSError, store.db.sqlite3.Error):
        st.error(t('Не удалось открыть демонстрационную базу. Проверьте доступ к каталогу data.'))
        st.stop()
    role = st.session_state.get('tt_role')
    if role not in ('student', 'buyer', 'school', 'organizer', 'parent'):
        landing()
        return
    kind = st.session_state.get('tt_buyer_kind', 'company')
    profiles = store.people('buyer', organization_kind=kind) if role == 'buyer' else store.people('student') if role == 'student' else network.people(role)
    by_id = {p['id']: p for p in profiles}
    role_pages = {'student': {'catalog': t('Задания'), 'projects': t('Мой проект'), 'works': t('Мои работы'), 'achievements': t('Достижения'), 'portfolio': t('Моё портфолио'), 'invitations': t('Приглашения'), 'about': t('О проекте')}, 'buyer': {'review': t('Проверка работ'), 'challenges': t('Мои задания'), 'discovery': t('Каталог работ'), 'invitations': t('Приглашения'), 'about': t('О проекте')}, 'school': {'registry': t('Результаты учеников'), 'about': t('О проекте')}, 'organizer': {'registry': t('Реестр результатов'), 'about': t('О проекте')}, 'parent': {'children': t('Ребёнок и согласие'), 'about': t('О проекте')}}
    pages = role_pages[role]
    cabinet = BUYER_CABINETS.get(kind, t('Кабинет организации')) if role == 'buyer' else {'student': t('Кабинет школьника'), 'school': t('Кабинет школы'), 'organizer': t('Кабинет организатора'), 'parent': t('Кабинет родителя')}[role]
    with st.sidebar:
        brand()
        st.caption(t(cabinet))
        if not by_id:
            st.info(t('Для этой роли пока нет демонстрационных профилей.'))
            st.button(t('Сменить роль'), key='tt_change_role', on_click=enter, args=(None,))
            return
        person_id = st.selectbox(t('Демонстрационный профиль'), list(by_id), format_func=lambda i: t(by_id[i]['name']), key=f'tt_person_{role}')
        if st.session_state.get('tt_current_person') != person_id:
            for key in list(st.session_state):
                if key.startswith('tt_') and key not in ('tt_role', f'tt_person_{role}', 'tt_page', 'tt_buyer_kind'):
                    del st.session_state[key]
            st.session_state['tt_current_person'] = person_id
        st.divider()
        current = st.session_state.setdefault('tt_page', next(iter(pages)))
        for page, label in pages.items():
            st.button(label, key=f'tt_nav_{page}', type='primary' if page == current else 'secondary', use_container_width=True, on_click=navigate, args=(page,))
        st.divider()
        st.button(t('Сменить роль'), key='tt_change_role', use_container_width=True, on_click=enter, args=(None,))
        st.caption(t('HackHub · Талант до вуза\n\nВсе данные вымышлены. Выбор профиля — демонстрация, не вход в аккаунт.'))
    if (message := st.session_state.pop('tt_flash', None)):
        st.success(message)
    st.caption(t('ДЕМО · Тестовые профили и работы · Без реальных персональных данных'))
    page = st.session_state['tt_page']
    if page == 'about':
        about()
    elif page == 'invitations' and role in ('student', 'buyer'):
        invitations(person_id, role)
    elif role == 'student':
        {'catalog': challenge_catalog, 'projects': render_projects, 'works': student_works, 'portfolio': portfolio, 'achievements': render_student_records}.get(page, challenge_catalog)(person_id)
    elif role == 'buyer':
        {'review': buyer_review, 'challenges': buyer_challenges, 'discovery': discovery}.get(page, buyer_review)(person_id)
    elif role == 'parent':
        render_parent(person_id)
    else:
        render_source(person_id)
