"""Deterministic conversion of a client's verbatim "when" wording into a conservative date range.

Never guesses an exact date from vague words: only explicit dates and today/yesterday are "exact".
Everything relative ("last week", "three weeks ago") becomes an "estimate" range, and anything
unrecognised is "unknown" with no dates.
"""

from __future__ import annotations

import re
from datetime import date, timedelta

_WD = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
_MON = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]

_MONTHS = {}
for _i, _names in enumerate(
    [
        "january januar janvier gennaio",
        "february februar février fevrier febbraio",
        "march märz maerz mars marzo",
        "april avril aprile",
        "may mai maggio",
        "june juni juin giugno",
        "july juli juillet luglio",
        "august août aout agosto",
        "september septembre settembre",
        "october oktober octobre ottobre",
        "november novembre",
        "december dezember décembre decembre dicembre",
    ],
    start=1,
):
    for _n in _names.split():
        _MONTHS[_n] = _i

_WEEKDAYS = {}
for _i, _names in enumerate(
    [
        "monday montag lundi lunedì lunedi",
        "tuesday dienstag mardi martedì martedi",
        "wednesday mittwoch mercredi mercoledì mercoledi",
        "thursday donnerstag jeudi giovedì giovedi",
        "friday freitag vendredi venerdì venerdi",
        "saturday samstag sonnabend samedi sabato",
        "sunday sonntag dimanche domenica",
    ]
):
    for _n in _names.split():
        _WEEKDAYS[_n] = _i

_NUMBER_WORDS = {
    # English
    "one": 1, "two": 2, "three": 3, "four": 4, "five": 5,
    "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10,
    # German
    "ein": 1, "eins": 1, "eine": 1, "einem": 1, "einen": 1, "einer": 1,
    "zwei": 2, "drei": 3, "vier": 4, "fünf": 5, "fuenf": 5,
    "sechs": 6, "sieben": 7, "acht": 8, "neun": 9, "zehn": 10,
    # French
    "un": 1, "une": 1, "deux": 2, "trois": 3, "quatre": 4, "cinq": 5,
    "sept": 7, "huit": 8, "neuf": 9, "dix": 10,
    # Italian
    "uno": 1, "una": 1, "due": 2, "tre": 3, "quattro": 4, "cinque": 5,
    "sei": 6, "sette": 7, "otto": 8, "nove": 9, "dieci": 10,
}


def _alt(words) -> str:
    return "|".join(sorted((re.escape(w) for w in words), key=len, reverse=True))


_MONTH_RE = _alt(_MONTHS)
_WD_RE = _alt(_WEEKDAYS)
def _num_re(name: str, english: bool = False) -> str:
    return rf"(?P<{name}>\d{{1,3}}|{'a|an|' if english else ''}{_alt(_NUMBER_WORDS)})"
# Optional leading weekday ("Monday, 3 November") so the explicit date wins over the bare weekday.
_WD_PREFIX = rf"(?:(?:{_WD_RE})[,.]?\s+(?:(?:the|den|le|il|der)\s+)?)?"
_ORD = r"(?:st|nd|rd|th|er|\.)?"


def _fmt(d: date, year: bool = True) -> str:
    s = f"{_WD[d.weekday()]} {d.day} {_MON[d.month - 1]}"
    return f"{s} {d.year}" if year else s


def _fmt_range(a: date, b: date) -> str:
    return f"{_fmt(a, year=a.year != b.year)} to {_fmt(b)}"


def _num(m: re.Match) -> int:
    n = next(v for k, v in m.groupdict().items() if k.startswith("n") and v).lower()
    return int(n) if n.isdigit() else (1 if n in ("a", "an") else _NUMBER_WORDS[n])


def _month_span(year: int, month: int) -> tuple[date, date]:
    first = date(year, month, 1)
    nxt = date(year + (month == 12), month % 12 + 1, 1)
    return first, nxt - timedelta(days=1)


def _result(precision, d_from, d_to, explanation):
    return {"precision": precision, "date_from": d_from, "date_to": d_to, "explanation": explanation}


def _unknown(explanation: str):
    return _result("unknown", None, None, explanation)


def _estimate(phrase, d_from, d_to, today, how):
    d_from, d_to = min(d_from, today), min(d_to, today)
    return _result("estimate", d_from, d_to, f"'{phrase}' interpreted as {_fmt_range(d_from, d_to)} ({how}).")


def _exact(phrase, d, how=None):
    extra = f" ({how})" if how else ""
    return _result("exact", d, d, f"'{phrase}' interpreted as {_fmt(d)}{extra}.")


