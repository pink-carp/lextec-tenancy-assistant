# Three-way blind review: reviewer instructions

Instructions given to the reviewer (a Claude Opus 5.5 agent) on 8 November 2026 for the comparison reported in README Section 7. Only the local file paths have been replaced with the corresponding repository paths. The reviewer's output is `three_way_blind_review.json`; `three_way_key.json` maps the letters to the versions and was not available to the reviewer.

---

You are an independent, strict reviewer for a hackathon jury of lawyers. The product is an assistant for SOCIAL WORKERS (not lawyers) in the canton of Zurich: a social worker types a client's residential tenancy problem; the tool reads it, the social worker confirms the deciding facts, the tool asks follow-up questions, assigns a lane (1 = information/self-help, 2 = social worker handles it with care, more facts needed, 3 = refer to a professional), and shows legal statements, next actions, deadlines, a client handout and an expert brief. Swiss tenancy law (OR Art. 253-274g) applies. The jury punishes VISIBLE failures: wrong extraction, clearly irrelevant questions, missing clearly relevant questions, wrong summaries or legal statements.

File: `bench/results/evaluation_2026-11-08/three_way_blind_input.json`
11 cases; each has the client's words and three anonymous versions P, Q and R of the tool's output (different systems; the letters are shuffled per case, so P in case 1 is not necessarily P in case 2). Open only that file and, to check legal points, the official German law text in `corpus/law_paragraphs.jsonl`. Do not open any other file in that folder (never a "key" file) and do not try to identify the systems.

For each case and each version, count:
- questions: relevant / irrelevant / duplicate / already_answered (the client's words say it) / legally_wrong; and missing obvious questions (max 3).
- legal_statements: ok / wrong_law / inapplicable / misleading / noise.
- actions: ok / wrong_law / inapplicable / unsupported / unhelpful.
- wrong statements in situation_summary, client_handout and expert_brief (quote each).
- lane: appropriate / too low / too high.
- usefulness to a social worker (1-5) and "would a lawyer on the jury spot a clear error?" (yes/no).
Judge each version on its own merits; a version that shows fewer legal statements is not penalised for that unless an obviously needed point is missing (count it under missing key points).

Write per-case, per-version results to `bench/results/evaluation_2026-11-08/three_way_blind_review.json` as {"<case>": {"P": {...counts..., "errors": ["..."], "usefulness": n, "jury_spots_error": true/false}, "Q": ..., "R": ...}}.

Report back (under ~500 words): a short list per case of the clear errors per version letter (the letters change per case, so always say case and letter), and your general observations. Do not total across cases (the letters are shuffled); I will unblind and total them.
