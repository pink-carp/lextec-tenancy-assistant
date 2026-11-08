"""v6 Prüfungskern: the team's integrated reasoning method (LIIT_Pruefungskern_v2.0.0, core 2.0.0, modules M01-M09).

How the eight steps are split between Apertus and code:
- K01 facts: the existing reading step (pipeline.understand); the description's numbered sentences are the facts.
  A fact from the client's account is "asserted", never "verified" (core: a narrated fact is not proven).
- K02 applicability: Apertus judges the module's scope (residential tenancy) with a sentence; code sets the temporal
  check (current law) from the recorded dates.
- K03-K05 rights and duties, the legally relevant event, and the selection of remedies (outcomes): one Apertus call
  per confirmed module; every selected outcome needs a reason.
- K06 each element of the selected outcomes: one Apertus call per module (status, sentence numbers, one-line
  reasoning). Code rule from the core: a definitive status without a fact reference becomes "unknown".
- Combination: code only (port of runtime/evaluator.mjs, LIIT-EXPR-1: all/any/not, unknown stays unknown).
- K07 deadlines stay with the existing deadline code (app/deadlines.py); "external_service" elements stay open.
- K08 Apertus writes the concrete result per remedy (who, what, from when, open conditions) and next steps, only for
  outcomes whose conditions the logic supports; open elements become the questions to the client.
No pre-written legal text is shown except each module's own rule statement (legal_effect) and element labels."""
import json
import re
from concurrent.futures import ThreadPoolExecutor
from datetime import date
from functools import lru_cache
from pathlib import Path

from . import corpus
from .llm import ask_json

PKG = Path(__file__).resolve().parent.parent / "LIIT_Pruefungskern_v2.0.0"
DEFINITIVE = ("satisfied", "not_satisfied")
STATES = ("satisfied", "not_satisfied", "unknown", "disputed", "legal_review_required")
OPEN_ORDER = ("legal_review_required", "disputed", "unknown")

# English labels for the module picker (the module titles themselves are German)
TITLE_EN = {"M01": "Rent arrears and payment demand", "M02": "Termination by the landlord",
            "M03": "Notice by the tenant and early move-out", "M04": "Rent and one-sided contract changes",
            "M05": "Defects in the flat", "M06": "Rent deposit and its return", "M07": "Co-tenants and shared flats",
            "M08": "Pets, house rules and duty of care", "M09": "Protection of the family home"}
STATUS_EN = {"rule_conditions_supported": "Conditions met (documented)",
             "conditional_facts": "Conditions met on the client's account (not yet proven)",
             "conditional_applicability": "Conditions met, if the special tenancy rules apply",
             "unresolved": "Open: depends on facts still missing",
             "rule_conditions_not_supported": "Conditions not met on the facts given",
             "not_applicable": "Not applicable"}
ELEMENT_EN = {"satisfied": "met", "not_satisfied": "not met", "unknown": "unknown", "disputed": "disputed",
              "legal_review_required": "needs legal review"}


@lru_cache(maxsize=1)
def core():
    return json.loads((PKG / "core.v2.0.0.json").read_text(encoding="utf-8"))


@lru_cache(maxsize=1)
def load():
    out = {}
    for f in sorted((PKG / "legacy_modules").glob("M0*.json")):
        m = json.loads(f.read_text(encoding="utf-8"))
        m["binding"] = json.loads((PKG / "bindings" / f"{m['module_id']}.json").read_text(encoding="utf-8"))
        out[m["module_id"]] = m
    return out


def titles():
    return {k: f"{TITLE_EN[k]} ({m['title']})" for k, m in load().items()}


def active(case):
    return [load()[m] for m in case.get("modules", []) if m in load()]


# ---------------------------------------------------------------- logic (port of runtime/evaluator.mjs)

def refs(x):
    if "element" in x:
        return [x["element"]]
    if "not" in x:
        return refs(x["not"])
    out = []
    for e in x.get("all") or x.get("any"):
        out += [r for r in refs(e) if r not in out]
    return out