# ---- handlers: (match, phrase, today) -> result dict ----

def _h_today(m, phrase, today):
    return _exact(phrase, today, "today")


def _h_yesterday(m, phrase, today):
    return _exact(phrase, today - timedelta(days=1), "the day before today")


def _h_day_before_yesterday(m, phrase, today):
    return _exact(phrase, today - timedelta(days=2), "two days before today")


def _full_date(m, phrase, today, y, mo, d):
    try:
        dt = date(y, mo, d)
    except ValueError:
        return _unknown(f"'{phrase}' is not a valid calendar date, so no date was inferred.")
    if dt > today:
        return _unknown(f"'{phrase}' is in the future ({_fmt(dt)}), so no date was inferred.")
    return _exact(phrase, dt)


def _h_ymd(m, phrase, today):
    return _full_date(m, phrase, today, int(m["y"]), int(m["m"]), int(m["d"]))


def _h_dmy_text(m, phrase, today):
    return _full_date(m, phrase, today, int(m["y"]), _MONTHS[m["mon"].lower()], int(m["d"]))


def _h_dmy_num(m, phrase, today):
    return _full_date(m, phrase, today, int(m["y"]), int(m["m"]), int(m["d"]))


def _day_month(m, phrase, today, mo, d):
    for year in range(today.year, today.year - 9, -1):
        try:
            dt = date(year, mo, d)
        except ValueError:
            continue
        if dt <= today:
            return _exact(phrase, dt, "no year given, so the most recent such date not in the future")
    return _unknown(f"'{phrase}' is not a valid calendar date, so no date was inferred.")


def _h_dm_text(m, phrase, today):
    return _day_month(m, phrase, today, _MONTHS[m["mon"].lower()], int(m["d"]))


def _h_dm_num(m, phrase, today):
    return _day_month(m, phrase, today, int(m["m"]), int(m["d"]))


def _h_last_week(m, phrase, today):
    monday = today - timedelta(days=today.weekday() + 7)
    return _estimate(phrase, monday, monday + timedelta(days=6), today, "previous calendar week")


def _h_this_week(m, phrase, today):
    monday = today - timedelta(days=today.weekday())
    return _estimate(phrase, monday, today, today, "Monday of this week to today")


def _h_days_ago(m, phrase, today):
    n = _num(m)
    c = today - timedelta(days=n)
    return _estimate(phrase, c - timedelta(days=1), c + timedelta(days=1), today, f"{n} days back, plus or minus 1 day")


def _h_weeks_ago(m, phrase, today):
    n = _num(m)
    c = today - timedelta(days=7 * n)
    return _estimate(phrase, c - timedelta(days=3), c + timedelta(days=3), today, f"{n} weeks back, plus or minus 3 days")


def _h_few_days(m, phrase, today):
    return _estimate(phrase, today - timedelta(days=6), today - timedelta(days=2), today, "a few days taken as 2 to 6 days back")


