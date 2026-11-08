"""Benchmark: our harness vs the same model without harness vs a more expensive model.

All systems get the same legal team documents and the full tenancy law. Cases are the team's
9 example cases (bench/cases.json); the expected answers are never shown to any system.

Usage: python bench/run_bench.py run [systems...]   -> raw outputs in bench/results/<system>/case_<n>.json
       python bench/run_bench.py score              -> metrics in bench/results/summary.json
"""
import json
import re
import sys
import time
import traceback
from concurrent.futures import ThreadPoolExecutor
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from app import checks, corpus, guidance, pipeline  # noqa: E402
from app.llm import chat, PRICES  # noqa: E402

ROOT = Path(__file__).resolve().parent
RES = ROOT / "results"
TODAY = date(2026, 11, 8)
CASES = json.load(open(ROOT / "cases.json"))
# Judge: Nemotron 120B (larger than Apertus 70B). Command A+ was planned but the account hit its monthly
# request limit on 2026-11-08. Nemotron also judges its own baseline answers, which if anything favours
# that baseline, not our harness.
JUDGE = "aisingapore/Nemotron-SEA-LION-v4.8-120B-A12B"

SYSTEMS = {
    "harness_apertus70b": {"kind": "harness", "model": "swiss-ai/apertus-v1.5-70b"},      # round 1
    "harness_v2_apertus70b": {"kind": "harness", "model": "swiss-ai/apertus-v1.5-70b"},   # round 2: grounded deadlines, recalibrated lanes
    "harness_v3_apertus70b": {"kind": "harness", "model": "swiss-ai/apertus-v1.5-70b"},   # round 3: + deadline applicability check
    "harness_final_apertus70b": {"kind": "harness", "model": "swiss-ai/apertus-v1.5-70b"},  # final: + code-review fixes, per-claim checks
    "plain_apertus70b": {"kind": "plain", "model": "swiss-ai/apertus-v1.5-70b"},
    "plain_nemotron120b": {"kind": "plain", "model": "aisingapore/Nemotron-SEA-LION-v4.8-120B-A12B"},
}

# Repeat runs (same configuration) to measure run-to-run variation of the lane decision.
for _base in ("harness_final_apertus70b", "plain_apertus70b", "plain_nemotron120b"):
    for _r in ("r2", "r3"):
        SYSTEMS[f"{_base}_{_r}"] = SYSTEMS[_base]

PLAIN_SCHEMA = {"type": "object", "properties": {
    "lane": {"type": "string", "enum": ["1", "2", "3"]},
    "lane_reason": {"type": "string"},
    "follow_up_questions": {"type": "array", "maxItems": 8, "items": {"type": "object", "properties": {
        "question": {"type": "string"}, "why": {"type": "string"}}, "required": ["question", "why"]}},
    "deadlines": {"type": "array", "maxItems": 4, "items": {"type": "object", "properties": {
        "action": {"type": "string"}, "deadline": {"type": "string"}, "legal_basis": {"type": "string"}},
        "required": ["action", "deadline", "legal_basis"]}},
    "actions": {"type": "array", "maxItems": 6, "items": {"type": "object", "properties": {
        "what": {"type": "string"}, "who": {"type": "string"}, "when": {"type": "string"}},
        "required": ["what", "who", "when"]}},
    "legal_rules": {"type": "array", "maxItems": 8, "items": {"type": "object", "properties": {
        "statement": {"type": "string"}, "citation": {"type": "string", "description": "e.g. Art. 257d Abs. 1 OR"}},
        "required": ["statement", "citation"]}},
    "summary": {"type": "string"}},
    "required": ["lane", "lane_reason", "follow_up_questions", "deadlines", "actions", "legal_rules", "summary"]}


