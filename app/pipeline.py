"""The harness: AI identifies, code checks, calculates and constrains.

Steps (see the plan): 1 intake (mask), 2 understand (AI), 3 confirm (social worker),
4 expand sources (code), 5 questions (AI), 6 answers, 7 deadlines (AI identifies, code calculates),
8 indices and lane (code + AI rubric + social worker), 9 write (AI), 10 verify (code + AI),
11 handout / brief / translation (AI on click), 12 contacts (code).
"""
import json
import re
import uuid
from datetime import date, timedelta

from . import checks, contacts, corpus, guidance, scoring
from .deadlines import DeadlineSpec, compute_deadline, effective_receipt
from .llm import chat

SYSTEM_ROLE = (
    "You support a social worker in the canton of Zurich, Switzerland, who is talking with a client about a "
    "residential tenancy problem. Everything you produce is LEGAL INFORMATION for the social worker, never legal "
    "advice. Use only the facts given and only the legal sources provided. Never invent facts, dates, articles or "
    "decisions. An unknown fact is unknown, never a 'no'. Write in plain, calm English that a non-lawyer understands."
)

# ---------------------------------------------------------------- step 1: intake

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


# ---------------------------------------------------------------- step 2: understand

SIGNAL_KINDS = ["court_or_enforcement_step", "termination_notice", "payment_demand", "other_deadline",
                "housing_loss", "essential_needs", "health", "family", "financial", "violence",
                "migration", "multiple_areas_of_law", "missing_document", "contradiction", "other"]
# escalation.md "Personal Vulnerability" indicators, one per bullet
VULN_INDICATORS = ["children_minors_pregnancy_or_single_parent", "violence_threats_or_coercive_control",
                   "disability_or_difficulty_accessing_services", "exploitation_trafficking_or_dependency",
                   "severe_financial_hardship_unemployment_or_debt", "language_literacy_or_communication_barrier"]
# escalation.md "Severity of Consequences", made concrete for tenancy (which stage the housing risk has reached)
CONSEQUENCES = ["landlord_termination_received", "eviction_or_court_step", "payment_demand_and_cannot_pay",
                "essential_needs_unmet", "payment_demand", "termination_threatened", "rent_increase",
                "defect_impairing_use_or_health", "money_at_stake", "other_legal_consequence"]
SEVERITY_HIGH = {"landlord_termination_received", "eviction_or_court_step", "payment_demand_and_cannot_pay",
                 "essential_needs_unmet"}
TOPICS = ["debt", "financial_hardship", "domestic_violence", "sexual_violence", "asylum_migration", "disability",
          "children_youth", "trafficking_exploitation", "isolation_stress", "language_barrier"]


def understand_schema(n_sentences, article_keys):
    sid = {"type": "array", "maxItems": 6, "items": {"type": "integer", "minimum": 1, "maximum": n_sentences}}
    return {"type": "object", "properties": {
        "language": {"type": "string"},
        "municipality": {"type": "string", "description": "municipality of the rented flat if stated, else empty"},
        "scope": {"type": "object", "properties": {
            "tenancy_related": {"type": "string", "enum": ["yes", "no", "unclear"]},
            "residential": {"type": "string", "enum": ["yes", "no", "unknown"]},
            "canton_zurich": {"type": "string", "enum": ["yes", "no", "unknown"]},
            "other_areas_of_law": {"type": "array", "maxItems": 4, "items": {"type": "string"}}},
            "required": ["tenancy_related", "residential", "canton_zurich", "other_areas_of_law"]},
        "facts": {"type": "array", "maxItems": 10, "items": {"type": "object", "properties": {
            "heading": {"type": "string", "enum": ["who", "where", "what", "when", "current_position"]},
            "statement": {"type": "string"},
            "sentences": sid,
            "status": {"type": "string", "enum": ["reported", "documented", "inferred"]}},
            "required": ["heading", "statement", "sentences", "status"]}},
        "disputes": {"type": "array", "maxItems": 4, "items": {"type": "object", "properties": {
            "topic": {"type": "string"}, "client_position": {"type": "string"},
            "other_party": {"type": "string"}, "other_position": {"type": "string"},
            "sentences": sid, "evidence_that_could_settle_it": {"type": "string"}},
            "required": ["topic", "client_position", "other_party", "other_position", "sentences",
                         "evidence_that_could_settle_it"]}},
        "issues": {"type": "array", "maxItems": 5, "items": {"type": "object", "properties": {
            "issue": {"type": "string", "description": "plain-language legal issue"},
            "articles": {"type": "array", "maxItems": 6, "items": {"type": "string", "enum": article_keys}},
            "why": {"type": "string"}},
            "required": ["issue", "articles", "why"]}},
        "signals": {"type": "array", "maxItems": 8, "items": {"type": "object", "properties": {
            "index": {"type": "string", "enum": ["urgency", "severity", "complexity", "vulnerability", "information"]},
            "kind": {"type": "string", "enum": SIGNAL_KINDS},
            "description": {"type": "string"},
            "concerns": {"type": "string", "enum": ["client", "household_member", "other_person", "unclear"]},
            "tense": {"type": "string", "enum": ["current", "past", "hypothetical", "future"]},
            "sentences": sid},
            "required": ["index", "kind", "description", "concerns", "tense", "sentences"]}},
        "vulnerability_indicators": {"type": "array", "maxItems": 6, "items": {"type": "object", "properties": {
            "indicator": {"type": "string", "enum": VULN_INDICATORS}, "sentences": {**sid, "minItems": 1}},
            "required": ["indicator", "sentences"]}},
        "consequences": {"type": "array", "maxItems": 6, "items": {"type": "object", "properties": {
            "consequence": {"type": "string", "enum": CONSEQUENCES},
            "tense": {"type": "string", "enum": ["current", "past", "hypothetical", "future"]},
            "sentences": {**sid, "minItems": 1}},
            "required": ["consequence", "tense", "sentences"]}},
        "events": {"type": "array", "maxItems": 6, "description": "dated events that may start a deadline (documents received, notices, moving in/out)",
                   "items": {"type": "object", "properties": {
                       "event": {"type": "string"},
                       "precision": {"type": "string", "enum": ["exact", "estimate", "unknown"]},
                       "date": {"type": "string", "description": "YYYY-MM-DD if exact, else empty"},
                       "date_from": {"type": "string", "description": "YYYY-MM-DD lower bound if estimate, else empty"},
                       "date_to": {"type": "string", "description": "YYYY-MM-DD upper bound if estimate, else empty"},
                       "sentences": sid},
                       "required": ["event", "precision", "date", "date_from", "date_to", "sentences"]}},
        "topics": {"type": "array", "maxItems": 4, "items": {"type": "object", "properties": {
            "topic": {"type": "string", "enum": TOPICS}, "sentences": {**sid, "minItems": 1}},
            "required": ["topic", "sentences"]}},
        "client_gender": {"type": "string", "enum": ["female", "male", "unknown"]},
        "immediate_danger": {"type": "boolean", "description": "true only for a current threat to someone's physical safety (violence, threats, unsafe dwelling); never for legal or housing risks"},
        "documents_mentioned": {"type": "array", "maxItems": 5, "items": {"type": "object", "properties": {
            "document": {"type": "string"}, "sentences": sid}, "required": ["document", "sentences"]}},
        "search_terms_de": {"type": "array", "maxItems": 8, "items": {"type": "string"}},
    }, "required": ["language", "municipality", "scope", "facts", "disputes", "issues", "signals", "vulnerability_indicators", "consequences",
                    "events", "topics", "client_gender", "immediate_danger", "documents_mentioned", "search_terms_de"]}


