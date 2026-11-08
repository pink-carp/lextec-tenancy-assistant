"""Step 6 (answers, uploads) and step 11 (client handout, translation, expert brief).

The handout and brief are rewritten from the verified result; they never re-analyse the case."""
import base64
import json
import re
import io
from datetime import date  # noqa: F401

from . import checks, scoring
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

# Client disclosure printed on the handout. The data sentence uses the cautious variant because
# the AI provider's and the host's data retention have not been verified.
CLIENT_DISCLOSURE = (
    "About this sheet: Your social worker made this sheet with a computer tool and checked it. Its legal texts were "
    "checked in advance; artificial intelligence (AI) wrote the summary. It may contain mistakes. This is general legal "
    "information, not legal advice. It does not replace a lawyer. Our tool does not save your case. Your information was "
    "sent to an AI service (Public AI), which may keep data for a short time. For advice on your own case, contact a "
    "service on this sheet. If a deadline is mentioned, act in time.")


def _ids(items, key, allowed):
    return [x for x in (items or []) if isinstance(x, dict) and x.get(key) in allowed]


def handout(case):
    """v4: built by code from the checked module texts written for clients; no new AI text (translation is separate)."""
    scr = case["screen"]
    answered = {a["question_id"] for a in case.get("answers", []) if a.get("status") == "answered"}
    act_now = []
    for d in case.get("deadlines", []):
        if d.get("who_must_act") == "client" and d.get("earliest"):
            day = d["earliest"] if isinstance(d["earliest"], str) else d["earliest"].isoformat()
            act_now.append(f"{d['action']}: by {day}" + (" at the latest (this date is an estimate: act earlier)" if d.get("precautionary") or d.get("latest") != d.get("earliest") else "") + ".")
        elif d.get("who_must_act") == "client" and d.get("not_determinable_reason") == "missing_fact":
            act_now.append(f"{d['action']}: a time limit may be running. Find out the exact date the letter arrived.")
    act_now += [a["client_text"] for a in scr["actions"] if a.get("group") == "immediate" and a.get("client_text")][:2]
    if "violence_threats_or_coercion" in scoring.safety_signs(case) or case["understanding"].get("immediate_danger"):
        act_now.insert(0, "If you are in danger, call the police on 117. Victim support is available day and night on 142.")
    points = [p["client_text"] for b in scr.get("modules", []) for p in b["points"] if p.get("client_text")]
    out = {"act_now": " ".join(act_now), "summary": scr.get("situation", ""),
           "points": points,
           "actions": [{"action_id": a["id"], "text": a["client_text"]} for a in scr["actions"] if a.get("client_text")],
           "questions": [{"question_id": q["id"], "text": q["question"], "why": q.get("why_we_ask", ""), "helpful_document": ""}
                         for q in case.get("questions", []) if q["id"] not in answered],
           "uncertain": "" if not scr.get("out_of_scope") else scr["out_of_scope"],
           "check": {"removed": [], "client_actions_missing": []}, "disclosure": CLIENT_DISCLOSURE,
           "contacts": [{"name": c["name"], "phones": c.get("phones", []), "email": c.get("email"), "url": c.get("url"),
                         "address": c.get("address")} for c in case["contacts"]]}
    case["handout"] = {"English": out}
    return out


def translate(case, language):
    """Translate the handout into the client's language. The English version stays next to it."""
    src = case["handout"]["English"]
    payload = {k: src[k] for k in ("act_now", "summary", "uncertain", "disclosure")}
    payload["points"] = list(src.get("points", []))
    payload["actions"] = [a["text"] for a in src["actions"]]
    payload["questions"] = [{"text": q["text"], "why": q["why"], "helpful_document": q["helpful_document"]} for q in src["questions"]]
    raw = ask_json(f"Translate every string value of this JSON from English into {language}. Keep the keys, the list "
                   "lengths, names, dates, numbers, phone numbers and article citations exactly. Use simple, everyday "
                   "words. Answer with the translated JSON only.\n\n" + json.dumps(payload, ensure_ascii=False),
                   trace=case["trace"], step=f"11 translate ({language})", max_tokens=2500)
    out = {k: str(raw.get(k) or "") for k in ("act_now", "summary", "uncertain", "disclosure")}
    out["actions"] = [str(x) for x in (raw.get("actions") or [])]
    out["points"] = [str(x) for x in (raw.get("points") or [])]
    out["questions"] = [{k: str(q.get(k, "")) for k in ("text", "why", "helpful_document")}
                        for q in (raw.get("questions") or []) if isinstance(q, dict)]
    # code checks: dates and numbers must survive unchanged, and nothing may go missing
    nums = lambda t: set(re.findall(r"\d[\d.:'/-]*\d|\d", t))
    lost = nums(json.dumps(payload)) - nums(json.dumps(out, ensure_ascii=False))
    out["check"] = {"numbers_changed_or_missing": sorted(lost),
                    "items_missing": (len(payload["actions"]) - len(out["actions"])) + (len(payload["questions"]) - len(out["questions"]))
                    + (len(payload["points"]) - len(out["points"]))}
    case["handout"][language] = out
    return out


