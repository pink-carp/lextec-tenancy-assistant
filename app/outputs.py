"""Step 6 (answers, uploads) and step 11 (client handout, translation, expert brief).

The handout and brief are rewritten from the verified result; they never re-analyse the case."""
import base64
import json
import re
import io
from datetime import date  # noqa: F401

from . import checks
from .llm import ask_json, chat
from .pipeline import SYSTEM_ROLE, _d, allowed_dates, facts_block, mask

# ---------------------------------------------------------------- answers and uploads


def apply_answers(case, answers):
    """answers: [{question_id, value, status: answered|dont_know|cant_get}]. A date answer to a question
    that dates an event updates that event (marked as the client's statement)."""
    qs = {q["id"]: q for q in case.get("questions", [])}
    events = {e["id"]: e for e in case.get("events", [])}
    clean = []
    for a in answers:
        q = qs.get(a["question_id"])
        if not q:
            continue
        a = {**a, "question": q["question"], "value": mask(str(a.get("value", "")))[0]}
        clean.append(a)
        ev = events.get(q.get("dates_event"))
        if a.get("status") == "answered" and q["input_type"] == "date" and _d(a.get("value")):
            if ev is None:  # the question dates an event the AI had not recorded: add it, and link it
                ev = {"id": f"L{len(events) + 1}", "event": q["question"], "sentences": [],
                      "precision": "unknown", "date": "", "date_from": "", "date_to": ""}
                case.setdefault("events", []).append(ev)
                events[ev["id"]] = ev
                q["dates_event"] = ev["id"]
            ev.setdefault("original", {k: ev.get(k, "") for k in ("precision", "date", "date_from", "date_to")})
            ev.update({"precision": "exact", "date": a["value"], "date_from": "", "date_to": "",
                       "source": "client's answer, not documented"})
        elif ev is not None and "original" in ev:  # answer withdrawn: back to what the description said
            ev.update(ev.pop("original"))
            ev.pop("source", None)
        # a yes/no answer about a deciding event updates that event (as the client's statement)
        k = q.get("event_id")
        if k and k in case.get("event_status", {}) and a.get("status") == "answered" and a["value"].lower() in ("yes", "no"):
            case["event_status"][k] = {**case["event_status"][k], "answer": "A" if a["value"].lower() == "yes" else "B",
                                       "source": "client's answer"}
    case["answers"] = clean
    from . import events
    events.derive(case)
    return case


def read_upload(case, filename, content: bytes):
    """Text PDFs are read by code; photos and scans by Apertus' image function. The social worker must
    confirm the text before it is used."""
    name = filename.lower()
    if name.endswith(".pdf"):
        import pdfplumber
        with pdfplumber.open(io.BytesIO(content)) as pdf:
            text = "\n".join((p.extract_text() or "") for p in pdf.pages).strip()
        if text:
            return {"method": "text layer of the PDF (read by code)", "text": text[:8000]}
        return {"method": "none", "text": "", "warning": "This PDF has no text layer. Please upload a photo of each page instead."}
    from PIL import Image, UnidentifiedImageError
    try:
        img = Image.open(io.BytesIO(content))
    except UnidentifiedImageError:
        return {"method": "none", "text": "", "warning": "This file type cannot be read. Please upload a PDF, JPG or PNG."}
    warning = None
    if min(img.size) < 1200:
        warning = (f"Low resolution ({img.size[0]}x{img.size[1]} px). In our tests, low-resolution scans were "
                   "misread in ways that change the meaning. Please check the text carefully or take a sharper photo.")
    mime = "image/png" if name.endswith(".png") else "image/jpeg"
    b64 = base64.b64encode(content).decode()
    text = chat([{"role": "user", "content": [
        {"type": "text", "text": "Transcribe all text in this document exactly, line by line. Do not summarise, "
                                 "translate or correct anything. Mark unreadable words as [unreadable]."},
        {"type": "image_url", "image_url": {"url": f"data:{mime};base64,{b64}"}}]}],
        max_tokens=2000, trace=case["trace"], step="6 read scanned document")
    return {"method": "image read by Apertus (AI transcription)", "text": text, "warning": warning}


def add_document(case, name, text):
    """Called after the social worker confirmed the extracted text. Kept apart from case['documents']
    (the letters the client mentioned), and shown to later steps as documented evidence."""
    text = mask(text)[0]
    case.setdefault("uploaded", []).append({"name": name, "text": text[:6000]})
    case.setdefault("facts", []).append({"id": f"F{len(case.get('facts', [])) + 1}", "heading": "what",
                                         "statement": f"Document '{name}' uploaded; text confirmed by the social worker.",
                                         "quote": "", "status": "documented"})
    return case


# ---------------------------------------------------------------- handout