def evaluate_expr(x, lookup):
    if "element" in x:
        s = lookup(x["element"])
        return {"status": s, "leaves": [x["element"]], "open": [] if s in DEFINITIVE else [x["element"]]}
    if "not" in x:
        r = evaluate_expr(x["not"], lookup)
        s = {"satisfied": "not_satisfied", "not_satisfied": "satisfied"}.get(r["status"], r["status"])
        return {**r, "status": s}
    op = "all" if "all" in x else "any"
    rs = [evaluate_expr(e, lookup) for e in x[op]]
    ss = [r["status"] for r in rs]
    opened = next((o for o in OPEN_ORDER if o in ss), "unknown")
    if op == "all":
        s = "not_satisfied" if "not_satisfied" in ss else "satisfied" if all(v == "satisfied" for v in ss) else opened
    else:
        s = "satisfied" if "satisfied" in ss else "not_satisfied" if all(v == "not_satisfied" for v in ss) else opened
    leaves, opn = [], []
    for r in rs:
        leaves += [v for v in r["leaves"] if v not in leaves]
        opn += [v for v in r["open"] if v not in opn]
    return {"status": s, "leaves": leaves, "open": opn}


def leaf_elements(m, ids):
    """Elements to assess for the given outcomes; derived elements are expanded into their sub-elements."""
    els = {e["id"]: e for e in m["elements"]}
    out = []

    def add(i):
        e = els[i]
        if e["assessment"]["mode"] == "derived":
            for j in refs(e["assessment"]["expression"]):
                add(j)
        elif i not in out:
            out.append(i)
    for o in m["outcomes"]:
        if o["id"] in ids:
            for i in refs(o["when"]):
                add(i)
    return out


def evaluate(m, k):
    """k: the module's record in case['kern'] (selection, context, assessments). Mirrors evaluator.mjs: context
    'excluded' -> not_applicable; open or assumed context -> conditional_applicability; open expression ->
    unresolved; a leaf resting on the client's account (asserted) -> conditional_facts."""
    els = {e["id"]: e for e in m["elements"]}
    raw = k.get("assessments", {})
    memo = {}

    def node(i):
        if i in memo:
            return memo[i]
        e = els[i]
        if e["assessment"]["mode"] == "derived":
            x = evaluate_expr(e["assessment"]["expression"], lambda j: node(j)["status"])
            sub = [node(j) for j in x["leaves"]]
            r = {"status": x["status"], "assumed": any(t["assumed"] for t in sub), "facts": [],
                 "why": "Derived from its sub-elements.", "leaf_ids": [v for t in sub for v in t["leaf_ids"]]}
        else:
            a = raw.get(i) or {"status": "unknown", "facts": [], "why": "Not assessed.", "assumed": False}
            r = {**a, "leaf_ids": [i]}
        r = {**r, "id": i, "label": e["label"], "question": e["assessment"]["question"], "mode": e["assessment"]["mode"],
             "legal_basis": e.get("legal_basis", [])}
        memo[i] = r
        return r
    ctx = k.get("context", {})
    if any(c["status"] == "not_satisfied" and not c.get("assumed") for c in ctx.values()):
        app = "excluded"
    elif all(c["status"] == "satisfied" and not c.get("assumed") for c in ctx.values()):
        app = "applicable"
    else:
        app = "conditional"
    results = []
    for o in m["outcomes"]:
        if o["id"] not in k.get("selected", {}):
            continue
        x = evaluate_expr(o["when"], lambda j: node(j)["status"])
        leaves = []
        for j in x["leaves"]:
            leaves += [v for v in node(j)["leaf_ids"] if v not in leaves]
        items = [node(j) for j in leaves]
        assumed = any(t.get("assumed") for t in items)
        s = x["status"]
        status = ("not_applicable" if app == "excluded" else "conditional_applicability" if app == "conditional" and s == "satisfied"
                  else "unresolved" if s not in DEFINITIVE else "conditional_facts" if assumed and s == "satisfied"
                  else "rule_conditions_supported" if s == "satisfied" else "rule_conditions_not_supported")
        results.append({"id": o["id"], "status": status, "status_en": STATUS_EN[status], "expression_status": s,
                        "applicability": app, "legal_effect": o["legal_effect"], "legal_basis": o.get("legal_basis", []),
                        "reason": k["selected"][o["id"]], "elements": items,
                        "open_elements": [t["id"] for t in items if t["status"] not in DEFINITIVE]})
    return results


# ---------------------------------------------------------------- AI steps