def new_case(description, client_language="English", today=None):
    masked, applied = mask(description)
    sents = split_sentences(masked)
    return {"id": uuid.uuid4().hex[:12], "today": (today or date.today()).isoformat(),
            "description": description, "masked": masked, "masking": applied, "sentences": sents,
            "client_language": client_language, "trace": [], "answers": [], "log": []}


def understand(case):
    keys = corpus.all_article_keys()
    _, toc = corpus.toc_articles()
    numbered = "\n".join(f"S{i + 1}: {s}" for i, s in enumerate(case["sentences"]))
    system = "\n\n".join([
        SYSTEM_ROLE,
        f"Today's date is {case['today']}.",
        "TASK: Read the client's situation (sentences S1...) and build a structured case file.\n"
        "- facts: one fact per item, under the five chronology headings of the method (who, where, what, when, "
        "current position). Cite the sentence numbers. status = 'reported' for the client's own account, "
        "'documented' only if a document was actually seen, 'inferred' if you concluded it rather than read it.\n"
        "- disputes: where the client and another party disagree. Do not decide them.\n"
        "- issues: the legal issues in plain words, each with the relevant articles chosen ONLY from the article "
        "list (tenancy law below in full; other laws in the table of contents). Choose an article only if its text "
        "or heading plainly concerns the issue; never guess from the number. Include procedural and exception "
        "rules that may change the outcome.\n"
        "- Classify documents exactly as described, never more: a payment demand with a termination warning, a "
        "termination notice, a rent-increase notice and court or conciliation papers are different things with "
        "different consequences. Do not assume a termination, a court case or a deadline that the description does "
        "not state; record it as unknown.\n"
        "- Convert relative dates ('today', 'last week', 'two months ago') using today's date.\n"
        "- Keep every text field short (one sentence, under 20 words).\n"
        "- signals: warning signs for the five indices of the escalation framework, judged by meaning, not keywords. "
        "Say who they concern and whether they are current, past, hypothetical or future. Use kind "
        "'payment_demand', 'termination_notice' or 'court_or_enforcement_step' only when that is actually stated "
        "('termination_notice' = the landlord has actually terminated the lease, not merely threatened; a notice "
        "given by the tenant or a co-tenant is not one).\n"
        "- vulnerability_indicators: tick each personal-vulnerability indicator of the escalation framework that "
        "the description states for the client's household, with its sentence numbers. Never infer one from a "
        "name, nationality or tone. Vulnerability never changes legal rights.\n"
        "- consequences: what is at stake, at the stage actually reached: 'landlord_termination_received' only if "
        "the landlord has terminated (a notice by the tenant or a co-tenant is not); 'payment_demand_and_cannot_pay' "
        "only if a payment demand exists AND the client says they cannot pay in time; 'essential_needs_unmet' for "
        "no heating, water or power now; otherwise the lower categories.\n"
        "- events: every event that may start a legal deadline (a document received, a notice, a collection slip, "
        "moving in or out). 'today' gives an exact date; 'last week' an estimate range; unknown otherwise.\n"
        "- topics: only support needs actually stated in the description, each with its sentence numbers. "
        "Definitions: debt = unpaid bills or arrears; financial_hardship = not enough money to live; domestic_violence = "
        "violence, threats or coercive control by a partner or family member; sexual_violence = sexual assault or "
        "harassment; asylum_migration = asylum or residence status matters; disability = a stated disability or "
        "illness affecting daily life; children_youth = a child or young person at risk; trafficking_exploitation = "
        "forced work or exploitation; isolation_stress = loneliness or emotional strain; language_barrier = limited "
        "command of the local language. Pressure from a landlord is NOT violence. Never infer sensitive topics.\n"
        "- client_gender: 'female' or 'male' only from explicit words about the client (she/he, woman/man, widow/"
        "widower, Mrs/Mr); never from a first name; otherwise 'unknown'.\n"
        "- search_terms_de: 3-8 German legal terms to search Swiss court decisions (e.g. 'Zahlungsrückstand').",
        "METHOD (legal team, legal_workflow.md):\n" + guidance.legal_workflow(),
        "ESCALATION FRAMEWORK (legal team, escalation.md):\n" + guidance.escalation(),
        "TENANCY LAW (OR Art. 253-274g, official text, citation IDs in brackets):\n" + corpus.tenancy_text(),
        "TABLE OF CONTENTS OF OTHER LAWS (article: heading):\n" + toc,
    ])
    out = chat([{"role": "system", "content": system}, {"role": "user", "content": numbered}],
               schema=understand_schema(len(case["sentences"]), keys), schema_name="case_file",
               max_tokens=3500, trace=case["trace"], step="2 understand")
    # code checks on the extraction
    n = len(case["sentences"])
    topics = []
    for t in out["topics"]:  # a topic needs a real source sentence, otherwise it is dropped
        if any(1 <= s <= n for s in t["sentences"]) and t["topic"] not in topics:
            topics.append(t["topic"])
        elif t["topic"] not in topics:
            case["log"].append(f"Topic '{t['topic']}' dropped: no valid source sentence")
    out["topic_evidence"], out["topics"] = out["topics"], topics
    out["search_terms_de"] = list(dict.fromkeys(out["search_terms_de"]))
    for iss in out["issues"]:
        iss["articles"] = list(dict.fromkeys(iss["articles"]))
    for i, e in enumerate(out["events"]):
        e["id"] = f"E{i + 1}"
        if e["precision"] == "exact" and not _d(e["date"]):
            e["precision"] = "estimate" if (_d(e["date_from"]) or _d(e["date_to"])) else "unknown"
    case["events"] = out["events"]
    for i, f in enumerate(out["facts"]):
        f["id"] = f"F{i + 1}"
        f["sentences"] = [s for s in f["sentences"] if 1 <= s <= n]
        if not f["sentences"] and f["status"] != "inferred":
            f["status"] = "inferred"  # no source sentence: shown as 'inferred - please check'
            case["log"].append(f"{f['id']} had no valid source sentence; marked inferred")
    for i, s in enumerate(out["signals"]):
        s["id"] = f"W{i + 1}"
        s["confirmed"] = True
    for i, d in enumerate(out["disputes"]):
        d["id"] = f"X{i + 1}"
    case["understanding"] = out
    case["facts"] = out["facts"]
    case["disputes"] = out["disputes"]
    case["signals"] = out["signals"]
    # code turns the ticked indicators into levels (only those with a real source sentence count)
    vind = sorted({v["indicator"] for v in out["vulnerability_indicators"] if any(1 <= x <= n for x in v["sentences"])})
    score = {0: 2, 1: 4, 2: 6}.get(len(vind), 8)
    if {"violence_threats_or_coercive_control", "exploitation_trafficking_or_dependency"} & set(vind):
        score = max(score, 8)
    case["vulnerability_indicators"] = vind
    case["vulnerability_score"] = score
    case["vulnerability_source"] = (f"suggested from {len(vind)} indicator(s) of escalation.md"
                                    + (f": {', '.join(v.replace('_', ' ') for v in vind)}" if vind else "")
                                    + "; not yet confirmed by the social worker")
    cons = [c for c in out["consequences"] if any(1 <= x <= n for x in c["sentences"])]
    case["consequences"] = cons
    case["municipality"] = out["municipality"]
    return case