# ---------------------------------------------------------------- expert brief (output.md section 7)

# AI writes only the descriptive fields; the legal parts are assembled by code (approval A: less AI legal prose)
# Apertus writes only the two descriptive fields; everything legal comes from the checked modules and code
BRIEF_FIELDS = ["main_issue", "objective_and_context"]


def brief(case):
    """v4: no new AI text. Main issue = the situation summary already shown (checked by code); context = the client's own
    (masked) words; risks from the code-calculated deadlines and lane; legal parts from the checked modules."""
    scr = case["screen"]
    removed = []
    out = {"main_issue": scr.get("situation", ""), "objective_and_context": "Client's own words (masked): " + case["masked"]}
    answered = {a["question_id"] for a in case.get("answers", []) if a.get("status") == "answered"}
    from .events import events as ev_names
    names = ev_names()
    out.update({
        "review_status": "Draft from the tool - please check before sending",
        "check": {"removed": removed},
        "escalation_trigger": case["lane_rule"],
        "immediate_risk": "; ".join(
            [f"{d['action']} (by {d['earliest'] if isinstance(d['earliest'], str) else d['earliest'].isoformat()})"
             for d in case.get("deadlines", []) if d.get("earliest")]
            + [r for k in ("urgency", "severity") if case["indices"].get(k) == "high" for r in case["index_reasons"][k]])
            or "No running deadline or high-risk factor identified by the tool; please check.",
        "preliminary_assessment": [{"issue": b["title"], "articles": sorted({x for p in b["points"] for x in p.get("basis", [])}),
                                    "rules": [p["text"] for p in b["points"]]} for b in scr.get("modules", [])],
        "lawyer_asked_to_assess": " ".join(scr.get("lawyer_questions", [])) or "Please assess the client's legal position.",
        "deciding_facts": [{"fact": names.get(k, k), "answer": {"A": "yes", "B": "no", "C": "unknown"}[v["answer"]],
                            "source": v.get("source", "")} for k, v in case.get("event_status", {}).items() if v.get("source") != "code"],
        "facts": [{"statement": f["statement"], "status": {"reported": "reported by the client", "documented": "documented",
                                                           "inferred": "check wording"}.get(f["status"], f["status"])}
                  for f in case["facts"]],
        "disputed": [f"{d['topic']}: client says {d['client_position']}; {d['other_party']} says {d['other_position']}"
                     for d in case.get("disputes", [])],
        "chronology": [{"date": e.get("date") or (f"{e.get('date_from')} to {e.get('date_to')}" if e.get("date_from") else "unknown"),
                        "event": e["event"], "source": e.get("source", "client's description")} for e in case.get("events", [])],
        "deadlines": [{"action": d["action"], "date": (d["earliest"] if isinstance(d["earliest"], str) else d["earliest"].isoformat()) if d.get("earliest") else "not established",
                       "precautionary": d.get("precautionary"), "basis": d["legal_basis"], "calculation": d["steps"]}
                      for d in case["deadlines"]],
        "evidence_available": [doc["name"] for doc in case.get("uploaded", [])] or ["No documents seen yet"],
        "missing": [q["question"] for q in case.get("questions", []) if q["id"] not in answered],
        "already_done": "Nothing recorded by the tool.",
    })
    case["brief"] = out
    return out
