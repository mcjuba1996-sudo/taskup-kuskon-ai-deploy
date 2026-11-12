"""Private student drafts and self-assessment; demo roles are not authentication.

A personal project never becomes externally verified through this module. Explicit
handoff creates a separate submission snapshot in the selected challenge.
"""
import html
import json
import re

import database as db
import talent_store as talent


CHECKLIST = (
    {'id': 'reproducible', 'label': 'Я описал, как воспроизвести результат'},
    {'id': 'personalcontribution', 'label': 'Я отделил личный вклад от полученной помощи'},
    {'id': 'tests', 'label': 'Я проверил основной сценарий и записал результат'},
    {'id': 'limitations', 'label': 'Я описал ограничения и следующий шаг'},
)
SELF_ASSESSMENT = 'Самооценка. Внешняя проверка не проводилась'


def init_projects():
    """Add an empty private namespace after talent.init(); no fabricated works."""
    with db.connect() as conn:
        conn.execute('''CREATE TABLE IF NOT EXISTS talent_personal_projects(
            id INTEGER PRIMARY KEY,
            student_id INTEGER NOT NULL REFERENCES talent_people(id),
            title TEXT NOT NULL, description TEXT NOT NULL DEFAULT '',
            evidence_url TEXT NOT NULL DEFAULT '', contribution TEXT NOT NULL DEFAULT '',
            tools_help TEXT NOT NULL DEFAULT '', checks TEXT NOT NULL DEFAULT '[]',
            source_version TEXT NOT NULL DEFAULT '',
            version INTEGER NOT NULL DEFAULT 1 CHECK(version >= 1),
            created TEXT NOT NULL, updated TEXT NOT NULL)''')
        conn.execute('''CREATE INDEX IF NOT EXISTS talent_personal_project_owner
                        ON talent_personal_projects(student_id, updated)''')


def _text(value, label, minimum=0, maximum=6000):
    return talent._text(value, label, minimum, maximum)


def _student(conn, student_id):
    if type(student_id) is not int or student_id < 1:
        raise ValueError('Выберите демопрофиль школьника.')
    talent._role(conn, student_id, 'student')


def _checks(checks):
    valid = {item['id'] for item in CHECKLIST}
    if (not isinstance(checks, list) or any(type(item) is not str or item not in valid for item in checks)
            or len(checks) != len(set(checks))):
        raise ValueError('Выберите только известные пункты самопроверки без повторов.')
    return [item['id'] for item in CHECKLIST if item['id'] in checks]


def _project(row):
    result = dict(row)
    result['checks'] = json.loads(result['checks'])
    return result


def _owned(conn, project_id, student_id):
    if type(project_id) is not int or project_id < 1:
        raise ValueError('Личный проект не найден.')
    row = conn.execute('SELECT * FROM talent_personal_projects WHERE id=?', (project_id,)).fetchone()
    if not row or row['student_id'] != student_id:
        raise ValueError('Личный проект доступен только его владельцу.')
    return _project(row)


def _version(project, expected_version):
    if type(expected_version) is not int or expected_version != project['version']:
        raise ValueError('Проект уже изменён или версия не указана. Обновите страницу.')


def projects(student_id):
    """Return only this student's drafts; there is no buyer-scoped listing."""
    with db.connect() as conn:
        _student(conn, student_id)
        return [_project(row) for row in conn.execute('''SELECT * FROM talent_personal_projects
            WHERE student_id=? ORDER BY updated DESC,id DESC''', (student_id,))]


def save_project(student_id, title, description, evidence_url, contribution, tools_help,
                 checks, source_version='', project_id=None, expected_version=None):
    """A title is sufficient for a draft; updates require the displayed version."""
    title = _text(title, 'Название проекта', 3, 140)
    description = _text(description, 'Описание проекта', 0, 5500)
    evidence_url = _text(evidence_url, 'Ссылка на результат', 0, 2000)
    if evidence_url and not db.valid_url(evidence_url):
        raise ValueError('Укажите корректную http/https-ссылку или оставьте черновик без ссылки.')
    contribution = _text(contribution, 'Личный вклад', 0, 2500)
    tools_help = _text(tools_help, 'Инструменты и помощь', 0, 1000)
    source_version = _text(source_version, 'Версия исходного результата', 0, 200)
    checks_json = json.dumps(_checks(checks), ensure_ascii=False)
    stamp = db.now()
    values = (title, description, evidence_url, contribution, tools_help, checks_json, source_version)
    with db.connect() as conn:
        conn.execute('BEGIN IMMEDIATE')
        _student(conn, student_id)
        if project_id is None:
            if expected_version is not None:
                raise ValueError('Для нового проекта версия не указывается.')
            return conn.execute('''INSERT INTO talent_personal_projects
                (student_id,title,description,evidence_url,contribution,tools_help,checks,
                 source_version,created,updated) VALUES(?,?,?,?,?,?,?,?,?,?)''',
                (student_id, *values, stamp, stamp)).lastrowid
        existing = _owned(conn, project_id, student_id)
        _version(existing, expected_version)
        conn.execute('''UPDATE talent_personal_projects SET title=?,description=?,evidence_url=?,
            contribution=?,tools_help=?,checks=?,source_version=?,version=version+1,updated=?
            WHERE id=? AND student_id=? AND version=?''',
            (*values, stamp, project_id, student_id, expected_version))
        return project_id


