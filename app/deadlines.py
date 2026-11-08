"""Deterministic deadline arithmetic for the tenancy-law assistant.

An AI model upstream decides WHICH deadline applies and fills in a
DeadlineSpec. This module only does the date arithmetic and explains every
step in plain English. Rules follow deadlines.md (section 3 and 5).

Standard library only.
"""

from dataclasses import dataclass
from datetime import date, timedelta
from typing import Literal


# ---------------------------------------------------------------------------
# 1. Public holidays in the canton of Zurich
# ---------------------------------------------------------------------------

def easter_sunday(year: int) -> date:
    """Easter Sunday by the anonymous Gregorian algorithm (Meeus/Jones/Butcher)."""
    a = year % 19
    b, c = divmod(year, 100)
    d, e = divmod(b, 4)
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i, k = divmod(c, 4)
    l = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * l) // 451
    month, day = divmod(h + l - 7 * m + 114, 31)
    return date(year, month, day + 1)


def zurich_public_holidays(year: int) -> dict[date, str]:
    """The nine statutory public holidays of the canton of Zurich.

    Source: Canton of Zurich, "Feiertage" (Amt fuer Wirtschaft / Arbeitsbedingungen),
    https://zh.ch/de/wirtschaft-arbeit/arbeitsbedingungen/arbeitsssicherheit-gesundheitsschutz/arbeits-ruhezeiten/feiertage.html
    Accessed 2026-11-08. The page states: "Im Kanton Zuerich gelten neun
    gesetzliche Feiertage" (equal to Sundays) and lists them, with 2026 and 2027
    dates (e.g. Good Friday 3 April 2026 / 26 March 2027), which match the
    Easter calculation below. Legal basis: para. 1 of the cantonal
    Ruhetags- und Ladenoeffnungsgesetz.

    NOT included, because they are not statutory public holidays in Zurich
    (the same page calls them local, non-statutory days): Berchtoldstag
    (2 Jan), Sechselaeuten, Knabenschiessen, Fasnachtsmontag.
    Other local days of a particular municipality were not verified and are left out.
    """
    easter = easter_sunday(year)
    return {
        date(year, 1, 1): "New Year's Day",
        easter - timedelta(days=2): "Good Friday",
        easter + timedelta(days=1): "Easter Monday",
        date(year, 5, 1): "Labour Day (1 May)",
        easter + timedelta(days=39): "Ascension Day",
        easter + timedelta(days=50): "Whit Monday",
        date(year, 8, 1): "Swiss National Day (1 August)",
        date(year, 12, 25): "Christmas Day",
        date(year, 12, 26): "St Stephen's Day",
    }


def holiday_name(d: date) -> str | None:
    """Name of the Zurich public holiday on this date, or None."""
    return zurich_public_holidays(d.year).get(d)


def is_working_day(d: date) -> bool:
    """Monday to Friday and not a Zurich public holiday.

    Saturdays count as non-working days for federal deadlines
    (Bundesgesetz ueber den Fristenlauf an Samstagen, SR 173.110.3).
    """
    return d.weekday() < 5 and d not in zurich_public_holidays(d.year)


def _next_working_day(d: date) -> date:
    while not is_working_day(d):
        d += timedelta(days=1)
    return d


def _why_not_working(d: date) -> str:
    name = holiday_name(d)
    if name:
        return f"a public holiday ({name})"
    return d.strftime("a %A")


# ---------------------------------------------------------------------------
# 2. Court holidays (Art. 145 ZPO)
# ---------------------------------------------------------------------------

def court_holiday_periods(year: int) -> list[tuple[date, date, str]]:
    """Suspension periods of Art. 145 ZPO in the given year (both ends inclusive)."""
    easter = easter_sunday(year)
    return [
        (easter - timedelta(days=7), easter + timedelta(days=7),
         "Easter (7 days before to 7 days after Easter Sunday)"),
        (date(year, 7, 15), date(year, 8, 15), "summer (15 July to 15 August)"),
        (date(year, 12, 18), date(year + 1, 1, 2), "Christmas (18 December to 2 January)"),
    ]


def is_court_holiday(d: date) -> bool:
    # The Christmas period starts in the previous year, so check both years.
    periods = court_holiday_periods(d.year - 1) + court_holiday_periods(d.year)
    return any(start <= d <= end for start, end, _ in periods)


