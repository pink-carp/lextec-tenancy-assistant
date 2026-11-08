"""Build the static benchmark page (app/static/benchmark.html) from the saved evaluation files, so every number on the
page can be traced to a data file in bench/results/. Run: .venv/bin/python bench/build_report.py"""
import collections
import html
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
EV = ROOT / "bench" / "results" / "evaluation_2026-11-08"
OUT = ROOT / "app" / "static" / "benchmark.html"
NAMES = {"scoped": "v4 live: checked situation content, Apertus",
         "openai_generative": "v5: no pre-written text, OpenAI gpt-5.6-sol",
         "apertus_generative": "v3: no pre-written text, Apertus"}
ORDER = ["scoped", "openai_generative", "apertus_generative"]
COST = {"scoped": "about USD 0.02", "openai_generative": "about USD 0.30 (price estimate)", "apertus_generative": "about USD 0.03"}
e = html.escape


def three_way():
    rev = json.loads((EV / "three_way_blind_review.json").read_text())
    key = json.loads((EV / "three_way_key.json").read_text())
    T = collections.defaultdict(collections.Counter)
    U, J, per_case = collections.defaultdict(list), collections.Counter(), {}
    lanes_ok = collections.Counter()
    for n, c in rev.items():
        per_case[n] = {}
        for letter, v in c.items():
            s = key[n][letter]
            for sec in ("questions", "legal_statements", "actions"):
                for lab, cnt in (v.get(sec) or {}).items():
                    if isinstance(cnt, (int, float)):
                        T[s][f"{sec}.{lab}"] += cnt
            T[s]["missing"] += v.get("missing_questions_count") or 0
            T[s]["wrong_text"] += len(v.get("wrong_statements") or [])
            U[s].append(v.get("usefulness"))
            J[s] += 1 if v.get("jury_spots_error") else 0
            lanes_ok[s] += 1 if str(v.get("lane", "")).startswith("appropriate") else 0
            per_case[n][s] = {"u": v.get("usefulness"), "jury": v.get("jury_spots_error"), "errors": v.get("errors") or []}
    return T, U, J, lanes_ok, per_case, len(rev)


def early():
    s = json.loads((ROOT / "bench" / "results" / "summary.json").read_text())
    rows = []
    names = {"harness_apertus70b": "v1 harness, Apertus (round 1)", "harness_final_apertus70b": "v1 harness, Apertus (final)",
             "plain_apertus70b": "Plain Apertus 70B (one call)", "plain_nemotron120b": "Plain Nemotron 120B (one call)"}
    for k in names:
        v = s.get(k) or []
        ok = [r for r in v if not r.get("error")]
        cl = collections.Counter()
        for r in ok:
            cl.update(r.get("claims") or {})
        tot = sum(cl[x] for x in ("supported", "conditional", "partly", "not_supported", "not_applicable", "no_valid_citation"))
        sup = f"{round(100 * (cl['supported'] + cl['conditional']) / tot)}%" if tot else "-"
        rows.append((names[k], f"{sum(1 for r in ok if r.get('lane_ok'))} / {len(v)}", sup, len(v) - len(ok)))
    return rows