def _months_back(today: date, n: int) -> tuple[date, date]:
    idx = today.year * 12 + today.month - 1 - n
    return _month_span(idx // 12, idx % 12 + 1)


def _h_last_month(m, phrase, today):
    a, b = _months_back(today, 1)
    return _estimate(phrase, a, b, today, "previous calendar month")


def _h_months_ago(m, phrase, today):
    n = _num(m)
    a, b = _months_back(today, n)
    return _estimate(phrase, a, b, today, f"whole calendar month {n} months back")


def _h_recently(m, phrase, today):
    return _estimate(phrase, today - timedelta(days=30), today - timedelta(days=1), today, "recently taken as the last 30 days")


def _h_weekday(m, phrase, today):
    idx = _WEEKDAYS[m["wd"].lower()]
    d = today - timedelta(days=(today.weekday() - idx) % 7 or 7)
    return _estimate(phrase, d, d, today, "weekday interpreted as the most recent such day before today")


# ---- pattern table: (regex, handler); order is the tie-break at equal start position ----

_PATTERNS_SRC = [
    # explicit dates (most specific first)
    (rf"{_WD_PREFIX}(?<!\d)(?P<y>\d{{4}})-(?P<m>\d{{1,2}})-(?P<d>\d{{1,2}})(?!\d)", _h_ymd),
    (rf"{_WD_PREFIX}(?<!\d)(?P<d>\d{{1,2}})\.(?P<m>\d{{1,2}})\.(?P<y>\d{{4}})(?!\d)", _h_dmy_num),
    (rf"{_WD_PREFIX}(?<!\d)(?P<d>\d{{1,2}}){_ORD}\s*(?:of\s+)?(?P<mon>{_MONTH_RE})\s*,?\s*(?P<y>\d{{4}})(?!\d)", _h_dmy_text),
    (rf"{_WD_PREFIX}(?P<mon>{_MONTH_RE})\s+(?P<d>\d{{1,2}})(?:st|nd|rd|th)?\s*,?\s*(?P<y>\d{{4}})(?!\d)", _h_dmy_text),
    (rf"{_WD_PREFIX}(?<!\d)(?P<d>\d{{1,2}})\.(?P<m>\d{{1,2}})\.(?!\d)", _h_dm_num),
    (
        rf"{_WD_PREFIX}(?<!\d)(?P<d>\d{{1,2}}){_ORD}\s*(?:of\s+)?(?P<mon>{_MONTH_RE})"
        rf"(?!\s*,?\s*\d{{4}})(?!\s+(?:be|have|not|also|still|need|get|apply|cause)\b)",
        _h_dm_text,
    ),
    (
        rf"{_WD_PREFIX}(?P<mon>{_MONTH_RE})\s+(?P<d>\d{{1,2}})(?:st|nd|rd|th)?(?!\d)(?!\s*,?\s*\d{{4}})"
        rf"(?!\s*(?:days?|weeks?|months?|years?|times?|tage|woche|jours?|giorni))",
        _h_dm_text,
    ),
    # today / yesterday
    (r"(?:day before yesterday|vorgestern|avant-hier|l['’]altro ieri|ieri l['’]altro)", _h_day_before_yesterday),
    (r"(?:today|heute|aujourd['’]hui|oggi)", _h_today),
    (r"(?:yesterday|gestern|hier|ieri)", _h_yesterday),
    # weeks
    (r"(?:last|previous|past) week|(?:letzte[nrm]?|vergangene[nrm]?) woche|la semaine (?:dernière|derniere|passée|passee)|la settimana scorsa", _h_last_week),
    (r"this week|diese[rn]? woche|cette semaine|questa settimana", _h_this_week),
    # N units ago
    (rf"{_num_re('n1', True)}\s+days?\s+ago|vor\s+{_num_re('n2')}\s+tag(?:en)?|il\s+y\s+a\s+{_num_re('n3')}\s+jours?|{_num_re('n4')}\s+giorn[oi]\s+fa", _h_days_ago),
    (rf"{_num_re('n1', True)}\s+weeks?\s+ago|vor\s+{_num_re('n2')}\s+wochen?|il\s+y\s+a\s+{_num_re('n3')}\s+semaines?|{_num_re('n4')}\s+settiman[ae]\s+fa", _h_weeks_ago),
    (rf"{_num_re('n1', True)}\s+months?\s+ago|vor\s+{_num_re('n2')}\s+monat(?:en)?|il\s+y\s+a\s+{_num_re('n3')}\s+mois|{_num_re('n4')}\s+mes[ei]\s+fa", _h_months_ago),
    (r"(?:a\s+)?few\s+days\s+ago|vor\s+(?:ein\s+)?paar\s+tagen|il\s+y\s+a\s+quelques\s+jours|qualche\s+giorno\s+fa", _h_few_days),
    # months
    (r"(?:last|previous) month|(?:letzte[nrm]?|vergangene[nrm]?) monat|le mois dernier|il mese scorso", _h_last_month),
    (r"recently|kürzlich|kuerzlich|neulich|récemment|recemment|di recente|recentemente", _h_recently),
    # bare / "last" weekdays
    (
        rf"(?:(?:on|last|am|letzte[nrm]?|vergangene[nrm]?)\s+)?(?P<wd>{_WD_RE})(?:\s+(?:dernier|scorso))?",
        _h_weekday,
    ),
]

_PATTERNS = [
    (re.compile(rf"(?<!\w)(?:{src})(?!\w)", re.IGNORECASE), h) for src, h in _PATTERNS_SRC
]


def parse_when(words: str, today: date) -> dict:
    """Convert the client's verbatim time wording into a conservative date range."""
    text = (words or "").strip()
    best = None  # (start, pattern index, match, handler)
    for i, (rx, handler) in enumerate(_PATTERNS):
        m = rx.search(text)
        if m and (best is None or (m.start(), i) < (best[0], best[1])):
            best = (m.start(), i, m, handler)
    if best is None:
        return _unknown("No recognisable time expression found, so no date was inferred.")
    _, _, m, handler = best
    return handler(m, " ".join(m.group(0).split()), today)
