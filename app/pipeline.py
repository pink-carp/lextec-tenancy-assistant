"""The harness (v2): many small, single-job AI calls; code checks, calculates and assembles.

Design rules learned from testing on 2026-11-08:
- The model writes free JSON (no forced grammar) and code validates it.
- Each AI call does ONE job with a short prompt; independent calls run in parallel.
- Everything extracted must carry the client's own words ("quote"); code drops what the text does not contain.
- Dates are computed by code from the client's words (app/dates.py); deadlines come from the legal team's
  table in deadlines.md, keyed by the type of document received.
- Legal explanations shown on screen are reviewed plain-language summaries of the official text
  (corpus/paragraph_summaries.json); the AI writes only actions and one conditional note per issue,
  and every legal sentence it writes is checked against the cited text before it is shown.
"""
import json
import re
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import date
from functools import lru_cache
from pathlib import Path

from . import checks, contacts, corpus, events, guidance, modules, scoring, writer
from .dates import parse_when
from .deadlines import DeadlineSpec, compute_deadline
from .llm import ask_json

ROOT = Path(__file__).resolve().parent.parent

SYSTEM_ROLE = (
    "You support a social worker in the canton of Zurich, Switzerland, who is talking with a client about a "
    "residential tenancy problem. Everything you produce is LEGAL INFORMATION for the social worker, never legal "
    "advice. Use only the facts given and only the legal sources provided. Never invent facts, dates, articles or "
    "decisions. An unknown fact is unknown, never a 'no'. Write in plain, calm English that a non-lawyer understands."
)

# ---------------------------------------------------------------- step 1: intake (masking)

_MASKS = [
    (re.compile(r"[\w.+-]+@[\w-]+\.[\w.]+"), "[E-MAIL]"),
    (re.compile(r"\bCH\d{2}(?:\s?[0-9A-Z]{4}){4}\s?[0-9A-Z]{1,2}\b"), "[IBAN]"),
    (re.compile(r"\b756[.\s]?\d{4}[.\s]?\d{4}[.\s]?\d{2}\b"), "[AHV-NUMBER]"),
    (re.compile(r"(?:\+41|0041)\s?(?:\(0\)\s?)?\d{2}[\s/.-]?\d{3}[\s.-]?\d{2}[\s.-]?\d{2}\b"), "[PHONE]"),
    (re.compile(r"\b0\d{2}[\s/.-]?\d{3}[\s.-]?\d{2}[\s.-]?\d{2}\b"), "[PHONE]"),
]


def mask(text):
    applied = []
    for rx, repl in _MASKS:
        text, n = rx.subn(repl, text)
        if n:
            applied.append(f"{repl} x{n}")
    return text, applied


def split_sentences(text):
    parts = re.split(r"(?<=[.!?])\s+|\n+", text.strip())
    return [p.strip() for p in parts if p.strip()]


def new_case(description, client_language="English", today=None):
    masked, applied = mask(description)
    return {"id": uuid.uuid4().hex[:12], "today": (today or date.today()).isoformat(),
            "description": description, "masked": masked, "masking": applied,
            "sentences": split_sentences(masked), "client_language": client_language,
            "trace": [], "answers": [], "log": []}


def _d(s):
    try:
        return date.fromisoformat(s) if s else None
    except (ValueError, TypeError):
        return None


# ---------------------------------------------------------------- grounding in the client's words

def _norm(t):
    t = (t or "").lower().replace("’", "'").replace("“", '"').replace("”", '"')
    return re.sub(r"\s+", " ", t).strip(" .,;:!?\"'")


def grounded(quote, text):
    """True if the quoted words really are in the client's text (allowing small copying differences)."""
    q, t = _norm(quote), _norm(text)
    if len(q) < 3:
        return False
    if q in t:
        return True
    words = re.findall(r"\w{4,}", q)
    return bool(words) and sum(w in t for w in words) / len(words) >= 0.8


def _enum(value, allowed, default):
    return value if value in allowed else default


# ---------------------------------------------------------------- reviewed article summaries

@lru_cache(maxsize=1)
def summaries():
    f = ROOT / "corpus" / "paragraph_summaries.json"
    return json.loads(f.read_text(encoding="utf-8")) if f.exists() else {}


def article_summary(key):
    """'OR 257d' -> reviewed plain summary of all its paragraphs (falls back to the official text)."""
    out = []
    for p in corpus.by_article().get(key, []):
        s = summaries().get(p["id"], {}).get("summary")
        out.append(s or p["text"])
    return " ".join(out)


# ---------------------------------------------------------------- step 2: understand (parallel single-job calls)

DOC_TYPES = ["payment_demand_with_termination_warning", "termination_by_landlord", "notice_given_by_tenant_or_cotenant",
             "rent_increase_notice", "court_or_conciliation_document", "other_letter_or_message", "unclear"]
DOC_LABEL = {"payment_demand_with_termination_warning": "payment demand with termination warning",
             "termination_by_landlord": "termination by the landlord",
             "notice_given_by_tenant_or_cotenant": "notice given by a tenant or co-tenant",
             "rent_increase_notice": "rent-increase notice", "court_or_conciliation_document": "court or conciliation document",
             "other_letter_or_message": "letter or message", "unclear": "document (type unclear)"}
INTENTS = ["reduce_or_withhold_rent", "move_out", "ignore_the_letter", "wait_before_paying", "sign_something"]
SITUATIONS = ["defect_in_flat", "no_heating_water_or_power", "deposit_return", "co_tenant_left_or_gave_notice",
              "house_rules_or_pets", "neighbour_disturbance", "rent_increase", "rent_arrears", "termination",
              "moving_out_or_early_departure", "subletting", "ancillary_costs"]
