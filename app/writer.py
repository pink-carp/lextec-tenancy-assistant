"""Step 5 and 9 (v3): Apertus writes everything the social worker sees; code decides what it may write about and
checks what it wrote. Nothing shown on screen is pre-written.

What Apertus gets per call: the German law text of the paragraphs at issue, each with a STATUS set by code from the
confirmed events (applies / open / not yet), the confirmed facts and the client's words. One job per call.
What code enforces afterwards: every sentence names a paragraph it relies on; a sentence about an 'open' or 'not yet'
paragraph must be conditional ("If ..."); no action may rest on a 'not yet' paragraph; numbers must come from the law
or the client's words; then two Apertus checks (English and German, closed answers) and any flag removes the sentence.
Measured on 2026-11-08 (Claude-judged test sets): gating by confirmed events removed most misapplied rules; the two
checks together caught about 9 in 10 wrong sentences, at the price of removing about 1 in 4 correct ones."""
import re
from concurrent.futures import ThreadPoolExecutor

from . import corpus, events
from .llm import ask_json, chat

PID = re.compile(r"(?:OR|ZGB|ZPO) Art\. \d+[a-z]*(?: Abs\. \d+)?")
COND = re.compile(r"^\s*(if|should|once|only if|in case|as soon as|unless|whether)\b", re.I)
SHOW_NOTES = False  # see pipeline.write: measured too unreliable to show
LEVEL = "guidance"  # "guidance" (practical, for social workers) or "legal" (applies the provisions); see the comparison test


def pids(*texts):
    return [m for t in texts for m in PID.findall(str(t or ""))]


def _status_of(pid, st):
    if pid in st:
        return st[pid][0]
    sub = {v[0] for k, v in st.items() if k.startswith(pid + " Abs.")}
    return "applies" if "applies" in sub else ("open" if "open" in sub else ("not_yet" if sub else None))


def statuses(case, articles):
    ev = case.get("event_status", {})
    return {p["id"]: events.para_status(p["id"], ev) for a in articles for p in corpus.by_article().get(a, [])}


def law_block(articles, st):
    names = events.events()
    out = []
    for a in articles:
        for p in corpus.by_article().get(a, []):
            s, miss = st[p["id"]]
            miss_t = "; ".join(names.get(m, m) for m in miss)
            lab = {"applies": "applies", "open": f"open (unknown: {miss_t})", "not_yet": f"not yet (has not happened: {miss_t})"}[s]
            out.append(f"[{p['id']}] STATUS {lab}\n{p['text']}")
    return "\n".join(out)


def _ctx(case):
    from .pipeline import facts_block
    return "\n".join(case["sentences"]), facts_block(case), case["today"]


def _ask(prompt, case, step, mt):
    try:
        return ask_json(prompt, trace=case["trace"], step=step, max_tokens=mt)
    except Exception as e:  # noqa: BLE001 - shown as "could not be written", never as invented text
        return {"_error": str(e)}


# ---------------------------------------------------------------- notes per issue

_RULES_COMMON = (
    "- STATUS applies: say what it means for this client now. STATUS open: the sentence must start with \"If\" and "
    "name the missing fact. STATUS not yet: at most one sentence, starting with \"If\", about what would follow later.\n"
    "- Use only what the German text says; where it gives different rules for different premises, use only the rule "
    "for flats (Wohnungen). An unknown fact is unknown, never a 'no'.\n")
NOTE_PROMPTS = {
    "legal": ("Write a short note (max 4 sentences) that applies the law to this client.\n" + _RULES_COMMON +
              "- Say who must act. Give the paragraph ID for each sentence.\n"),
    "guidance": ("Write short practical guidance for the social worker (max 3 sentences) in everyday words: what this "
                 "issue means for the client in practice and what to do or watch out for.\n" + _RULES_COMMON +
                 "- Do not quote provisions and do not name articles in the text; give the paragraph ID your sentence "
                 "relies on in \"para\".\n- Write no numbers of days, months, percentages or amounts unless they are in "
                 "the client's words; say \"the date in the letter\" or \"the time limit\" (deadlines are calculated "
                 "separately).\n"),
}


