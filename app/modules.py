"""Situation modules (v4, limited scope): checked content for common tenancy situations, shown item by item when the
confirmed facts meet each item's conditions.

Why: on 2026-11-08 every generative option was measured (blind Claude reviews, 11 cases). Even with confirmed facts,
code gating and two Apertus checks, about 1 in 4 AI-written legal sentences shown was wrong. So legal points,
questions and actions now come from modules drafted from the German text and checked in a second pass
(corpus/modules/*.json, format in SPEC.md). Apertus still reads the description, pre-fills the deciding events and
the answers the description already gives, writes the neutral situation summary and translates the handout.
Situations without a module get no legal guidance, only a referral."""
import json
import re
from concurrent.futures import ThreadPoolExecutor
from datetime import date
from functools import lru_cache
from pathlib import Path

from . import scoring
from .dates import parse_when
from .deadlines import DeadlineSpec, compute_deadline
from .llm import ask_json

DIR = Path(__file__).resolve().parent.parent / "corpus" / "modules"


@lru_cache(maxsize=1)
def load():
    out = {}
    for f in sorted(DIR.glob("*.json")):
        m = json.loads(f.read_text(encoding="utf-8"))
        out[m["id"]] = m
    return out


# ---------------------------------------------------------------- conditions

def _ctx(case):
    ans = {}
    qid = {q["id"]: q.get("qid", q["id"]) for q in case.get("questions", [])}  # UI ids (Q1...) -> module question ids
    for a in case.get("answers", []):
        v = str(a.get("value", "")).strip().lower()
        ans[qid.get(a["question_id"], a["question_id"])] = {"yes": "yes", "no": "no"}.get(
            v, "answered" if a.get("status") == "answered" and v else "unknown")
    return {"events": {k: v.get("answer", "C") for k, v in case.get("event_status", {}).items()},
            "answers": ans, "deadlines": {d.get("kind") for d in case.get("deadlines", []) if d.get("earliest")},
            "situations": {s["situation"] for s in case.get("situations", [])},
            "docs": {d["doc_type"] for d in case.get("documents", [])},
            "vuln": scoring.safety_signs(case)}


def holds(atom, ctx):
    atom = atom.strip()
    m = re.fullmatch(r"(E\d+)\s*(!?=)\s*([ABC])", atom)
    if m:
        v = ctx["events"].get(m.group(1), "C")
        return (v == m.group(3)) if m.group(2) == "=" else (v != m.group(3))
    m = re.fullmatch(r"q:(\w+)\s*(!?=)\s*(yes|no|unknown|answered)", atom)
    if m:
        v = ctx["answers"].get(m.group(1), "unknown")
        hit = (v != "unknown") if m.group(3) == "answered" else (v == m.group(3))
        return hit if m.group(2) == "=" else not hit
    m = re.fullmatch(r"deadline:(\w+)", atom)
    if m:
        return m.group(1) in ctx["deadlines"]
    m = re.fullmatch(r"situation:(\w+)", atom)
    if m:
        return m.group(1) in ctx["situations"]
    m = re.fullmatch(r"doc:(\w+)", atom)
    if m:
        return m.group(1) in ctx["docs"]
    m = re.fullmatch(r"vuln:(\w+)", atom)
    if m:
        return m.group(1) in ctx.get("vuln", set())
    raise ValueError(f"unknown condition atom: {atom}")  # content errors must fail loudly in tests


def shown(item, ctx):
    return all(holds(a, ctx) for a in item.get("show_if") or [])


def suggest(case):
    """Modules whose triggers match what the AI read (the social worker confirms in step 2)."""
    ctx = _ctx(case)
    # a trigger may combine atoms with "&" (all must hold)
    return [mid for mid, m in load().items()
            if any(all(holds(a, ctx) for a in t.split("&")) for t in m.get("triggers") or [])]


_PICK = """A social worker describes a client's tenancy problem (numbered sentences). Below is a list of situations for which
the tool has checked guidance. Which of them does the client's problem CLEARLY belong to? Choose only situations that
actually fit; it is fine to choose none. A threat to terminate is not a termination; a tenant who wants to leave is not a
termination by the landlord; subletting to a lodger is not a co-tenancy.
SITUATIONS:
{menu}
Answer JSON only: {{"situations": [{{"id": "<id from the list>", "sentence": <number of the sentence that shows it>}}]}}  (empty list if none fits)

DESCRIPTION:
{text}"""


