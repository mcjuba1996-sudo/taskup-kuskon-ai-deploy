"""Demo schools, organizers and guardians; no production identity verification.

Actors live outside talent_people and cannot obtain its buyer/student roles.
Source records are supplemental statements, never automatic talent scores.
"""
import json

import database as db
import talent_store as talent


KINDS = ('school', 'organizer', 'parent')
DEMO_NOTICE = ('Демонстрационная запись вымышленного источника. Личность организации, '
               'подлинность документа и результат внешней проверки в реальном мире не подтверждены.')


def _id(value):
    if type(value) is not int or value < 1:
        raise ValueError('Некорректный идентификатор демопрофиля.')
    return value


def _actor(conn, actor_id, kinds=KINDS):
    row = conn.execute('SELECT * FROM talent_network_actors WHERE id=?', (_id(actor_id),)).fetchone()
    if not row or row['kind'] not in kinds:
        raise ValueError('Действие недоступно для этого демопрофиля.')
    return dict(row)


def _student(conn, student_id):
    return talent._role(conn, _id(student_id), 'student')


def _source_student(conn, source_id, student_id):
    _actor(conn, source_id, ('school', 'organizer'))
    student = _student(conn, student_id)
    if not conn.execute('SELECT 1 FROM talent_source_roster WHERE source_id=? AND student_id=?',
                        (source_id, student_id)).fetchone():
        raise ValueError('Источник может работать только со своим демонстрационным списком участников.')
    return student


def _child(conn, parent_id, student_id):
    _actor(conn, parent_id, ('parent',))
    row = _student(conn, student_id)
    if not conn.execute('SELECT 1 FROM talent_guardian_links WHERE parent_id=? AND student_id=?',
                        (parent_id, student_id)).fetchone():
        raise ValueError('Родителю доступен только связанный с ним демопрофиль ребёнка.')
    return _child_summary(row)


def _child_summary(row):
    child = {key: row[key] for key in ('id', 'name', 'grade', 'region', 'focus')}
    child.update(share_profile=bool(row['share_profile']), guardian_consent=bool(row['guardian_consent']))
    return child


def _new_actor(conn, preferred, kind, name):
    used = {r['id'] for r in conn.execute('SELECT id FROM talent_network_actors')}
    used.update(r['id'] for r in conn.execute('SELECT id FROM talent_people'))
    actor_id = preferred if preferred not in used else max(used | {preferred}) + 1
    conn.execute('INSERT INTO talent_network_actors VALUES(?,?,?)', (actor_id, kind, name))
    return actor_id