def _suspended_days_between(after: date, up_to: date) -> int:
    """Number of suspended days d with after < d <= up_to."""
    n, d = 0, after + timedelta(days=1)
    while d <= up_to:
        n += is_court_holiday(d)
        d += timedelta(days=1)
    return n


# ---------------------------------------------------------------------------
# 3. Effective receipt date
# ---------------------------------------------------------------------------

def effective_receipt(
    principle: Literal["direct", "absolute", "relative_7day"],
    *,
    handed_over: date | None = None,
    notice_slip_date: date | None = None,
    collected_on: date | None = None,
) -> tuple[date | None, date | None, str]:
    """Legally effective receipt date as (earliest, latest, explanation)."""
    # Handed over in person: receipt is that day under every principle.
    if handed_over is not None:
        return handed_over, handed_over, (
            f"Handed over in person on {handed_over}: receipt is that day.")

    if principle == "direct":
        if collected_on is not None:
            return collected_on, collected_on, (
                f"Direct receipt: the document was received on {collected_on}.")
        return None, None, "Direct receipt: no delivery date is known."

    if principle == "absolute":
        if notice_slip_date is not None:
            first_possible = notice_slip_date + timedelta(days=1)
            if collected_on is not None and collected_on < first_possible:
                first_possible = collected_on
            return first_possible, first_possible, (
                f"Absolute receipt principle: a collection slip was left on {notice_slip_date}, "
                f"so receipt is when collection first became possible, {first_possible}. "
                "It is not automatically 7 days later (Zurich Obergericht LF190080, as summarised by the team).")
        if collected_on is not None:
            return collected_on, collected_on, (
                f"Absolute receipt principle: the notice was collected on {collected_on}.")
        return None, None, "Absolute receipt principle: no handover, slip or collection date is known."

    if principle == "relative_7day":
        if notice_slip_date is not None:
            deemed = notice_slip_date + timedelta(days=7)
            if collected_on is not None:
                actual = min(collected_on, deemed)
                return actual, actual, (
                    f"Relative receipt principle: slip left {notice_slip_date}; collected {collected_on}. "
                    f"Receipt is the collection date if within the 7-day collection period "
                    f"(ending {deemed}), otherwise the 7th day after the slip: {actual}.")
            return notice_slip_date, deemed, (
                f"Relative receipt principle: slip left {notice_slip_date}, collection date unknown. "
                f"Receipt is somewhere from {notice_slip_date} (earliest, planning date) to {deemed} "
                "(slip + 7 days, latest). Ask when it was actually collected.")
        if collected_on is not None:
            return collected_on, collected_on, (
                f"Relative receipt principle: collected on {collected_on} (slip date unknown).")
        return None, None, "Relative receipt principle: no slip or collection date is known."

    raise ValueError(f"unknown receipt principle: {principle}")


# ---------------------------------------------------------------------------
# 4. Deadline calculation
# ---------------------------------------------------------------------------

@dataclass
class DeadlineSpec:
    period_amount: int
    period_unit: Literal["days", "months"]
    direction: Literal["forward", "backward"]
    trigger_earliest: date | None
    trigger_latest: date | None
    shift_final_day: bool       # Art. 78 OR + SR 173.110.3, or Art. 142(3) ZPO
    court_holidays_apply: bool  # Art. 145-146 ZPO suspension


def _add_months(d: date, months: int) -> date:
    """Same calendar date `months` later (may be negative); if it does not
    exist, the last day of that month."""
    total = d.year * 12 + (d.month - 1) + months
    year, month = divmod(total, 12)
    month += 1
    # last day of target month = day before first of next month
    first_next = date(year + (month == 12), month % 12 + 1, 1)
    last_day = (first_next - timedelta(days=1)).day
    return date(year, month, min(d.day, last_day))