SITUATION_LABEL = {"defect_in_flat": "Defect in the flat", "no_heating_water_or_power": "No heating, water or power",
                   "deposit_return": "Return of the rent deposit", "co_tenant_left_or_gave_notice": "A co-tenant left or gave notice",
                   "house_rules_or_pets": "House rules or pets", "neighbour_disturbance": "Disturbance by neighbours",
                   "rent_increase": "Rent increase", "rent_arrears": "Unpaid rent and payment demand",
                   "termination": "Termination of the lease", "moving_out_or_early_departure": "Moving out early",
                   "subletting": "Subletting", "ancillary_costs": "Ancillary costs"}
AREAS = ["migration", "family", "debt_enforcement", "social_assistance", "criminal", "employment", "other"]
VULN = ["children_or_minors", "pregnancy", "single_parent_household", "violence_threats_or_coercion",
        "disability_or_access_difficulty", "exploitation_or_dependency",
        "severe_financial_hardship_unemployment_or_debt", "language_or_literacy_barrier"]
VULN_LABEL = {"children_or_minors": "children or minors in the household", "pregnancy": "pregnancy",
              "single_parent_household": "single-parent household",
              "violence_threats_or_coercion": "violence, threats or coercion",
              "disability_or_access_difficulty": "disability or difficulty accessing services",
              "exploitation_or_dependency": "exploitation or dependency",
              "severe_financial_hardship_unemployment_or_debt": "severe financial hardship, unemployment or debt",
              "language_or_literacy_barrier": "language or literacy barrier"}


def _prompt_facts(text):
    return ("Read a social worker's description of a client's tenancy problem.\n"
            "1. facts: the key facts (max 10), each under one heading: who, where, what, when, current_position. One short "
            "sentence each, and copy into 'quote' the client's exact words it comes from. Only what the words state.\n"
            "2. disputes: points where the client and another party disagree (max 3). Do not decide them.\n"
            'Answer JSON only: {"facts": [{"heading": "what", "statement": "...", "quote": "..."}], '
            '"disputes": [{"topic": "...", "client_position": "...", "other_party": "...", "other_position": "...", '
            '"evidence_that_could_settle_it": "...", "quote": "..."}]}\n\nDESCRIPTION:\n' + text)


def _prompt_documents(text):
    return ("Read the client's description of a tenancy problem. Record ONLY what the words say; anything not said is "
            '"unknown".\nAnswer JSON only, in this shape:\n'
            '{"documents": [{"client_words": "<the client\'s exact words about this letter or notice>", '
            '"document_type": "' + " | ".join(DOC_TYPES) + '", '
            '"sender": "landlord_or_manager | tenant_or_cotenant | court_or_authority | other | unknown", '
            '"when_words": "<only the client\'s exact words for WHEN it was received, e.g. \'last week\', or empty>"}], '
            '"household": {"married_or_registered_partner": "yes|no|unknown", "children_in_household": "yes|no|unknown"}, '
            '"intends": [{"intent": "' + " | ".join(INTENTS) + '", "quote": "<client\'s exact words>"}]}\n'
            'Rules: list only real letters, notices or forms (not phone calls). "termination_by_landlord" only if the '
            "landlord has actually terminated; a threat to terminate if rent is not paid is a payment demand. A husband or "
            'wife means married; a boyfriend or girlfriend means not married. "yes" only if explicitly stated. "intends" '
            "only for what the client says they are considering doing.\n\nDESCRIPTION:\n" + text)


def _prompt_situation(text):
    return ("Read the client's description of a tenancy problem. Answer JSON only, in this shape:\n"
            '{"situations": [{"situation": "' + " | ".join(SITUATIONS) + '", "quote": "<client\'s exact words>"}], '
            '"cannot_pay": {"stated": "yes|no", "quote": ""}, '
            '"scope": {"tenancy_related": "yes|no|unclear", "residential": "yes|no|unknown", "canton_zurich": "yes|no|unknown", '
            '"municipality": "<as stated, or empty>"}, '
            '"other_areas_of_law": [{"area": "' + " | ".join(AREAS) + '", "quote": "<client\'s exact words>"}], '
            '"client_gender": "female|male|unknown"}\n'
            "Rules: only what the words state. 'termination' only if the lease HAS been terminated (by either side); a "
            "threat to terminate (e.g. if rent is not paid) is not a termination. 'cannot_pay' is yes only if the client says they cannot pay what is owed in "
            "time. 'other_areas_of_law' only for legal matters beyond tenancy that the text raises (e.g. residence permit, "
            "divorce, debt collection). 'client_gender' only from explicit words (she/he, husband/wife, Mrs/Mr), never "
            "from a name. Zurich, Winterthur, Uster, Schlieren etc. are in the canton of Zurich.\n\nDESCRIPTION:\n" + text)


def _prompt_vulnerability(text):
    return ("Read the client's description. Using the personal-vulnerability indicators of the escalation framework, "
            "list ONLY those the words explicitly state for the client or their household, each with the client's exact "
            "words. Never infer from a name, nationality, tone or worry. Also say if anyone is in immediate physical danger.\n"
            'Answer JSON only: {"vulnerability": [{"indicator": "' + " | ".join(VULN) + '", "quote": "..."}], '
            '"immediate_danger": {"stated": "yes|no", "quote": ""}}\n\n'
            "ESCALATION FRAMEWORK:\n" + guidance.escalation() + "\n\nDESCRIPTION:\n" + text)


