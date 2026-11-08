"""Step 6 (answers, uploads) and step 11 (client handout, translation, expert brief).

The handout and brief are rewritten from the verified result; they never re-analyse the case."""
import base64
import io
from datetime import date

from . import checks
from .llm import chat
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
                ev = {"id": f"E{len(events) + 1}", "event": q["question"], "sentences": [],
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
    case["answers"] = clean
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
    """Called after the social worker confirmed the extracted text."""
    text = mask(text)[0]
    case.setdefault("documents", []).append({"name": name, "text": text[:6000]})
    case.setdefault("facts", []).append({"id": f"F{len(case['facts']) + 1}", "heading": "what",
                                         "statement": f"Document '{name}' (uploaded, text confirmed by the social worker): {text[:1500]}",
                                         "sentences": [], "status": "documented"})
    return case


# ---------------------------------------------------------------- handout


def handout(case):
    scr = case["screen"]
    action_ids = [a["id"] for a in scr["actions"]]
    open_q = [q for q in case.get("questions", [])
              if q["id"] not in {a["question_id"] for a in case.get("answers", []) if a.get("status") == "answered"}]
    q_ids = [q["id"] for q in open_q] or ["none"]
    schema = {"type": "object", "properties": {
        "act_now": {"type": "string", "description": "one or two sentences if something must happen urgently, else empty"},
        "summary": {"type": "string"},
        "actions": {"type": "array", "maxItems": 5, "items": {"type": "object", "properties": {
            "action_id": {"type": "string", "enum": action_ids or ["none"]}, "text": {"type": "string"}},
            "required": ["action_id", "text"]}},
        "questions": {"type": "array", "maxItems": 6, "items": {"type": "object", "properties": {
            "question_id": {"type": "string", "enum": q_ids}, "text": {"type": "string"},
            "why": {"type": "string"}, "helpful_document": {"type": "string"}},
            "required": ["question_id", "text", "why", "helpful_document"]}},
        "uncertain": {"type": "string"}},
        "required": ["act_now", "summary", "actions", "questions", "uncertain"]}
    dl = "\n".join(f"{d['id']}: {d['action']} — {d['earliest'].isoformat() if d.get('earliest') else 'date not yet known'}"
                   + (" (precautionary planning date)" if d.get("precautionary") else "") for d in case["deadlines"])
    system = "\n\n".join([SYSTEM_ROLE,
        "TASK: Write the CLIENT HANDOUT from the verified assessment below, addressed directly to the client "
        "('you'), in everyday words and short sentences. Keep exactly the same facts, dates and actions; do not add "
        "new advice. Rewrite every action whose 'who' is the client; for social-worker actions say the social "
        "worker will handle it, without implying it is done. Include the still-open questions with a short reason "
        "and a helpful document. Explain unavoidable legal terms. Never present a provisional result as certain. "
        "This is legal information, not legal advice."])
    user = ("ASSESSMENT:\n" + str({"situation": scr["situation"], "actions": scr["actions"], "issues": scr["issues"],
                                   "open_points": scr["open_points"], "lane": case["lane"]}) +
            "\n\nDEADLINES:\n" + (dl or "none") + "\n\nOPEN QUESTIONS:\n" +
            "\n".join(f"{q['id']}: {q['question']} (why: {q['why_we_ask']})" for q in open_q))
    out = chat([{"role": "system", "content": system}, {"role": "user", "content": user}], schema=schema,
               schema_name="handout", max_tokens=1800, trace=case["trace"], step="11 handout")
    # code check: same actions, no new dates or law
    ok_dates = allowed_dates(case)
    arts = {s["article"] for s in case["sources"].values() if s["type"] == "law"}
    decs = [s["label"] for s in case["sources"].values() if s["type"] == "decision"]
    removed = []
    out["summary"] = checks.clean_text(out["summary"], arts, decs, ok_dates, "handout summary", removed)
    out["act_now"] = checks.clean_text(out["act_now"], arts, decs, ok_dates, "handout act now", removed)
    for a in out["actions"]:
        a["text"] = checks.clean_text(a["text"], arts, decs, ok_dates, f"handout {a['action_id']}", removed)
    client_actions = {a["id"] for a in scr["actions"] if a["who"] == "client"}
    covered = {a["action_id"] for a in out["actions"]}
    out["check"] = {"removed": removed, "client_actions_missing": sorted(client_actions - covered)}
    out["contacts"] = [{"name": c["name"], "phones": c.get("phones", []), "email": c.get("email"), "url": c.get("url"),
                        "address": c.get("address")} for c in case["contacts"]]
    case["handout"] = {"English": out}
    return out


def translate(case, language):
    """Translate the handout into the client's language. The English version stays next to it."""
    src = case["handout"]["English"]
    payload = {k: src[k] for k in ("act_now", "summary", "uncertain")}
    payload["actions"] = [a["text"] for a in src["actions"]]
    payload["questions"] = [{"text": q["text"], "why": q["why"], "helpful_document": q["helpful_document"]} for q in src["questions"]]
    schema = {"type": "object", "properties": {
        "act_now": {"type": "string"}, "summary": {"type": "string"}, "uncertain": {"type": "string"},
        "actions": {"type": "array", "items": {"type": "string"}},
        "questions": {"type": "array", "items": {"type": "object", "properties": {
            "text": {"type": "string"}, "why": {"type": "string"}, "helpful_document": {"type": "string"}},
            "required": ["text", "why", "helpful_document"]}}},
        "required": ["act_now", "summary", "uncertain", "actions", "questions"]}
    out = chat([{"role": "system", "content": f"Translate every string value of this JSON from English into {language}. "
                                              "Keep names, dates, numbers, phone numbers and article citations exactly. "
                                              "Use simple, everyday words."},
                {"role": "user", "content": str(payload)}],
               schema=schema, schema_name="translation", max_tokens=2000, trace=case["trace"], step=f"11 translate ({language})")
    # code check: dates and numbers must survive translation unchanged
    import re
    nums = lambda t: set(re.findall(r"\d[\d.:'/-]*\d|\d", t))
    lost = nums(str(payload)) - nums(str(out))
    out["check"] = {"numbers_changed_or_missing": sorted(lost)}
    case["handout"][language] = out
    return out


# ---------------------------------------------------------------- expert brief (output.md section 7)


def brief(case):
    scr = case["screen"]
    schema = {"type": "object", "properties": {
        "main_issue": {"type": "string"}, "escalation_trigger": {"type": "string"},
        "immediate_risk": {"type": "string"}, "objective_and_context": {"type": "string"},
        "preliminary_assessment": {"type": "string"}, "lawyer_asked_to_assess": {"type": "string"}},
        "required": ["main_issue", "escalation_trigger", "immediate_risk", "objective_and_context",
                     "preliminary_assessment", "lawyer_asked_to_assess"]}
    system = "\n\n".join([SYSTEM_ROLE,
        "TASK: Fill the free-text parts of an EXPERT BRIEF for a lawyer, to be read in two minutes. Use only the "
        "verified assessment. Distinguish a possible legal argument from an established conclusion; name the "
        "sources by their IDs. One to three sentences per field."])
    user = str({"lane": case["lane"], "lane_rule": case["lane_rule"], "indices": case["indices"],
                "index_reasons": case["index_reasons"], "situation": scr["situation"], "issues": scr["issues"],
                "deadlines": [{k: d.get(k) for k in ("id", "action", "earliest", "precautionary", "legal_basis")} for d in case["deadlines"]]})
    out = chat([{"role": "system", "content": system}, {"role": "user", "content": user}], schema=schema,
               schema_name="brief", max_tokens=1200, trace=case["trace"], step="11 expert brief")
    answered = {a["question_id"] for a in case.get("answers", []) if a.get("status") == "answered"}
    out.update({
        "review_status": "AI draft – not yet checked by the social worker",
        "facts": [{"statement": f["statement"], "status": {"reported": "reported by the client", "documented": "documented",
                                                           "inferred": "inferred – check"}.get(f["status"], f["status"])}
                  for f in case["facts"]],
        "disputed": [f"{d['topic']}: client says {d['client_position']}; {d['other_party']} says {d['other_position']}"
                     for d in case.get("disputes", [])],
        "chronology": [{"date": e.get("date") or (f"{e.get('date_from')}–{e.get('date_to')}" if e.get("date_from") else "unknown"),
                        "event": e["event"], "source": e.get("source", "client's description")} for e in case.get("events", [])],
        "deadlines": [{"action": d["action"], "date": d["earliest"].isoformat() if d.get("earliest") else "not established",
                       "precautionary": d.get("precautionary"), "basis": d["legal_basis"], "calculation": d["steps"]}
                      for d in case["deadlines"]],
        "evidence_available": [doc["name"] for doc in case.get("documents", [])] or ["No documents seen yet"],
        "missing": [q["question"] for q in case.get("questions", []) if q["id"] not in answered],
        "already_done": "Nothing recorded by the tool.",
    })
    case["brief"] = out
    return out
