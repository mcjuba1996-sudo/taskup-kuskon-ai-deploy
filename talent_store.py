"""TaskUp Talent demo persistence; the role picker is not authentication.

Only explicitly shared, guardian-consented profiles with accepted evidence enter
discovery. Challenge owners may still review work submitted to their challenges.
All added tables are namespaced so the original TaskUp data remains untouched.
"""
import json
from contextlib import nullcontext

import database as db


WEIGHTS = (40, 35, 25)
PASS_SCORE = 70
DEMO_EVIDENCE_URLS = {
    challenge_id: 'https://github.com/mcjuba1996-sudo/taskup-kuskon-ai-deploy/blob/'
                  f'codex/hackhub-talent/demo_evidence/{filename}.md'
    for challenge_id, filename in ((1, 'attendance'), (2, 'schedule'), (3, 'signup'))
}
DEMO_DESCRIPTION = ('Синтетический пример работы: результат, воспроизводимые проверки и пояснение решений. '
                    'Материалы созданы для демонстрации продукта и не являются работой реального школьника.')
DEMO_PENDING_DESCRIPTION = ('Демонстрационная работа на проверке: скрипт сопоставляет интервалы и выводит найденные '
                            'конфликты. Приложены синтетические примеры и инструкция воспроизведения; реального автора нет.')
CRITERIA = [
    {'label': 'Работоспособность результата', 'description': '0 — результата нет; 1 — частичный результат без подтверждения; 2 — базовый сценарий воспроизводим; 3 — сценарий выполнен полностью с примерами; 4 — полный результат с проверками крайних случаев.', 'weight': 40},
    {'label': 'Обоснование решений', 'description': '0 — объяснения нет; 1 — общие слова без примеров; 2 — основные решения объяснены воспроизводимо; 3 — все решения обоснованы примерами; 4 — сравнили альтернативы и проверили ограничения.', 'weight': 35},
    {'label': 'Самостоятельность и рефлексия', 'description': '0 — вклад не описан; 1 — общие утверждения без примеров; 2 — описаны личные действия и полученная помощь; 3 — вклад и исправления показаны на примерах; 4 — выводы проверены и намечен следующий шаг. Рубрика оценивает описание вклада, а не доказывает авторство.', 'weight': 25},
]


def _text(value, label, minimum=1, maximum=6000):
    if not isinstance(value, str) or not minimum <= len(value.strip()) <= maximum:
        raise ValueError(f'{label}: от {minimum} до {maximum} символов.')
    return value.strip()


def _role(conn, profile_id, role):
    row = conn.execute('SELECT * FROM talent_people WHERE id=?', (profile_id,)).fetchone()
    if not row or row['role'] != role:
        raise ValueError('Действие недоступно для этого демопрофиля.')
    return row


def _person(row):
    item = dict(row)
    item['share_profile'] = bool(item['share_profile'])
    item['guardian_consent'] = bool(item['guardian_consent'])
    return item


def _criteria(value):
    if not isinstance(value, list) or len(value) != 3:
        raise ValueError('Нужны ровно три критерия с весами 40, 35 и 25%.')
    clean = []
    for item, weight in zip(value, WEIGHTS):
        if (not isinstance(item, dict) or set(item) != {'label', 'description', 'weight'}
                or type(item['weight']) is not int or item['weight'] != weight):
            raise ValueError('Критерии должны содержать название, рубрику и веса 40, 35 и 25%.')
        clean.append({'label': _text(item['label'], 'Название критерия', 3, 100),
                      'description': _text(item['description'], 'Рубрика критерия', 20, 1500),
                      'weight': weight})
    if len({item['label'].casefold() for item in clean}) != 3:
        raise ValueError('Названия трёх критериев должны различаться.')
    return clean


def _visible(conn, student_id):
    return bool(conn.execute('''SELECT 1 FROM talent_people p WHERE p.id=?
        AND p.role='student' AND p.share_profile=1 AND p.guardian_consent=1
        AND EXISTS (SELECT 1 FROM talent_submissions s WHERE s.student_id=p.id
                    AND s.status='approved')''', (student_id,)).fetchone())


def _total(ratings):
    """Weights and integer ratings yield exact quarter points; do not round."""
    return sum(weight * rating for weight, rating in zip(WEIGHTS, ratings)) / 4