def _prompt_issues(text):
    return ("You identify the Swiss tenancy-law issues in a client's description. Below is the full tenancy law "
            "(OR Art. 253-274g) with paragraph IDs. List the legal issues (max 5) in plain words and, for each, the "
            'article numbers whose TEXT governs it (e.g. "257d"). Only choose an article if its text clearly concerns the '
            "issue. Include rules that protect the tenant or that create risks for what the client plans to do.\n"
            'Answer JSON only: {"issues": [{"issue": "<plain words>", "articles": ["257d"]}]}\n\n'
            "LAW:\n" + corpus.tenancy_text() + "\n\nDESCRIPTION:\n" + text)


# Safety net: articles that must be considered for a situation (always reviewed by the AI-independent checks)
SAFETY_NET = {
    "defect_in_flat": ["OR 256", "OR 259a", "OR 259b", "OR 259d", "OR 259g"],
    "no_heating_water_or_power": ["OR 256", "OR 259a", "OR 259b", "OR 259d", "OR 259g"],
    "neighbour_disturbance": ["OR 257f", "OR 259a", "OR 259d"],
    "deposit_return": ["OR 257e", "OR 267", "OR 267a"],
    "co_tenant_left_or_gave_notice": ["OR 266l", "OR 544", "OR 143"],
    "house_rules_or_pets": ["OR 256", "OR 257f", "OR 269d"],
    "rent_increase": ["OR 269", "OR 269a", "OR 269d", "OR 270b"],
    "rent_arrears": ["OR 257d", "OR 266n", "OR 272a"],
    "termination": ["OR 266l", "OR 266n", "OR 266o", "OR 271", "OR 271a", "OR 272", "OR 273"],
    "moving_out_or_early_departure": ["OR 264"],
    "subletting": ["OR 262"],
    "ancillary_costs": ["OR 257a", "OR 257b"],
}
DOC_SAFETY_NET = {
    "payment_demand_with_termination_warning": ("rent_arrears", ["OR 257d", "OR 266n", "OR 272a"]),
    "termination_by_landlord": ("termination", ["OR 266l", "OR 266n", "OR 266o", "OR 271", "OR 271a", "OR 272", "OR 273"]),
    "rent_increase_notice": ("rent_increase", ["OR 269", "OR 269a", "OR 269d", "OR 270b"]),
    "notice_given_by_tenant_or_cotenant": ("co_tenant_left_or_gave_notice", ["OR 266l"]),
}
INTENT_SAFETY_NET = {"reduce_or_withhold_rent": ["OR 257d", "OR 259g", "OR 259h"]}
# rules on challenging or extending a termination: only relevant once a termination has actually happened
TERMINATION_CHALLENGE_ARTICLES = {f"OR {a}" for a in ["271", "271a", "272", "272b", "272c", "272d", "273", "273a"]}
DEFECT_ARTICLES = {f"OR {a}" for a in ["259", "259a", "259b", "259c", "259d", "259e", "259f", "259g", "259h", "259i"]}
SPOUSE_ARTICLES = {"OR 266m", "OR 266n", "OR 266o"}


