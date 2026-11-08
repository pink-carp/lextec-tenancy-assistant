# Tenancy information assistant for social workers (LexTec challenge, HSG Hackathon 2026)

A prototype that helps social workers in the canton of Zurich turn a client's tenancy problem into follow-up
questions, a lane (1 information, 2 information with open questions, 3 referral to a specialist), action
recommendations, a neutral case summary with verified sources, a client handout and an expert brief.
Everything it produces is **legal information, not legal advice**.

It runs on **Apertus 1.5 70B** (Swiss AI Initiative) via the Public AI inference service.

## Design: the AI identifies, code checks, calculates and constrains

| Step | Done by | What code guarantees |
| --- | --- | --- |
| Mask numbers, split sentences | code | phone numbers, e-mails, IBAN and AHV numbers are masked before text is sent (description, edited facts, answers, document text); photos of documents are sent as images and are not masked |
| Understand the case | AI | every fact points to the sentence it came from; articles can only be chosen from the official corpus (schema enum), so non-existent articles cannot be cited |
| Social worker confirms facts, rates vulnerability 1-10 | person | the lane is computed from confirmed facts |
| Expand sources | code | adds articles that refer to a chosen one (e.g. Art. 257d -> 272a, 266n), same sub-section, leading decisions |
| Follow-up questions | AI + critic AI | each question cites a retrieved source; a second pass drops questions whose law does not fit |
| Deadlines | AI identifies, code calculates | the period must be quoted from the cited law or `deadlines.md` (otherwise dropped); dates per Art. 77-78 OR, Saturday law, Art. 142/145 ZPO, Zurich public holidays |
| Lane | code + AI rubric + person | rules in `app/scoring.py`, every level with its reasons |
| Write the result | AI | can only cite retrieved sources; facts are printed by code |
| Verify | code + AI | sentences naming law, decisions or dates outside the sources are removed; an applicability check removes claims the cited law does not support or that do not apply to the facts |
| Handout, translation, expert brief | AI on click | same action IDs, dates and numbers as the verified result |

## Run it

```bash
python3 -m venv --system-site-packages .venv
.venv/bin/pip install fastapi uvicorn python-multipart httpx pydantic pdfplumber pillow
echo "PUBLICAI_API_KEY=your_key" > .env
.venv/bin/uvicorn app.server:app --port 8000
# open http://localhost:8000
```

Case data lives only in memory and is deleted with "End case".

## Legal sources (`corpus/`)

- Official federal law from Fedlex (OR, ZPO, ZGB, VMWG, Saturday-deadline law), current consolidated versions,
  split per paragraph with official links: `build_law_corpus.py`.
- 332 court decisions from OpenCaseLaw (CC0): the decisions cited by the legal team plus the 5 most-cited
  decisions per tenancy and procedure article: `fetch_decisions.py`, `fetch_leading_cases.py`.
- Commentary extracts supplied by the legal team are used as background only and are **not** part of this
  repository (copyright).

## Benchmark (`bench/`)

`bench/run_bench.py` runs the legal team's 9 example cases through the harness and through baselines that get the
same documents and the full tenancy law but no harness, then scores lane accuracy, citation validity, recall of the
articles the legal team cited, claim support (independent judge model) and question coverage.

## Team documents

`legal_workflow.md`, `escalation.md`, `output.md`, `deadlines.md`, `resources.md` and the example cases were written
by the legal team and drive the prompts, rules and tests.

Licence: Apache-2.0.
