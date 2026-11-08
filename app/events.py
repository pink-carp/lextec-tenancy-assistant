"""Deciding events: has the event a rule needs actually happened for this client?

Apertus pre-fills each event with ONE closed question per call (A yes / B no / C not said) and the number of the
sentence it relies on; code cross-checks; the social worker confirms or corrects every event in step 2.
Code then sets each law paragraph's status from corpus/article_requirements.json (built offline from the German text):
  applies = every event it needs has happened; open = a needed event is unknown; not_yet = a needed event has not happened.
Why (tests on 2026-11-08): Apertus misread these deciding events in 15-30% of cases (mostly a threat read as a
termination), and every such error came with a genuine quote, so the human confirmation is the real safeguard."""
import json
import re
from concurrent.futures import ThreadPoolExecutor
from datetime import date, timedelta
from functools import lru_cache
from pathlib import Path

from .llm import ask_json

ROOT = Path(__file__).resolve().parent.parent
TABLE = ROOT / "corpus" / "article_requirements.json"

# used until the verified table is available; the table's own event list takes precedence
DEFAULT_EVENTS = {
    "E1": "The landlord has given the tenant notice of termination of the lease.",
    "E2": "The tenant (or one of several tenants) has given the landlord notice of termination.",
    "E3": "The landlord has set the tenant a written payment deadline with a warning that the lease will be terminated.",
    "E4": "The flat has a defect, or the tenant is disturbed in using it.",
    "E5": "The landlord has given notice of a rent increase or another one-sided change of the contract.",
    "E6": "The tenant has moved out or handed the flat back.",
    "E7": "The tenancy has ended.",
    "E8": "The tenant is married or in a registered partnership.",
    "E9": "The tenant is behind with paying rent or ancillary costs.",
    "E10": "The payment deadline set by the landlord has passed without full payment.",
}
CODE_ONLY = {"E10"}  # decided by code from dates, never asked
_COND = re.compile(r"\b(if|otherwise|unless|or else|threat|threaten|will terminate|would|could|wants? to|plan|"
                   r"thinking|consider|wenn|falls|sonst|androh|will\b|möchte)", re.I)


@lru_cache(maxsize=1)
def table():
    return json.loads(TABLE.read_text(encoding="utf-8")) if TABLE.exists() else {}


def events():
    ev = table().get("events") or DEFAULT_EVENTS
    return {k: (v if isinstance(v, str) else v.get("definition") or v.get("text") or str(v)) for k, v in ev.items()}


def requirements(pid):
    return (table().get("paragraphs") or {}).get(pid)


_ASK = """Read the client's words (numbered sentences). Question: is this statement ALREADY true for the client?
STATEMENT: {event}
Choose one letter:
A = yes, the client's words say it has happened or is true
B = no: it has not happened, or it is only threatened, planned, feared or expected
C = the client's words do not say
Answer JSON only: {{"answer": "A", "sentence": 3}}   (sentence = the number of the sentence that decides it; 0 for C)

CLIENT'S WORDS:
{text}"""


def needed_for(articles):
    """The events that decide the paragraphs of these articles (from the table), plus the basic ones that change
    which rules come into question at all."""
    from . import corpus
    need = {"E1", "E2", "E3", "E4", "E8", "E9"}
    for a in articles:
        for p in corpus.by_article().get(a, []):
            r = requirements(p["id"]) or {}
            need |= set(r.get("needs_all") or []) | set(r.get("needs_any") or [])
    return [k for k in events() if k in need]