def init_network():
    """Call after talent.init(); additive, idempotent and collision-safe demo seed."""
    pupil_id = talent.ecosystem_demo_ids()['student']
    with db.connect() as conn:
        conn.executescript('''
        CREATE TABLE IF NOT EXISTS talent_network_actors(
            id INTEGER PRIMARY KEY, kind TEXT NOT NULL CHECK(kind IN ('school','organizer','parent')),
            name TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS talent_source_roster(
            source_id INTEGER NOT NULL REFERENCES talent_network_actors(id),
            student_id INTEGER NOT NULL REFERENCES talent_people(id),
            PRIMARY KEY(source_id,student_id));
        CREATE TABLE IF NOT EXISTS talent_guardian_links(
            parent_id INTEGER NOT NULL REFERENCES talent_network_actors(id),
            student_id INTEGER NOT NULL UNIQUE REFERENCES talent_people(id),
            PRIMARY KEY(parent_id,student_id));
        CREATE TABLE IF NOT EXISTS talent_source_records(
            id INTEGER PRIMARY KEY, source_id INTEGER NOT NULL REFERENCES talent_network_actors(id),
            student_id INTEGER NOT NULL REFERENCES talent_people(id),
            title TEXT NOT NULL,event TEXT NOT NULL,result TEXT NOT NULL,evidence_url TEXT NOT NULL,
            check_method TEXT NOT NULL,limitations TEXT NOT NULL DEFAULT '',
            status TEXT NOT NULL DEFAULT 'offered' CHECK(status IN ('offered','accepted','declined','revoked')),
            issued_at TEXT NOT NULL, responded_at TEXT, revoked_at TEXT,
            revocation_reason TEXT NOT NULL DEFAULT '');
        CREATE TABLE IF NOT EXISTS talent_network_meta(key TEXT PRIMARY KEY,value TEXT NOT NULL);
        ''')
        conn.execute('BEGIN IMMEDIATE')
        if conn.execute("SELECT 1 FROM talent_network_meta WHERE key='demo_network_v1'").fetchone():
            return
        _student(conn, pupil_id)
        school = _new_actor(conn, 301, 'school', 'Школа «Өркен» · демо')
        organizer = _new_actor(conn, 302, 'organizer', 'Региональный IT-конкурс · демо')
        parent = _new_actor(conn, 401, 'parent', f'Родитель участника A-{pupil_id} · демо')
        for source_id, student_ids in ((school, (101, pupil_id)), (organizer, (102, 105))):
            for student_id in set(student_ids):
                row = conn.execute("SELECT 1 FROM talent_people WHERE id=? AND role='student'", (student_id,)).fetchone()
                if row:
                    conn.execute('INSERT INTO talent_source_roster VALUES(?,?)', (source_id, student_id))
        conn.execute('INSERT INTO talent_guardian_links VALUES(?,?)', (parent, pupil_id))
        for source_id, student_id, challenge_id, title in (
                (school, 101, 1, 'Учебный анализ данных · демонстрация'),
                (organizer, 102, 2, 'Участие в IT-конкурсе · демонстрация')):
            if conn.execute('SELECT 1 FROM talent_source_roster WHERE source_id=? AND student_id=?',
                            (source_id, student_id)).fetchone():
                conn.execute('''INSERT INTO talent_source_records
                    (source_id,student_id,title,event,result,evidence_url,check_method,limitations,issued_at)
                    VALUES(?,?,?,?,?,?,?,?,?)''',
                    (source_id, student_id, title, 'Вымышленное учебное событие TaskUp Talent',
                     'Предложение тестовой записи для демонстрации принятия школьником.',
                     talent.DEMO_EVIDENCE_URLS[challenge_id],
                     'Демо: источник ссылается на общий синтетический артефакт команды, не на реальную проверку.',
                     DEMO_NOTICE, db.now()))
        mapping = {'school': school, 'organizer': organizer, 'parent': parent, 'student': pupil_id}
        conn.execute('INSERT INTO talent_network_meta VALUES(?,?)', ('demo_network_v1', json.dumps(mapping)))


def demo_ids():
    with db.connect() as conn:
        row = conn.execute("SELECT value FROM talent_network_meta WHERE key='demo_network_v1'").fetchone()
        if not row:
            raise ValueError('Демонстрационные роли ещё не инициализированы.')
        return json.loads(row['value'])


def people(kind):
    if kind not in KINDS:
        raise ValueError('Неизвестный тип участника.')
    with db.connect() as conn:
        return [dict(row) for row in conn.execute('SELECT * FROM talent_network_actors WHERE kind=? ORDER BY id', (kind,))]


def person(actor_id):
    with db.connect() as conn:
        return _actor(conn, actor_id)


def has_guardian(student_id):
    with db.connect() as conn:
        _student(conn, student_id)
        if not conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='talent_guardian_links'").fetchone():
            return False
        return bool(conn.execute('SELECT 1 FROM talent_guardian_links WHERE student_id=?', (student_id,)).fetchone())


def source_students(source_id):
    with db.connect() as conn:
        _actor(conn, source_id, ('school', 'organizer'))
        return [dict(row) for row in conn.execute('''SELECT p.id,p.name,p.grade,p.region,p.focus
            FROM talent_people p JOIN talent_source_roster r ON r.student_id=p.id
            WHERE r.source_id=? AND p.role='student' ORDER BY p.id''', (source_id,))]


_RECORDS = '''SELECT r.*,a.name AS issuer_name,a.kind AS issuer_kind,p.name AS student_name
    FROM talent_source_records r JOIN talent_network_actors a ON a.id=r.source_id
    JOIN talent_people p ON p.id=r.student_id'''


def _records(conn, condition, args):
    return [{**dict(row), 'demo_notice': DEMO_NOTICE}
            for row in conn.execute(_RECORDS + ' WHERE ' + condition + ' ORDER BY r.id DESC', args)]


def issue_record(source_id, student_id, title, event, result, evidence_url, check_method, limitations=''):
    values = (talent._text(title, 'Название записи', 3, 140),
              talent._text(event, 'Событие', 3, 200), talent._text(result, 'Результат', 3, 2000),
              talent._text(evidence_url, 'Ссылка на основание', 8, 2000),
              talent._text(check_method, 'Способ проверки источником', 20, 2000),
              talent._text(limitations, 'Ограничения', 0, 2000))
    if not db.valid_url(values[3]):
        raise ValueError('Нужна корректная http/https-ссылка на основание записи.')
    with db.connect() as conn:
        conn.execute('BEGIN IMMEDIATE')
        _source_student(conn, source_id, student_id)
        return conn.execute('''INSERT INTO talent_source_records
            (source_id,student_id,title,event,result,evidence_url,check_method,limitations,issued_at)
            VALUES(?,?,?,?,?,?,?,?,?)''', (source_id, student_id, *values, db.now())).lastrowid