def _numbered(case):
    """K01 facts as numbered lines: the description's sentences, then answers and confirmed documents."""
    lines = [f"{i + 1}. {s}" for i, s in enumerate(case["sentences"])]
    n = len(lines)
    extra = []
    for a in case.get("answers", []):
        if a.get("status") == "answered" and str(a.get("value", "")).strip():
            extra.append(f"Client's answer to \"{a.get('question', '')}\": {a['value']}")
    for d in case.get("uploaded", []):
        extra.append(f"Document (text confirmed by the social worker) {d['name']}: {d['text'][:600]}")
    lines += [f"{n + j + 1}. {t}" for j, t in enumerate(extra)]
    return "\n".join(lines), n + len(extra), n


_METHOD = """You are helping a social worker in the canton of Zurich. You follow the team's legal examination method
(LIIT Prüfungskern 2.0.0). Rules: keep facts separate from legal assessment; a statement by the client is not proof;
never treat an unknown point as not met; do not invent facts, dates, amounts or thresholds; a termination or a rent
notice is not by itself a breach of duty; every remedy is examined on its own."""

_SELECT = _METHOD + """
STEP K02-K05 for the module "{title}" ({legal_question}).
Scope of this module: {scope}
1. K02: Do the special rules for residential tenancy (Wohnraummiete) apply? "satisfied" only if the facts show a
   rented home/flat/room used to live in; "not_satisfied" only if the facts clearly show something else (business
   premises, owner-occupied, holiday flat, no tenancy); otherwise "unknown". Give the sentence numbers.
2. K03/K04: In one short sentence each: the relevant right or duty (who owes what to whom) and the legally relevant
   event (what happened, described as a fact).
3. K05: Which of the outcomes below could the client's situation concern? Select only outcomes that the facts make
   relevant (possible remedies to examine), each with a one-sentence reason. Do not judge yet whether they succeed.
OUTCOMES:
{outcomes}
Answer JSON only: {{"scope": {{"status": "satisfied|not_satisfied|unknown", "sentences": [n], "why": "..."}},
"right_or_duty": "...", "event": "...", "selected": [{{"id": "O01", "reason": "..."}}]}}

FACTS (numbered):
{facts}"""

_ASSESS = _METHOD + """
STEP K06 for the module "{title}". Examine each element below on its own: rule (definition) -> facts (sentence
numbers) -> short reasoning -> answer to the element's QUESTION.
Judge on the facts AS STATED (the client's account and any documents). Whether a fact is proven is recorded separately
by the code, so never answer "unknown" just because something is not proven or not documented.
Answer each element's QUESTION literally:
"yes" if the stated facts answer the question with yes, read in its ordinary meaning (cite the sentence numbers);
"no" if the stated facts answer it with no (cite them);
"unknown" only if the facts say nothing about this point;
"disputed" if the parties' accounts conflict on it;
"lawyer" if it turns on a legal evaluation that needs a lawyer (for example reasonableness, abuse, hardship) and the
facts do not settle it.
What the client says happened counts as stated (for example: the client says a letter arrived -> it arrived; the
client says the letter threatens termination -> it does). An exception that nothing in the facts suggests (for example
"caused by the tenant?") is "unknown", not "no". Never use a threshold that the rule does not state.
ELEMENTS:
{elements}
Answer JSON only: {{"E01": {{"answer": "yes|no|unknown|disputed|lawyer", "sentences": [n], "why": "one short sentence in English"}}, ...}}

FACTS (numbered):
{facts}"""

_QUESTIONS = """A social worker will ask their client follow-up questions. Below are open points from a legal
examination (each with an id). Write ONE short, plain question in English that the social worker can ask the client
for each open point that the client could answer (skip points only a lawyer or a court can decide, and points the
client's situation already answers). Read each rule carefully (German legal terms: "Übernahme" = the tenant received
the flat; "Mietsache" = the rented flat). Do not state any law. Keep the client's situation in mind. At most 8 questions, the most decisive first.
OPEN POINTS:
{points}
CLIENT'S SITUATION:
{facts}
Answer JSON only: {{"questions": [{{"point": "<id>", "question": "...", "why": "one short reason a client understands", "type": "yes_no|text|date"}}]}}"""

_WRITE = _METHOD + """
STEP K08 for the module "{title}". For each outcome below, the code has combined the element results; the status is
fixed and you must not change it. Write in plain English for a social worker:
- "result": 1-2 sentences: who can demand what from whom, from when and for how long, as far as the facts show;
  name every open condition with "if ..."; say "not yet known" for missing amounts or dates. Do not add rules that are
  not in the outcome text.
- "steps": up to 2 next steps (form, recipient, prior steps such as a written notice first) that this outcome supports.
  A step that depends on an open condition starts with "If".
OUTCOMES:
{outcomes}
Answer JSON only: {{"O01": {{"result": "...", "steps": [{{"text": "...", "who": "client|social_worker"}}]}}, ...}}

FACTS (numbered):
{facts}"""


