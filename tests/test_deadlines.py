"""Tests for app/deadlines.py. Each test shows the hand calculation so a
lawyer can check it. Weekdays are stated where they matter."""

import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.deadlines import (DeadlineSpec, compute_deadline, court_holiday_periods,
                           effective_receipt, is_working_day, zurich_public_holidays)


def spec(n, unit="days", direction="forward", t1=None, t2=None, shift=True, court=False):
    return DeadlineSpec(n, unit, direction, t1, t2, shift, court)


def test_holidays_2026():
    # Easter Sunday 2026 = 5 April.
    # Good Friday = 5 Apr - 2 = 3 Apr; Easter Monday = 6 Apr;
    # Ascension = Easter + 39 = 14 May; Whit Monday = Easter + 50 = 25 May.
    h = zurich_public_holidays(2026)
    assert {d for d, n in h.items() if n in ("Good Friday", "Easter Monday", "Ascension Day", "Whit Monday")} == {
        date(2026, 4, 3), date(2026, 4, 6), date(2026, 5, 14), date(2026, 5, 25)}
    assert len(h) == 9
    assert date(2026, 1, 2) not in h  # Berchtoldstag is not statutory in Zurich


def test_holidays_2027():
    # Easter Sunday 2027 = 28 March.
    # Good Friday = 26 Mar; Easter Monday = 29 Mar; Ascension = 28 Mar + 39 = 6 May;
    # Whit Monday = 28 Mar + 50 = 17 May.
    h = zurich_public_holidays(2027)
    assert date(2027, 3, 26) in h and date(2027, 3, 29) in h
    assert date(2027, 5, 6) in h and date(2027, 5, 17) in h


def test_working_day():
    assert not is_working_day(date(2026, 10, 3))  # Saturday
    assert not is_working_day(date(2026, 4, 6))   # Easter Monday (a Monday)
    assert is_working_day(date(2026, 4, 7))       # ordinary Tuesday


def test_court_holiday_periods_2026():
    # Easter 5 Apr 2026: 7 days before = 29 Mar, 7 days after = 12 Apr.
    p = court_holiday_periods(2026)
    assert (date(2026, 3, 29), date(2026, 4, 12)) == p[0][:2]
    assert (date(2026, 7, 15), date(2026, 8, 15)) == p[1][:2]
    assert (date(2026, 12, 18), date(2027, 1, 2)) == p[2][:2]


def test_day_based_weekend_shift():
    # Receipt Thu 3 Sep 2026. Day 1 = 4 Sep. 3 Sep + 30 days = 3 Oct 2026 = Saturday.
    # Saturday is not a working day -> next working day = Monday 5 Oct.
    r = compute_deadline(spec(30, t1=date(2026, 9, 3), t2=date(2026, 9, 3)))
    assert r["earliest"] == r["latest"] == date(2026, 10, 5)
    assert r["determinable"] and not r["precautionary"]
    # Without the shift, the plain end date stays 3 Oct.
    r = compute_deadline(spec(30, t1=date(2026, 9, 3), shift=False))
    assert r["earliest"] == date(2026, 10, 3)


def test_month_based_end_of_month():
    # 31 Jan 2027 + 1 month: 31 Feb does not exist -> last day of Feb = 28 Feb 2027 (Sunday).
    r = compute_deadline(spec(1, "months", t1=date(2027, 1, 31), shift=False))
    assert r["earliest"] == date(2027, 2, 28)
    # With final-day shift: Sunday -> Monday 1 Mar 2027.
    r = compute_deadline(spec(1, "months", t1=date(2027, 1, 31), shift=True))
    assert r["earliest"] == date(2027, 3, 1)


def test_court_holidays_30_days_across_christmas():
    # Receipt Thu 10 Dec 2026. Days 1-7 = 11..17 Dec. 18 Dec - 2 Jan is suspended.
    # Counting resumes 3 Jan 2027 = day 8; day 30 = 3 Jan + 22 = 25 Jan 2027 (Monday).
    r = compute_deadline(spec(30, t1=date(2026, 12, 10), court=True))
    assert r["earliest"] == date(2027, 1, 25)
    # Without suspension: 10 Dec + 30 = 9 Jan 2027 (Saturday) -> Monday 11 Jan.
    r = compute_deadline(spec(30, t1=date(2026, 12, 10), court=False))
    assert r["earliest"] == date(2027, 1, 11)