def _forward(trigger: date, spec: DeadlineSpec, steps: list[str]) -> date:
    n, unit = spec.period_amount, spec.period_unit
    start = trigger
    if spec.court_holidays_apply and is_court_holiday(trigger + timedelta(days=1)):
        # The period would start inside a suspension: counting starts the day after it ends.
        d = trigger + timedelta(days=1)
        while is_court_holiday(d):
            d += timedelta(days=1)
        start = d - timedelta(days=1)
        steps.append(f"The period would start inside a court holiday, so counting starts on {d} "
                     "(Art. 145 ZPO).")

    if unit == "days":
        steps.append(f"Day-based period: counting starts the day after receipt, so {trigger} itself "
                     "is not counted (Art. 77 OR / Art. 142 ZPO).")
        end, counted = start, 0
        while counted < n:
            end += timedelta(days=1)
            if not (spec.court_holidays_apply and is_court_holiday(end)):
                counted += 1
        steps.append(f"Counting {n} calendar days gives {end}"
                     + (" (court-holiday days skipped, Art. 145 ZPO)." if spec.court_holidays_apply else "."))
        return end

    # months
    end = _add_months(start, n)
    steps.append(f"Month-based period: the period ends on the same calendar date {n} month(s) later "
                 f"({end}); if that date does not exist, the last day of the month; no extra day "
                 "(Art. 77 OR / 5A_691/2023).")
    if spec.court_holidays_apply:
        base, suspended = end, 0
        while True:
            new_suspended = _suspended_days_between(start, end)
            if new_suspended == suspended:
                break
            suspended = new_suspended
            end = base + timedelta(days=suspended)
        if suspended:
            steps.append(f"{suspended} court-holiday day(s) fall inside the period and do not count, "
                         f"so the end moves to {end} (Art. 145 ZPO).")
        else:
            steps.append("No court-holiday days fall inside the period (Art. 145 ZPO).")
    return end


def _backward(reference: date, spec: DeadlineSpec, steps: list[str]) -> date:
    n = spec.period_amount
    if spec.period_unit == "days":
        result = reference - timedelta(days=n)
    else:
        result = _add_months(reference, -n)
    steps.append(f"Backward period: {n} {spec.period_unit} before {reference} is {result}.")
    if not is_working_day(result):
        earlier = result - timedelta(days=1)
        while not is_working_day(earlier):
            earlier -= timedelta(days=1)
        steps.append(f"{result} is {_why_not_working(result)}; it is NOT moved to a later working day "
                     "because that would shorten the notice. To be safe, the act should be completed by the last "
                     f"working day before it: {earlier}.")
        result = earlier
    return result


def _one_scenario(trigger: date, spec: DeadlineSpec, steps: list[str]) -> date:
    if spec.direction == "backward":
        return _backward(trigger, spec, steps)
    end = _forward(trigger, spec, steps)
    if spec.shift_final_day and not is_working_day(end):
        shifted = _next_working_day(end)
        steps.append(f"The last day, {end}, is {_why_not_working(end)}, so the deadline moves to the next "
                     f"working day, {shifted} (Art. 78 OR with SR 173.110.3 / Art. 142(3) ZPO).")
        end = shifted
    return end


def compute_deadline(spec: DeadlineSpec) -> dict:
    """Compute the deadline for a spec; see the module docstring for the rules."""
    if spec.trigger_earliest is None:
        return {"earliest": None, "latest": None, "determinable": False, "precautionary": False,
                "steps": ["The triggering date (receipt or reference date) is not known, so no "
                          "deadline can be calculated. Ask for it."]}

    trig_latest = spec.trigger_latest or spec.trigger_earliest
    ranged = trig_latest != spec.trigger_earliest

    steps: list[str] = []
    if ranged:
        steps.append(f"The trigger date is uncertain: between {spec.trigger_earliest} and {trig_latest}. "
                     "Both cases are calculated.")
        steps.append(f"Case A, trigger {spec.trigger_earliest}:")
    earliest = _one_scenario(spec.trigger_earliest, spec, steps)
    if ranged:
        steps.append(f"Case B, trigger {trig_latest}:")
        latest = _one_scenario(trig_latest, spec, steps)
    else:
        latest = earliest

    # Backward periods: an earlier reference date gives an earlier date, so the
    # earliest/latest ordering is the same as for forward periods.
    precautionary = ranged or earliest != latest
    if precautionary:
        steps.append(f"Because the result is uncertain, {earliest} is the precautionary planning date "
                     "(earliest plausible), not a verified legal deadline.")
    return {"earliest": earliest, "latest": latest, "determinable": True,
            "precautionary": precautionary, "steps": steps}