def build():
    T, U, J, lanes_ok, per_case, n = three_way()
    t = lambda s, k: T[s][k]
    rows = [
        ("Usefulness to a social worker (1-5, mean)", lambda s: f"{sum(U[s]) / len(U[s]):.1f}"),
        ("Cases where a lawyer would spot a clear error", lambda s: f"{J[s]} of {n}"),
        ("Legal statements: correct", lambda s: t(s, "legal_statements.ok") or "none shown"),
        ("Legal statements: wrong law", lambda s: t(s, "legal_statements.wrong_law")),
        ("Legal statements: do not apply to the client", lambda s: t(s, "legal_statements.inapplicable")),
        ("Actions: correct", lambda s: t(s, "actions.ok")),
        ("Actions: wrong law, inapplicable or unsupported", lambda s: t(s, "actions.wrong_law") + t(s, "actions.inapplicable") + t(s, "actions.unsupported")),
        ("Questions: relevant", lambda s: t(s, "questions.relevant")),
        ("Questions: irrelevant", lambda s: t(s, "questions.irrelevant")),
        ("Questions: already answered by the client", lambda s: t(s, "questions.already_answered")),
        ("Questions: legally wrong", lambda s: t(s, "questions.legally_wrong")),
        ("Obvious questions missing", lambda s: t(s, "missing")),
        ("Wrong statements in summary, handout and brief", lambda s: t(s, "wrong_text")),
        ("Lane appropriate", lambda s: f"{lanes_ok[s]} of {n}"),
        ("Cost per case", lambda s: COST[s]),
    ]
    main_table = "<tr><th>Measure</th>" + "".join(f"<th>{e(NAMES[s])}</th>" for s in ORDER) + "</tr>" + "".join(
        f"<tr><td>{e(label)}</td>" + "".join(f"<td class='num'>{e(str(f(s)))}</td>" for s in ORDER) + "</tr>" for label, f in rows)
    expected = {1: "2", 2: "3", 3: "2", 4: "2", 5: "2", 6: "3", 7: "2 or 3", 8: "3", 9: "2", 10: "1", 11: "3"}
    v4_lane = {1: 2, 2: 3, 3: 2, 4: 2, 5: 2, 6: 3, 7: 3, 8: 3, 9: 2, 10: 1, 11: 3}
    case_rows = "".join(
        f"<tr><td>{c}</td><td>{expected[int(c)]}</td><td class='good'>{v4_lane[int(c)]}</td>" + "".join(
            f"<td class='{'bad' if per_case[c][s]['jury'] else 'good'}'>{per_case[c][s]['u']}"
            f"{' · error a lawyer would spot' if per_case[c][s]['jury'] else ''}</td>" for s in ORDER) + "</tr>"
        for c in sorted(per_case, key=int))
    early_rows = "".join(f"<tr><td>{e(a)}</td><td class='num'>{b}</td><td class='num'>{c}</td><td class='num'>{d}</td></tr>" for a, b, c, d in early())
    page = f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Evaluation Results</title>