def _migrate_demo(conn):
    if not conn.execute("SELECT 1 FROM talent_meta WHERE key='exact_scores_v1'").fetchone():
        for row in conn.execute("SELECT id,ratings FROM talent_submissions WHERE status!='pending'").fetchall():
            ratings = json.loads(row['ratings'])
            if (isinstance(ratings, list) and len(ratings) == 3
                    and all(type(rating) is int and rating in range(5) for rating in ratings)):
                # SQLite's numeric affinity also stores fractions in earlier INTEGER columns.
                conn.execute('UPDATE talent_submissions SET total=? WHERE id=?', (_total(ratings), row['id']))
        conn.execute("INSERT INTO talent_meta VALUES('exact_scores_v1','done')")
    if not conn.execute("SELECT 1 FROM talent_meta WHERE key='demo_evidence_v1'").fetchone():
        old_description = ('Синтетический пример принятой работы: результат, проверочные примеры и пояснение решений. '
                           'Ссылка-заглушка ведёт на example.com.')
        old_pending_description = ('Демонстрационная работа на проверке: скрипт сопоставляет интервалы и выводит найденные '
                                   'конфликты. Ссылка является заглушкой.')
        for challenge_id, student_id in ((1, 101), (2, 102), (3, 103), (1, 104), (2, 105)):
            old_url = f'https://example.com/demo/talent/{student_id}/{challenge_id}'
            conn.execute('''UPDATE talent_submissions SET evidence_url=?,
                description=CASE WHEN description=? THEN ? WHEN description=? THEN ? ELSE description END
                WHERE challenge_id=? AND student_id=? AND evidence_url=?''',
                (DEMO_EVIDENCE_URLS[challenge_id], old_description, DEMO_DESCRIPTION,
                 old_pending_description, DEMO_PENDING_DESCRIPTION, challenge_id, student_id, old_url))
        conn.execute("INSERT INTO talent_meta VALUES('demo_evidence_v1','done')")


def _migrate_verification(conn):
    """Add audit metadata without inventing evidence for earlier reviews."""
    columns = {row['name'] for row in conn.execute('PRAGMA table_info(talent_submissions)')}
    additions = {
        'work_revision': 'INTEGER NOT NULL DEFAULT 1',
        'source_version': "TEXT NOT NULL DEFAULT ''",
        'criterion_evidence': "TEXT NOT NULL DEFAULT '[]'",
        'reviewer_name': "TEXT NOT NULL DEFAULT ''",
        'reviewer_role': "TEXT NOT NULL DEFAULT ''",
        'reviewer_org': "TEXT NOT NULL DEFAULT ''",
        'review_limitations': "TEXT NOT NULL DEFAULT ''",
    }
    for name, definition in additions.items():
        if name not in columns:
            conn.execute(f'ALTER TABLE talent_submissions ADD COLUMN {name} {definition}')


def _baseline_history(conn):
    for row in conn.execute('''SELECT s.id FROM talent_submissions s WHERE NOT EXISTS
            (SELECT 1 FROM talent_work_history h WHERE h.submission_id=s.id)''').fetchall():
        _record_history(conn, row['id'], 'baseline_imported', None,
                        note='Снимок при подключении истории. Прошлые версии не восстановлены; '
                             'новые сведения о проверяющем и защите не добавлены задним числом.')