def test_court_holidays_start_inside_suspension():
    # Receipt Mon 21 Dec 2026 (inside suspension). Counting starts 3 Jan 2027 (day 1).
    # Day 10 = 12 Jan 2027 (Tuesday).
    r = compute_deadline(spec(10, t1=date(2026, 12, 21), court=True))
    assert r["earliest"] == date(2027, 1, 12)


def test_court_holidays_month_based():
    # Trigger 10 Dec 2026, +1 month = 10 Jan 2027. Suspended days in between:
    # 18-31 Dec (14) + 1-2 Jan (2) = 16. 10 Jan + 16 = 26 Jan 2027 (Tuesday); no more suspended days.
    r = compute_deadline(spec(1, "months", t1=date(2026, 12, 10), court=True))
    assert r["earliest"] == date(2027, 1, 26)


def test_receipt_absolute_with_slip():
    # Slip left 10 Nov 2026 -> collection possible 11 Nov. NOT 7 days later.
    e, l, text = effective_receipt("absolute", notice_slip_date=date(2026, 11, 10))
    assert e == l == date(2026, 11, 11) and text
    # Collected 14 Nov after a slip of 10 Nov: still 11 Nov.
    e, l, _ = effective_receipt("absolute", notice_slip_date=date(2026, 11, 10), collected_on=date(2026, 11, 14))
    assert e == l == date(2026, 11, 11)
    # Handed over in person.
    e, l, _ = effective_receipt("absolute", handed_over=date(2026, 11, 3))
    assert e == l == date(2026, 11, 3)


def test_receipt_relative_7day():
    # Slip 10 Nov, collection unknown: earliest 10 Nov, latest 10 Nov + 7 = 17 Nov.
    e, l, _ = effective_receipt("relative_7day", notice_slip_date=date(2026, 11, 10))
    assert (e, l) == (date(2026, 11, 10), date(2026, 11, 17))
    # Collected 13 Nov (within 7 days): 13 Nov.
    e, l, _ = effective_receipt("relative_7day", notice_slip_date=date(2026, 11, 10), collected_on=date(2026, 11, 13))
    assert e == l == date(2026, 11, 13)
    # Collected 25 Nov (after the period): 17 Nov.
    e, l, _ = effective_receipt("relative_7day", notice_slip_date=date(2026, 11, 10), collected_on=date(2026, 11, 25))
    assert e == l == date(2026, 11, 17)
    # Nothing known.
    e, l, text = effective_receipt("relative_7day")
    assert e is None and l is None and text


def test_range_trigger_is_precautionary():
    # Receipt between Tue 10 Nov and Tue 17 Nov 2026, 30 days, shift on.
    # 10 Nov + 30 = 10 Dec (Thu). 17 Nov + 30 = 17 Dec (Thu).
    r = compute_deadline(spec(30, t1=date(2026, 11, 10), t2=date(2026, 11, 17)))
    assert (r["earliest"], r["latest"]) == (date(2026, 12, 10), date(2026, 12, 17))
    assert r["precautionary"] and r["determinable"]


def test_backward_notice_period():
    # Reference (permitted termination date) Sat 1 Aug 2026; 3 months back = 1 May 2026,
    # a Friday and a public holiday. Never moved forward (would shorten notice); instead the
    # last working day before it is shown: Thu 30 Apr 2026.
    r = compute_deadline(spec(3, "months", "backward", t1=date(2026, 8, 1)))
    assert r["earliest"] == date(2026, 4, 30)
    assert any("last working day before" in s and "NOT moved" in s for s in r["steps"])
    # Days: 30 days before Wed 30 Sep 2026 = 31 Aug 2026 (Monday, working day), no warning.
    r = compute_deadline(spec(30, "days", "backward", t1=date(2026, 9, 30)))
    assert r["earliest"] == date(2026, 8, 31)
    assert not any("NOT moved" in s for s in r["steps"])


def test_undeterminable():
    r = compute_deadline(spec(30))
    assert r["determinable"] is False
    assert r["earliest"] is None and r["latest"] is None
    assert r["steps"]