def confirm(case, facts=None, signals=None, vulnerability_score=None):
    """Step 3: the social worker's corrections replace the AI's reading."""
    if facts is not None:
        for f in facts:  # the social worker's edits are masked too
            f["statement"] = mask(f["statement"])[0]
        case["facts"] = facts
    if signals is not None:
        case["signals"] = signals
    if vulnerability_score is not None:
        case["vulnerability_score"] = int(vulnerability_score)
        case["vulnerability_source"] = "social worker"
    case["log"].append("Social worker confirmed the case file")
    return case


# ---------------------------------------------------------------- step 4: expand sources (code)

def gather_sources(case):
    chosen = []
    for iss in case["understanding"]["issues"]:
        for a in iss["articles"]:
            if a not in chosen:
                chosen.append(a)
    if not chosen:  # nothing identified (vague or out-of-scope description): start from the general tenancy rules
        chosen = ["OR 253", "OR 256"]
        case["log"].append("No articles identified; fell back to OR 253 and OR 256")
    expanded, reasons = corpus.expand_articles(chosen)
    query = " ".join(case["understanding"]["search_terms_de"])
    decs = corpus.relevant_decisions(expanded, query, k=6)
    comm = corpus.relevant_commentary(expanded, query, k=3)
    sources = {}
    for p in corpus.paragraphs_for(expanded):
        sources[p["id"]] = {"type": "law", "label": p["id"], "text": p["text"], "url": p["url"],
                            "article": f"{p['law']} {p['article']}", "version": p["version_date"]}
    for d in decs:
        sources[d["id"]] = {"type": "decision", "label": d["id"], "text": d["regeste"] + "\n[Excerpt] " + d["passage"],
                            "url": d["url"], "date": d["date"]}
    case["articles_chosen"] = chosen
    case["articles_expanded"] = reasons
    case["sources"] = sources
    case["commentary"] = comm
    return case


def sources_block(case, with_text=True):
    lines = []
    for sid, s in case["sources"].items():
        lines.append(f"[{sid}] {s['text'] if with_text else ''}".strip())
    if case.get("commentary"):
        lines.append("\nBACKGROUND COMMENTARY (not citable; cite the article or decision it names instead):")
        for c in case["commentary"]:
            lines.append(f"({c['source']}) {c['text'][:1100]}")
    return "\n".join(lines)


def facts_block(case):
    out = [f"{f['id']} [{f['heading']}, {f['status']}]: {f['statement']}" for f in case["facts"]]
    for d in case.get("disputes", []):
        out.append(f"{d['id']} [disputed] {d['topic']}: client says {d['client_position']}; {d['other_party']} says {d['other_position']}")
    for a in case.get("answers", []):
        if a.get("status") == "answered":
            out.append(f"Answer to {a['question_id']} ({a.get('question', '')}): {a['value']} [client's statement, not documented]")
        else:
            out.append(f"{a['question_id']} ({a.get('question', '')}): {a['status'].replace('_', ' ')}")
    return "\n".join(out)


# ---------------------------------------------------------------- step 5: questions

def critic(case, qs):
    """Second short AI pass: drop questions whose cited law does not concern them, that the facts already
    answer, or that ask the client for a legal judgement."""
    listing = "\n".join(
        f"Q{n + 1}: {q['question']} | cites: " + " | ".join(f"[{s}] {case['sources'][s]['text'][:300]}" for s in q["legal_basis"])
        for n, q in enumerate(qs))
    schema = {"type": "object", "properties": {"reviews": {"type": "array", "maxItems": 10, "items": {"type": "object", "properties": {
        "q": {"type": "integer"}, "keep": {"type": "boolean"}, "reason": {"type": "string"}},
        "required": ["q", "keep", "reason"]}}}, "required": ["reviews"]}
    system = ("You review follow-up questions for a Swiss tenancy case. Drop a question ONLY if (a) its cited law "
              "clearly has nothing to do with what it asks, (b) the FACTS already answer it exactly, or (c) it asks the "
              "client for a legal judgement instead of a fact. Otherwise keep it. Reason in under 15 words.")
    out = chat([{"role": "system", "content": system}, {"role": "user", "content": "FACTS:\n" + facts_block(case) + "\n\n" + listing}],
               schema=schema, schema_name="reviews", max_tokens=700, trace=case["trace"], step="5b question critic")
    drop = {r["q"]: r["reason"] for r in out["reviews"] if not r["keep"]}
    kept = []
    for n, q in enumerate(qs):
        if n + 1 in drop and not q.get("added_by"):
            case.setdefault("dropped_questions", []).append({"question": q["question"], "reason": drop[n + 1]})
        else:
            kept.append(q)
    return kept