def run_plain(model, prompt):
    trace = []
    system = "\n\n".join([
        pipeline.SYSTEM_ROLE, f"Today's date is {TODAY.isoformat()}.",
        "TASK: Assess the client's situation following the legal team's documents below. Assign a lane (1, 2 or 3) "
        "per output.md, list the follow-up questions the social worker should ask, identify running deadlines with "
        "their dates where possible, give action recommendations, list the legal rules relied on with exact "
        "citations (e.g. 'Art. 257d Abs. 1 OR', court decisions by number), and a short neutral case summary.",
        "METHOD (legal_workflow.md):\n" + guidance.legal_workflow(),
        "ESCALATION FRAMEWORK (escalation.md):\n" + guidance.escalation(),
        "OUTPUT RULES (output.md):\n" + guidance.output_rules(),
        "DEADLINE RULES (deadlines.md):\n" + guidance.deadlines(),
        "TENANCY LAW (OR Art. 253-274g):\n" + corpus.tenancy_text(),
    ])
    t = time.time()
    out = chat([{"role": "system", "content": system}, {"role": "user", "content": prompt}], schema=PLAIN_SCHEMA,
               schema_name="assessment", model=model, max_tokens=3000, trace=trace, step="plain")
    out["lane"] = int(out["lane"])
    return {"output": out, "seconds": round(time.time() - t, 1), "cost_usd": sum(x["cost_usd"] for x in trace),
            "trace": trace}


def run_harness(prompt):
    t = time.time()
    case = pipeline.run_all(prompt, today=TODAY)
    return {"case": pipeline.to_jsonable(case), "seconds": round(time.time() - t, 1),
            "cost_usd": sum(x["cost_usd"] for x in case["trace"])}


def run(systems):
    def one(sysname, c):
        f = RES / sysname / f"case_{c['case_no']}.json"
        if f.exists():
            return
        f.parent.mkdir(parents=True, exist_ok=True)
        spec = SYSTEMS[sysname]
        try:
            res = run_harness(c["prompt"]) if spec["kind"] == "harness" else run_plain(spec["model"], c["prompt"])
            res["error"] = None
        except Exception as e:  # recorded, so failures count in the benchmark
            res = {"error": f"{type(e).__name__}: {e}", "tb": traceback.format_exc()[-1500:]}
        f.write_text(json.dumps(res, ensure_ascii=False, indent=1))
        print(sysname, c["case_no"], "ERROR " + res["error"][:120] if res["error"] else f"{res['seconds']}s", flush=True)

    jobs = [(s, c) for s in systems for c in CASES]
    with ThreadPoolExecutor(4) as ex:
        list(ex.map(lambda a: one(*a), jobs))


# ---------------------------------------------------------------- scoring

_ART_NORM = re.compile(r"(OR|ZPO|ZGB|VMWG) (\d+[a-z]?)")


def normalise(system, res):
    """Common view of any system's output: lane, questions, claims [(statement, [article/decision ids])], all text."""
    if system.startswith("harness"):
        c = res["case"]
        scr = c["screen"]
        claims = [(r["statement"], r["sources"]) for i in scr["issues"] for r in i["rules"]]
        # scan only the written text, not the source-ID lists (which the citation sets below cover)
        text = " ".join([scr["situation"], scr["lane_explanation"]] + [a["what"] + " " + a["when"] for a in scr["actions"]]
                        + [r["statement"] for st in scr["issues"] for r in st["rules"]] + [i["application"] for i in scr["issues"]]
                        + scr["open_points"] + [d["action"] for d in c["deadlines"]])
        cited = {checks.source_article(s) or s for s in [x for st, ss in claims for x in ss]}
        cited |= {checks.source_article(s) or s for a in scr["actions"] for s in a["sources"]}
        cited |= {checks.source_article(s) or s for d in c["deadlines"] for s in d["legal_basis"]}
        questions = [q["question"] for q in c["questions"]]
        # question citations are shown to the social worker too (baselines' question texts are scanned likewise)
        cited |= {checks.source_article(s) or s for q in c["questions"] for s in q["legal_basis"]}
        text += " " + " ".join(q["question"] + " " + q["why_we_ask"] for q in c["questions"])
        return c["lane"], questions, claims, text, cited
    o = res["output"]
    claims = [(r["statement"], [r["citation"]]) for r in o["legal_rules"]]
    text = json.dumps(o, ensure_ascii=False)
    cited = set()
    for frag in [r["citation"] for r in o["legal_rules"]] + [d["legal_basis"] for d in o["deadlines"]] + [text]:
        cited |= checks.mentioned_articles(frag)
        cited |= checks.mentioned_decisions(frag)
    return o["lane"], [q["question"] for q in o["follow_up_questions"]], claims, text, cited