def _sent_list(v, nmax):
    out = []
    for x in v if isinstance(v, list) else [v]:
        try:
            n = int(x)
        except (TypeError, ValueError):
            continue
        if 1 <= n <= nmax and n not in out:
            out.append(n)
    return out


def _temporal(case):
    """Code rule (K02 temporal): the modules were checked against the law in force on 2026-11-08 (OR edition
    2026-10-01). An event dated before 2026-10-01 needs the earlier version: left open."""
    early = [e for e in case.get("events", []) if (e.get("date") or e.get("date_from") or "9999") < "2026-10-01"]
    if early:
        return {"status": "unknown", "facts": [], "assumed": False,
                "why": "An event is dated before 2026-10-01: the law in force then must be compared (module rule)."}
    return {"status": "satisfied", "facts": [], "assumed": False,
            "why": "No recorded event before 2026-10-01; the current law version used by the module applies."}


def select(case, m):
    facts, nmax, _ = _numbered(case)
    outs = "\n".join(f"- {o['id']}: {o['legal_effect']} [{', '.join(o.get('legal_basis', []))}]" for o in m["outcomes"])
    r = ask_json(_SELECT.format(title=m["title"], legal_question=m["legal_question"], scope=m["scope"], outcomes=outs,
                                facts=facts), trace=case["trace"], step=f"K02-K05 {m['module_id']}", max_tokens=700)
    sc = r.get("scope") if isinstance(r.get("scope"), dict) else {}
    st = sc.get("status") if sc.get("status") in ("satisfied", "not_satisfied", "unknown") else "unknown"
    sn = _sent_list(sc.get("sentences"), nmax)
    if st in DEFINITIVE and not sn:  # core: definitive assessment requires facts
        st = "unknown"
    ids = {o["id"] for o in m["outcomes"]}
    sel = {}
    for x in r.get("selected") or []:
        if isinstance(x, dict) and x.get("id") in ids and str(x.get("reason", "")).strip():
            sel[x["id"]] = str(x["reason"]).strip()
    return {"context": {"scope": {"status": st, "facts": sn, "why": str(sc.get("why", ""))[:300],
                                  "assumed": st in DEFINITIVE},  # resting on the client's account
                        "temporal": _temporal(case)},
            "right_or_duty": str(r.get("right_or_duty", ""))[:300], "event": str(r.get("event", ""))[:300],
            "selected": sel}


def assess_elements(case, m, k):
    facts, nmax, ndesc = _numbered(case)
    ids = leaf_elements(m, set(k["selected"]))
    els = {e["id"]: e for e in m["elements"]}
    todo = [i for i in ids if els[i]["assessment"]["mode"] == "legal_assessment"]
    out = {}
    for i in ids:
        if els[i]["assessment"]["mode"] == "external_service":
            out[i] = {"status": "unknown", "facts": [], "assumed": False,
                      "why": "Deadline question: see the deadlines calculated by code; not decided here."}
    if todo:
        lines = "\n".join(f"- {i}: QUESTION: {els[i]['assessment']['question']} Rule: {els[i]['definition']} [{', '.join(els[i].get('legal_basis', []))}]"
                          for i in todo)
        r = ask_json(_ASSESS.format(title=m["title"], elements=lines, facts=facts), trace=case["trace"],
                     step=f"K06 {m['module_id']}", max_tokens=150 + 90 * len(todo))
        for i in todo:
            a = r.get(i) if isinstance(r.get(i), dict) else {}
            st = {"yes": "satisfied", "no": "not_satisfied", "disputed": "disputed", "lawyer": "legal_review_required"}.get(
                str(a.get("answer", "")).strip().lower(), "unknown")
            sn = _sent_list(a.get("sentences"), nmax)
            why = str(a.get("why", "")).strip()[:300] or "No reasoning given."
            if st in DEFINITIVE and not sn:
                st, why = "unknown", "No fact cited for a definite answer, so left open (core rule). " + why
            # facts from the description or the client's answers are "asserted"; only a confirmed document is not
            assumed = st in DEFINITIVE and any(n <= ndesc or "Client's answer" in facts.split("\n")[n - 1] for n in sn)
            out[i] = {"status": st, "facts": sn, "why": why, "assumed": assumed,
                      "quotes": [facts.split("\n")[n - 1].split(". ", 1)[-1][:200] for n in sn]}
    k["assessments"] = out
    return k