def understand(case):
    text = "\n".join(case["sentences"])
    jobs = {"facts": _prompt_facts, "documents": _prompt_documents, "situation": _prompt_situation,
            "vulnerability": _prompt_vulnerability, "issues": _prompt_issues}
    with ThreadPoolExecutor(5) as ex:
        futs = {k: ex.submit(ask_json, f(text), trace=case["trace"], step=f"2 understand: {k}",
                             max_tokens=1200 if k in ("facts", "issues") else 700) for k, f in jobs.items()}
        out = {k: f.result() for k, f in futs.items()}
    today = date.fromisoformat(case["today"])
    log = case["log"]

    # facts: status by code (a fact is 'documented' only once a document has been uploaded)
    facts = []
    for f in (out["facts"].get("facts") or [])[:10]:
        if not isinstance(f, dict) or not f.get("statement"):
            continue
        ok = grounded(f.get("quote", ""), text)
        facts.append({"id": f"F{len(facts) + 1}", "heading": _enum(f.get("heading"), ["who", "where", "what", "when", "current_position"], "what"),
                      "statement": mask(f["statement"])[0], "quote": f.get("quote", "") if ok else "",
                      "status": "reported" if ok else "inferred"})
    disputes = []
    for d in (out["facts"].get("disputes") or [])[:3]:
        if isinstance(d, dict) and d.get("topic") and grounded(d.get("quote", "") or d.get("client_position", ""), text):
            disputes.append({"id": f"X{len(disputes) + 1}", **{k: str(d.get(k, "")) for k in
                             ("topic", "client_position", "other_party", "other_position", "evidence_that_could_settle_it")}})

    # documents and dates
    docs, timeline = [], []
    for dd in (out["documents"].get("documents") or [])[:4]:
        if not isinstance(dd, dict):
            continue
        cw = dd.get("client_words", "")
        if not grounded(cw, text):
            log.append(f"Document dropped (words not in the description): {cw[:60]}")
            continue
        dtype = _enum(dd.get("document_type"), DOC_TYPES, "unclear")
        when_words = dd.get("when_words") or ""
        if when_words and not grounded(when_words, text):
            when_words = ""
        w = parse_when(when_words, today) if when_words else parse_when(cw, today)
        doc = {"id": f"L{len(timeline) + 1}", "doc_type": dtype, "event": f"{DOC_LABEL[dtype].capitalize()} received",
               "client_words": cw, "sender": dd.get("sender", "unknown"), "when_words": when_words,
               "precision": w["precision"], "date": w["date_from"].isoformat() if w["precision"] == "exact" else "",
               "date_from": w["date_from"].isoformat() if w["date_from"] else "",
               "date_to": w["date_to"].isoformat() if w["date_to"] else "", "explanation": w["explanation"]}
        docs.append(doc)
        timeline.append(doc)
    hh = out["documents"].get("household") or {}
    household = {"married_or_registered_partner": _enum(hh.get("married_or_registered_partner"), ["yes", "no", "unknown"], "unknown"),
                 "children_in_household": _enum(hh.get("children_in_household"), ["yes", "no", "unknown"], "unknown")}
    intents = [i for i in (out["documents"].get("intends") or []) if isinstance(i, dict)
               and i.get("intent") in INTENTS and grounded(i.get("quote", ""), text)]

    # situation and scope
    sit = out["situation"]
    situations = [s for s in (sit.get("situations") or []) if isinstance(s, dict)
                  and s.get("situation") in SITUATIONS and grounded(s.get("quote", ""), text)]
    cp = sit.get("cannot_pay") or {}
    cannot_pay = cp.get("stated") == "yes" and grounded(cp.get("quote", ""), text)
    sc = sit.get("scope") or {}
    scope = {"tenancy_related": _enum(sc.get("tenancy_related"), ["yes", "no", "unclear"], "unclear"),
             "residential": _enum(sc.get("residential"), ["yes", "no", "unknown"], "unknown"),
             "canton_zurich": _enum(sc.get("canton_zurich"), ["yes", "no", "unknown"], "unknown")}
    areas = [a for a in (sit.get("other_areas_of_law") or []) if isinstance(a, dict)
             and a.get("area") in AREAS and grounded(a.get("quote", ""), text)]
    scope["other_areas_of_law"] = sorted({a["area"].replace("_", " ") for a in areas})
    gender = _enum(sit.get("client_gender"), ["female", "male", "unknown"], "unknown")

    # vulnerability indicators: only those backed by the client's words
    vv = out["vulnerability"]
    vind = []
    for v in (vv.get("vulnerability") or []):
        if isinstance(v, dict) and v.get("indicator") in VULN and grounded(v.get("quote", ""), text) \
                and v["indicator"] not in [x["indicator"] for x in vind]:
            vind.append({"indicator": v["indicator"], "quote": v.get("quote", "")})
    dg = vv.get("immediate_danger") or {}
    danger = dg.get("stated") == "yes" and grounded(dg.get("quote", ""), text)

    # issues and articles: the AI's choice is kept; the safety net and guards are applied by assemble_issues(),
    # again after the social worker has confirmed the deciding facts
    ai_issues = []
    for i in (out["issues"].get("issues") or [])[:5]:
        if not isinstance(i, dict) or not i.get("issue"):
            continue
        arts = []
        for a in i.get("articles") or []:
            m = re.match(r"\s*(?:Art\.?\s*)?(\d+[a-z]?)", str(a))
            k = f"OR {m.group(1)}" if m else None
            if k and k in corpus.by_article() and k not in arts:
                arts.append(k)
        ai_issues.append({"issue": i["issue"], "articles": arts, "source": "AI"})
    # warning signs (shown in step 2, confirmable)
    signals = []
    kind_of = {"termination_by_landlord": "termination_notice", "court_or_conciliation_document": "court_or_enforcement_step",
               "payment_demand_with_termination_warning": "payment_demand", "rent_increase_notice": "other_deadline"}
    for d in docs:
        if d["doc_type"] in kind_of:
            signals.append({"id": f"W{len(signals) + 1}", "index": "urgency", "kind": kind_of[d["doc_type"]],
                            "description": DOC_LABEL[d["doc_type"]].capitalize(), "quote": d["client_words"],
                            "tense": "current", "concerns": "client", "confirmed": True})
    for v in vind:
        signals.append({"id": f"W{len(signals) + 1}", "index": "vulnerability", "kind": v["indicator"],
                        "description": VULN_LABEL[v["indicator"]].capitalize(), "quote": v["quote"],
                        "tense": "current", "concerns": "client", "confirmed": True})
    if danger:
        signals.append({"id": f"W{len(signals) + 1}", "index": "severity", "kind": "violence", "description": "Immediate danger",
                        "quote": dg.get("quote", ""), "tense": "current", "concerns": "client", "confirmed": True})
    for a in areas:
        signals.append({"id": f"W{len(signals) + 1}", "index": "complexity", "kind": "other_area_of_law",
                        "description": f"Other area of law: {a['area'].replace('_', ' ')}", "quote": a.get("quote", ""),
                        "tense": "current", "concerns": "client", "confirmed": True})
    if cannot_pay:
        signals.append({"id": f"W{len(signals) + 1}", "index": "severity", "kind": "cannot_pay",
                        "description": "Client says they cannot pay in time", "quote": cp.get("quote", ""),
                        "tense": "current", "concerns": "client", "confirmed": True})
    for s in situations:
        if s["situation"] == "no_heating_water_or_power":
            signals.append({"id": f"W{len(signals) + 1}", "index": "severity", "kind": "essential_needs",
                            "description": "No heating, water or power", "quote": s.get("quote", ""),
                            "tense": "current", "concerns": "client", "confirmed": True})

    n_v = len(vind)
    score = {0: 2, 1: 4, 2: 7}.get(n_v, 8)  # two indicators already count as high: lean towards the higher lane
    if {"violence_threats_or_coercion", "exploitation_or_dependency"} & {v["indicator"] for v in vind}:
        score = 9
    case.update({
        "ai_issues": ai_issues,
        "understanding": {"issues": [], "scope": scope, "topics": _topics(vind, areas, cannot_pay),
                          "immediate_danger": danger, "client_gender": gender, "household": household,
                          "documents_mentioned": [{"document": d["client_words"]} for d in docs]},
        "facts": facts, "disputes": disputes, "events": timeline, "documents": docs, "intents": intents,
        "situations": situations, "signals": signals, "vulnerability_indicators": [v["indicator"] for v in vind],
        "vulnerability_score": score,
        "vulnerability_source": (f"suggested from {n_v} indicator(s) stated in the description"
                                 + (": " + ", ".join(VULN_LABEL[v["indicator"]] for v in vind) if vind else "")
                                 + "; please confirm or change"),
        "municipality": (sit.get("scope") or {}).get("municipality", ""),
    })
    assemble_issues(case)  # first pass: the articles in question decide which events need asking
    arts = [a for i in case["understanding"]["issues"] for a in i["articles"]]
    events.prefill(case, only=events.needed_for(arts))  # one closed call per event, confirmed in step 2
    assemble_issues(case)
    case["modules_suggested"], case["modules_suggested_by"] = modules.suggest_ai(case)
    case["modules"] = list(case["modules_suggested"])
    deadlines(case)  # no AI involved: available already for the provisional lane
    return case