def decision_exists(label, cache):
    if label in cache:
        return cache[label]
    known = {d["id"] for d in corpus.decisions().values()}
    if label in known or any(label in k or k.endswith(label) for k in known):
        cache[label] = True
        return True
    import httpx
    q = re.sub(r"^(BGer|BGE)\s+", "", label) if not label.startswith("BGE") else label
    r = httpx.get("https://mcp.opencaselaw.ch/api/lookup", params={"q": q, "limit": 1},
                  headers={"User-Agent": "lextec-hackathon-prototype/0.1"}, timeout=60).json()
    cache[label] = bool(r.get("results"))
    return cache[label]


def judge_claims(claims, case_prompt):
    """Independent judge (a different, more expensive model) rates each claim against the cited official text."""
    rows = []
    for st, cites in claims:
        srcs = []
        for c in cites:
            for a in ({checks.source_article(c)} if checks.source_article(c) else checks.mentioned_articles(c)):
                ps = corpus.by_article().get(a)
                if ps:
                    srcs.append((a, " ".join(p["text"] for p in ps)))
            if c in {d["id"] for d in corpus.decisions().values()}:
                d = next(d for d in corpus.decisions().values() if d["id"] == c)
                srcs.append((c, d["regeste"]))
        rows.append((st, srcs))
    judgeable = [(st, s) for st, s in rows if s]
    unverifiable = len(rows) - len(judgeable)
    if not judgeable:
        return {"supported": 0, "conditional": 0, "partly": 0, "not_supported": 0, "not_applicable": 0,
                "no_valid_citation": unverifiable}
    try:
        verdicts = pipeline.check_claims(judgeable, "CLIENT'S DESCRIPTION:\n" + case_prompt, model=JUDGE, max_tokens=3000)
    except Exception as e:  # recorded, not hidden
        return {"judge_error": str(e)[:200], "no_valid_citation": unverifiable}
    counts = {"supported": 0, "conditional": 0, "partly": 0, "not_supported": 0, "not_applicable": 0,
              "no_valid_citation": unverifiable}
    for n in range(len(judgeable)):
        v = verdicts.get(n + 1)
        counts[v["verdict"] if v else "not_supported"] += 1
    return counts


def judge_questions(gold, ours):
    if not gold or not ours:
        return None
    schema = {"type": "object", "properties": {"covered": {"type": "array", "items": {"type": "object", "properties": {
        "gold": {"type": "integer"}, "covered": {"type": "boolean"}}, "required": ["gold", "covered"]}}},
        "required": ["covered"]}
    msg = ("For each GOLD question (written by legal experts), say whether the SYSTEM questions ask for "
           "substantially the same information (wording may differ).\n\nGOLD:\n" +
           "\n".join(f"{i + 1}. {g}" for i, g in enumerate(gold)) + "\n\nSYSTEM:\n" + "\n".join(f"- {q}" for q in ours))
    try:
        out = chat([{"role": "user", "content": msg}], schema=schema, schema_name="coverage", model=JUDGE, max_tokens=4000)
    except Exception:
        return None  # judge failure: coverage not scored for this case (reported as missing)
    cov = {x["gold"]: x["covered"] for x in out["covered"]}
    return sum(1 for i in range(len(gold)) if cov.get(i + 1)) / len(gold)