def source_records(source_id):
    with db.connect() as conn:
        _actor(conn, source_id, ('school', 'organizer'))
        return _records(conn, 'r.source_id=?', (source_id,))


def student_records(student_id):
    with db.connect() as conn:
        _student(conn, student_id)
        return _records(conn, 'r.student_id=?', (student_id,))


def respond_record(record_id, student_id, accept):
    if type(accept) is not bool:
        raise ValueError('Примите или отклоните предложенную запись явно.')
    with db.connect() as conn:
        conn.execute('BEGIN IMMEDIATE')
        _student(conn, student_id)
        record = conn.execute('SELECT * FROM talent_source_records WHERE id=?', (_id(record_id),)).fetchone()
        if not record or record['student_id'] != student_id:
            raise ValueError('Ответить на запись может только её получатель.')
        if record['status'] != 'offered':
            raise ValueError('Запись уже обработана или отозвана; обновите страницу.')
        conn.execute('UPDATE talent_source_records SET status=?,responded_at=? WHERE id=?',
                     ('accepted' if accept else 'declined', db.now(), record_id))


def revoke_record(record_id, source_id, reason):
    reason = talent._text(reason, 'Причина отзыва', 10, 2000)
    with db.connect() as conn:
        conn.execute('BEGIN IMMEDIATE')
        _actor(conn, source_id, ('school', 'organizer'))
        record = conn.execute('SELECT * FROM talent_source_records WHERE id=?', (_id(record_id),)).fetchone()
        if not record or record['source_id'] != source_id:
            raise ValueError('Отозвать запись может только выдавший её источник.')
        if record['status'] not in ('offered', 'accepted'):
            raise ValueError('Эта запись уже отклонена или отозвана.')
        conn.execute("UPDATE talent_source_records SET status='revoked',revoked_at=?,revocation_reason=? WHERE id=?",
                     (db.now(), reason, record_id))


def public_records(buyer_id, student_id):
    with db.connect() as conn:
        talent._role(conn, _id(buyer_id), 'buyer')
        _student(conn, student_id)
        if not talent._visible(conn, student_id):
            return []
        return _records(conn, "r.student_id=? AND r.status='accepted'", (student_id,))


def guardian_children(parent_id):
    with db.connect() as conn:
        _actor(conn, parent_id, ('parent',))
        return [_child_summary(row) for row in conn.execute('''SELECT p.* FROM talent_people p
            JOIN talent_guardian_links g ON g.student_id=p.id
            WHERE g.parent_id=? AND p.role='student' ORDER BY p.id''', (parent_id,))]


def guardian_overview(parent_id, student_id):
    with db.connect() as conn:
        child = _child(conn, parent_id, student_id)
        works = []
        for row in conn.execute('''SELECT s.id,s.status,s.total,s.feedback,c.title FROM talent_submissions s
                JOIN talent_challenges c ON c.id=s.challenge_id WHERE s.student_id=? ORDER BY s.id DESC''', (student_id,)):
            works.append({'id': row['id'], 'title': row['title'], 'status': row['status'],
                          'score': row['total'] if row['status'] == 'approved' else None,
                          'feedback': row['feedback'] if row['status'] == 'approved' else ''})
        invitations = [dict(row) for row in conn.execute('''SELECT i.id,p.name AS buyer_name,i.message,
            i.status,i.created,i.responded_at FROM talent_invitations i
            JOIN talent_people p ON p.id=i.buyer_id WHERE i.student_id=? ORDER BY i.id DESC''', (student_id,))]
        return {'child': child, 'works': works, 'invitations': invitations}


def set_guardian_consent(parent_id, student_id, granted):
    if type(granted) is not bool:
        raise ValueError('Согласие законного представителя должно быть явно включено или выключено.')
    with db.connect() as conn:
        conn.execute('BEGIN IMMEDIATE')
        _child(conn, parent_id, student_id)
        conn.execute('UPDATE talent_people SET guardian_consent=? WHERE id=?', (int(granted), student_id))
        if not granted:
            conn.execute('DELETE FROM talent_saved WHERE student_id=?', (student_id,))
            conn.execute('''UPDATE talent_invitations SET status='withdrawn',responded_at=?
                WHERE student_id=? AND status='pending' ''', (db.now(), student_id))