def note(issue, st, case, level=None):
    text, facts, today = _ctx(case)
    prompt = ("A social worker (not a lawyer) in the canton of Zurich helps a client with a residential tenancy problem. "
              "Below are the client's words, the known facts, and the German text of the law for ONE issue. Code has "
              "already checked, for each paragraph, whether the event it requires has happened (STATUS).\n"
              + NOTE_PROMPTS[level or LEVEL] +
              "Answer JSON only. Every sentence MUST be an object with its paragraph ID, exactly like this:\n"
              '{"sentences": [{"text": "If the letter ...", "para": "OR Art. 257d Abs. 1"}]}\n'
              f"\nTODAY: {today}\nISSUE: {issue['issue']}\nLAW:\n{law_block(issue['articles'], st)}"
              f"\n\nKNOWN FACTS:\n{facts}\n\nCLIENT'S WORDS:\n{text}")
    r = _ask(prompt, case, "9 note per issue", 600)
    keep, dropped = [], []
    for s in r.get("sentences") or []:
        if not isinstance(s, dict) or not s.get("text"):
            continue
        t = re.sub(r"\s*\((?:para|paragraph|who)[^)]*\)", "", str(s["text"])).strip()
        ids = [i for i in pids(s.get("para"), t) if _status_of(i, st)]
        if not ids:
            dropped.append({"sentence": t, "reason": "names no paragraph of this issue"})
            continue
        sts = {_status_of(i, st) for i in ids}
        if "applies" not in sts and not COND.match(t):
            dropped.append({"sentence": t, "reason": "the rule's event has not happened or is unknown, but the "
                                                     "sentence is not conditional"})
            continue
        keep.append({"text": t, "para": ids[0], "status": "/".join(sorted(sts))})
    return keep, dropped, r.get("_error")


# ---------------------------------------------------------------- questions

def question_facts(case, articles, st):
    """The facts whose answers decide the rules at issue: unknown events, the table's deciding facts for paragraphs
    that apply or are open, and missing receipt dates of letters that start a time limit."""
    names, out = events.events(), []
    ev = case.get("event_status", {})
    for k, v in ev.items():
        if v.get("answer") == "C" and k not in events.CODE_ONLY and any(k in m for s, m in st.values() if s == "open"):
            out.append({"fact": f"whether this is the case: {names.get(k, k)}", "critical": True, "event": k})
    for pid, (s, _) in st.items():
        if s in ("applies", "open"):
            for f in (events.requirements(pid) or {}).get("deciding_facts") or []:
                if f not in [x["fact"] for x in out]:
                    out.append({"fact": f, "critical": False, "para": pid})
    for e in case.get("events", []):
        if e.get("doc_type") in ("payment_demand_with_termination_warning", "termination_by_landlord",
                                 "rent_increase_notice") and e.get("precision") != "exact":
            said = f' (the client said "{e["when_words"]}")' if e.get("when_words") else ""
            out.insert(0, {"fact": f"the exact date the client received the {e['doc_type'].replace('_', ' ')}{said}; "
                                   "for registered mail collected later, the date on the collection slip", "critical": True,
                           "dates_event": e["id"]})
    for i, f in enumerate(out):
        f["id"] = f"K{i + 1}"
    return out[:14]


def questions(case, articles, st):
    text, facts, today = _ctx(case)
    kf = question_facts(case, articles, st)
    if not kf:
        return [], []
    listing = "\n".join(f"{f['id']}: {f['fact']}" for f in kf)
    prompt = ("A social worker helps a client with a residential tenancy problem in the canton of Zurich. Below are the "
              "facts that decide the client's legal position (FACTS TO ESTABLISH), what is already known, and the client's "
              "words. Write one follow-up question for each fact that the known facts and the client's words do NOT "
              "already answer (max 7, most decisive first). Rules: one fact per question; plain words, addressed to the "
              "client ('you'); no legal terms and no legal rules; 'why' = one short everyday sentence on why the answer "
              "matters, without stating any rule; 'input' = date, yes_no_unknown, number, short_text or upload (upload "
              "when the answer is in a letter or contract).\n"
              'Answer JSON only: {"questions": [{"fact": "K1", "question": "...", "why": "...", "input": "date"}]}\n\n'
              f"FACTS TO ESTABLISH:\n{listing}\n\nKNOWN FACTS:\n{facts}\n\nCLIENT'S WORDS:\n{text}")
    r = _ask(prompt, case, "5 questions", 800)
    by_id = {f["id"]: f for f in kf}
    out, seen, dropped = [], set(), []
    for q in r.get("questions") or []:
        if not isinstance(q, dict) or not q.get("question"):
            continue
        fid = str(q.get("fact", ""))
        if fid not in by_id:
            dropped.append({"question": q["question"], "reason": "not linked to a fact that decides the case"})
            continue
        if fid in seen:
            dropped.append({"question": q["question"], "reason": "duplicate (same fact)"})
            continue
        if pids(q["question"]) or re.search(r"\b(required by law|legally|article|art\.)", q["question"], re.I):
            dropped.append({"question": q["question"], "reason": "contains a legal statement"})
            continue
        seen.add(fid)
        f = by_id[fid]
        out.append({"question": q["question"], "why_we_ask": str(q.get("why", "")),
                    "input_type": q.get("input") if q.get("input") in ("date", "yes_no_unknown", "number", "short_text", "upload") else "short_text",
                    "priority": "urgent" if f.get("critical") else "core", "fact": f["fact"],
                    "legal_basis": [f["para"]] if f.get("para") else [], "dates_event": f.get("dates_event", "none"),
                    "event_id": f.get("event", ""), "options": [], "answer_instead": []})
    # completeness by code: a critical fact without a question gets one focused call (still written by Apertus)
    for f in kf:
        if f.get("critical") and f["id"] not in seen:
            r2 = _ask("Write ONE short question to a client, in plain words, addressed to 'you', asking about this: "
                      f"{f['fact']}.\n" + 'Answer JSON only: {"question": "...", "why": "<one everyday sentence>"}',
                      case, "5 question (completeness)", 120)
            if r2.get("question") and not pids(r2["question"]):
                out.insert(0, {"question": r2["question"], "why_we_ask": str(r2.get("why", "")),
                               "input_type": "date" if f.get("dates_event") else "yes_no_unknown", "priority": "urgent",
                               "fact": f["fact"], "legal_basis": [], "dates_event": f.get("dates_event", "none"),
                               "event_id": f.get("event", ""), "options": [], "answer_instead": []})
    out.sort(key=lambda q: q["priority"] != "urgent")
    for i, q in enumerate(out[:10]):
        q["id"] = f"Q{i + 1}"
    return out[:10], dropped