def init():
    """Create only additive tables and seed fictional examples once, atomically."""
    with db.connect() as conn:
        conn.executescript('''
        CREATE TABLE IF NOT EXISTS talent_people(
            id INTEGER PRIMARY KEY, role TEXT NOT NULL CHECK(role IN ('student','buyer')),
            name TEXT NOT NULL, region TEXT NOT NULL, grade INTEGER, focus TEXT NOT NULL,
            share_profile INTEGER NOT NULL DEFAULT 0 CHECK(share_profile IN (0,1)),
            guardian_consent INTEGER NOT NULL DEFAULT 0 CHECK(guardian_consent IN (0,1)));
        CREATE TABLE IF NOT EXISTS talent_challenges(
            id INTEGER PRIMARY KEY, buyer_id INTEGER NOT NULL REFERENCES talent_people(id),
            title TEXT NOT NULL, brief TEXT NOT NULL, skill TEXT NOT NULL,
            duration TEXT NOT NULL, deliverable TEXT NOT NULL, criteria TEXT NOT NULL,
            created TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS talent_submissions(
            id INTEGER PRIMARY KEY, challenge_id INTEGER NOT NULL REFERENCES talent_challenges(id),
            student_id INTEGER NOT NULL REFERENCES talent_people(id), evidence_url TEXT NOT NULL,
            description TEXT NOT NULL, reflection TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'pending' CHECK(status IN ('pending','changes_requested','approved')),
            ratings TEXT NOT NULL DEFAULT '[]', feedback TEXT NOT NULL DEFAULT '',
            total REAL NOT NULL DEFAULT 0 CHECK(total BETWEEN 0 AND 100),
            version INTEGER NOT NULL DEFAULT 1, reviewed_at TEXT,
            created TEXT NOT NULL, updated TEXT NOT NULL,
            UNIQUE(challenge_id, student_id));
        CREATE TABLE IF NOT EXISTS talent_saved(
            buyer_id INTEGER NOT NULL REFERENCES talent_people(id),
            student_id INTEGER NOT NULL REFERENCES talent_people(id), created TEXT NOT NULL,
            PRIMARY KEY(buyer_id, student_id));
        CREATE TABLE IF NOT EXISTS talent_invitations(
            id INTEGER PRIMARY KEY, buyer_id INTEGER NOT NULL REFERENCES talent_people(id),
            student_id INTEGER NOT NULL REFERENCES talent_people(id), message TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'pending'
                CHECK(status IN ('pending','accepted','declined','withdrawn')),
            created TEXT NOT NULL, responded_at TEXT);
        CREATE UNIQUE INDEX IF NOT EXISTS talent_one_active_invitation
            ON talent_invitations(buyer_id, student_id) WHERE status IN ('pending','accepted');
        CREATE TABLE IF NOT EXISTS talent_meta(key TEXT PRIMARY KEY, value TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS talent_defenses(
            id INTEGER PRIMARY KEY, submission_id INTEGER NOT NULL REFERENCES talent_submissions(id),
            work_revision INTEGER NOT NULL, version INTEGER NOT NULL DEFAULT 1,
            question TEXT NOT NULL, change_request TEXT NOT NULL,
            answer TEXT NOT NULL DEFAULT '', change_description TEXT NOT NULL DEFAULT '',
            evidence_url TEXT NOT NULL DEFAULT '', source_version TEXT NOT NULL DEFAULT '',
            status TEXT NOT NULL DEFAULT 'requested'
                CHECK(status IN ('requested','answered','confirmed','needs_clarification')),
            observations TEXT NOT NULL DEFAULT '', reviewer_name TEXT NOT NULL DEFAULT '',
            reviewer_role TEXT NOT NULL DEFAULT '', reviewer_org TEXT NOT NULL DEFAULT '',
            limitations TEXT NOT NULL DEFAULT '', created TEXT NOT NULL,
            answered_at TEXT, assessed_at TEXT);
        CREATE TABLE IF NOT EXISTS talent_work_history(
            id INTEGER PRIMARY KEY, submission_id INTEGER NOT NULL REFERENCES talent_submissions(id),
            event TEXT NOT NULL, created TEXT NOT NULL, actor_id INTEGER REFERENCES talent_people(id),
            actor_name TEXT NOT NULL, snapshot TEXT NOT NULL);
        CREATE TRIGGER IF NOT EXISTS talent_history_no_update BEFORE UPDATE ON talent_work_history
            BEGIN SELECT RAISE(ABORT, 'History snapshots are immutable'); END;
        CREATE TRIGGER IF NOT EXISTS talent_history_no_delete BEFORE DELETE ON talent_work_history
            BEGIN SELECT RAISE(ABORT, 'History snapshots are immutable'); END;
        ''')
        conn.execute('BEGIN IMMEDIATE')
        _migrate_verification(conn)
        if not conn.execute("SELECT 1 FROM talent_meta WHERE key='seed_v1'").fetchone():
            # Never replace existing imported or manually created talent data.
            if not conn.execute('SELECT 1 FROM talent_people LIMIT 1').fetchone():
                _seed(conn)
                conn.execute("INSERT INTO talent_meta VALUES('seed_v1','done')")
        _migrate_demo(conn)
        _baseline_history(conn)


def people(role):
    if role not in ('student', 'buyer'):
        raise ValueError('Неизвестная роль.')
    with db.connect() as conn:
        return [_person(row) for row in conn.execute(
            'SELECT * FROM talent_people WHERE role=? ORDER BY id', (role,))]


def person(profile_id):
    with db.connect() as conn:
        row = conn.execute('SELECT * FROM talent_people WHERE id=?', (profile_id,)).fetchone()
        if not row:
            raise ValueError('Демопрофиль не найден.')
        return _person(row)


def challenges(buyer_id=None):
    with db.connect() as conn:
        args = ()
        sql = 'SELECT * FROM talent_challenges'
        if buyer_id is not None:
            _role(conn, buyer_id, 'buyer')
            sql += ' WHERE buyer_id=?'
            args = (buyer_id,)
        result = []
        for row in conn.execute(sql + ' ORDER BY id DESC', args):
            item = dict(row)
            item['criteria'] = json.loads(item['criteria'])
            result.append(item)
        return result


def create_challenge(buyer_id, title, brief, skill, duration, deliverable, criteria):
    values = (_text(title, 'Название', 5, 140), _text(brief, 'Описание задачи', 30, 6000),
              _text(skill, 'Навык', 2, 80), _text(duration, 'Срок', 2, 100),
              _text(deliverable, 'Ожидаемый результат', 10, 2000),
              json.dumps(_criteria(criteria), ensure_ascii=False))
    with db.connect() as conn:
        _role(conn, buyer_id, 'buyer')
        return conn.execute('''INSERT INTO talent_challenges
            (buyer_id,title,brief,skill,duration,deliverable,criteria,created)
            VALUES(?,?,?,?,?,?,?,?)''', (buyer_id, *values, db.now())).lastrowid


_SUBMISSION_SELECT = '''SELECT s.*, c.title AS challenge_title, c.skill, c.criteria,
    p.name AS student_name, b.name AS buyer_name, c.buyer_id
    FROM talent_submissions s JOIN talent_challenges c ON c.id=s.challenge_id
    JOIN talent_people p ON p.id=s.student_id JOIN talent_people b ON b.id=c.buyer_id'''