def score(systems):
    cache_f = RES / "decision_exists.json"
    cache = json.loads(cache_f.read_text()) if cache_f.exists() else {}
    valid_articles = set(corpus.by_article().keys())
    summary = {}
    for s in systems:
        rows = []
        for c in CASES:
            f = RES / s / f"case_{c['case_no']}.json"
            if not f.exists():
                continue
            res = json.loads(f.read_text())
            row = {"case": c["case_no"], "expected": c["acceptable_lanes"]}
            if res.get("error"):
                row.update({"error": res["error"]})
                rows.append(row)
                continue
            lane, qs, claims, text, cited = normalise(s, res)
            arts = {x for x in cited if _ART_NORM.fullmatch(x)}
            decs = {x for x in cited if not _ART_NORM.fullmatch(x)}
            mentioned = checks.mentioned_articles(text) | arts
            valid = {a for a in mentioned if a in valid_articles}
            dec_valid = {d for d in decs if decision_exists(d, cache)}
            gold = set(c["gold_articles"])
            gold_q = [q["text"] for q in c["gold_questions"] if q.get("source") == "list"] or [q["text"] for q in c["gold_questions"]]
            row.update({
                "lane": lane, "lane_ok": lane in c["acceptable_lanes"],
                "under_escalated": lane < min(c["acceptable_lanes"]), "over_escalated": lane > max(c["acceptable_lanes"]),
                "articles_mentioned": len(mentioned), "articles_invalid": sorted(mentioned - valid),
                "decisions_mentioned": len(decs), "decisions_invalid": sorted(decs - dec_valid),
                "gold_recall": round(len(gold & valid) / len(gold), 2) if gold else None,
                "gold_found": sorted(gold & valid), "gold_missed": sorted(gold - valid),
                "claims": judge_claims(claims, c["prompt"]),
                "question_coverage": judge_questions(gold_q, qs),
                "seconds": res["seconds"], "cost_usd": round(res["cost_usd"], 4),
            })
            if s.startswith("harness"):
                ver = res["case"]["verification"]
                row["harness_removed_by_checks"] = len(ver["removed"])
                row["harness_questions_dropped"] = len(res["case"].get("dropped_questions", []))
            rows.append(row)
            print(s, c["case_no"], "lane", lane, row["lane_ok"], "recall", row["gold_recall"], "claims", row["claims"], flush=True)
        summary[s] = rows
        (RES / s / "score.json").write_text(json.dumps(rows, ensure_ascii=False, indent=1))
        cache_f.write_text(json.dumps(cache, indent=1))
    merged = {p.parent.name: json.loads(p.read_text()) for p in sorted(RES.glob("*/score.json"))}
    (RES / "summary.json").write_text(json.dumps(merged, ensure_ascii=False, indent=1))
    return merged


def lanes_report():
    """Lane decisions over the repeat runs (code only, no judge): per run and per case."""
    out = {}
    for base in ("harness_final_apertus70b", "plain_apertus70b", "plain_nemotron120b"):
        runs = [base, f"{base}_r2", f"{base}_r3"]
        per_run, per_case = [], {c["case_no"]: [] for c in CASES}
        for r in runs:
            ok = under = over = err = 0
            for c in CASES:
                f = RES / r / f"case_{c['case_no']}.json"
                if not f.exists():
                    continue
                res = json.loads(f.read_text())
                if res.get("error"):
                    err += 1
                    per_case[c["case_no"]].append("failed")
                    continue
                lane = res["case"]["lane"] if "case" in res else res["output"]["lane"]
                per_case[c["case_no"]].append(lane)
                ok += lane in c["acceptable_lanes"]
                under += lane < min(c["acceptable_lanes"])
                over += lane > max(c["acceptable_lanes"])
            per_run.append({"run": r, "correct": ok, "under": under, "over": over, "failed": err})
        out[base] = {"runs": per_run, "per_case": per_case}
    (RES / "lanes.json").write_text(json.dumps(out, indent=1))
    return out


if __name__ == "__main__":
    cmd = sys.argv[1]
    systems = sys.argv[2:] or list(SYSTEMS)
    if cmd == "run":
        run(systems)
    elif cmd == "score":
        score(systems)
    elif cmd == "lanes":
        print(json.dumps(lanes_report(), indent=1))
