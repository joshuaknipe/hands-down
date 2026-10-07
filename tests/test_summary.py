from datetime import date

from handsdown.summary import format_duration, recent_days, summarise

RECORDS = [
    {"time": "2026-10-06T09:15:00", "kind": "episode", "duration_s": 4.0, "alerted": True, "ended": "released"},
    {"time": "2026-10-07T09:10:00", "kind": "alert", "reminder": False},
    {"time": "2026-10-07T09:10:03", "kind": "alert", "reminder": True},
    {"time": "2026-10-07T09:10:05", "kind": "episode", "duration_s": 5.5, "alerted": True, "ended": "released"},
    {"time": "2026-10-07T14:02:00", "kind": "episode", "duration_s": 2.0, "alerted": True, "ended": "interrupted"},
    {"time": "2026-10-07T14:03:00", "kind": "false_alert", "alert_time": "2026-10-07T14:01:58"},
    {"time": "2026-10-07T14:05:00", "kind": "state", "state": "watching"},
    {"time": "not a time", "kind": "episode", "duration_s": 1.0},
    {"kind": "episode"},
]


def test_summarise_counts_each_day():
    days = summarise(RECORDS)
    today = days[date(2026, 10, 7)]
    assert today.episodes == 2 and today.total_s == 7.5
    assert today.repeats == 1 and today.false_marks == 1
    assert today.by_hour[9] == 1 and today.by_hour[14] == 1 and sum(today.by_hour) == 2
    assert days[date(2026, 10, 6)].episodes == 1


def test_damaged_records_are_skipped():
    assert set(summarise(RECORDS)) == {date(2026, 10, 6), date(2026, 10, 7)}


def test_recent_days_fill_quiet_days_newest_first():
    days = recent_days(summarise(RECORDS), date(2026, 10, 7), count=3)
    assert [d.day for d in days] == [date(2026, 10, 7), date(2026, 10, 6), date(2026, 10, 5)]
    assert days[2].episodes == 0


def test_durations_read_naturally():
    assert format_duration(0) == "0 s"
    assert format_duration(45.4) == "45 s"
    assert format_duration(185) == "3 min"
    assert format_duration(3900) == "1 h 5 min"