# ---------------------------------------------------------------- actions and situation summary

def actions(case, articles, st):
    text, facts, today = _ctx(case)
    dl = "\n".join(f"{d['id']}: {d['action']}" for d in case.get("deadlines", [])) or "none"
    ct = "\n".join(f"{c['id']}: {c['name']}" for c in case.get("contacts", [])) or "none"
    prompt = ("A social worker (not a lawyer) in the canton of Zurich helps a client with a residential tenancy problem. "
              "Write the next actions for the social worker and the client (max 5, most urgent first) and a two-sentence "
              "neutral summary of the client's situation and goal (facts only, no legal rules, no dates).\n"
              "Each action must follow from a paragraph whose STATUS is applies (give its ID in 'basis'), or clarify an open "
              "fact (give the paragraph ID and, in 'depends_on', the answer it waits for), or be a referral to a listed "
              "contact ('basis': the contact ID). Never base an action on a paragraph whose status is 'not yet'. Lane 3: the "
              "first action is the referral. Refer to deadlines and contacts only by their IDs; write no dates. Everyday "
              "words; name no articles in the text.\n"
              'Answer JSON only: {"situation": "...", "actions": [{"what": "...", "who": "client|social_worker|professional", '
              '"basis": "OR Art. 257d Abs. 1", "deadline_ids": ["D1"], "contact_ids": [], "depends_on": ""}]}\n\n'
              f"LANE {case['lane']}\nLAW:\n{law_block(articles, st)}\n\nDEADLINES (calculated by code):\n{dl}\n\n"
              f"CONTACTS:\n{ct}\n\nKNOWN FACTS:\n{facts}\n\nCLIENT'S WORDS:\n{text}")
    r = _ask(prompt, case, "9 actions", 900)
    keep, dropped = [], []
    cids = {c["id"] for c in case.get("contacts", [])}
    dids = {d["id"] for d in case.get("deadlines", [])}
    for a in r.get("actions") or []:
        if not isinstance(a, dict) or not a.get("what"):
            continue
        ids = pids(a.get("basis"), a["what"])
        sts = {_status_of(i, st) for i in ids} - {None}
        if ids and not sts & {"applies", "open"}:
            dropped.append({"sentence": a["what"], "reason": "rests on a rule whose event has not happened"})
            continue
        if ids and "applies" not in sts and not a.get("depends_on"):
            dropped.append({"sentence": a["what"], "reason": "rests on an open rule but does not say what it depends on"})
            continue
        keep.append({"what": str(a["what"]), "who": a.get("who") if a.get("who") in ("client", "social_worker", "professional") else "social_worker",
                     "basis": ids[:1], "deadline_ids": [x for x in a.get("deadline_ids") or [] if x in dids],
                     "contact_ids": [x for x in a.get("contact_ids") or [] if x in cids] or ([a["basis"]] if a.get("basis") in cids else []),
                     "depends_on": str(a.get("depends_on") or ""), "group": "referral" if a.get("basis") in cids else
                     ("needs_clarification" if a.get("depends_on") else "now")})
    if case["lane"] == 3:
        keep.sort(key=lambda a: a["group"] != "referral")
    return str(r.get("situation", "")), keep, dropped


