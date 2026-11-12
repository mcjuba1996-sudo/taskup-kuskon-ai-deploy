"""Синтетический пример TaskUp Talent, подготовлен командой с Codex."""
import csv
from collections import Counter, defaultdict
from pathlib import Path

REASONS = {"illness": "Самоотчёт: самочувствие",
           "transport": "Самоотчёт: транспорт",
           "timetable": "Самоотчёт: другое занятие"}
FIELDS = {"session_id", "participant_id", "status", "self_reported_reason"}


def analyze(path):
    """Считать события посещения, не делать причинных выводов."""
    sessions = defaultdict(Counter)
    reasons, participants, seen = Counter(), set(), set()
    with Path(path).open(encoding="utf-8", newline="") as source:
        reader = csv.DictReader(source)
        if set(reader.fieldnames or []) != FIELDS:
            raise ValueError("Неверные столбцы CSV")
        for line, row in enumerate(reader, start=2):
            if None in row or any(value is None for value in row.values()):
                raise ValueError(f"Строка {line}: неверное число полей")
            row = {key: value.strip() for key, value in row.items()}
            session, participant = row["session_id"], row["participant_id"]
            status, reason = row["status"], row["self_reported_reason"]
            if not session or not participant or (session, participant) in seen:
                raise ValueError(f"Строка {line}: пустой или повторный идентификатор")
            if status not in {"present", "absent"}:
                raise ValueError(f"Строка {line}: неизвестный статус")
            if (status == "present" and reason) or (status == "absent" and reason not in REASONS):
                raise ValueError(f"Строка {line}: причина не соответствует статусу")
            seen.add((session, participant))
            participants.add(participant)
            sessions[session][status] += 1
            if reason:
                reasons[reason] += 1
    if not seen:
        raise ValueError("Нет наблюдений для расчёта")
    present = sum(counts["present"] for counts in sessions.values())
    return {"observations": len(seen), "participants": len(participants),
            "present": present, "absent": len(seen) - present,
            "attendance_pct": 100 * present / len(seen),
            "sessions": dict(sessions), "reasons": dict(reasons)}


def report(data):
    lines = ["СИНТЕТИЧЕСКИЕ ДАННЫЕ · TaskUp Talent / Codex",
             f"Участников: {data['participants']}; событий посещения: {data['observations']}",
             f"Присутствия: {data['present']}; пропуски: {data['absent']}",
             f"Посещаемость: {data['attendance_pct']:.2f}%",
             "\nГрафик 1. Присутствия по занятиям (# = одно присутствие):"]
    for session, counts in sorted(data["sessions"].items()):
        total = sum(counts.values())
        lines.append(f"{session}: {'#' * counts['present']} {counts['present']}/{total} "
                     f"({100 * counts['present'] / total:.2f}%)")
    lines.append("\nГрафик 2. Указанные причины (# = один пропуск):")
    for key, label in REASONS.items():
        count = data["reasons"].get(key, 0)
        share = 100 * count / data["absent"] if data["absent"] else 0
        lines.append(f"{label}: {'#' * count} {count} ({share:.2f}% пропусков)")
    lines.append("Самоотчёты не доказывают причины оттока. Повторные события не независимы.")
    return "\n".join(lines)


if __name__ == "__main__":
    print(report(analyze(Path(__file__).with_name("attendance.csv"))))