<style>
  :root {{ --ink:#1b1b1b; --muted:#5a5a5a; --line:#c9c9c9; --bg:#fff; --panel:#f4f4f2; --accent:#1d4f91; --okbg:#e7f4ea; --badbg:#fdeaea; }}
  @media (prefers-color-scheme: dark) {{ :root {{ --ink:#e8e8e8; --muted:#a8a8a8; --line:#444; --bg:#161616; --panel:#222; --accent:#7aa7e6; --okbg:#1d3a25; --badbg:#4a2020; }} }}
  body {{ margin:0; font:16px/1.5 system-ui, -apple-system, "Segoe UI", Roboto, Arial, sans-serif; color:var(--ink); background:var(--bg); }}
  header {{ border-bottom:3px solid var(--accent); padding:14px 16px; }} header h1 {{ margin:0; font-size:22px; }}
  main {{ max-width:1100px; margin:0 auto; padding:16px; }}
  h2 {{ font-size:19px; margin:28px 0 8px; border-bottom:1px solid var(--line); padding-bottom:4px; }}
  table {{ border-collapse:collapse; width:100%; font-size:15px; margin:10px 0 18px; }}
  th, td {{ border:1px solid var(--line); padding:6px 8px; text-align:left; vertical-align:top; }} th {{ background:var(--panel); }}
  td.num {{ text-align:right; }} .good {{ background:var(--okbg); }} .bad {{ background:var(--badbg); }}
  .muted {{ color:var(--muted); font-size:14px; }} .wrap {{ overflow-x:auto; }} a {{ color:var(--accent); }}
  .note {{ background:var(--panel); border-left:4px solid var(--accent); padding:10px 12px; margin:10px 0; }}
</style>
</head>
<body>
<header><h1>Evaluation: how accurate is each version?</h1></header>
<main>
<p><a href="/">Back to the tool</a></p>
<div class="note"><strong>In short.</strong> We measured whether the Swiss open model Apertus can write correct legal text for
social workers. Even with confirmed facts, rule filters and two automatic checks, about one in four AI-written legal sentences
was wrong. The live version therefore shows <strong>checked content for nine common situations</strong> and uses Apertus for
what it does reliably: reading the case, pre-filling facts, suggesting the situation and summarising. In a blind review of
11 cases, it had no wrong legal statements and the right lane in all cases. A version with a strong commercial model
(OpenAI gpt-5.6-sol) and no pre-written text also wrote the law correctly, but asked many ill-fitting questions.</div>

<h2>1. Final comparison of the three designs ({n} cases, blind review)</h2>
<p class="muted">One reviewer (a fresh Claude agent, not a lawyer) judged the three versions' outputs for the same {n} cases with
the same rules, without being told which version was which (the labels were shuffled per case). The cases are the legal
team's 9 example cases plus 2 extra scenarios (lane 1 and lane 3). Inputs, labels and the key are in
<code>bench/results/evaluation_2026-11-08/three_way_*.json</code>.</p>
<div class="wrap"><table>{main_table}</table></div>

<h2>2. Per case: lane and usefulness</h2>
<p class="muted">Expected lane: the legal team's assessment (cases 1-9) or the scenario design (10-11). Usefulness 1-5 from
the blind review; red = the reviewer found an error a lawyer would spot.</p>
<div class="wrap"><table><tr><th>Case</th><th>Expected lane</th><th>v4 lane</th>{''.join(f'<th>{e(NAMES[s])}</th>' for s in ORDER)}</tr>{case_rows}</table></div>

<h2>3. How we got here: measurements of the generative options (Apertus only)</h2>
<div class="wrap"><table>
<tr><th>Approach</th><th>Result</th><th>Data</th></tr>
<tr><td>Apertus writes plain-language summaries of each law paragraph</td><td>109 of 235 drafts needed correction (46%)</td><td><code>corpus/build_summaries.py</code></td></tr>
<tr><td>Extract the rule's conditions first, write from them, check by reading the sentence back</td><td>Of the statements kept, 13% legally false and 26% true but not applicable; the read-back check wrongly removed 39% of correct statements</td><td>experiment notes (not in repo)</td></tr>
<tr><td>Writer limited by confirmed facts (rule only if its event happened), 11 cases, blind judge</td><td>Lawyer-level notes: 29 of 90 sentences harmful (32%). Practical guidance: 24 of 84 (29%)</td><td><code>writer_levels_*.json</code></td></tr>
<tr><td>Same, after two Apertus checks (English and German)</td><td>Checks caught 16 of 24 harmful sentences but removed 21 of 45 correct ones; 23-26% of the sentences still shown were harmful</td><td><code>writer_levels_after_checks.json</code></td></tr>
<tr><td>Full AI-written Apertus version (v3), 11 cases</td><td>Questions: 25 of 63 relevant, 8 legally wrong. Actions: 37 of 49 correct. Handout: 10 wrong or misleading statements; expert brief: 11</td><td><code>v3_generative_review.json</code></td></tr>
<tr><td>Live version (v4), first review</td><td>Legal points: 0 of 54 wrong. Actions: 0 of 48 wrong. Questions: 45 of 64 relevant, 14 asked for facts already given (fixed in part since)</td><td><code>v4_first_review.json</code></td></tr>
</table></div>

<h2>4. Early benchmark (first harness, overnight)</h2>
<p class="muted">The first harness design against plain one-call baselines on the 9 team cases; claims judged by Nemotron 120B
against the cited article text. The harness was tuned on the same cases, so these are not independent estimates. Data:
<code>bench/results/summary.json</code>.</p>
<div class="wrap"><table><tr><th>System</th><th>Correct lane</th><th>Legal claims supported by the cited text</th><th>Failed runs</th></tr>{early_rows}</table></div>

<h2>5. Method and limits</h2>
<ul class="muted">
<li>All judges are AI reviewers (Claude agents), one reviewer per test, not lawyers. Legal points were checked against the
official German text (fedlex, in <code>corpus/law_paragraphs.jsonl</code>).</li>
<li>All tests use known cases; the live version's situation content was written with these cases in view. A test on new,
unseen cases is still to be done.</li>
<li>The checked situation content was drafted from the German text by Claude and checked in a second pass; it has not been
reviewed by a lawyer.</li>
<li>Prices for the OpenAI model are third-party estimates; Apertus prices are Public AI's list prices (USD 0.82 / 2.92 per
million input / output tokens).</li>
<li>Social-worker steps (confirming facts and situations, answering yes/no questions) were simulated by Claude from the
client's words.</li>
</ul>
<p class="muted">Generated by <code>bench/build_report.py</code>.</p>
</main>
</body>
</html>
"""
    OUT.write_text(page, encoding="utf-8")
    print("written", OUT)


if __name__ == "__main__":
    build()