# ---------------------------------------------------------------- checks before anything is shown

def _numbers_ok(sentence, law_text, client_text, level):
    nums = re.findall(r"\d+", re.sub(PID, "", sentence))
    pool = client_text if level == "guidance" else client_text + " " + law_text
    return all(n in pool for n in nums)


def _check_en(st_text, law, facts, case):
    system = ("You are a strict checker of statements written for a social worker about Swiss tenancy law. Decide whether "
              "the CITED law text states the STATEMENT and whether it fits these FACTS. Answer in exactly two lines:\n"
              "VERDICT: <supported|conditional|partly|not_supported|not_applicable>\nREASON: <one short sentence>")
    try:
        t = chat([{"role": "user", "content": f"{system}\n\nFACTS:\n{facts}\n\nSTATEMENT: {st_text}\nCITED:\n{law}"}],
                 max_tokens=120, trace=case["trace"], step="10 check (English)")
    except Exception:  # noqa: BLE001
        return None, "could not be checked"
    m = (re.search(r"VERDICT:\s*\**\s*(supported|conditional|partly|not_supported|not_applicable)", t, re.I)
         or re.match(r"\s*\**\s*(supported|conditional|partly|not_supported|not_applicable)\b", t, re.I))
    reason = (re.search(r"REASON:\s*(.+)", t) or [None, ""])[1]
    return (m.group(1).lower() if m else None), reason


def _check_de(st_text, law, facts, case):
    p = (f"GESETZESTEXT (amtlicher Wortlaut):\n{law}\n\nSACHVERHALT (Englisch):\n{facts}\n\n"
         f"AUSSAGE (für die Sozialarbeiterin, Englisch): {st_text}\n\n"
         "Prüfe die AUSSAGE streng am deutschen Gesetzestext. Wähle einen Buchstaben:\n"
         "A = der Gesetzestext sagt das (oder die Aussage ist eine korrekte, vorsichtige Vereinfachung), und es passt auf den Sachverhalt\n"
         "B = der Gesetzestext sagt etwas anderes (andere Voraussetzung, Rechtsfolge, Person oder Frist)\n"
         "C = diese Regel steht nicht im Gesetzestext\n"
         "D = die Regel gibt es, aber sie passt nicht auf den Sachverhalt (das nötige Ereignis ist nicht eingetreten)\n"
         "Antworte in zwei Zeilen:\nBUCHSTABE: <A|B|C|D>\nGRUND: <ein Satz>")
    try:
        t = chat([{"role": "user", "content": p}], max_tokens=120, trace=case["trace"], step="10 check (German)")
    except Exception:  # noqa: BLE001
        return None, "could not be checked"
    m = re.search(r"BUCHSTABE:\s*\**\s*([ABCD])\b", t) or re.match(r"\s*\**\s*([ABCD])\b", t)  # also a bare letter first
    return (m.group(1) if m else None), (re.search(r"GRUND:\s*(.+)", t) or [None, ""])[1]


def check(items, case, level=None):
    """items: [{"text", "para"}]; returns (kept, removed). Any flag from code or either Apertus check removes."""
    from .pipeline import facts_block
    facts, client = facts_block(case), case["description"]
    level = level or LEVEL

    def one(it):
        art = re.sub(r" Abs\. \d+$", "", it["para"]).replace(" Art.", "")
        law = "\n".join(f"[{p['id']}] {p['text']}" for p in corpus.by_article().get(art, []))
        if not _numbers_ok(it["text"], law, client, level):
            return it, "a number is neither in the law text nor in the client's words"
        with ThreadPoolExecutor(2) as ex:
            en, de = ex.submit(_check_en, it["text"], law, facts, case), ex.submit(_check_de, it["text"], law, facts, case)
            (v_en, r_en), (v_de, r_de) = en.result(), de.result()
        if v_en != "supported" and not (v_en == "conditional" and COND.match(it["text"])):
            return it, f"English check: {v_en or 'no answer'} - {r_en}"
        if v_de != "A":
            return it, f"German check: {v_de or 'no answer'} - {r_de}"
        return it, None

    with ThreadPoolExecutor(4) as ex:
        res = list(ex.map(one, items))
    kept = [it for it, why in res if not why]
    removed = [{"sentence": it["text"], "reason": why, "para": it["para"]} for it, why in res if why]
    return kept, removed