def questions(case, use_critic=True):
    ids = list(case["sources"].keys())
    event_ids = [e["id"] for e in case.get("events", [])] + ["none"]
    schema = {"type": "object", "properties": {"questions": {"type": "array", "maxItems": 8, "items": {
        "type": "object", "properties": {
            "question": {"type": "string"}, "why_we_ask": {"type": "string"},
            "dates_event": {"type": "string", "enum": event_ids, "description": "for date questions: the EVENT whose date it asks, else 'none'"},
            "legal_basis": {"type": "array", "minItems": 1, "maxItems": 3, "items": {"type": "string", "enum": ids}},
            "resolves": {"type": "string", "description": "which open issue or deadline this settles"},
            "input_type": {"type": "string", "enum": ["date", "yes_no_unknown", "choice", "number", "short_text", "upload"]},
            "options": {"type": "array", "maxItems": 6, "items": {"type": "string"}},
            "priority": {"type": "string", "enum": ["urgent", "core", "helpful"]},
            "answer_instead": {"type": "array", "maxItems": 4, "items": {"type": "string"},
                               "description": "for uploads only: 2-4 questions that capture what the document would show"}},
        "required": ["question", "why_we_ask", "dates_event", "legal_basis", "resolves", "input_type", "options",
                     "priority", "answer_instead"]}}}, "required": ["questions"]}
    system = "\n\n".join([
        SYSTEM_ROLE, f"Today's date is {case['today']}.",
        "TASK: Write the follow-up questions the social worker should ask the client now, so the legal issues can "
        "be assessed. Rules:\n"
        "- One clear, answerable fact per question, in everyday words; never ask the client for a legal judgement.\n"
        "- Every question must serve a legal issue and cite at least one SOURCE by its ID; 'why_we_ask' explains in "
        "two short sentences, for both social worker and client, why the answer matters.\n"
        "- Do not ask what the FACTS already answer.\n"
        "- Whenever a letter, notice or form may start a deadline, ask when and how it was received (date, "
        "registered mail, collection slip) and what exactly it says.\n"
        "- Ask for key documents with input_type 'upload' and give 2-4 'answer_instead' questions.\n"
        "- Ask whether the client is married or in a registered partnership when the family home rules may apply.\n"
        "- priority: 'urgent' = needed to date a running deadline or to rule out a serious risk; 'core' = needed "
        "for the legal assessment; 'helpful' = useful context. Urgent first. At most 8 questions; keep each field short. answer_instead stays empty unless input_type is upload.",
        "METHOD (legal_workflow.md):\n" + guidance.legal_workflow(),
        "QUESTIONNAIRE RULES (output.md):\n" + guidance.section(guidance.output_rules(), "**A. Questionnaire", "**B. Action"),
        "SOURCES (cite by the ID in brackets):\n" + sources_block(case),
    ])
    user = "FACTS:\n" + facts_block(case) + "\n\nLEGAL ISSUES:\n" + "\n".join(
        f"- {i['issue']} ({', '.join(i['articles'])})" for i in case["understanding"]["issues"]) + \
        "\n\nDOCUMENTS MENTIONED:\n" + "\n".join(f"- {d['document']}" for d in case["understanding"]["documents_mentioned"]) + \
        "\n\nEVENTS:\n" + "\n".join(f"{e['id']}: {e['event']} ({e['precision']})" for e in case.get("events", []))
    out = chat([{"role": "system", "content": system}, {"role": "user", "content": user}], schema=schema,
               schema_name="questions", max_tokens=2600, trace=case["trace"], step="5 questions")
    qs = out["questions"]
    if use_critic and qs:
        qs = critic(case, qs)
    # code completeness check: an urgency signal must come with a date question
    has_date_q = any(q["input_type"] == "date" for q in qs)
    urgent_signal = any(s["index"] == "urgency" and s.get("confirmed", True) for s in case["signals"])
    undated = [e for e in case.get("events", []) if e["precision"] != "exact"]
    if urgent_signal and not has_date_q:
        basis = [i for i in ids if i.startswith("ZPO") or "273" in i or "257d" in i][:1] or ids[:1]
        qs.insert(0, {"question": "On what date did the client receive the letter or notice (or the collection slip, if it was sent by registered mail)?",
                      "why_we_ask": "Legal deadlines usually start when a notice is received. Without this date we cannot tell how much time is left.",
                      "legal_basis": basis, "resolves": "start of a running deadline", "input_type": "date", "dates_event": undated[0]["id"] if undated else "none",
                      "options": [], "priority": "urgent", "answer_instead": [], "added_by": "code completeness check"})
    # the same code check as the final text: no law or decision outside the sources, no unexplained dates
    arts = {x["article"] for x in case["sources"].values() if x["type"] == "law"}
    decs = [x["label"] for x in case["sources"].values() if x["type"] == "decision"]
    removed = case.setdefault("question_text_removed", [])
    for q in qs:
        q["why_we_ask"] = checks.clean_text(q["why_we_ask"], arts, decs, allowed_dates(case), f"why: {q['question'][:40]}", removed)
    order = {"urgent": 0, "core": 1, "helpful": 2}
    qs.sort(key=lambda q: order[q["priority"]])
    for i, q in enumerate(qs):
        q["id"] = f"Q{i + 1}"
    case["questions"] = qs
    return case


# ---------------------------------------------------------------- step 7 + 8: deadlines and rubric