def _understanding(conn, submission_id, work_revision):
    row = conn.execute('''SELECT status FROM talent_defenses
        WHERE submission_id=? AND work_revision=? ORDER BY id DESC LIMIT 1''',
        (submission_id, work_revision)).fetchone()
    return row['status'] if row else 'not_requested'


def _decode_submission(conn, row):
    item = dict(row)
    for key in ('ratings', 'criteria', 'criterion_evidence'):
        item[key] = json.loads(item[key])
    item['understanding_status'] = _understanding(conn, item['id'], item['work_revision'])
    return item


def _submission(conn, submission_id):
    row = conn.execute(_SUBMISSION_SELECT + ' WHERE s.id=?', (submission_id,)).fetchone()
    if not row:
        raise ValueError('Работа не найдена.')
    return _decode_submission(conn, row)


def _defenses(conn, submission_id):
    return [dict(row) for row in conn.execute('''SELECT * FROM talent_defenses
        WHERE submission_id=? ORDER BY id''', (submission_id,))]


def _record_history(conn, submission_id, event, actor_id, note=''):
    snapshot = _submission(conn, submission_id)
    snapshot['defense_rounds'] = _defenses(conn, submission_id)
    if note:
        snapshot['history_note'] = note
    actor = conn.execute('SELECT name FROM talent_people WHERE id=?', (actor_id,)).fetchone() if actor_id else None
    conn.execute('''INSERT INTO talent_work_history
        (submission_id,event,created,actor_id,actor_name,snapshot) VALUES(?,?,?,?,?,?)''',
        (submission_id, event, db.now(), actor_id, actor['name'] if actor else 'Импорт существующего состояния',
         json.dumps(snapshot, ensure_ascii=False)))


def _view_work(conn, submission_id, viewer_id):
    work = _submission(conn, submission_id)
    viewer = conn.execute('SELECT role FROM talent_people WHERE id=?', (viewer_id,)).fetchone()
    if not viewer:
        raise ValueError('Демопрофиль не найден.')
    if viewer['role'] == 'student' and work['student_id'] == viewer_id:
        return work
    if viewer['role'] == 'buyer' and (work['buyer_id'] == viewer_id
            or (work['status'] == 'approved' and _visible(conn, work['student_id']))):
        return work
    raise ValueError('История и защита этой работы недоступны для профиля.')


def _reviewer(name, role, limits):
    return (_text(name, 'Имя демопроверяющего', 3, 120),
            _text(role, 'Роль проверяющего', 3, 120),
            _text(limits, 'Ограничения проверки', 0, 2000))


def _submissions(conn, student_id=None, buyer_id=None, approved_only=False):
    conditions, args = [], []
    if student_id is not None:
        conditions.append('s.student_id=?')
        args.append(student_id)
    if buyer_id is not None:
        conditions.append('c.buyer_id=?')
        args.append(buyer_id)
    if approved_only:
        conditions.append("s.status='approved'")
    sql = _SUBMISSION_SELECT + (' WHERE ' + ' AND '.join(conditions) if conditions else '')
    result = []
    for row in conn.execute(sql + ' ORDER BY s.id DESC', args):
        result.append(_decode_submission(conn, row))
    return result


def submissions(student_id=None, buyer_id=None):
    """Internal demo service; caller chooses an own-profile or own-challenge scope."""
    with db.connect() as conn:
        if student_id is not None:
            _role(conn, student_id, 'student')
        if buyer_id is not None:
            _role(conn, buyer_id, 'buyer')
        return _submissions(conn, student_id, buyer_id)


def submit_work(challenge_id, student_id, evidence_url, description, reflection, source_version='', *, _conn=None):
    url = _text(evidence_url, 'Ссылка на результат', 8, 2000)
    if not db.valid_url(url):
        raise ValueError('Нужна корректная http/https-ссылка на результат.')
    description = _text(description, 'Описание результата', 20, 6000)
    reflection = _text(reflection, 'Рефлексия', 20, 4000)
    source_version = _text(source_version, 'Версия исходников', 0, 200)
    stamp = db.now()
    with (nullcontext(_conn) if _conn is not None else db.connect()) as conn:
        if _conn is None:
            conn.execute('BEGIN IMMEDIATE')
        _role(conn, student_id, 'student')
        challenge = conn.execute('SELECT * FROM talent_challenges WHERE id=?', (challenge_id,)).fetchone()
        if not challenge:
            raise ValueError('Задание не найдено.')
        if challenge['buyer_id'] == student_id:
            raise ValueError('Нельзя сдавать собственное задание.')
        existing = conn.execute('''SELECT id,status FROM talent_submissions
            WHERE challenge_id=? AND student_id=?''', (challenge_id, student_id)).fetchone()
        if existing:
            if existing['status'] != 'changes_requested':
                raise ValueError('Повторная сдача доступна только после запроса доработки.')
            conn.execute('''UPDATE talent_submissions SET evidence_url=?,description=?,reflection=?,
                status='pending',ratings='[]',feedback='',total=0,reviewed_at=NULL,
                source_version=?,criterion_evidence='[]',reviewer_name='',reviewer_role='',
                reviewer_org='',review_limitations='',work_revision=work_revision+1,
                version=version+1,updated=? WHERE id=?''',
                (url, description, reflection, source_version, stamp, existing['id']))
            _record_history(conn, existing['id'], 'resubmitted', student_id)
            return existing['id']
        submission_id = conn.execute('''INSERT INTO talent_submissions
            (challenge_id,student_id,evidence_url,description,reflection,source_version,created,updated)
            VALUES(?,?,?,?,?,?,?,?)''',
            (challenge_id, student_id, url, description, reflection, source_version, stamp, stamp)).lastrowid
        _record_history(conn, submission_id, 'submitted', student_id)
        return submission_id


