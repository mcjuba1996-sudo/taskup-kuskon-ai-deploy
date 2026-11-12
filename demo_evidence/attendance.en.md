# Attendance analysis: a synthetic example

**Demo artifact prepared by the Kuskon AI team with help from Codex.** This is shared test material for several fictional profiles, not the work of an individual teenager. The data, reasons and ratings in the app were invented to test the workflow.

**Task:** calculate attendance reproducibly, show three participant-reported reasons for absences and propose a testable improvement. The source is `attendance.csv`; the calculation is in `analyze_attendance.py`, using only the Python 3.11+ standard library.

```bash
python demo_evidence/analyze_attendance.py
```

## Result

6 fictional participants × 4 sessions = **24 attendance events**. There were **17 attendances** and **7 absences**. Attendance rate: `17 / 24 × 100 = 70.83%`. The unit of analysis is an attendance event, not the number of unique children.

**Chart 1. Attendance by session.** Each `#` represents one attendance; 6 participants were expected at every session. Numeric formatting in the source charts is preserved.

```text
DEMO-01  #####  5/6  83,33%
DEMO-02  ####   4/6  66,67%
DEMO-03  #####  5/6  83,33%
DEMO-04  ###    3/6  50,00%
```

**Chart 2. Reported reasons for absences.** Each `#` represents one absence; percentages use the 7 absences as the denominator, not all 24 events. Source data labels are preserved: «Самочувствие» means feeling unwell, «Транспорт» means transport, and «Другое занятие» means another class.

```text
Самочувствие      ###  3/7  42,86%
Транспорт         ##   2/7  28,57%
Другое занятие    ##   2/7  28,57%
```

These are **self-reports in a synthetic table**, not proven causes of dropout. Four sessions cannot establish that participants left permanently or that changing the time would improve attendance. Repeated events for the same participant are not independent observations.

## Proposal and evaluation

Hypothesis: an alternative session time would reduce absences due to timetable conflicts. In a future agreed pilot, offer two time slots, define the observation period in advance, and compare attendance rates and the reported reason “another class”. Record actual slot choices and the limitations of the comparison; do not claim a causal effect without random assignment. No real experiment has taken place, and no improvement has been measured.

## Self-checks and limitations

The script checks headers, missing fields, duplicate participant/session pairs, permitted statuses and consistency between the reason and status. An empty CSV is rejected. Running the script reproduces the report totals; no data is downloaded. If there are no absences, the reason percentages are zero. There is no statistical estimate of an effect and no real personal data.