def run(case, reselect=True):
    """K02-K06 for every confirmed module (parallel), then the code combination."""
    prev = case.get("kern", {})

    def one(m):
        mid = m["module_id"]
        try:
            k = select(case, m) if reselect or mid not in prev else prev[mid]
            if k["selected"]:
                assess_elements(case, m, k)
            return mid, k
        except Exception as e:  # noqa: BLE001 - shown as an open module, not hidden
            return mid, {"error": f"AI step failed: {e}", "selected": {}, "context": {}}
    with ThreadPoolExecutor(4) as ex:
        case["kern"] = dict(ex.map(one, active(case)))
    case["kern_results"] = {mid: evaluate(load()[mid], k) for mid, k in case["kern"].items()}
    return case


def questions(case):
    """K08 next questions: open elements of the selected outcomes, phrased by Apertus; code keeps only questions tied
    to an open element and adds the element's affected outcomes."""
    points, meta = [], {}
    for mid, res in case.get("kern_results", {}).items():
        for o in res:
            if o["status"] == "rule_conditions_not_supported":
                continue
            for t in o["elements"]:
                if t["status"] in ("unknown", "disputed") and t["mode"] == "legal_assessment":
                    key = f"{mid}.{t['id']}"
                    if key not in meta:
                        meta[key] = {"label": t["label"], "basis": t["legal_basis"], "outcomes": []}
                        rule = next(e["definition"] for e in load()[mid]["elements"] if e["id"] == t["id"])
                        points.append(f"- {key}: {t['label']}. Rule: {rule}")
                    meta[key]["outcomes"].append(f"{mid}.{o['id']}")
    qs = []
    if points:
        facts, _, _ = _numbered(case)
        try:
            r = ask_json(_QUESTIONS.format(points="\n".join(points[:24]), facts=facts), trace=case["trace"],
                         step="K08 questions", max_tokens=900)
        except Exception:  # noqa: BLE001
            r = {}
        seen = set()
        for x in r.get("questions") or []:
            if not isinstance(x, dict) or x.get("point") not in meta or x["point"] in seen or not str(x.get("question", "")).strip():
                continue
            seen.add(x["point"])
            t = {"yes_no": "yes_no_unknown", "date": "date"}.get(x.get("type"), "text")
            qs.append({"element": x["point"], "question": str(x["question"]).strip(), "why_we_ask":
                       f"{str(x.get('why', '')).strip()} (Open point: {meta[x['point']]['label']}; affects {', '.join(meta[x['point']]['outcomes'])})",
                       "input_type": t, "legal_basis": _pids(meta[x["point"]]["basis"]), "priority": "core",
                       "options": [], "answer_instead": [], "dates_event": "none"})
    for i, q in enumerate(qs[:8]):
        q["id"] = f"Q{i + 1}"
    case["questions"] = qs[:8]
    return case


