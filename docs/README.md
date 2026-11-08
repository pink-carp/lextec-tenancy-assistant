# Sub-challenge 2 documents

The framework, the regulatory notes and the disclosures depend on what each version of the tool actually does, so each version has its own folder. **v4 is the live and recommended version.** The other three are kept for comparison.

| Folder | Version | Branch, where | AI model | What the user sees |
|---|---|---|---|---|
| [`versions/v4-scoped-live/`](versions/v4-scoped-live/) | **v4 limited scope: LIVE, recommended** | `main` (= `v4-scoped` plus one later fix), https://liit.bouveng.org | Apertus 1.5 70B via Public AI | Checked situation content for 9 situations; the AI writes only a two-sentence summary |
| [`versions/v2-baseline/`](versions/v2-baseline/) | v2 baseline (earlier) | `v2-baseline`, Vercel preview (login) | Apertus via Public AI | Reviewed summaries of AI-chosen articles; AI-written questions, actions and handout |
| [`versions/v3-generative/`](versions/v3-generative/) | v3 generative | `v3-generative`, Vercel preview | Apertus via Public AI | AI-written questions, actions and handout (AI legal notes switched off) |
| [`versions/v5-openai/`](versions/v5-openai/) | v5 OpenAI comparison (test only, invented cases) | `v5-openai`, Vercel preview | OpenAI gpt-5.6-sol (USA) | Everything AI-written, including legal notes per issue |

Each folder has:
- `framework.md`: when the AI must step back (lanes, indices, hard triggers, human checkpoints) as that version implements it;
- `regulatory.md`: preliminary regulatory notes (DSG, IDG ZH, secrecy, liability, transparency, EU AI Act) for that version's data flows;
- `disclosure.md`: the client handout disclosure and the social-worker terms of use for that version.

The main differences: only v4 and v5 have hard Lane 3 triggers (violence, threats, exploitation, immediate danger, migration status); only v4 sends a case without checked guidance to at least Lane 2 and lets a confirmed urgent answer raise urgency and severity; only v5 sends data to a US provider (OpenAI), which is why its regulatory notes cover cross-border transfer.

[`scenarios.md`](scenarios.md) holds the two extra test scenarios (case 10 = Lane 1, case 11 = Lane 3). They do not depend on the version.