def assess_schema(ids, event_ids):
    lvl = {"type": "string", "enum": ["low", "medium", "high"]}
    return {"type": "object", "properties": {
        "deadlines": {"type": "array", "maxItems": 4, "items": {"type": "object", "properties": {
            "action": {"type": "string"}, "legal_basis": {"type": "array", "minItems": 1, "maxItems": 3, "items": {"type": "string", "enum": ids}},
            "who_must_act": {"type": "string", "enum": ["client", "landlord", "authority"]},
            "trigger_event_id": {"type": "string", "enum": event_ids + ["none"]},
            "trigger_is_collection_slip": {"type": "boolean"},
            "receipt_principle": {"type": "string", "enum": ["direct", "absolute", "relative_7day", "not_applicable"]},
            "period_quote": {"type": "string", "description": "the exact words of a cited SOURCE or of the DEADLINE RULES table that set this period, e.g. 'innert 30 Tagen nach Empfang der Kündigung'"},
            "period_amount": {"type": "integer", "minimum": 0}, "period_unit": {"type": "string", "enum": ["days", "months"]},
            "direction": {"type": "string", "enum": ["forward", "backward"]},
            "shift_final_day": {"type": "boolean"}, "court_holidays_apply": {"type": "boolean"},
            "determinable": {"type": "boolean"},
            "not_determinable_reason": {"type": "string", "enum": ["none", "missing_fact", "legal_uncertainty"]},
            "explanation": {"type": "string"}},
            "required": ["action", "legal_basis", "who_must_act", "trigger_event_id", "trigger_is_collection_slip",
                         "receipt_principle", "period_quote", "period_amount", "period_unit", "direction", "shift_final_day",
                         "court_holidays_apply", "determinable", "not_determinable_reason", "explanation"]}},
        "complexity": {"type": "object", "properties": {"level": lvl, "reasons": {"type": "string"},
                                                         "other_areas_of_law": {"type": "array", "maxItems": 4, "items": {"type": "string"}}},
                       "required": ["level", "reasons", "other_areas_of_law"]},
    }, "required": ["deadlines", "complexity"]}


_NUMWORDS = {1: ["ein", "einen", "einem", "one"], 2: ["zwei", "two"], 3: ["drei", "three"], 6: ["sechs", "six"],
             7: ["sieben", "seven"], 10: ["zehn", "ten"], 14: ["vierzehn"], 20: ["zwanzig", "twenty"],
             30: ["dreissig", "thirty"], 60: ["sechzig", "sixty"]}


def _norm(t):
    return re.sub(r"\s+", " ", re.sub(r"[‐-‒–—-]", "-", (t or "").lower())).strip()


def repair_basis_from_table(dl, sources):
    """If the period wording comes from the legal team's deadlines.md table, take the legal basis from that table
    row (e.g. 'Challenge termination | 30 days after receipt | Art. 273(1) OR' -> OR Art. 273 Abs. 1) instead of
    trusting the AI's citation. Adds the paragraph to the case sources if needed."""
    q = _norm(dl.get("period_quote"))
    if len(q) < 6:
        return dl
    for line in guidance.deadlines().splitlines():
        if line.startswith("|") and q in _norm(line):
            ids = []
            for art, para, law in re.findall(r"Art\.\s*(\d+[a-z]?)(?:\((\d+)\))?[^|]*?\b(OR|ZPO)\b", line):
                pid = f"{law} Art. {art}" + (f" Abs. {para}" if para else "")
                cands = [pid] if pid in corpus.by_id() else [p["id"] for p in corpus.by_article().get(f"{law} {art}", [])]
                for c in cands:
                    p = corpus.by_id()[c]
                    sources.setdefault(c, {"type": "law", "label": c, "text": p["text"], "url": p["url"],
                                           "article": f"{p['law']} {p['article']}", "version": p["version_date"]})
                    ids.append(c)
            if ids and not set(ids) & set(dl["legal_basis"]):
                dl["basis_repaired_from"] = list(dl["legal_basis"])
                dl["legal_basis"] = ids
            break
    return dl


def period_is_grounded(dl, sources):
    """Code check against invented deadlines: the period must be quoted from a cited source (or from the
    legal team's deadlines.md) and the quote must contain the period length."""
    q = _norm(dl.get("period_quote"))
    if len(q) < 6:
        return False, "no statutory wording quoted for this period"
    texts = [_norm(sources[s]["text"]) for s in dl["legal_basis"] if s in sources] + [_norm(guidance.deadlines())]
    if not any(q in t for t in texts):
        return False, f"the quoted wording ('{dl['period_quote'][:80]}') is not in the cited source"
    n = dl["period_amount"]
    if not (re.search(rf"\b{n}\b", q) or any(re.search(rf"\b{w}\b", q) for w in _NUMWORDS.get(n, []))):
        return False, f"the quoted wording does not state a period of {n} {dl['period_unit']}"
    unit_words = ("tag", "day") if dl["period_unit"] == "days" else ("monat", "month")
    if not any(w in q for w in unit_words):
        return False, f"the quoted wording does not state the unit ({dl['period_unit']})"
    return True, ""


def _d(s):
    try:
        return date.fromisoformat(s) if s else None
    except ValueError:
        return None


def calculate(dl, events, today):
    """Turn the AI's deadline identification into dates, by code (deadlines.md rules).
    Dates come from the recorded events (description or answers), never from the AI's deadline output."""
    steps = []
    if not dl["determinable"] or dl["period_amount"] <= 0:
        return {"earliest": None, "latest": None, "determinable": False, "precautionary": False,
                "steps": [f"Not calculated: {dl['not_determinable_reason'].replace('_', ' ')}. {dl['explanation']}"]}
    ev = events.get(dl["trigger_event_id"])
    t0 = t1 = None
    if ev and ev["precision"] == "exact" and _d(ev["date"]):
        day = _d(ev["date"])
        if dl["trigger_is_collection_slip"] and dl["receipt_principle"] in ("absolute", "relative_7day"):
            t0, t1, why = effective_receipt(dl["receipt_principle"], notice_slip_date=day)
            steps.append(why)
        else:
            t0 = t1 = day
            steps.append(f"Triggering event: {ev['event']} on {day.isoformat()} ({ev.get('source', 'from the description')}).")
    elif ev and ev["precision"] == "estimate" and (_d(ev["date_from"]) or _d(ev["date_to"])):
        t0, t1 = _d(ev["date_from"]) or _d(ev["date_to"]), _d(ev["date_to"]) or _d(ev["date_from"])
        steps.append(f"Triggering event: {ev['event']}, date not known exactly; estimated between "
                     f"{t0.isoformat()} and {t1.isoformat()} from the description.")
        if dl["trigger_is_collection_slip"] and dl["receipt_principle"] in ("absolute", "relative_7day"):
            t0 = effective_receipt(dl["receipt_principle"], notice_slip_date=t0)[0]
            t1 = effective_receipt(dl["receipt_principle"], notice_slip_date=t1)[1]
            steps.append(f"Receipt rule ({dl['receipt_principle'].replace('_', ' ')}) applied to the estimated "
                         f"collection-slip dates: receipt between {t0.isoformat()} and {t1.isoformat()}.")
    if t0 is None:
        return {"earliest": None, "latest": None, "determinable": False, "precautionary": False,
                "steps": ["Not calculated: the triggering date is unknown (ask the client)."],
                "missing_trigger": True}
    if dl["direction"] == "backward" and t1 <= today:
        return {"earliest": None, "latest": None, "determinable": False, "precautionary": False,
                "steps": steps + ["Not calculated: a backward (notice) period needs a future reference date; "
                                  f"{t1.isoformat()} is not in the future. Check which deadline applies."],
                "missing_trigger": True}
    spec = DeadlineSpec(period_amount=dl["period_amount"], period_unit=dl["period_unit"], direction=dl["direction"],
                        trigger_earliest=t0, trigger_latest=t1, shift_final_day=dl["shift_final_day"],
                        court_holidays_apply=dl["court_holidays_apply"])
    res = compute_deadline(spec)
    res["steps"] = steps + res["steps"]
    if t0 != t1:
        res["precautionary"] = True
    return res