def suggest_ai(case):
    """One closed Apertus call: pick the matching situations from the module menu (or none). Each pick must cite a
    sentence. Falls back to the trigger rules if the call fails."""
    menu = "\n".join(f"- {mid}: {m['title']}. {m.get('summary_for_sw', '')}" for mid, m in load().items())
    sents = case["sentences"]
    text = "\n".join(f"{i + 1}. {x}" for i, x in enumerate(sents))
    try:
        r = ask_json(_PICK.format(menu=menu, text=text), trace=case["trace"], step="2 situation", max_tokens=150)
    except Exception:  # noqa: BLE001
        return suggest(case), "rules (the AI call failed)"
    out = []
    for x in r.get("situations") or []:
        if not isinstance(x, dict) or x.get("id") not in load():
            continue
        try:
            n = int(x.get("sentence") or 0)
        except (TypeError, ValueError):
            n = 0
        if 1 <= n <= len(sents) and x["id"] not in out:
            out.append(x["id"])
    return out, "AI (one closed question, each pick cites a sentence)"


def active(case):
    return [load()[m] for m in case.get("modules", []) if m in load()]


# ---------------------------------------------------------------- questions

_PREFILL = """Below are numbered sentences from a client's description and one question to the client. Does the
description already answer the question, fully or in part?
- "full" or "part": give the answer in a few words, using only what the description says, and the sentence number.
- "no": the description does not say it, or it would only follow by guessing or inference.
For a question that can be answered yes or no, the value must be "yes" or "no", and only if the description says so
explicitly (a plan or wish is not a fact; if unsure, answer "no").
Answer JSON only: {{"answered": "full" | "part" | "no", "value": "<answer or empty>", "sentence": <number or 0>}}
QUESTION: {q}

DESCRIPTION:
{text}"""


_MONTHS = {m: i + 1 for i, m in enumerate(["january", "february", "march", "april", "may", "june", "july", "august",
                                             "september", "october", "november", "december"])}


def _end_of_month(words, today):
    """'end of March' / 'end of March 2027' -> last day of that month (the next one if no year is given)."""
    m = re.search(r"end of (\w+)(?:\s+(\d{4}))?", words.lower())
    if not m or m.group(1) not in _MONTHS:
        return None
    mon = _MONTHS[m.group(1)]
    year = int(m.group(2)) if m.group(2) else (today.year if mon >= today.month else today.year + 1)
    nxt = date(year + (mon == 12), mon % 12 + 1, 1)
    return date.fromordinal(nxt.toordinal() - 1)


def questions(case):
    """Visible questions of the confirmed modules (deduplicated by id); answers the description already gives are
    pre-filled by Apertus with the sentence they come from, for the social worker to confirm."""
    ctx = _ctx(case)
    qs, seen = [], set()
    for k, m in enumerate(active(case)):
        n = 0
        for q in m.get("questions") or []:
            if q["id"] not in seen and shown(q, ctx) and (k == 0 or n < 3):  # secondary situations: their first 3 only
                seen.add(q["id"])
                qs.append({**q, "module": m["id"]})
                n += 1
    qs.sort(key=lambda q: not q.get("urgent"))
    sents = case["sentences"]
    text = "\n".join(f"{i + 1}. {s}" for i, s in enumerate(sents))
    today = date.fromisoformat(case["today"])

    def prefill(q):
        # yes/no questions are never pre-filled: in tests (2026-11-08) Apertus answered "yes" where the description only
        # implied it (a payment demand read as a termination), so the social worker asks these directly
        if not q.get("prefill") or q["input"] == "yes_no_unknown":
            return q
        try:
            r = ask_json(_PREFILL.format(q=q["text"], text=text), trace=case["trace"], step="5 prefill answer", max_tokens=80)
        except Exception:  # noqa: BLE001 - no prefill, the question is simply asked
            return q
        try:
            n = int(r.get("sentence") or 0)
        except (TypeError, ValueError):
            n = 0
        val = str(r.get("value") or "").strip()
        if r.get("answered") not in ("full", "part", "yes") or not val or not 1 <= n <= len(sents):
            return q
        partly = r.get("answered") == "part"
        if q["input"] == "yes_no_unknown" and val.lower() not in ("yes", "no"):
            return q
        if q["input"] == "date":
            w = parse_when(val, today)
            eom = _end_of_month(val, today)
            if w["precision"] != "exact" and eom:
                return {**q, "prefilled": eom.isoformat(), "prefill_quote": sents[n - 1],
                        "prefill_note": f'"{val}" read as {eom.isoformat()} (the next such month-end) - please confirm.'}
            if w["precision"] != "exact":
                return {**q, "prefill_note": f'The client said "{val}" - please ask for the exact date.'}
            val = w["date_from"].isoformat()
        if q["input"] == "number" and not re.fullmatch(r"\d+(?:[.,]\d+)?", val):
            m = re.search(r"\d+(?:[.,]\d+)?", val)
            if not m:
                return q
            val = m.group(0)
        out = {**q, "prefilled": val, "prefill_quote": sents[n - 1]}
        if partly:
            out["prefill_note"] = "Only partly answered in the description - please complete with the client."
        return out

    with ThreadPoolExecutor(4) as ex:
        qs = list(ex.map(prefill, qs))
    qs = qs[:8]
    for i, q in enumerate(qs):
        q["qid"] = q["id"]
        q["id"] = f"Q{i + 1}"
        q["question"] = q["text"]
        q["why_we_ask"] = q.get("why", "")
        q["input_type"] = q["input"]
        q["legal_basis"] = q.get("basis", [])
        q["priority"] = "urgent" if q.get("urgent") else "core"
        q.setdefault("options", [])
        q.setdefault("answer_instead", [])
        q["dates_event"] = "none"
    case["questions"] = qs
    return case