def prefill(case, only=None):
    """One closed Apertus call per event, in parallel; code cross-checks the answers."""
    sents = case["sentences"]
    text = "\n".join(f"{i + 1}. {s}" for i, s in enumerate(sents))
    ev = {k: v for k, v in events().items() if k not in CODE_ONLY and (only is None or k in only)}

    def one(k):
        try:
            r = ask_json(_ASK.format(event=ev[k], text=text), trace=case["trace"], step=f"2 event {k}", max_tokens=60)
        except Exception:
            return k, {"answer": "C", "sentence": 0, "quote": "", "source": "AI (no answer)"}
        a = str(r.get("answer", "C")).strip()[:1].upper()
        try:
            n = int(r.get("sentence") or 0)
        except (TypeError, ValueError):
            n = 0
        quote = sents[n - 1] if 1 <= n <= len(sents) else ""
        out = {"answer": a if a in "ABC" else "C", "sentence": n, "quote": quote, "source": "AI"}
        if out["answer"] in "AB" and not quote:  # an answer must point to a real sentence
            out.update(answer="C", note="no valid sentence given")
        if k in ("E1", "E2") and out["answer"] == "A" and _COND.search(quote):
            out.update(answer="C", note="the sentence reads like a threat or a plan; please check")
        return k, out

    with ThreadPoolExecutor(4) as ex:
        status = dict(ex.map(one, ev))
    # documents classified by their own single-job call: agreement is checked, disagreement is shown
    doc_event = {"termination_by_landlord": "E1", "payment_demand_with_termination_warning": "E3",
                 "rent_increase_notice": "E5", "notice_given_by_tenant_or_cotenant": "E2"}
    for d in case.get("documents", []):
        k = doc_event.get(d.get("doc_type"))
        if k and k in status and status[k]["answer"] != "A":
            status[k] = {**status[k], "answer": "C",
                         "note": f"the letter was classified as '{d['doc_type'].replace('_', ' ')}' but the question "
                                 "gave a different answer; please check"}
    hh = case.get("understanding", {}).get("household", {})
    if hh.get("married_or_registered_partner") in ("yes", "no") and "E8" in status:
        want = "A" if hh["married_or_registered_partner"] == "yes" else "B"
        if status["E8"]["answer"] != want:
            status["E8"] = {**status["E8"], "answer": "C", "note": "two readings disagree; please check"}
    case["event_status"] = status
    derive(case)
    return case


def derive(case):
    """Events decided by code from dates (E10: a payment deadline cannot have passed within 30 days of receipt)."""
    st = case.setdefault("event_status", {})
    today = date.fromisoformat(case["today"])
    e10 = {"answer": "C", "sentence": 0, "quote": "", "source": "code"}
    if st.get("E3", {}).get("answer") == "A":
        recv = [e for e in case.get("events", []) if e.get("doc_type") == "payment_demand_with_termination_warning"]
        latest = max((date.fromisoformat(e.get("date") or e.get("date_to") or e["date_from"]) for e in recv
                      if e.get("date") or e.get("date_from")), default=None)
        if latest and latest + timedelta(days=30) > today:
            e10.update(answer="B", note="received less than 30 days ago (the minimum period for flats)")
    elif st.get("E3", {}).get("answer") == "B":
        e10["answer"] = "B"
    st["E10"] = e10
    return case


def confirm(case, edits):
    """edits: {event_id: 'A'|'B'|'C'} from the social worker; recorded as confirmed."""
    st = case.setdefault("event_status", {})
    for k, v in (edits or {}).items():
        if k in st and v in ("A", "B", "C"):
            if st[k]["answer"] != v:
                st[k] = {**st[k], "answer": v, "source": "social worker"}
            st[k]["confirmed"] = True
    derive(case)
    return case


def para_status(pid, status):
    """(status, missing_event_ids) for one paragraph."""
    r = requirements(pid)
    if not r or r.get("general"):
        return "applies", []
    need_all, need_any = r.get("needs_all") or [], r.get("needs_any") or []
    ans = lambda e: status.get(e, {}).get("answer", "C")
    if any(ans(e) == "B" for e in need_all) or (need_any and all(ans(e) == "B" for e in need_any)):
        return "not_yet", [e for e in need_all if ans(e) != "A"] + (need_any if need_any and "A" not in map(ans, need_any) else [])
    missing = [e for e in need_all if ans(e) != "A"]
    if need_any and "A" not in map(ans, need_any):
        missing += need_any
    return ("open", missing) if missing else ("applies", [])
