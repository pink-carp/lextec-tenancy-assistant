"""Web service. Run locally:  .venv/bin/uvicorn app.server:app --port 8000   then open http://localhost:8000

Stateless: the browser holds the case and sends it back with every step, so nothing is stored on the server
(this also lets it run on serverless hosting). "End case" simply discards it in the browser.
If the environment variable APP_ACCESS_CODE is set, every /api/ call needs the header X-Access-Code."""
import json
import os
from datetime import date
from pathlib import Path

from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel

from . import outputs, pipeline

app = FastAPI(title="Tenancy information assistant for social workers")
STATIC = Path(__file__).resolve().parent / "static"
ROOT = STATIC.parent.parent


@app.middleware("http")
async def access_code(request: Request, call_next):
    code = os.environ.get("APP_ACCESS_CODE")
    open_paths = ("/api/examples", "/api/benchmark")  # no cost, no client data
    if (code and request.url.path.startswith("/api/") and request.url.path not in open_paths
            and request.headers.get("X-Access-Code") != code):
        return JSONResponse({"detail": "access code required"}, status_code=401)
    return await call_next(request)


def _load(state: dict):
    """Rebuild a case from the browser's copy (dates travel as ISO strings)."""
    if not state or "id" not in state:
        raise HTTPException(400, "Case state missing; please start again.")
    case = dict(state)
    for d in case.get("deadlines", []):
        for k in ("earliest", "latest"):
            if isinstance(d.get(k), str):
                d[k] = date.fromisoformat(d[k])
    return case


def _out(case, keys):
    view = {k: case.get(k) for k in keys} | {"id": case["id"], "state": case}
    return JSONResponse(pipeline.to_jsonable(view))


class NewCase(BaseModel):
    description: str
    client_language: str = "English"


class Confirm(BaseModel):
    state: dict
    facts: list | None = None
    signals: list | None = None
    vulnerability_score: int | None = None


class Answers(BaseModel):
    state: dict
    answers: list = []
    override: dict | None = None


class Doc(BaseModel):
    state: dict
    name: str
    text: str


class Lang(BaseModel):
    state: dict
    language: str = "English"


@app.get("/")
def index():
    return FileResponse(STATIC / "index.html")


@app.get("/benchmark")
def benchmark_page():
    return FileResponse(STATIC / "benchmark.html")


@app.get("/api/examples")
def examples():
    """The legal team's example prompts, for demonstrations."""
    f = ROOT / "bench" / "cases.json"
    return [{"case_no": c["case_no"], "prompt": c["prompt"]} for c in json.loads(f.read_text())] if f.exists() else []


@app.get("/api/benchmark")
def benchmark_data():
    res = ROOT / "bench" / "results"
    load = lambda n: json.loads((res / n).read_text()) if (res / n).exists() else {}
    return {"summary": load("summary.json"), "lanes": load("lanes.json")}


@app.post("/api/case")
def create(body: NewCase):
    if len(body.description.strip()) < 20:
        raise HTTPException(400, "Please describe the situation in a few sentences.")
    case = pipeline.new_case(body.description, body.client_language, today=date.today())
    pipeline.understand(case)
    pipeline.gather_sources(case)
    case["provisional_lane"] = pipeline.provisional_lane(case)
    return _out(case, ["sentences", "masking", "understanding", "facts", "disputes", "signals", "events",
                       "documents", "intents", "situations", "deadlines", "provisional_lane",
                       "vulnerability_score", "vulnerability_source", "vulnerability_indicators",
                       "municipality", "articles_expanded"])


@app.post("/api/case/questions")
def ask(body: Confirm):
    case = _load(body.state)
    pipeline.confirm(case, body.facts, body.signals, body.vulnerability_score)
    pipeline.questions(case)
    case["provisional_lane"] = pipeline.provisional_lane(case)
    return _out(case, ["questions", "dropped_questions", "sources", "provisional_lane"])


@app.post("/api/case/upload")
async def upload(file: UploadFile = File(...), state: str = Form(...)):
    case = _load(json.loads(state))
    content = await file.read()
    return JSONResponse(pipeline.to_jsonable(outputs.read_upload(case, file.filename, content) | {"state": case}))


@app.post("/api/case/document")
def document(body: Doc):
    case = _load(body.state)
    outputs.add_document(case, body.name, body.text)
    return _out(case, [])


@app.post("/api/case/assess")
def assess(body: Answers):
    case = _load(body.state)
    outputs.apply_answers(case, body.answers)
    pipeline.assess(case)
    pipeline.score(case, override=body.override)
    pipeline.write(case)
    pipeline.verify(case)
    return _out(case, ["lane", "lane_rule", "indices", "index_reasons", "deadlines", "contacts", "screen",
                       "verification", "applicability", "sources", "facts", "disputes", "events", "scope_note",
                       "dropped_deadlines", "vulnerability_score", "vulnerability_source"])


@app.post("/api/case/handout")
def make_handout(body: Lang):
    case = _load(body.state)
    out = {"English": outputs.handout(case)}
    if body.language and body.language.lower() != "english":
        out[body.language] = outputs.translate(case, body.language)
    return JSONResponse(pipeline.to_jsonable({"handout": out, "state": case}))


@app.post("/api/case/brief")
def make_brief(body: Lang):
    case = _load(body.state)
    return JSONResponse(pipeline.to_jsonable({"brief": outputs.brief(case), "state": case}))
