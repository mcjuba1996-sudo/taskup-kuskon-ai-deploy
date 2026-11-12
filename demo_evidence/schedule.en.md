# Finding timetable conflicts

**Synthetic Kuskon AI demo artifact prepared with Codex.** It is used as a shared example in fictional profiles. It is not an original work by a real school student or proof of their skills.

**Task:** find every pair of overlapping classes in a single-day timetable. The code is in `schedule.py`; no external libraries or network access are required.

```bash
python demo_evidence/schedule.py
```

The command runs **9 tests**, including several checks for invalid input. To use the function (the original example labels are preserved):

```python
from demo_evidence.schedule import find_conflicts

print(find_conflicts([
    ("Python", "09:00", "10:00"),
    ("Дизайн", "09:30", "10:30"),
    ("Математика", "10:30", "11:30"),
]))
# [('Python', 'Дизайн')]
```

## Solution

Times in `HH:MM` format are converted into minutes from the start of the day. Each pair is checked using `max(starts) < min(ends)`. Intervals are **half-open**: `[start, end)`. A class ending at 10:00 therefore does not conflict with one starting exactly at 10:00. Nested and identical intervals belonging to different classes do conflict.

| Check | Expected result |
|---|---|
| 09:00–10:00 and 09:30–10:30 | One conflicting pair |
| 09:00–10:00 and 10:00–11:00 | No conflicts |
| Non-overlapping classes in reverse order | No conflicts |
| Two classes with identical times and different names | One conflicting pair |
| One class entirely inside another | One conflicting pair |
| Three mutually overlapping classes | All three pairs |
| Empty timetable or a single class | Empty list |
| Invalid format, nonexistent time, zero duration or crossing midnight | `ValueError` |
| Duplicate name, empty name or invalid input structure | `ValueError` |

## Limitations and reflection

The algorithm performs up to `n × (n − 1) / 2` comparisons: `O(n²)` time and up to `O(n²)` memory for results. This is an understandable solution for a small learning timetable. Class names must be unique; permitted times run from 00:00 to 23:59, with the start before the end. Dates, time zones, midnight crossings, classrooms and teachers are not modelled: all classes are treated as resources for one group. The next step is to add explicit resources and tests for multiple days.

The checks are automated, not user research. The app may show different synthetic ratings for the same shared artifact: they demonstrate the work passport mechanism, not real student results.