def completeness(project):
    """Missing handoff fields, not a talent score or verification judgement."""
    missing = []
    url = project.get('evidence_url', '')
    if not isinstance(url, str) or not url.strip() or not db.valid_url(url):
        missing.append('Добавьте корректную http/https-ссылку на результат.')
    for field, label in (('description', 'Описание результата'), ('contribution', 'Личный вклад')):
        value = project.get(field, '')
        if not isinstance(value, str) or len(value.strip()) < 20:
            missing.append(f'{label}: нужно не менее 20 символов перед отправкой.')
    return missing


def _quoted(value):
    """Render submitted text as quoted data, never as trusted Markdown/HTML."""
    text = value if isinstance(value, str) else ''
    text = html.escape(text.strip() or 'Не указано', quote=False)
    text = re.sub(r'([\\`*_{}\[\]()#+.!|>-])', r'\\\1', text)
    return '\n'.join('> ' + line for line in text.splitlines())


def project_report(project):
    """Export self-reported text only; ignore status/ratings supplied by callers."""
    if not isinstance(project, dict):
        raise ValueError('Нужна карточка личного проекта.')
    missing = completeness(project)
    lines = ['# Мой проект', '', f'**{SELF_ASSESSMENT}**', '',
             'Личный учебный материал. Описания и отметки ниже сообщены автором; '
             'они не подтверждают авторство, качество или уровень таланта.', '',
             '**Черновик: поля для отправки заполнены не полностью.**' if missing else
             'Обязательные поля для отправки заполнены. Это не результат проверки.', '']
    for key, label in (('title', 'Название'), ('description', 'Описание результата'),
                       ('evidence_url', 'Ссылка на результат'), ('source_version', 'Версия исходного результата'),
                       ('contribution', 'Мой вклад'), ('tools_help', 'Инструменты и полученная помощь')):
        lines.extend([f'## {label} — со слов автора', '', _quoted(project.get(key, '')), ''])
    checks = project.get('checks', [])
    checks = checks if isinstance(checks, list) else []
    lines.extend(['## Самопроверка автора', '', 'Отметки не проверены третьей стороной.', ''])
    for item in CHECKLIST:
        lines.append(f"- [{'x' if item['id'] in checks else ' '}] {item['label']}")
    if missing:
        lines.extend(['', '## Перед отправкой', '', *['- ' + item for item in missing]])
    lines.extend(['', 'Экспорт не публикует проект и не передаёт его покупателю. '
                  'Передача на выбранное задание — отдельное действие владельца.', ''])
    return '\n'.join(lines)


def transfer_project(project_id, student_id, challenge_id, expected_version):
    """Atomically submit a copy; later personal edits cannot change that copy."""
    with db.connect() as conn:
        conn.execute('BEGIN IMMEDIATE')
        _student(conn, student_id)
        project = _owned(conn, project_id, student_id)
        _version(project, expected_version)
        if type(challenge_id) is not int or not conn.execute(
                'SELECT 1 FROM talent_challenges WHERE id=?', (challenge_id,)).fetchone():
            raise ValueError('Выберите существующее задание для отправки.')
        missing = completeness(project)
        if missing:
            raise ValueError(' '.join(missing))
        existing = conn.execute('''SELECT status FROM talent_submissions
            WHERE challenge_id=? AND student_id=?''', (challenge_id, student_id)).fetchone()
        if existing and existing['status'] != 'changes_requested':
            raise ValueError('На это задание уже есть работа. Ожидайте проверки или запроса доработки.')
        description = (f"Личный проект: {project['title']}\n\n{project['description']}\n\n"
                       f"Копия проекта №{project['id']}, версия {project['version']}.")
        checked = [item['label'] for item in CHECKLIST if item['id'] in project['checks']]
        reflection = (f"Личный вклад (самоотчёт):\n{project['contribution']}\n\n"
                      f"Инструменты и помощь (самоотчёт):\n{project['tools_help'] or 'Не указаны'}\n\n"
                      'Самопроверка, не внешняя оценка:\n' + ('; '.join(checked) or 'Нет отметок'))
        return talent.submit_work(challenge_id, student_id, project['evidence_url'], description,
                                  reflection, source_version=project['source_version'], _conn=conn)