# docs/disclosure.md section A (draft for the legal team). The data sentence uses the cautious variant because
# the AI provider's and the host's data retention have not been verified.
CLIENT_DISCLOSURE = (  # docs/versions/v5-openai/disclosure.md, section A (on main)
    "About this sheet: Test version: for invented cases only. This sheet was made with a computer tool that uses "
    "artificial intelligence (AI) from OpenAI, a US company. The AI wrote it. It may contain mistakes. This is general "
    "legal information, not legal advice. It does not replace a lawyer. Our tool does not save your case. Your information "
    "was sent to OpenAI in the USA, which may keep data. For advice on your own case, contact a service listed on this "
    "sheet. If a deadline is mentioned, act in time.")


def _ids(items, key, allowed):
    return [x for x in (items or []) if isinstance(x, dict) and x.get(key) in allowed]


def handout(case):
    scr = case["screen"]
    answered = {a["question_id"] for a in case.get("answers", []) if a.get("status") == "answered"}
    open_q = [q for q in case.get("questions", []) if q["id"] not in answered]
    dl = "\n".join(f"{d['id']}: {d['action']} - " + (d["earliest"].isoformat() if d.get("earliest") else "date not yet known")
                   + (" (precautionary planning date)" if d.get("precautionary") else "") for d in case["deadlines"])
    acts = "\n".join(f"{a['id']} (who: {a['who']}): {a['what']}" for a in scr["actions"])
    prompt = "\n\n".join([SYSTEM_ROLE,
        "TASK: Write the CLIENT HANDOUT from the checked assessment below, addressed directly to the client ('you'), in "
        "everyday words and short sentences. Keep exactly the same facts, dates and actions; add no new advice and no "
        "legal rules. Rewrite every action whose 'who' is the client; for other actions say the social worker will "
        "handle it, without implying it is done. Include the open questions with a short reason and a helpful document. "
        "Never present a provisional result as certain.",
        'Answer JSON only: {"act_now": "<one or two sentences if something must happen urgently, else empty>", '
        '"summary": "<two or three sentences>", "actions": [{"action_id": "A1", "text": "..."}], '
        '"questions": [{"question_id": "Q1", "text": "...", "why": "...", "helpful_document": "..."}], '
        '"uncertain": "<what is still unclear, one sentence>"}',
        "SITUATION:\n" + scr["situation"], "ACTIONS:\n" + (acts or "none"), "DEADLINES:\n" + (dl or "none"),
        "OPEN QUESTIONS:\n" + ("\n".join(f"{q['id']}: {q['question']} (why: {q['why_we_ask']})" for q in open_q) or "none")])
    raw = ask_json(prompt, trace=case["trace"], step="11 handout", max_tokens=1500)
    out = {k: str(raw.get(k) or "") for k in ("act_now", "summary", "uncertain")}
    out["actions"] = [{"action_id": a["action_id"], "text": str(a.get("text", ""))}
                      for a in _ids(raw.get("actions"), "action_id", {a["id"] for a in scr["actions"]})]
    out["questions"] = [{k: str(q.get(k, "")) for k in ("question_id", "text", "why", "helpful_document")}
                        for q in _ids(raw.get("questions"), "question_id", {q["id"] for q in open_q})]
    # code check: same actions, no new dates or law
    ok_dates = allowed_dates(case)
    arts = {s["article"] for s in case["sources"].values() if s["type"] == "law"}
    removed = []
    for k in ("summary", "act_now", "uncertain"):
        out[k] = checks.clean_text(out[k], arts, [], ok_dates, f"handout {k}", removed)
    for a in out["actions"]:
        a["text"] = checks.clean_text(a["text"], arts, [], ok_dates, f"handout {a['action_id']}", removed)
    client_actions = {a["id"] for a in scr["actions"] if a["who"] == "client"}
    out["check"] = {"removed": removed,
                    "client_actions_missing": sorted(client_actions - {a["action_id"] for a in out["actions"]})}
    out["contacts"] = [{"name": c["name"], "phones": c.get("phones", []), "email": c.get("email"), "url": c.get("url"),
                        "address": c.get("address")} for c in case["contacts"]]
    out["disclosure"] = CLIENT_DISCLOSURE
    case["handout"] = {"English": out}
    return out