def answer_ctx_ids(case):
    """Answers keyed by module question id (the UI uses Q1, Q2 ...)."""
    by_q = {q["id"]: q for q in case.get("questions", [])}
    out = []
    for a in case.get("answers", []):
        q = by_q.get(a["question_id"])
        if q:
            out.append({**a, "question_id": q["qid"], "_q": q})
    return out


def apply_answers(case):
    """Answers set events (sets_event), raise indices (raises) and facts used for deadlines (fact)."""
    facts = {}
    case["raised"] = []
    for a in answer_ctx_ids(case):
        q, v = a["_q"], str(a.get("value", "")).strip()
        if a.get("status") != "answered" or not v:
            continue
        if q.get("sets_event") and v.lower() in ("yes", "no"):
            ev = case.setdefault("event_status", {})
            ev[q["sets_event"]] = {**ev.get(q["sets_event"], {}), "answer": "A" if v.lower() == "yes" else "B",
                                   "source": "answer to a question"}
        if q.get("raises") and v.lower() == "yes":
            case.setdefault("raised", []).append({"by": q.get("why") or q["text"], "indices": q["raises"]})
        if q.get("fact"):
            facts[q["fact"]] = v
            m = re.fullmatch(r"receipt_date:(\w+)", q["fact"])
            if m:  # an exact receipt date from the client replaces the estimate from the description
                try:
                    d = date.fromisoformat(v)
                except ValueError:
                    continue
                for e in case.get("events", []):
                    if e.get("doc_type") == m.group(1):
                        e.setdefault("original", {k: e.get(k, "") for k in ("precision", "date", "date_from", "date_to")})
                        e.update({"precision": "exact", "date": d.isoformat(), "date_from": "", "date_to": "",
                                  "source": "client's answer, not documented"})
    case["module_facts"] = facts
    return case


# ---------------------------------------------------------------- deadlines

def tenant_notice_deadline(case):
    f = case.get("module_facts", {})
    try:
        end = date.fromisoformat(f.get("desired_end_date", ""))
        months = int(float(str(f.get("notice_months", "")).replace(",", ".")))
    except (ValueError, TypeError):
        return None
    res = compute_deadline(DeadlineSpec(months, "months", "backward", end, end, False, False))
    return {"id": "", "kind": "tenant_notice", "action": "Your signed notice letter must reach the landlord by this date",
            "legal_basis": ["OR Art. 266a Abs. 1", "OR Art. 266l Abs. 1"], "who_must_act": "client", "direction": "backward",
            **res, "not_determinable_reason": "none", "check": "code",
            "steps": res["steps"] + [f"Notice period {months} month(s) and end date {end.isoformat()} as given by the client; "
                                     "a longer period or other dates in the lease prevail. What counts is receipt by the landlord."]}


# ---------------------------------------------------------------- result

def assemble(case):
    """Points, actions and lawyer questions of the confirmed modules whose conditions hold."""
    ctx = _ctx(case)
    blocks, actions, lawyer = [], [], []
    for m in active(case):
        pts = [p for p in m.get("points") or [] if shown(p, ctx)]
        acts = [a for a in m.get("actions") or [] if shown(a, ctx)]
        blocks.append({"module": m["id"], "title": m["title"], "summary": m.get("summary_for_sw", ""), "points": pts})
        for a in acts:
            if a["id"] not in [x["mid"] for x in actions]:
                actions.append({"mid": a["id"], "what": a["text"], "client_text": a.get("client_text"), "who": a["who"],
                                "group": a["group"], "sources": a.get("basis", []), "deadline_kind": a.get("deadline"),
                                "module": m["id"]})
        lawyer += [x["text"] for x in m.get("lawyer_questions") or [] if shown(x, ctx)]
    order = {"referral": 1, "immediate": 0, "now": 2, "needs_clarification": 3}
    if case.get("lane") == 3:
        order["referral"] = -1
    actions.sort(key=lambda a: order.get(a["group"], 9))
    kinds = {d.get("kind"): d["id"] for d in case.get("deadlines", [])}
    for i, a in enumerate(actions):
        a["id"] = f"A{i + 1}"
        a["deadline_ids"] = [kinds[a["deadline_kind"]]] if a.get("deadline_kind") in kinds else []
        a["contact_ids"] = []
        a["depends_on"] = ""
    return blocks, actions, lawyer
