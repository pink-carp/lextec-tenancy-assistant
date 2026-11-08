from datetime import date

import pytest

from app.dates import parse_when

TODAY = date(2026, 11, 8)  # a Sunday


def d(y, m, day):
    return date(y, m, day)


def check(words, precision, d_from, d_to):
    r = parse_when(words, TODAY)
    assert (r["precision"], r["date_from"], r["date_to"]) == (precision, d_from, d_to), r
    assert isinstance(r["explanation"], str) and r["explanation"]
    return r


@pytest.mark.parametrize("words", ["Today I received a letter", "heute", "Aujourd'hui", "oggi", "TODAY"])
def test_today(words):
    check(words, "exact", TODAY, TODAY)


@pytest.mark.parametrize("words", ["yesterday", "gestern", "hier", "ieri"])
def test_yesterday(words):
    check(words, "exact", d(2026, 11, 7), d(2026, 11, 7))


def test_day_before_yesterday_is_not_yesterday():
    check("the day before yesterday", "exact", d(2026, 11, 6), d(2026, 11, 6))
    check("vorgestern", "exact", d(2026, 11, 6), d(2026, 11, 6))


@pytest.mark.parametrize(
    "words",
    ["2026-11-03", "03.11.2026", "3.11.2026", "3 November 2026", "November 3, 2026",
     "3. November 2026", "3 novembre 2026", "Tuesday, 3 November 2026"],
)
def test_explicit_full_dates(words):
    check(words, "exact", d(2026, 11, 3), d(2026, 11, 3))


def test_day_month_no_year():
    check("on 3 November", "exact", d(2026, 11, 3), d(2026, 11, 3))
    check("am 3. November", "exact", d(2026, 11, 3), d(2026, 11, 3))
    check("le 3 novembre", "exact", d(2026, 11, 3), d(2026, 11, 3))
    check("il 3 novembre", "exact", d(2026, 11, 3), d(2026, 11, 3))
    check("on 8 November", "exact", TODAY, TODAY)


def test_day_month_in_future_goes_to_previous_year():
    check("on 9 November", "exact", d(2025, 11, 9), d(2025, 11, 9))
    check("am 25. Dezember", "exact", d(2025, 12, 25), d(2025, 12, 25))


def test_leap_day_falls_back_to_valid_year():
    check("29 February", "exact", d(2024, 2, 29), d(2024, 2, 29))


def test_invalid_or_future_explicit_dates_are_unknown():
    check("31 November 2026", "unknown", None, None)
    check("3 November 2027", "unknown", None, None)


@pytest.mark.parametrize(
    "words",
    ["last week", "letzte Woche", "vergangene Woche", "la semaine dernière", "la settimana scorsa"],
)
def test_last_week(words):
    r = check(words, "estimate", d(2026, 10, 26), d(2026, 11, 1))
    if words == "last week":
        assert r["explanation"] == "'last week' interpreted as Monday 26 Oct to Sunday 1 Nov 2026 (previous calendar week)."


@pytest.mark.parametrize("words", ["this week", "diese Woche", "cette semaine", "questa settimana"])
def test_this_week(words):
    check(words, "estimate", d(2026, 11, 2), TODAY)


@pytest.mark.parametrize(
    "words",
    ["3 days ago", "three days ago", "vor drei Tagen", "vor 3 Tagen", "il y a 3 jours",
     "il y a trois jours", "3 giorni fa", "tre giorni fa"],
)
def test_n_days_ago(words):
    check(words, "estimate", d(2026, 11, 4), d(2026, 11, 6))


def test_days_ago_never_after_today():
    check("1 day ago", "estimate", d(2026, 11, 6), TODAY)
    check("0 days ago", "estimate", d(2026, 11, 7), TODAY)


@pytest.mark.parametrize(
    "words", ["two weeks ago", "2 weeks ago", "vor zwei Wochen", "il y a deux semaines", "due settimane fa"]
)
def test_n_weeks_ago(words):
    check(words, "estimate", d(2026, 10, 22), d(2026, 10, 28))


@pytest.mark.parametrize(
    "words", ["a few days ago", "vor ein paar Tagen", "il y a quelques jours", "qualche giorno fa"]
)
def test_few_days(words):
    check(words, "estimate", d(2026, 11, 2), d(2026, 11, 6))


@pytest.mark.parametrize("words", ["last month", "letzten Monat", "le mois dernier", "il mese scorso"])
def test_last_month(words):
    check(words, "estimate", d(2026, 10, 1), d(2026, 10, 31))


def test_n_months_ago():
    check("two months ago", "estimate", d(2026, 9, 1), d(2026, 9, 30))
    check("vor drei Monaten", "estimate", d(2026, 8, 1), d(2026, 8, 31))
    check("il y a deux mois", "estimate", d(2026, 9, 1), d(2026, 9, 30))
    check("tre mesi fa", "estimate", d(2026, 8, 1), d(2026, 8, 31))
    check("11 months ago", "estimate", d(2025, 12, 1), d(2025, 12, 31))  # year boundary
    check("12 months ago", "estimate", d(2025, 11, 1), d(2025, 11, 30))


@pytest.mark.parametrize("words", ["recently", "kürzlich", "neulich", "récemment", "di recente"])
def test_recently(words):
    check(words, "estimate", d(2026, 10, 9), d(2026, 11, 7))


@pytest.mark.parametrize(
    "words,day",
    [
        ("on Monday", d(2026, 11, 2)),
        ("last Friday", d(2026, 11, 6)),
        ("am Montag", d(2026, 11, 2)),
        ("lundi dernier", d(2026, 11, 2)),
        ("lunedì scorso", d(2026, 11, 2)),
        ("on Sunday", d(2026, 11, 1)),  # today is Sunday: most recent one BEFORE today
    ],
)
def test_weekdays(words, day):
    r = check(words, "estimate", day, day)
    assert "weekday" in r["explanation"]


def test_embedded_in_sentence():
    check("Last week a termination arrived by registered mail", "estimate", d(2026, 10, 26), d(2026, 11, 1))
    check("Ich habe die Kündigung vor drei Tagen erhalten.", "estimate", d(2026, 11, 4), d(2026, 11, 6))


def test_first_expression_wins():
    check("Last week, actually on 3 November", "estimate", d(2026, 10, 26), d(2026, 11, 1))
    check("On 3 November, not last week", "exact", d(2026, 11, 3), d(2026, 11, 3))


def test_bare_may_verb_not_a_date():
    check("I think 3 may be wrong", "unknown", None, None)


@pytest.mark.parametrize("words", ["", "   ", "a while ago", "sometime", "tomorrow", "next week", "last weekend"])
def test_unknown(words):
    check(words, "unknown", None, None)


def test_all_dates_never_after_today():
    for w in ["today", "this week", "1 day ago", "recently", "on Monday", "last month", "0 days ago"]:
        r = parse_when(w, TODAY)
        assert r["date_to"] <= TODAY