def assess(case):
    ids = [i for i, s in case["sources"].items() if s["type"] == "law"] or list(case["sources"].keys())
    rubric = (
        "COMPLEXITY rubric: high = the outcome depends on another area of law needing specialist advice (e.g. "
        "migration status, debt enforcement proceedings, divorce), conflicting rules, unclear jurisdiction, or "
        "non-standard accommodation; medium = contested facts that need evidence (e.g. suspected retaliation) or "
        "several tenancy issues interacting; low = otherwise.")
    system = "\n\n".join([
        SYSTEM_ROLE, f"Today's date is {case['today']}.",
        "TASK: (1) Identify every legal deadline that may matter now, following DEADLINE RULES exactly, and only "
        "deadlines that are actually running or about to start on the facts (not hypothetical later stages). For "
        "each, name the EVENT (by ID) that starts it; code takes the date from that event. If the client received "
        "the document in person or it is said to be received, receipt_principle is 'direct'; set "
        "trigger_is_collection_slip only if the event is a collection slip for registered mail. direction is "
        "'forward' (counted from the event) for payment, challenge, extension and filing periods; 'backward' only "
        "for notice periods counted back from a future termination or expiry date. Do NOT calculate the final date "
        "yourself: code does that. If a deadline exists but no event dates it, use trigger_event_id 'none' with "
        "determinable=true. Set determinable=false with "
        "reason 'legal_uncertainty' only if you cannot tell which rule applies. Court holidays (Art. 145 ZPO) never "
        "apply to substantive OR periods or to conciliation proceedings. (2) Rate complexity with the "
        "rubric. Keep every text field to one short sentence. List at most the 4 most important deadlines. "
        "List a deadline only if a SOURCE or the DEADLINE RULES table states its period, and copy those exact "
        "words into period_quote; a defect, a repair or a rent reduction has no statutory period unless one is "
        "quoted.",
        "DEADLINE RULES (legal team, deadlines.md):\n" + guidance.deadlines(),
        rubric,
        "SOURCES:\n" + sources_block(case),
    ])
    events = {e["id"]: e for e in case.get("events", [])}
    user = "FACTS:\n" + facts_block(case) + "\n\nEVENTS:\n" + ("\n".join(
        f"{e['id']}: {e['event']} — " + (e["date"] if e["precision"] == "exact" else
                                          f"between {e['date_from']} and {e['date_to']}" if e["precision"] == "estimate" else "date unknown")
        for e in events.values()) or "none recorded")
    out = chat([{"role": "system", "content": system}, {"role": "user", "content": user}],
               schema=assess_schema(ids, list(events)), schema_name="assessment", max_tokens=2200,
               trace=case["trace"], step="7 deadlines + rubric")
    today = date.fromisoformat(case["today"])
    dls, case["dropped_deadlines"] = [], []
    for dl in out["deadlines"]:
        repair_basis_from_table(dl, case["sources"])
        ok, why = period_is_grounded(dl, case["sources"])
        if not ok:  # an invented or unsupported period never reaches the screen
            case["dropped_deadlines"].append({"action": dl["action"], "reason": why})
            continue
        i = len(dls)
        res = calculate(dl, events, today)
        if res.get("missing_trigger"):
            dl["not_determinable_reason"] = "missing_fact"
        dls.append({**dl, "id": f"D{i + 1}", **{k: v for k, v in res.items() if k != "missing_trigger"}})
    # applicability check of each deadline: the period exists in the law (checked above), but does it apply
    # to these facts and to this triggering event?
    if dls:
        claims = []
        for d in dls:
            ev = events.get(d["trigger_event_id"])
            claims.append((f"A deadline to '{d['action']}' ('{d['period_quote']}') applies now, started by: "
                           f"{ev['event'] if ev else 'an event not yet known'}.",
                           [(s, case["sources"][s]["text"]) for s in d["legal_basis"] if s in case["sources"]]))
        try:
            verdicts = check_claims(claims, facts_block(case), case["trace"])
        except Exception as e:  # never sink the case; keep the deadlines, flagged as unchecked
            verdicts = {}
            case["log"].append(f"Deadline applicability check failed: {type(e).__name__}")
        kept = []
        for n, d in enumerate(dls):
            v = verdicts.get(n + 1)
            if v and v["verdict"] in ("not_supported", "not_applicable"):
                case["dropped_deadlines"].append({"action": d["action"], "reason": f"applicability check: {v['reason']}"})
                continue
            if v and v["verdict"] == "conditional":
                d["condition"] = v.get("condition") or v["reason"]
            d["check"] = v["verdict"] if v else "not checked"
            d["id"] = f"D{len(kept) + 1}"
            kept.append(d)
        dls = kept
    case["deadlines"] = dls
    case["rubric"] = {"complexity": out["complexity"]}
    return case


def severity_level(case):
    """escalation.md severity, by code from the ticked consequences (current or future ones count)."""
    live = [c for c in case.get("consequences", []) if c["tense"] in ("current", "future")]
    high = [c["consequence"] for c in live if c["consequence"] in SEVERITY_HIGH]
    if high:
        return "high", [f"{c.replace('_', ' ')}" for c in sorted(set(high))]
    if live:
        return "medium", [f"{c.replace('_', ' ')}" for c in sorted({c['consequence'] for c in live})]
    return "low", ["No current housing or financial consequence identified."]