def review_work(submission_id, buyer_id, expected_version, ratings, feedback, approve, *,
                criterion_evidence, reviewer_name, reviewer_role, review_limits=''):
    if (not isinstance(ratings, list) or len(ratings) != 3
            or any(type(rating) is not int or rating not in range(5) for rating in ratings)):
        raise ValueError('Оцените каждый из трёх критериев целым числом от 0 до 4.')
    if type(approve) is not bool or type(expected_version) is not int:
        raise ValueError('Некорректные параметры проверки.')
    feedback = _text(feedback, 'Обратная связь', 10, 4000)
    if not isinstance(criterion_evidence, list) or len(criterion_evidence) != 3:
        raise ValueError('Укажите наблюдаемые свидетельства по каждому из трёх критериев.')
    evidence = [_text(item, 'Свидетельство по критерию', 20, 2000) for item in criterion_evidence]
    reviewer_name, reviewer_role, review_limits = _reviewer(reviewer_name, reviewer_role, review_limits)
    total = _total(ratings)
    if approve and (total < PASS_SCORE or min(ratings) < 2):
        raise ValueError('Для зачёта нужны минимум 70 баллов и минимум 2 по каждому критерию.')
    with db.connect() as conn:
        conn.execute('BEGIN IMMEDIATE')
        buyer = _role(conn, buyer_id, 'buyer')
        row = conn.execute('''SELECT s.*, c.buyer_id FROM talent_submissions s
            JOIN talent_challenges c ON c.id=s.challenge_id WHERE s.id=?''', (submission_id,)).fetchone()
        if not row or row['buyer_id'] != buyer_id or row['student_id'] == buyer_id:
            raise ValueError('Проверять работу может только заказчик этого задания.')
        if row['version'] != expected_version:
            raise ValueError('Работа уже изменена. Обновите страницу перед проверкой.')
        if row['status'] != 'pending':
            raise ValueError('Эта версия работы уже проверена.')
        understanding = _understanding(conn, submission_id, row['work_revision'])
        if approve and understanding in ('requested', 'answered', 'needs_clarification'):
            raise ValueError('Завершите запрос защиты и оцените наблюдения до принятия результата.')
        stamp = db.now()
        conn.execute('''UPDATE talent_submissions SET status=?,ratings=?,feedback=?,total=?,
            criterion_evidence=?,reviewer_name=?,reviewer_role=?,reviewer_org=?,review_limitations=?,
            version=version+1,reviewed_at=?,updated=? WHERE id=? AND version=?''',
            ('approved' if approve else 'changes_requested', json.dumps(ratings), feedback,
             total, json.dumps(evidence, ensure_ascii=False), reviewer_name, reviewer_role, buyer['name'],
             review_limits, stamp, stamp, submission_id, expected_version))
        _record_history(conn, submission_id, 'approved' if approve else 'changes_requested', buyer_id)


def request_defense(submission_id, buyer_id, expected_version, question, change_request):
    """Request one concrete explanation and reproducible modification of this revision."""
    question = _text(question, 'Вопрос по работе', 20, 2000)
    change_request = _text(change_request, 'Небольшое проверяемое изменение', 20, 2000)
    if type(expected_version) is not int:
        raise ValueError('Некорректная версия работы.')
    with db.connect() as conn:
        conn.execute('BEGIN IMMEDIATE')
        _role(conn, buyer_id, 'buyer')
        work = _submission(conn, submission_id)
        if work['buyer_id'] != buyer_id or work['student_id'] == buyer_id:
            raise ValueError('Запрашивать защиту может только заказчик задания.')
        if work['version'] != expected_version:
            raise ValueError('Работа уже изменена. Обновите страницу.')
        if work['status'] != 'pending':
            raise ValueError('Защита запрашивается только для ожидающей проверки работы.')
        if work['understanding_status'] in ('requested', 'answered'):
            raise ValueError('Предыдущий запрос защиты ещё не завершён.')
        stamp = db.now()
        defense_id = conn.execute('''INSERT INTO talent_defenses
            (submission_id,work_revision,question,change_request,created) VALUES(?,?,?,?,?)''',
            (submission_id, work['work_revision'], question, change_request, stamp)).lastrowid
        conn.execute('UPDATE talent_submissions SET version=version+1,updated=? WHERE id=?', (stamp, submission_id))
        _record_history(conn, submission_id, 'defense_requested', buyer_id)
        return defense_id


