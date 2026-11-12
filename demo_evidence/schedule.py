"""Демо TaskUp Talent / Codex: конфликты интервалов внутри одного дня."""
import re
import unittest


def minutes(value):
    if not isinstance(value, str) or not re.fullmatch(r"\d{2}:\d{2}", value):
        raise ValueError("Время должно иметь формат HH:MM")
    hour, minute = map(int, value.split(":"))
    if not 0 <= hour <= 23 or not 0 <= minute <= 59:
        raise ValueError("Время вне диапазона 00:00–23:59")
    return hour * 60 + minute


def find_conflicts(schedule):
    """[(имя, начало, конец), ...] -> пары конфликтов; интервалы [начало, конец)."""
    if not isinstance(schedule, (list, tuple)):
        raise ValueError("Расписание должно быть списком или кортежем")
    events, names = [], set()
    for item in schedule:
        if not isinstance(item, (list, tuple)) or len(item) != 3:
            raise ValueError("Занятие: имя, начало, конец")
        name, start, end = item
        if not isinstance(name, str) or not name.strip() or name in names:
            raise ValueError("Имена должны быть непустыми и уникальными")
        start, end = minutes(start), minutes(end)
        if start >= end:
            raise ValueError("Начало должно быть раньше конца; переход суток не поддерживается")
        names.add(name)
        events.append((name, start, end))
    return [(left[0], right[0])
            for i, left in enumerate(events) for right in events[i + 1:]
            if max(left[1], right[1]) < min(left[2], right[2])]


class ScheduleChecks(unittest.TestCase):
    def test_overlap(self):
        self.assertEqual(find_conflicts([("A", "09:00", "10:00"),
                                         ("B", "09:30", "10:30")]), [("A", "B")])

    def test_touching_boundaries_do_not_conflict(self):
        self.assertEqual(find_conflicts([("A", "09:00", "10:00"),
                                         ("B", "10:00", "11:00")]), [])

    def test_disjoint_unsorted(self):
        self.assertEqual(find_conflicts([("B", "12:00", "13:00"),
                                         ("A", "09:00", "10:00")]), [])

    def test_repeated_interval_different_events(self):
        self.assertEqual(find_conflicts([("A", "09:00", "10:00"),
                                         ("B", "09:00", "10:00")]), [("A", "B")])

    def test_nested(self):
        self.assertEqual(find_conflicts([("A", "09:00", "12:00"),
                                         ("B", "10:00", "11:00")]), [("A", "B")])

    def test_all_pairs_reported(self):
        self.assertEqual(find_conflicts([("A", "09:00", "12:00"),
            ("B", "10:00", "11:00"), ("C", "10:30", "11:30")]),
            [("A", "B"), ("A", "C"), ("B", "C")])

    def test_empty_and_single(self):
        self.assertEqual(find_conflicts([]), [])
        self.assertEqual(find_conflicts([("A", "09:00", "10:00")]), [])

    def test_invalid_time_and_duration(self):
        for start, end in [("9:00", "10:00"), ("24:00", "25:00"),
                           ("09:60", "11:00"), ("10:00", "10:00"), ("23:00", "01:00")]:
            with self.subTest(start=start, end=end), self.assertRaises(ValueError):
                find_conflicts([("A", start, end)])

    def test_duplicate_id_and_malformed(self):
        for value in [None, "", [("A",)], [("", "09:00", "10:00")],
                      [("A", "09:00", "10:00"), ("A", "11:00", "12:00")]]:
            with self.subTest(value=value), self.assertRaises(ValueError):
                find_conflicts(value)


if __name__ == "__main__":
    unittest.main(verbosity=2)