def assemble_issues(case):
    """AI-chosen articles + safety net, with guards from the deciding events (confirmed ones once step 2 is done).
    A guard removes articles whose event has clearly NOT happened; unknown events keep them (as 'open')."""
    log = case["log"]
    ev = {k: v.get("answer") for k, v in case.get("event_status", {}).items()}
    hh = case["understanding"]["household"]
    no = lambda k: ev.get(k) == "B"
    married_no = no("E8") or (not ev.get("E8") and hh.get("married_or_registered_partner") == "no")
    terminated_no = no("E1") and no("E2")
    docs, situations, intents = case.get("documents", []), case.get("situations", []), case.get("intents", [])
    sit_names = {s["situation"] for s in situations}
    for d in docs:
        if d["doc_type"] in DOC_SAFETY_NET:
            sit_names.add(DOC_SAFETY_NET[d["doc_type"]][0])
    # a payment demand that threatens termination is not a termination (unless one is confirmed)
    threat_only = any(d["doc_type"] == "payment_demand_with_termination_warning" for d in docs) and not any(
        d["doc_type"] in ("termination_by_landlord", "notice_given_by_tenant_or_cotenant") for d in docs)
    if terminated_no or (threat_only and ev.get("E1") != "A" and ev.get("E2") != "A"):
        sit_names.discard("termination")
        terminated_no = True
    defect_no = no("E4") and not (sit_names & {"defect_in_flat", "no_heating_water_or_power", "neighbour_disturbance"})

    def guard(arts, label):
        keep = [a for a in arts if not (defect_no and a in DEFECT_ARTICLES) and not (married_no and a in SPOUSE_ARTICLES)
                and not (terminated_no and a in TERMINATION_CHALLENGE_ARTICLES)]
        if keep != arts:
            log.append(f"Guard removed {sorted(set(arts) - set(keep))} from '{label}' (event has not happened)")
        return keep

    issues = []
    for i in case.get("ai_issues", []):
        arts = guard(i["articles"], i["issue"])
        if arts:
            issues.append({**i, "articles": arts})
    covered = {a for i in issues for a in i["articles"]}
    for s in sorted(sit_names):
        need = guard([a for a in SAFETY_NET.get(s, []) if a in corpus.by_article() and a not in covered], s)
        if need:
            issues.append({"issue": SITUATION_LABEL[s], "articles": need, "source": "safety net"})
            covered |= set(need)
    for it in intents:
        need = guard([a for a in INTENT_SAFETY_NET.get(it["intent"], []) if a not in covered], it["intent"])
        if need:
            issues.append({"issue": "What the client is considering: " + it["intent"].replace("_", " "),
                           "articles": need, "source": "safety net"})
            covered |= set(need)
    for iss in issues:
        iss["summaries"] = {a: article_summary(a) for a in iss["articles"]}
    case["understanding"]["issues"] = issues[:6]
    return case


def _topics(vind, areas, cannot_pay):
    t = []
    ind = {v["indicator"] for v in vind}
    if "violence_threats_or_coercion" in ind:
        t.append("domestic_violence")
    if "disability_or_access_difficulty" in ind:
        t.append("disability")
    if "exploitation_or_dependency" in ind:
        t.append("trafficking_exploitation")
    if "language_or_literacy_barrier" in ind:
        t.append("language_barrier")
    if cannot_pay or "severe_financial_hardship_unemployment_or_debt" in ind:
        t.append("debt")
    if any(a["area"] == "migration" for a in areas):
        t.append("asylum_migration")
    return t


def confirm(case, facts=None, signals=None, vulnerability_score=None, event_edits=None, modules_selected=None):
    """Step 3: the social worker's corrections replace the AI's reading; issues are rebuilt from the confirmed events."""
    events.confirm(case, event_edits)
    if modules_selected is not None:
        case["modules"] = [m for m in modules_selected if m in modules.load()]
    assemble_issues(case)
    if facts is not None:
        for f in facts:
            f["statement"] = mask(f["statement"])[0]
        case["facts"] = facts
    if signals is not None:
        case["signals"] = signals
    if vulnerability_score is not None:
        case["vulnerability_score"] = int(vulnerability_score)
        case["vulnerability_source"] = "social worker"
    case["log"].append("Social worker confirmed the case file")
    return case