def write(case):
    """K08 result per module: AI text only for outcomes whose combined conditions are met (possibly on the client's
    account); open and unmet outcomes get their status from code. Returns blocks and actions for the screen."""
    facts, _, _ = _numbered(case)
    blocks, actions, lawyer = [], [], []

    def one(item):
        mid, res = item
        m = load()[mid]
        pos = [o for o in res if o["expression_status"] == "satisfied" and o["status"] != "not_applicable"]
        if not pos:
            return mid, {}
        lines = "\n".join(f"- {o['id']} [{o['status_en']}]: {o['legal_effect']} [{', '.join(o['legal_basis'])}]. Elements: "
                          + "; ".join(f"{t['label']}: {ELEMENT_EN[t['status']]}" for t in o["elements"]) for o in pos)
        try:
            return mid, ask_json(_WRITE.format(title=m["title"], outcomes=lines, facts=facts), trace=case["trace"],
                                 step=f"K08 result {mid}", max_tokens=250 + 220 * len(pos))
        except Exception:  # noqa: BLE001
            return mid, {}
    with ThreadPoolExecutor(4) as ex:
        texts = dict(ex.map(one, case.get("kern_results", {}).items()))
    for mid, res in case.get("kern_results", {}).items():
        m, k = load()[mid], case["kern"][mid]
        outs = []
        for o in res:
            t = texts.get(mid, {}).get(o["id"]) if isinstance(texts.get(mid, {}).get(o["id"]), dict) else {}
            ok = o["expression_status"] == "satisfied" and o["status"] != "not_applicable"
            open_labels = [x["label"] for x in o["elements"] if x["status"] not in DEFINITIVE]
            outs.append({**o, "result": str(t.get("result", "")).strip() if ok else "", "open_labels": open_labels,
                         "basis": _pids(o["legal_basis"])})
            if ok:
                for s in (t.get("steps") or [])[:2]:
                    if isinstance(s, dict) and str(s.get("text", "")).strip():
                        conditional = o["status"] != "rule_conditions_supported"
                        actions.append({"what": str(s["text"]).strip(), "who": s.get("who") if s.get("who") in ("client", "social_worker") else "client",
                                        "group": "needs_clarification" if str(s["text"]).lower().startswith("if") else "now",
                                        "sources": _pids(o["legal_basis"]), "module": mid, "outcome": o["id"],
                                        "depends_on": "; ".join(x for x in [
                                            "rests on the client's account" if conditional else "",
                                            ", ".join(open_labels)] if x)})
            lawyer += [f"{TITLE_EN[mid]}: {x['label']}" for x in o["elements"] if x["status"] == "legal_review_required"]
        blocks.append({"module": mid, "title": titles()[mid], "summary": m["legal_question"], "points": [],
                       "kern": {"context": k.get("context", {}), "right_or_duty": k.get("right_or_duty", ""),
                                "event": k.get("event", ""), "error": k.get("error"), "outcomes": outs}})
    for i, a in enumerate(actions):
        a.update({"id": f"A{i + 1}", "deadline_ids": [], "contact_ids": []})
    return blocks, actions, list(dict.fromkeys(lawyer))


# ---------------------------------------------------------------- sources

_ART = re.compile(r"^(OR|ZGB|ZPO|VMWG|SchKG)\s+(\d+[a-z]*)(?:\s+Abs\.\s*(\d+))?")


def _pids(bases):
    """'OR 259a Abs. 1 lit. a' -> 'OR Art. 259a Abs. 1' (paragraph ids of the law corpus); unknown ones are dropped."""
    ids = corpus.by_id()
    out = []
    for b in bases:
        mm = _ART.match(b.strip())
        if not mm:
            continue
        law, art, abs_ = mm.groups()
        cand = f"{law} Art. {art} Abs. {abs_}" if abs_ else None
        if not cand or cand not in ids:
            cand = next((k for k in (f"{law} Art. {art} Abs. 1", f"{law} Art. {art}") if k in ids), None)
        if cand and cand not in out:
            out.append(cand)
    return out


def bases(case):
    out = []
    for res in case.get("kern_results", {}).values():
        for o in res:
            out += _pids(o["legal_basis"])
            for t in o["elements"]:
                out += _pids(t["legal_basis"])
    return out


_PICK = """A social worker describes a client's tenancy problem (numbered sentences). Below are the legal modules of the
tool. Which of them does the client's problem CLEARLY concern? Choose only modules that fit; none is fine. A threat to
terminate is not a termination; a tenant who wants to leave is not a termination by the landlord.
MODULES:
{menu}
Answer JSON only: {{"modules": [{{"id": "<id>", "sentence": <number of the sentence that shows it>}}]}}

DESCRIPTION:
{text}"""


def suggest_ai(case):
    menu = "\n".join(f"- {k}: {TITLE_EN[k]}. {m['scope']} Question: {m['legal_question']}" for k, m in load().items())
    sents = case["sentences"]
    text = "\n".join(f"{i + 1}. {x}" for i, x in enumerate(sents))
    try:
        r = ask_json(_PICK.format(menu=menu, text=text), trace=case["trace"], step="2 module", max_tokens=150)
    except Exception:  # noqa: BLE001
        return [], "none (the AI call failed)"
    out = []
    for x in r.get("modules") or []:
        if isinstance(x, dict) and x.get("id") in load() and x["id"] not in out and _sent_list(x.get("sentence"), len(sents)):
            out.append(x["id"])
    return out, "AI (one closed question, each pick cites a sentence)"
