"""Lane scoring (agreed proposal D5, D34): code scores urgency and information uncertainty,
the AI scores severity and complexity against a rubric, the social worker scores vulnerability.
Every level carries the reasons that produced it."""
from datetime import date

LEVELS = ["low", "medium", "high"]

# The only warning signs the AI may raise about the person (hard lane-3 triggers). Vulnerability itself is rated
# by the social worker only; these signs count only while the social worker keeps them ticked in step 2.
SAFETY = {"violence_threats_or_coercion": "violence, threats or coercion",
          "exploitation_or_dependency": "exploitation or dependency"}


def safety_signs(case) -> set:
    return {s["kind"] for s in case.get("signals", []) if s.get("kind") in SAFETY and s.get("confirmed", True)}


def _lvl(x):
    return LEVELS.index(x)


def vulnerability_level(score_1_to_10: int) -> str:
    if score_1_to_10 >= 7:
        return "high"
    if score_1_to_10 >= 4:
        return "medium"
    return "low"


def urgency(deadlines, signals, today: date):
    """High: a court/enforcement step, or a client deadline within 10 days or possibly missed.
    Medium: a client deadline within 30 days, or a running notice/demand. Low otherwise."""
    level, reasons = "low", []
    for s in signals:
        # the kind of document decides urgency, whichever index the AI filed the signal under
        urgent_kind = s.get("kind") in ("court_or_enforcement_step", "termination_notice", "payment_demand", "other_deadline")
        if not (s["index"] == "urgency" or urgent_kind) or s.get("tense") not in ("current", "future"):
            continue
        if s.get("concerns") not in ("client", "household_member", "unclear"):
            continue  # escalation.md rule 1: a notice received by someone else is not the client's deadline
        if s.get("kind") == "court_or_enforcement_step":
            level = "high"
            reasons.append(f"Court or enforcement step: {s['description']}")
        elif s.get("kind") == "termination_notice":
            # escalation.md rule 6: a critical deadline alone may justify human review; a received termination
            # can only be challenged within a short statutory period (deadlines.md: Art. 273 OR)
            level = "high"
            reasons.append(f"Termination notice received, challenge period running: {s['description']}")
        elif s.get("kind") in ("payment_demand", "other_deadline"):
            if _lvl(level) < 1:
                level = "medium"
            reasons.append(f"Running notice or deadline: {s['description']}")
    for d in deadlines:
        if d.get("who_must_act") == "client" and d.get("not_determinable_reason") == "missing_fact":
            # escalation.md rule 8: an unknown date is never proof that there is time left
            if _lvl(level) < 1:
                level = "medium"
            reasons.append(f"{d['action']}: a deadline may be running but its start date is unknown")
            continue
        if d.get("who_must_act") != "client" or not d.get("earliest"):
            continue
        days = (d["earliest"] - today).days
        label = "precautionary planning date" if d.get("precautionary") else "deadline"
        if days < 0:
            level = "high"
            reasons.append(f"{d['action']}: {label} {d['earliest'].isoformat()} may already have passed")
        elif days <= 10:
            level = "high"
            reasons.append(f"{d['action']}: {label} in {days} days ({d['earliest'].isoformat()})")
        elif days <= 30:
            if _lvl(level) < 1:
                level = "medium"
            reasons.append(f"{d['action']}: {label} in {days} days ({d['earliest'].isoformat()})")
    if not reasons:
        reasons.append("No running deadline or notice identified.")
    return level, reasons


def information(questions, answers, disputes, deadlines):
    """High: an urgent question unanswered or a key date unknown. Medium: core questions
    unanswered or a disputed fact. Low otherwise."""
    answered = {a["question_id"] for a in answers if a.get("status") == "answered"}
    level, reasons = "low", []
    urgent_open = [q for q in questions if q["priority"] == "urgent" and q["id"] not in answered]
    core_open = [q for q in questions if q["priority"] == "core" and q["id"] not in answered]
    missing_dates = [d for d in deadlines if d.get("not_determinable_reason") == "missing_fact"]
    if urgent_open:
        level = "high"
        reasons.append(f"{len(urgent_open)} urgent question(s) not yet answered")
    if missing_dates:
        level = "high"
        reasons.append(f"{len(missing_dates)} deadline(s) cannot be dated without more facts")
    if core_open:
        level = max(level, "medium", key=_lvl)
        reasons.append(f"{len(core_open)} core question(s) not yet answered")
    if disputes:
        level = max(level, "medium", key=_lvl)
        reasons.append(f"{len(disputes)} disputed fact(s)")
    if not reasons:
        reasons.append("The material facts are available.")
    return level, reasons


def decide_lane(ind):
    """ind: dict index -> level. Returns (lane, rule text). Rules in the order they are checked."""
    u, s, c, v, i = (ind[k] for k in ("urgency", "severity", "complexity", "vulnerability", "information"))
    if u == "high":
        return 3, "Lane 3: legal urgency is high."
    if c == "high":
        return 3, "Lane 3: legal complexity is high."
    if s == "high" and (_lvl(u) >= 1 or _lvl(v) >= 1):
        return 3, "Lane 3: severity is high and urgency or vulnerability is at least medium."
    if v == "high" and (_lvl(u) >= 1 or _lvl(s) >= 1):
        return 3, "Lane 3: personal vulnerability is high and urgency or severity is at least medium."
    if _lvl(i) >= 1:
        return 2, "Lane 2: material information is missing, unclear or disputed."
    return 1, "Lane 1: straightforward, non-urgent, low vulnerability, enough information."