# ---------------------------------------------------------------- step 4: sources (code)

def gather_sources(case):
    chosen = []
    for iss in case["understanding"]["issues"]:
        for a in iss["articles"]:
            if a not in chosen:
                chosen.append(a)
    if not chosen:
        chosen = ["OR 253", "OR 256"]
        case["log"].append("No articles identified; fell back to OR 253 and OR 256")
    expanded, reasons = corpus.expand_articles(chosen)
    sources = {}
    for p in corpus.paragraphs_for(expanded):
        sources[p["id"]] = {"type": "law", "label": p["id"], "text": p["text"], "url": p["url"],
                            "article": f"{p['law']} {p['article']}", "version": p["version_date"],
                            "summary": summaries().get(p["id"], {}).get("summary", "")}
    bases = [pid for d in case.get("deadlines", []) for pid in d["legal_basis"]]  # always citable
    bases += [pid for q in case.get("questions", []) for pid in q.get("legal_basis", [])]
    bases += [pid for m in modules.active(case) for k in ("questions", "points", "actions")
              for it in m.get(k) or [] for pid in it.get("basis") or []]
    for pid in bases:
        p = corpus.by_id().get(pid)
        if p:
            sources.setdefault(pid, {"type": "law", "label": pid, "text": p["text"], "url": p["url"],
                                     "article": f"{p['law']} {p['article']}", "version": p["version_date"],
                                     "summary": summaries().get(pid, {}).get("summary", "")})
    case["articles_chosen"] = chosen
    case["articles_expanded"] = reasons
    case["sources"] = sources
    return case


def facts_block(case):
    out = [f"{f['id']} [{f['heading']}, {f['status']}]: {f['statement']}" for f in case.get("facts", [])]
    for d in case.get("disputes", []):
        out.append(f"{d['id']} [disputed] {d['topic']}: client says {d['client_position']}; {d['other_party']} says {d['other_position']}")
    for e in case.get("events", []):
        when = e["date"] if e["precision"] == "exact" else (f"between {e['date_from']} and {e['date_to']}" if e["date_from"] else "date unknown")
        out.append(f"{e['id']} [event] {e['event']}: {when} (client: \"{e.get('client_words', '')[:120]}\")")
    for a in case.get("answers", []):
        if a.get("status") == "answered":
            out.append(f"Answer to {a['question_id']} ({a.get('question', '')}): {a['value']} [client's statement, not documented]")
        else:
            out.append(f"{a['question_id']} ({a.get('question', '')}): {a['status'].replace('_', ' ')}")
    for doc in case.get("uploaded", []):
        out.append(f"[document uploaded, text confirmed by the social worker] {doc['name']}: {doc['text'][:800]}")
    return "\n".join(out)


# ---------------------------------------------------------------- step 5: questions (one small call per issue)

def _articles(case):
    out = []
    for iss in case["understanding"]["issues"]:
        out += [a for a in iss["articles"] if a not in out]
    return out


def questions(case):
    """Step 5: the checked questions of the confirmed situation modules; Apertus pre-fills answers the description
    already gives (with the sentence), the social worker confirms. (v3 generative questions: writer.questions.)"""
    modules.questions(case)
    case["dropped_questions"] = []
    return case


# ---------------------------------------------------------------- step 7: deadlines (legal team's table, by code)

# deadlines.md section 4, keyed by the type of document the client received
DEADLINE_TABLE = {
    "payment_demand_with_termination_warning": [
        ("Pay the arrears in full within the payment period set in the letter (for flats at least 30 days after "
         "receipt; the date in the letter governs)", "OR Art. 257d Abs. 1"),
    ],
    "termination_by_landlord": [
        ("Challenge the termination at the conciliation authority", "OR Art. 273 Abs. 1"),
        ("If staying longer is the goal: request an extension of the tenancy at the conciliation authority "
         "(not possible after a termination for unpaid rent)", "OR Art. 273 Abs. 2"),
    ],
    "rent_increase_notice": [
        ("Challenge the rent increase at the conciliation authority", "OR Art. 270b Abs. 1"),
    ],
}


DEADLINE_KIND = {"OR Art. 257d Abs. 1": "payment_demand", "OR Art. 273 Abs. 1": "termination_challenge",
                 "OR Art. 273 Abs. 2": "termination_extension", "OR Art. 270b Abs. 1": "rent_increase_challenge"}