def translate(case, language):
    """Translate the handout into the client's language. The English version stays next to it."""
    src = case["handout"]["English"]
    payload = {k: src[k] for k in ("act_now", "summary", "uncertain", "disclosure")}
    payload["actions"] = [a["text"] for a in src["actions"]]
    payload["questions"] = [{"text": q["text"], "why": q["why"], "helpful_document": q["helpful_document"]} for q in src["questions"]]
    raw = ask_json(f"Translate every string value of this JSON from English into {language}. Keep the keys, the list "
                   "lengths, names, dates, numbers, phone numbers and article citations exactly. Use simple, everyday "
                   "words. Answer with the translated JSON only.\n\n" + json.dumps(payload, ensure_ascii=False),
                   trace=case["trace"], step=f"11 translate ({language})", max_tokens=2500)
    out = {k: str(raw.get(k) or "") for k in ("act_now", "summary", "uncertain", "disclosure")}
    out["actions"] = [str(x) for x in (raw.get("actions") or [])]
    out["questions"] = [{k: str(q.get(k, "")) for k in ("text", "why", "helpful_document")}
                        for q in (raw.get("questions") or []) if isinstance(q, dict)]
    # code checks: dates and numbers must survive unchanged, and nothing may go missing
    nums = lambda t: set(re.findall(r"\d[\d.:'/-]*\d|\d", t))
    lost = nums(json.dumps(payload)) - nums(json.dumps(out, ensure_ascii=False))
    out["check"] = {"numbers_changed_or_missing": sorted(lost),
                    "items_missing": (len(payload["actions"]) - len(out["actions"])) + (len(payload["questions"]) - len(out["questions"]))}
    case["handout"][language] = out
    return out


# ---------------------------------------------------------------- expert brief (output.md section 7)

# AI writes only the descriptive fields; the legal parts are assembled by code (approval A: less AI legal prose)
BRIEF_FIELDS = ["main_issue", "objective_and_context", "lawyer_asked_to_assess"]


def brief(case):
    scr = case["screen"]
    data = {"lane": case["lane"], "lane_rule": case["lane_rule"], "indices": case["indices"],
            "index_reasons": case["index_reasons"], "situation": scr["situation"],
            "issues": [{"issue": i["issue"], "articles": i["articles"]} for i in scr["issues"]],
            "deadlines": [{k: d.get(k) for k in ("id", "action", "earliest", "precautionary", "legal_basis")} for d in case["deadlines"]]}
    prompt = "\n\n".join([SYSTEM_ROLE,
        "TASK: Fill three free-text parts of an EXPERT BRIEF for a lawyer, to be read in two minutes. Use only the "
        "assessment and facts below. main_issue: the client's problem in one or two neutral sentences. "
        "objective_and_context: what the client wants and the relevant personal context. lawyer_asked_to_assess: two or "
        "three open QUESTIONS for the lawyer, phrased as questions; state no legal conclusions and no legal rules.",
        "Answer JSON only: {" + ", ".join(f'"{k}": "..."' for k in BRIEF_FIELDS) + "}",
        "ASSESSMENT:\n" + json.dumps(data, default=str, ensure_ascii=False), "FACTS:\n" + facts_block(case)])
    raw = ask_json(prompt, trace=case["trace"], step="11 expert brief", max_tokens=1200)
    ok_dates = allowed_dates(case)
    arts = {s["article"] for s in case["sources"].values() if s["type"] == "law"}
    removed = []
    out = {k: checks.clean_text(str(raw.get(k) or ""), arts, [], ok_dates, f"brief {k}", removed) for k in BRIEF_FIELDS}
    answered = {a["question_id"] for a in case.get("answers", []) if a.get("status") == "answered"}
    out.update({
        "review_status": "AI draft - not yet checked by the social worker",
        "escalation_trigger": case["lane_rule"],
        "immediate_risk": "; ".join(
            [f"{d['action']} (by {d['earliest'] if isinstance(d['earliest'], str) else d['earliest'].isoformat()})"
             for d in case.get("deadlines", []) if d.get("earliest")]
            + [r for k in ("urgency", "severity") if case["indices"].get(k) == "high" for r in case["index_reasons"][k]])
            or "No running deadline or high-risk factor identified by the tool; please check.",
        "preliminary_assessment": [{"issue": i["issue"], "articles": i["articles"],
                                    "rules": [x["text"] + f" [{x['para']}]" for x in i.get("sentences", [])]}
                                   for i in scr["issues"]],
        "check": {"removed": removed},
        "facts": [{"statement": f["statement"], "status": {"reported": "reported by the client", "documented": "documented",
                                                           "inferred": "inferred - check"}.get(f["status"], f["status"])}
                  for f in case["facts"]],
        "disputed": [f"{d['topic']}: client says {d['client_position']}; {d['other_party']} says {d['other_position']}"
                     for d in case.get("disputes", [])],
        "chronology": [{"date": e.get("date") or (f"{e.get('date_from')} to {e.get('date_to')}" if e.get("date_from") else "unknown"),
                        "event": e["event"], "source": e.get("source", "client's description")} for e in case.get("events", [])],
        "deadlines": [{"action": d["action"], "date": d["earliest"].isoformat() if d.get("earliest") else "not established",
                       "precautionary": d.get("precautionary"), "basis": d["legal_basis"], "calculation": d["steps"]}
                      for d in case["deadlines"]],
        "evidence_available": [doc["name"] for doc in case.get("uploaded", [])] or ["No documents seen yet"],
        "missing": [q["question"] for q in case.get("questions", []) if q["id"] not in answered],
        "already_done": "Nothing recorded by the tool.",
    })
    case["brief"] = out
    return out