def defense_rounds(submission_id, viewer_id):
    with db.connect() as conn:
        _view_work(conn, submission_id, viewer_id)
        return _defenses(conn, submission_id)


def _mutable_defense(conn, defense_id, expected_version):
    if type(expected_version) is not int:
        raise ValueError('Некорректная версия раунда защиты.')
    row = conn.execute('SELECT * FROM talent_defenses WHERE id=?', (defense_id,)).fetchone()
    if not row:
        raise ValueError('Запрос защиты не найден.')
    if row['version'] != expected_version:
        raise ValueError('Запрос защиты уже изменён. Обновите страницу.')
    work = _submission(conn, row['submission_id'])
    if work['status'] != 'pending' or work['work_revision'] != row['work_revision']:
        raise ValueError('Защита относится к завершённой или предыдущей версии работы.')
    return row, work


def answer_defense(defense_id, student_id, expected_version, answer, change_description,
                   evidence_url, source_version=''):
    answer = _text(answer, 'Ответ на вопрос', 20, 4000)
    change_description = _text(change_description, 'Что изменено и как проверить', 20, 4000)
    evidence_url = _text(evidence_url, 'Ссылка на изменённый результат', 8, 2000)
    if not db.valid_url(evidence_url):
        raise ValueError('Нужна корректная http/https-ссылка на результат защиты.')
    source_version = _text(source_version, 'Версия исходников защиты', 0, 200)
    with db.connect() as conn:
        conn.execute('BEGIN IMMEDIATE')
        _role(conn, student_id, 'student')
        row, work = _mutable_defense(conn, defense_id, expected_version)
        if work['student_id'] != student_id:
            raise ValueError('Ответить может только участник, отправивший работу.')
        if row['status'] != 'requested':
            raise ValueError('Ответ уже зафиксирован; нужен новый запрос для уточнения.')
        stamp = db.now()
        conn.execute('''UPDATE talent_defenses SET answer=?,change_description=?,evidence_url=?,
            source_version=?,status='answered',version=version+1,answered_at=? WHERE id=?''',
            (answer, change_description, evidence_url, source_version, stamp, defense_id))
        conn.execute('UPDATE talent_submissions SET version=version+1,updated=? WHERE id=?', (stamp, work['id']))
        _record_history(conn, work['id'], 'defense_answered', student_id)


def assess_defense(defense_id, buyer_id, expected_version, understood, observations,
                   reviewer_name, reviewer_role, limitations=''):
    if type(understood) is not bool:
        raise ValueError('Укажите решение по пониманию конкретной работы.')
    observations = _text(observations, 'Конкретные наблюдения проверяющего', 30, 4000)
    reviewer_name, reviewer_role, limitations = _reviewer(reviewer_name, reviewer_role, limitations)
    with db.connect() as conn:
        conn.execute('BEGIN IMMEDIATE')
        buyer = _role(conn, buyer_id, 'buyer')
        row, work = _mutable_defense(conn, defense_id, expected_version)
        if work['buyer_id'] != buyer_id or work['student_id'] == buyer_id:
            raise ValueError('Оценить защиту может только заказчик этого задания.')
        if row['status'] != 'answered':
            raise ValueError('Для оценки нужен ещё не оценённый ответ участника.')
        stamp = db.now()
        conn.execute('''UPDATE talent_defenses SET status=?,observations=?,reviewer_name=?,reviewer_role=?,
            reviewer_org=?,limitations=?,version=version+1,assessed_at=? WHERE id=?''',
            ('confirmed' if understood else 'needs_clarification', observations, reviewer_name,
             reviewer_role, buyer['name'], limitations, stamp, defense_id))
        conn.execute('UPDATE talent_submissions SET version=version+1,updated=? WHERE id=?', (stamp, work['id']))
        _record_history(conn, work['id'], 'defense_assessed', buyer_id)


def history(submission_id, viewer_id):
    with db.connect() as conn:
        _view_work(conn, submission_id, viewer_id)
        result = []
        for row in conn.execute('''SELECT * FROM talent_work_history
                WHERE submission_id=? ORDER BY id''', (submission_id,)):
            event = dict(row)
            event['snapshot'] = json.loads(event['snapshot'])
            result.append(event)
        return result


def set_visibility(student_id, share_profile, guardian_consent):
    if type(share_profile) is not bool or type(guardian_consent) is not bool:
        raise ValueError('Согласия должны быть явно включены или выключены.')
    with db.connect() as conn:
        conn.execute('BEGIN IMMEDIATE')
        _role(conn, student_id, 'student')
        conn.execute('''UPDATE talent_people SET share_profile=?,guardian_consent=? WHERE id=?''',
                     (int(share_profile), int(guardian_consent), student_id))
        if not (share_profile and guardian_consent):
            conn.execute('DELETE FROM talent_saved WHERE student_id=?', (student_id,))
            conn.execute('''UPDATE talent_invitations SET status='withdrawn',responded_at=?
                WHERE student_id=? AND status='pending' ''', (db.now(), student_id))