def deadlines(case):
    out = []
    for e in case.get("events", []):
        for action, basis in DEADLINE_TABLE.get(e.get("doc_type"), []):
            d = {"id": f"D{len(out) + 1}", "kind": DEADLINE_KIND[basis], "action": action, "legal_basis": [basis], "who_must_act": "client",
                 "direction": "forward", "trigger_event_id": e["id"], "check": "legal team's deadline table"}
            if e["precision"] == "exact" and _d(e["date"]):
                t0 = t1 = _d(e["date"])
                steps = [f"Received on {t0.isoformat()} ({e.get('source', 'from the description')})."]
            elif e["precision"] == "estimate" and _d(e["date_from"]):
                t0, t1 = _d(e["date_from"]), _d(e["date_to"]) or _d(e["date_from"])
                steps = [f"Receipt date not known exactly: {e['explanation']}"]
            else:
                out.append({**d, "earliest": None, "latest": None, "determinable": False, "precautionary": False,
                            "not_determinable_reason": "missing_fact",
                            "steps": ["Not calculated yet: the date the document was received is unknown (see the question)."]})
                continue
            res = compute_deadline(DeadlineSpec(period_amount=30, period_unit="days", direction="forward",
                                                trigger_earliest=t0, trigger_latest=t1, shift_final_day=True,
                                                court_holidays_apply=False))
            res["steps"] = steps + res["steps"] + ["Period: 30 days (" + basis + ", deadlines.md section 4)."]
            out.append({**d, **res, "not_determinable_reason": "none"})
        if e.get("doc_type") == "court_or_conciliation_document":
            out.append({"id": f"D{len(out) + 1}", "action": "A court or conciliation document sets its own time limit: have a "
                        "professional check it today", "legal_basis": [], "who_must_act": "client", "direction": "forward",
                        "earliest": None, "latest": None, "determinable": False, "precautionary": False,
                        "not_determinable_reason": "legal_uncertainty", "check": "code",
                        "steps": ["The time limit depends on the document and the procedure; it is not calculated here."]})
    if any("tenant_notice" in (m.get("deadlines") or []) for m in modules.active(case)):
        d = modules.tenant_notice_deadline(case)
        if d:
            out.append({**d, "id": f"D{len(out) + 1}"})
    case["deadlines"] = out
    return case


def assess(case):
    """After the answers: dates may have changed, so the deadlines are recalculated (no AI call needed)."""
    deadlines(case)
    gather_sources(case)
    return case


# ---------------------------------------------------------------- step 8: indices and lane (code)

def severity_level(case):
    sig = [s for s in case.get("signals", []) if s.get("confirmed", True)]
    kinds = {s["kind"] for s in sig}
    docs = {e.get("doc_type") for e in case.get("events", [])}
    if "termination_notice" in kinds or "court_or_enforcement_step" in kinds:
        return "high", ["A landlord's termination or a court step concerns the client's home."]
    if "violence" in kinds:
        return "high", ["Immediate danger was stated."]
    if "essential_needs" in kinds:
        return "high", ["No heating, water or power right now."]
    if "cannot_pay" in kinds and "payment_demand" in kinds:
        return "high", ["A payment demand with termination warning, and the client says they cannot pay in time."]
    if docs & set(DOC_TYPES[:5]) or case.get("situations"):
        return "medium", ["Housing or money is at stake: " + ", ".join(sorted(
            {SITUATION_LABEL[s["situation"]] for s in case.get("situations", [])} |
            {DOC_LABEL[d] for d in docs if d in DOC_LABEL and d not in ("other_letter_or_message", "unclear")}))]
    return "low", ["No current housing or financial consequence identified."]


def complexity_level(case):
    sig = [s for s in case.get("signals", []) if s.get("confirmed", True)]
    areas = case["understanding"]["scope"].get("other_areas_of_law", [])
    if any(a in ("migration", "debt enforcement", "criminal") for a in areas) or any(s["kind"] == "violence" for s in sig):
        return "high", ["Another area of law needing specialist advice: " + (", ".join(areas) or "immediate danger")]
    if any(d.get("not_determinable_reason") == "legal_uncertainty" for d in case.get("deadlines", [])):
        return "high", ["A time limit cannot be determined here (court or conciliation document)."]
    if areas or case.get("disputes") or any(s["situation"] == "co_tenant_left_or_gave_notice" for s in case.get("situations", [])):
        why = []
        if areas:
            why.append("other area of law: " + ", ".join(areas))
        if case.get("disputes"):
            why.append("disputed facts that need evidence")
        if any(s["situation"] == "co_tenant_left_or_gave_notice" for s in case.get("situations", [])):
            why.append("several tenants involved")
        return "medium", ["; ".join(why).capitalize()]
    return "low", ["A single tenancy issue without other areas of law."]