def score(case, override=None):
    today = date.fromisoformat(case["today"])
    sig = [s for s in case["signals"] if s.get("confirmed", True)]
    u, ur = scoring.urgency(case.get("deadlines", []), sig, today)
    i, ir = scoring.information(case.get("questions", []), case.get("answers", []), case.get("disputes", []),
                                case.get("deadlines", []))
    s, sr = severity_level(case)
    c = case["rubric"]["complexity"]["level"]
    cr = [case["rubric"]["complexity"]["reasons"]]
    if any(d.get("not_determinable_reason") == "legal_uncertainty" for d in case.get("deadlines", [])):
        c = "high"
        cr.append("A deadline could not be determined reliably (legal uncertainty), which counts as complexity.")
    v = scoring.vulnerability_level(case["vulnerability_score"])
    ind = {"urgency": u, "severity": s, "complexity": c, "vulnerability": v, "information": i}
    reasons = {"urgency": ur, "severity": sr, "complexity": cr,
               "vulnerability": [f"Rated {case['vulnerability_score']}/10 ({case['vulnerability_source']})"],
               "information": ir}
    lane, rule = scoring.decide_lane(ind)
    if override:
        lane, rule = int(override["lane"]), f"Lane {override['lane']}: set by the social worker ({override['reason']})."
    case["indices"], case["index_reasons"], case["lane"], case["lane_rule"] = ind, reasons, lane, rule
    sc = case["understanding"]["scope"]
    case["contacts"] = contacts.select(lane, ind, case["understanding"]["topics"], case.get("municipality", ""),
                                       case["understanding"]["immediate_danger"],
                                       case["understanding"].get("client_gender", "unknown"))
    case["scope_note"] = None
    if sc["canton_zurich"] == "no":
        case["scope_note"] = "This service covers the canton of Zurich only. Federal tenancy law applies everywhere, but contacts and court details here are for Zurich."
    if sc["tenancy_related"] == "no":
        case["scope_note"] = "This does not appear to be a tenancy problem. The service covers residential tenancy only."
    return case


# ---------------------------------------------------------------- step 9: write

def write(case):
    ids = list(case["sources"].keys())
    dl_ids = [d["id"] for d in case["deadlines"]] or ["none"]
    ct_ids = [c["id"] for c in case["contacts"]] or ["none"]
    src = {"type": "array", "maxItems": 4, "items": {"type": "string", "enum": ids}}
    schema = {"type": "object", "properties": {
        "actions": {"type": "array", "maxItems": 5, "items": {"type": "object", "properties": {
            "group": {"type": "string", "enum": ["referral", "immediate", "now", "needs_clarification"]},
            "what": {"type": "string"}, "who": {"type": "string", "enum": ["client", "social_worker", "professional"]},
            "when": {"type": "string"}, "deadline_ids": {"type": "array", "maxItems": 3, "items": {"type": "string", "enum": dl_ids}},
            "contact_ids": {"type": "array", "maxItems": 3, "items": {"type": "string", "enum": ct_ids}},
            "depends_on": {"type": "string"}, "sources": src},
            "required": ["group", "what", "who", "when", "deadline_ids", "contact_ids", "depends_on", "sources"]}},
        "situation": {"type": "string", "description": "client's situation and desired outcome, neutral"},
        "issues": {"type": "array", "maxItems": 4, "items": {"type": "object", "properties": {
            "issue": {"type": "string"},
            "rules": {"type": "array", "maxItems": 3, "items": {"type": "object", "properties": {
                "statement": {"type": "string"}, "sources": {"type": "array", "minItems": 1, "maxItems": 3, "items": {"type": "string", "enum": ids}}},
                "required": ["statement", "sources"]}},
            "application": {"type": "string", "description": "how the rules relate to the known facts, neutral, conditional where facts are missing"}},
            "required": ["issue", "rules", "application"]}},
        "open_points": {"type": "array", "maxItems": 5, "items": {"type": "string"}},
        "lane_explanation": {"type": "string"},
    }, "required": ["actions", "situation", "issues", "open_points", "lane_explanation"]}
    lane_txt = f"LANE {case['lane']} ({case['lane_rule']}). Index levels: " + json.dumps(case["indices"])
    dl_txt = "\n".join(
        f"{d['id']}: {d['action']} — " + (f"earliest {d['earliest'].isoformat()}" + (" (precautionary planning date)" if d.get('precautionary') else "")
                                           if d.get("earliest") else "date not yet determinable") +
        f"; basis {', '.join(d['legal_basis'])}" for d in case["deadlines"]) or "none identified"
    ct_txt = "\n".join(f"{c['id']}: {c['name']} — {c['reason_rule']}" for c in case["contacts"]) or "none"
    system = "\n\n".join([
        SYSTEM_ROLE, f"Today's date is {case['today']}.",
        "TASK: Write the social worker's screen as structured data.\n"
        "- actions: short, ordered by urgency. Lane 3: put the referral (group 'referral') and any immediate step "
        "first. Lane 2: separate 'now' from 'needs_clarification'. Refer to deadlines and contacts only by their IDs; "
        "never write a date that is not in DEADLINES or FACTS. Say when an action depends on an open question.\n"
        "- situation, issues, application: a NEUTRAL overview, no opinion and no advice. Every rule statement cites "
        "the SOURCES it relies on; do not name any article or decision that is not in SOURCES. Where facts are "
        "missing, explain conditionally ('If the notice was received on ..., ...').\n"
        "- lane_explanation: two plain sentences on why this lane was assigned, based on the index levels given.\n"
        "- Be concise: each text field one or two short sentences.",
        "OUTPUT RULES (output.md, social worker's screen):\n" + guidance.section(guidance.output_rules(), "**5\\. Social", "**6\\. Client"),
        "SOURCES:\n" + sources_block(case),
    ])
    user = "\n\n".join(["FACTS:\n" + facts_block(case), lane_txt, "DEADLINES (calculated by code):\n" + dl_txt,
                        "CONTACTS (chosen by rule):\n" + ct_txt])
    out = chat([{"role": "system", "content": system}, {"role": "user", "content": user}], schema=schema,
               schema_name="screen", max_tokens=2200, trace=case["trace"], step="9 write")
    for i, a in enumerate(out["actions"]):
        a["id"] = f"A{i + 1}"
    case["screen"] = out
    return case


# ---------------------------------------------------------------- step 10: verify