def discover(buyer_id, region='', skill=''):
    region = _text(region, 'Регион', 0, 100)
    skill = _text(skill, 'Навык', 0, 80)
    with db.connect() as conn:
        _role(conn, buyer_id, 'buyer')
        result = []
        for row in conn.execute('''SELECT p.*,
            EXISTS(SELECT 1 FROM talent_saved sv WHERE sv.buyer_id=? AND sv.student_id=p.id) AS saved
            FROM talent_people p WHERE p.role='student' AND p.share_profile=1
            AND p.guardian_consent=1 ORDER BY p.id''', (buyer_id,)):
            if region and region.casefold() not in row['region'].casefold():
                continue
            works = _submissions(conn, row['id'], approved_only=True)
            if skill:
                works = [work for work in works if skill.casefold() in work['skill'].casefold()]
            if not works:
                continue
            item = _person(row)
            item['saved'] = bool(item['saved'])
            item['works'] = works
            result.append(item)
        return result


def save_candidate(buyer_id, student_id, saved):
    if type(saved) is not bool:
        raise ValueError('Некорректное состояние списка кандидатов.')
    with db.connect() as conn:
        conn.execute('BEGIN IMMEDIATE')
        _role(conn, buyer_id, 'buyer')
        _role(conn, student_id, 'student')
        if saved:
            if not _visible(conn, student_id):
                raise ValueError('Профиль не открыт для поиска с подтверждёнными работами.')
            conn.execute('INSERT OR IGNORE INTO talent_saved VALUES(?,?,?)',
                         (buyer_id, student_id, db.now()))
        else:
            conn.execute('DELETE FROM talent_saved WHERE buyer_id=? AND student_id=?',
                         (buyer_id, student_id))


def invite(buyer_id, student_id, message):
    message = _text(message, 'Приглашение', 20, 1500)
    with db.connect() as conn:
        conn.execute('BEGIN IMMEDIATE')
        _role(conn, buyer_id, 'buyer')
        _role(conn, student_id, 'student')
        if not _visible(conn, student_id):
            raise ValueError('Приглашение доступно только для открытого профиля с подтверждённой работой.')
        if conn.execute('''SELECT 1 FROM talent_invitations WHERE buyer_id=? AND student_id=?
                AND status IN ('pending','accepted')''', (buyer_id, student_id)).fetchone():
            raise ValueError('Активное приглашение этому участнику уже существует.')
        return conn.execute('''INSERT INTO talent_invitations(buyer_id,student_id,message,created)
            VALUES(?,?,?,?)''', (buyer_id, student_id, message, db.now())).lastrowid


def invitations(student_id=None, buyer_id=None):
    with db.connect() as conn:
        conditions, args = [], []
        if student_id is not None:
            _role(conn, student_id, 'student')
            conditions.append('i.student_id=?')
            args.append(student_id)
        if buyer_id is not None:
            _role(conn, buyer_id, 'buyer')
            conditions.extend(['i.buyer_id=?', 'p.share_profile=1', 'p.guardian_consent=1',
                               "EXISTS(SELECT 1 FROM talent_submissions s WHERE s.student_id=p.id AND s.status='approved')"])
            args.append(buyer_id)
        sql = '''SELECT i.*, b.name AS buyer_name, p.name AS student_name
            FROM talent_invitations i JOIN talent_people b ON b.id=i.buyer_id
            JOIN talent_people p ON p.id=i.student_id'''
        if conditions:
            sql += ' WHERE ' + ' AND '.join(conditions)
        return [dict(row) for row in conn.execute(sql + ' ORDER BY i.id DESC', args)]


def respond_invitation(invitation_id, student_id, accept):
    if type(accept) is not bool:
        raise ValueError('Некорректный ответ на приглашение.')
    with db.connect() as conn:
        conn.execute('BEGIN IMMEDIATE')
        _role(conn, student_id, 'student')
        row = conn.execute('SELECT * FROM talent_invitations WHERE id=?', (invitation_id,)).fetchone()
        if not row or row['student_id'] != student_id:
            raise ValueError('Ответить может только приглашённый участник.')
        if row['status'] != 'pending':
            raise ValueError('Приглашение уже закрыто.')
        if not _visible(conn, student_id):
            raise ValueError('Приглашение недоступно после отзыва согласия.')
        conn.execute('UPDATE talent_invitations SET status=?,responded_at=? WHERE id=?',
                     ('accepted' if accept else 'declined', db.now(), invitation_id))