def score(case, override=None):
    today = date.fromisoformat(case["today"])
    sig = [s for s in case.get("signals", []) if s.get("confirmed", True)]
    u, ur = scoring.urgency(case.get("deadlines", []), sig, today)
    i, ir = scoring.information(case.get("questions", []), case.get("answers", []), case.get("disputes", []),
                                case.get("deadlines", []))
    s, sr = severity_level(case)
    c, cr = complexity_level(case)
    v = scoring.vulnerability_level(case["vulnerability_score"])
    ind = {"urgency": u, "severity": s, "complexity": c, "vulnerability": v, "information": i}
    reasons = {"urgency": ur, "severity": sr, "complexity": cr,
               "vulnerability": [f"Rated {case['vulnerability_score']}/10 ({case['vulnerability_source']})"],
               "information": ir}
    ind_v = set(case.get("vulnerability_indicators", []))
    if "essential_needs" in {x["kind"] for x in sig} and ind["urgency"] == "low":
        ind["urgency"] = "medium"
        reasons["urgency"].append("No heating, water or power right now.")
    if "violence_threats_or_coercion" in ind_v or case["understanding"].get("immediate_danger"):
        ind["urgency"], ind["severity"] = "high", "high"
        reasons["urgency"].append("Violence, threats or danger were stated: safety comes first.")
        reasons["severity"] = ["Violence, threats or danger were stated: the client's safety and home are at risk."]
    for r in case.get("raised", []):  # a confirmed answer such as "no heating in winter, children in the flat"
        for k in r["indices"]:
            if k in ind:
                ind[k] = "high"
                reasons[k] = [f"Confirmed in the follow-up questions. {r['by']}"]
    lane, rule = scoring.decide_lane(ind)
    # hard triggers (docs/framework.md): violence, exploitation or migration status always go to a human
    hard = [t for t, hit in [("violence, threats or coercion", "violence_threats_or_coercion" in ind_v),
                             ("exploitation or dependency", "exploitation_or_dependency" in ind_v),
                             ("immediate danger", bool(case["understanding"].get("immediate_danger"))),
                             ("migration status", "migration" in case["understanding"]["scope"].get("other_areas_of_law", []))] if hit]
    if hard and lane < 3:
        lane, rule = 3, "Lane 3: hard trigger (" + ", ".join(hard) + ") - always referred to a human."
    if not case.get("modules") and lane < 2:
        lane, rule = 2, "Lane 2: this tool has no checked guidance for this situation."
    if override:
        lane, rule = int(override["lane"]), f"Lane {override['lane']}: set by the social worker ({override['reason']})."
    case["indices"], case["index_reasons"], case["lane"], case["lane_rule"] = ind, reasons, lane, rule
    sc = case["understanding"]["scope"]
    case["contacts"] = contacts.select(lane, ind, case["understanding"]["topics"], case.get("municipality", ""),
                                       case["understanding"]["immediate_danger"], case["understanding"].get("client_gender", "unknown"))
    case["scope_note"] = None
    if sc.get("canton_zurich") == "no":
        case["scope_note"] = "This service covers the canton of Zurich only. Federal tenancy law applies everywhere, but contacts and court details here are for Zurich."
    if sc.get("tenancy_related") == "no":
        case["scope_note"] = "This does not appear to be a tenancy problem. The service covers residential tenancy only."
    return case


def provisional_lane(case):
    """Lane before the questions are answered (information treated as open)."""
    tmp = {**case, "questions": [{"id": "x", "priority": "urgent"}], "answers": []}
    score(tmp)
    return {"lane": tmp["lane"], "rule": tmp["lane_rule"], "indices": tmp["indices"]}


# ---------------------------------------------------------------- step 9: write (actions + one note per issue)

def lane_explanation(case):
    """Built by code from the lane rule and the reasons of the indices that are not low."""
    parts = [case["lane_rule"]]
    for k in ("severity", "urgency", "vulnerability", "complexity"):
        if case["indices"].get(k) in ("medium", "high"):
            parts.append(f"{k.capitalize()} {case['indices'][k]}: " + "; ".join(case["index_reasons"][k]))
    return " ".join(p if p.endswith(".") else p + "." for p in parts)


def allowed_dates(case):
    out = {date.fromisoformat(case["today"])}
    for d in case.get("deadlines", []):
        for k in ("earliest", "latest"):
            v = d.get(k)
            if v:
                out.add(v if isinstance(v, date) else _d(v))
    for e in case.get("events", []):
        for k in ("date", "date_from", "date_to"):
            if _d(e.get(k)):
                out.add(_d(e[k]))
    return {x for x in out if x} | checks.mentioned_dates(facts_block(case))


def situation_summary(case):
    """Apertus: two neutral sentences on the client's situation and goal (facts only); code removes law and dates."""
    prompt = ("Write two neutral sentences for a social worker summarising the client's situation and what the client "
              "wants. Facts only, from the client's words; no legal rules, no advice, no article numbers, no dates that "
              "the client did not give. 'Kündigung' means termination (not eviction).\nAnswer JSON only: {\"situation\": \"...\"}\n\nCLIENT'S WORDS:\n"
              + "\n".join(case["sentences"]))
    try:
        return str(ask_json(prompt, trace=case["trace"], step="9 situation summary", max_tokens=200).get("situation", ""))
    except Exception:  # noqa: BLE001
        return ""


def write(case):
    """Step 9 (v4): checked module content whose conditions hold; Apertus writes only the situation summary."""
    blocks, acts, lawyer = modules.assemble(case)
    note = None
    if not blocks:
        note = ("This tool has no checked guidance for this situation. Please refer the client to the tenant association "
                "or another advice service listed below.")
    case["screen"] = {"situation": situation_summary(case), "modules": blocks, "actions": acts, "issues": [],
                      "open_points": [], "lawyer_questions": lawyer, "out_of_scope": note,
                      "lane_explanation": lane_explanation(case)}
    return case


def verify(case, applicability=True):
    """Step 10 (v4): the only AI-written text on screen is the situation summary: code removes article references and
    dates that are not in the case. Module content is checked offline (corpus/modules, review entries)."""
    removed = []
    law_articles = {s["article"] for s in case["sources"].values() if s["type"] == "law"}
    scr = case["screen"]
    scr["situation"] = checks.clean_text(scr["situation"], law_articles, [], allowed_dates(case), "situation", removed)
    case["verification"] = {"removed": removed, "warnings": [], "rules_checked": 0, "rules_total": 0, "unverifiable": False}
    return case


# ---------------------------------------------------------------- full run (used by the benchmark)

def run_all(description, today=None, answers=None, applicability=True):
    case = new_case(description, today=today)
    understand(case)
    gather_sources(case)
    questions(case)
    case["answers"] = answers or []
    assess(case)
    score(case)
    write(case)
    verify(case, applicability=applicability)
    return case


def to_jsonable(obj):
    if isinstance(obj, dict):
        return {k: to_jsonable(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple, set)):
        return [to_jsonable(v) for v in obj]
    if isinstance(obj, date):
        return obj.isoformat()
    return obj