def check_claims(claims, facts_text, trace=None, model=None, max_tokens=500):
    """Applicability check (D10). claims = [(statement, [(source_id, source_text), ...]), ...].
    One short call per claim, run in parallel: a malformed reply then only leaves that one claim unchecked.
    The checker first quotes the decisive words of the cited text, then judges. Returns {n: verdict} (1-based)."""
    from concurrent.futures import ThreadPoolExecutor
    schema = {"type": "object", "properties": {
        "evidence": {"type": "string", "description": "the decisive words copied from the CITED text, at most 25 words"},
        "verdict": {"type": "string", "enum": ["supported", "conditional", "partly", "not_supported", "not_applicable"]},
        "condition": {"type": "string"},
        "reason": {"type": "string"}}, "required": ["evidence", "verdict", "condition", "reason"]}
    system = ("You are a strict checker of legal citations for Swiss tenancy law. First copy into 'evidence' the "
              "decisive words of the CITED text (at most 25 words; read all of it: a provision often covers more "
              "than one situation), then decide: 'supported' if the cited text states the CLAIM; 'partly' if only "
              "part is supported; 'not_supported' if the cited text does not say it; 'not_applicable' if the cited "
              "rule exists but does not apply to these FACTS (e.g. an exception excludes it, wrong type of lease, "
              "wrong stage of procedure); 'conditional' if it applies only if a fact that is still unknown turns out "
              "to be true (put that fact in 'condition', else leave 'condition' empty). Judge by meaning, not word "
              "matches. Reason in one short sentence.")
    kw = {"model": model} if model else {}

    # Plain-text reply parsed by code: with a JSON schema the model was observed to stall in whitespace
    # before the last field (2026-11-08), so the verdict is asked for as labelled lines instead.
    system += ("\n\nAnswer in exactly four lines:\nEVIDENCE: <decisive words>\nVERDICT: <supported|conditional|partly|"
               "not_supported|not_applicable>\nCONDITION: <unknown fact, or none>\nREASON: <one short sentence>")
    verdict_rx = re.compile(r"VERDICT:\s*\**\s*(supported|conditional|partly|not_supported|not_applicable)", re.I)

    def field(name, text):
        m = re.search(rf"{name}:\s*(.+)", text)
        return m.group(1).strip() if m else ""

    def one(item):
        st, srcs = item
        cited = " | ".join(f"[{sid}] {txt[:1500]}" for sid, txt in srcs)
        try:
            text = chat([{"role": "system", "content": system},
                         {"role": "user", "content": f"FACTS:\n{facts_text}\n\nCLAIM: {st}\nCITED: {cited}"}],
                        max_tokens=max_tokens, trace=trace, step="10 applicability check", **kw)
        except Exception:
            return None
        m = verdict_rx.search(text)
        if not m:
            return None
        cond = field("CONDITION", text)
        return {"evidence": field("EVIDENCE", text), "verdict": m.group(1).lower(),
                "condition": "" if cond.lower() in ("none", "-", "n/a", "") else cond, "reason": field("REASON", text)}

    with ThreadPoolExecutor(4) as ex:
        results = list(ex.map(one, claims))
    return {n + 1: {"claim": n + 1, **v} for n, v in enumerate(results) if v}


def allowed_dates(case):
    """Dates any AI-written text may contain: today, computed deadlines, recorded events, dates in the facts."""
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
    return out | checks.mentioned_dates(facts_block(case))


def verify(case, applicability=True):
    removed, warnings = [], []
    law_articles = {s["article"] for s in case["sources"].values() if s["type"] == "law"}
    decisions = [s["label"] for s in case["sources"].values() if s["type"] == "decision"]
    ok_dates = allowed_dates(case)
    facts_text = facts_block(case)
    scr = case["screen"]
    n_rules_total = sum(len(i["rules"]) for i in scr["issues"])  # counted before any removal

    def cl(text, where):
        return checks.clean_text(text, law_articles, decisions, ok_dates, where, removed)

    scr["situation"] = cl(scr["situation"], "situation")
    scr["lane_explanation"] = cl(scr["lane_explanation"], "lane explanation")
    for a in scr["actions"]:
        a["what"] = cl(a["what"], f"action {a['id']}")
        a["when"] = cl(a["when"], f"action {a['id']} timing")
    for ii, iss in enumerate(scr["issues"]):
        iss["application"] = cl(iss["application"], f"issue {ii + 1} application")
        for r in iss["rules"]:
            r["statement"] = cl(r["statement"], f"issue {ii + 1} rule")
    scr["open_points"] = [cl(p, "open point") for p in scr["open_points"]]

    # AI applicability check of every rule statement against its cited sources and the facts (D10)
    claims = []
    for ii, iss in enumerate(scr["issues"]):
        for ri, r in enumerate(iss["rules"]):
            if r["statement"]:
                claims.append((ii, ri, r))
    case["applicability"] = []
    if applicability and claims:
        try:
            by_n = check_claims([(r["statement"], [(s, case["sources"][s]["text"]) for s in r["sources"]]) for _, _, r in claims],
                                facts_text, case["trace"])
        except Exception as e:  # observed: the checker's reply can be malformed; never sink the whole case
            by_n = {}
            warnings.append({"claim": "all legal statements", "reason": f"The applicability check failed ({type(e).__name__}); statements are shown unchecked."})
        for n, (ii, ri, r) in enumerate(claims):
            v = by_n.get(n + 1)
            if not v:
                r["check"] = "not checked"
                warnings.append({"claim": r["statement"], "reason": "The applicability check could not be completed for this statement."})
                continue
            r["check"] = v["verdict"]
            case["applicability"].append({"claim": r["statement"], **v})
            if v["verdict"] in ("not_supported", "not_applicable"):
                removed.append({"where": f"issue {ii + 1} rule", "sentence": r["statement"],
                                "reason": f"applicability check: {v['verdict'].replace('_', ' ')} — {v['reason']}"})
                r["statement"] = ""
            elif v["verdict"] == "partly":
                warnings.append({"claim": r["statement"], "reason": v["reason"]})
            elif v["verdict"] == "conditional":
                r["condition"] = v.get("condition") or v["reason"]
    for iss in scr["issues"]:
        iss["rules"] = [r for r in iss["rules"] if r["statement"]]
    scr["actions"] = [a for a in scr["actions"] if a["what"]]
    n_removed = sum(1 for r in removed if "rule" in r["where"])
    case["verification"] = {"removed": removed, "warnings": warnings, "rules_checked": len(claims),
                            "rules_total": n_rules_total,
                            "unverifiable": n_rules_total > 0 and n_removed > n_rules_total / 2}
    return case


# ---------------------------------------------------------------- full run (used by the benchmark)

def run_all(description, today=None, answers=None, applicability=True):
    from concurrent.futures import ThreadPoolExecutor
    case = new_case(description, today=today)
    understand(case)
    gather_sources(case)
    case["answers"] = answers or []
    # questions and deadline identification are independent: run them side by side
    with ThreadPoolExecutor(2) as ex:
        fq, fa = ex.submit(questions, case), ex.submit(assess, case)
        fq.result(); fa.result()
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