def stats():
    with db.connect() as conn:
        def count(sql):
            return conn.execute(sql).fetchone()[0]
        return {
            'students': count("SELECT COUNT(*) FROM talent_people WHERE role='student'"),
            'buyers': count("SELECT COUNT(*) FROM talent_people WHERE role='buyer'"),
            'challenges': count('SELECT COUNT(*) FROM talent_challenges'),
            'submissions': count('SELECT COUNT(*) FROM talent_submissions'),
            'approved': count("SELECT COUNT(*) FROM talent_submissions WHERE status='approved'"),
            'pending': count("SELECT COUNT(*) FROM talent_submissions WHERE status='pending'"),
            'visible_students': count('''SELECT COUNT(*) FROM talent_people p WHERE role='student'
                AND share_profile=1 AND guardian_consent=1 AND EXISTS(SELECT 1 FROM talent_submissions s
                WHERE s.student_id=p.id AND s.status='approved')'''),
        }


def _seed(conn):
    stamp = db.now()
    profiles = [
        (101, 'student', 'Айлин А. · демо', 'Актюбинская область', 10, 'Аналитика данных', 1, 1),
        (102, 'student', 'Данияр К. · демо', 'Актюбинская область', 11, 'Python и автоматизация', 1, 1),
        (103, 'student', 'Мадина С. · демо', 'Актюбинская область', 9, 'Дизайн интерфейсов', 1, 1),
        (104, 'student', 'Арман Б. · демо', 'Актюбинская область', 10, 'Аналитика данных', 0, 0),
        (105, 'student', 'София Т. · демо', 'Актюбинская область', 11, 'Python и автоматизация', 0, 0),
        (201, 'buyer', 'Qadam IT Education · демо', 'Актюбинская область', None, 'Образовательные программы', 0, 0),
        (202, 'buyer', 'Aktobe CSR Lab · демо', 'Актюбинская область', None, 'Социальные проекты и наставничество', 0, 0),
    ]
    conn.executemany('INSERT INTO talent_people VALUES(?,?,?,?,?,?,?,?)', profiles)
    sample_challenges = [
        (1, 201, 'Помоги учебному центру увидеть отток учеников',
         'По синтетической таблице посещаемости найди три причины пропусков. Представь небольшой отчёт и предложи один проверяемый способ улучшить посещаемость. Реальные данные учеников не нужны.',
         'Аналитика данных', '3–5 часов', 'Таблица расчётов, 2 графика и пояснение на одну страницу.'),
        (2, 201, 'Автоматизируй расписание демокурсов',
         'Создай небольшой Python-скрипт, который находит пересечения в синтетическом расписании курсов. Покажи работу на пяти примерах, включая отсутствие конфликтов и повторяющиеся интервалы.',
         'Python и автоматизация', '4–6 часов', 'Ссылка на репозиторий с кодом, примерами и инструкцией запуска.'),
        (3, 202, 'Спроектируй запись на волонтёрскую встречу',
         'Подготовь прототип формы записи на бесплатную встречу наставников. Продумай понятные подписи, подтверждение записи и отказ от участия. Используй вымышленные данные.',
         'Дизайн интерфейсов', '3–4 часа', 'Прототип из трёх экранов, сценарий проверки и объяснение решений.'),
    ]
    for values in sample_challenges:
        conn.execute('INSERT INTO talent_challenges VALUES(?,?,?,?,?,?,?,?,?)',
                     (*values, json.dumps(CRITERIA, ensure_ascii=False), stamp))
    samples = [
        (1, 101, [4, 3, 4], 'Проверены расчёты и графики, выводы подтверждены примерами. Следующий шаг — сравнить группы по дням недели.'),
        (2, 102, [3, 4, 3], 'Скрипт находит пересечения на пяти примерах. Автор объяснил алгоритм и ограничения проверки времени.'),
        (3, 103, [3, 3, 4], 'Основной сценарий понятен; показаны отказ, повторная запись и изменения после проверки прототипа.'),
        (1, 104, [3, 3, 3], 'Расчёты воспроизводимы, объяснение выводов достаточно для принятия демоработы.'),
    ]
    for challenge_id, student_id, ratings, feedback in samples:
        total = _total(ratings)
        conn.execute('''INSERT INTO talent_submissions(challenge_id,student_id,evidence_url,
            description,reflection,status,ratings,feedback,total,version,reviewed_at,created,updated)
            VALUES(?,?,?,?,?,'approved',?,?,?,2,?,?,?)''',
            (challenge_id, student_id, DEMO_EVIDENCE_URLS[challenge_id], DEMO_DESCRIPTION,
             'Демо-рефлексия: самостоятельно подготовил основу, проверил примеры и исправил найденные ошибки. Следующий шаг — расширить набор проверок.',
             json.dumps(ratings), feedback, total, stamp, stamp, stamp))
    conn.execute('''INSERT INTO talent_submissions(challenge_id,student_id,evidence_url,
        description,reflection,created,updated) VALUES(2,105,?,?,?,?,?)''',
        (DEMO_EVIDENCE_URLS[2], DEMO_PENDING_DESCRIPTION,
         'Самостоятельно описала алгоритм; с подсказкой исправила сравнение границ. Нужно проверить пустое расписание.', stamp, stamp))
