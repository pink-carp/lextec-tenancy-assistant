# When must the AI step back? Escalation framework (v2, baseline)

**Version:** v2 baseline, an earlier version kept for comparison (branch `v2-baseline`, Vercel preview behind a Vercel login). AI model: Apertus 1.5 70B via Public AI. Not the live version; see `docs/README.md`.
Draft for jury and legal review, 8 Nov 2026. Sources: `output.md`, `escalation.md`, `app/scoring.py`, `app/pipeline.py` (`score`, `severity_level`, `complexity_level`) on branch `v2-baseline`.

## 1. Three lanes (output.md §2)

| Lane | When | What the system does |
|---|---|---|
| **1 AI assistance** | Straightforward, not urgent, limited consequences, low vulnerability, enough information | Assesses the case and gives supported recommendations |
| **2 Assistance with clarification** | Material information missing, unclear or contradictory; no Lane 3 concern | Keeps assessing what it can; asks only the questions that matter |
| **3 Human referral** | Urgency, serious consequences, vulnerability or complexity require a human | Explains the referral, names suitable services, gives the immediate steps it can support, drafts an expert brief |

In v2 the AI chooses the legal issues and the articles that govern them (code adds the articles for the situation and plans it identified). The screen explains those articles with plain-language summaries reviewed against the official text; AI notes applying the law to the case are switched off. The AI writes the summary, up to five actions and the handout. The lane uses only the five indices and the rules in §3: the hard triggers and extra adjustments of v4 and v5 do not exist in v2.

## 2. Five indices and how each is scored

| Index | Scored by | High | Medium | Low |
|---|---|---|---|---|
| **Urgency** | Code (`scoring.urgency`) from confirmed signals and calculated deadlines | Court or enforcement step; termination notice received; client deadline ≤ 10 days or possibly passed | Payment demand or other running deadline; client deadline ≤ 30 days; a deadline whose start date is unknown | Otherwise |
| **Information** | Code (`scoring.information`) | Urgent question unanswered, or a deadline cannot be dated for missing facts | Core question unanswered, or a disputed fact | Otherwise |
| **Severity** | Code (`pipeline.severity_level`) from the confirmed warning signs and from the documents and situations the AI found in the client's words (each must quote the client) | Landlord's termination or court step; immediate danger; no heating, water or power; payment demand and the client says they cannot pay in time | A payment demand, termination, notice, rent increase or court document, or any identified tenancy situation | None |
| **Vulnerability** | **Social worker**, 1–10. The system suggests a score from the escalation.md indicators found in the client's words: 0 → 2, 1 → 4, 2 → 7, 3+ → 8, and violence/threats or exploitation → 9 | ≥ 7 | 4–6 | ≤ 3 |
| **Complexity** | Code (`pipeline.complexity_level`) from the other areas of law the AI found in the client's words, disputes and deadlines | Another area of law needing specialist advice (migration, debt enforcement, criminal); immediate danger; a time limit that cannot be determined (court or conciliation document) | Any other area of law; disputed facts that need evidence; several tenants involved (a co-tenant left or gave notice) | Otherwise |

*Not in v2:* the v4/v5 adjustments (violence or danger sets urgency and severity to high; no heating, water or power sets urgency to at least medium) and v4's rule that a confirmed "urgent" answer raises urgency and severity.

## 3. Lane rules as implemented (`app/scoring.py`, `decide_lane`, checked in this order)

```
if u == "high":                                       Lane 3: legal urgency is high.
if c == "high":                                       Lane 3: legal complexity is high.
if s == "high" and (u >= medium or v >= medium):      Lane 3: severity is high and urgency or vulnerability is at least medium.
if v == "high" and (u >= medium or s >= medium):      Lane 3: personal vulnerability is high and urgency or severity is at least medium.
if i >= medium:                                       Lane 2: material information is missing, unclear or disputed.
otherwise                                             Lane 1: straightforward, non-urgent, low vulnerability, enough information.
```

The social worker's override (with the reason) then replaces the result. There is no further rule.

## 4. Proposed hard triggers: always Lane 3

| Trigger | Status in v2 |
|---|---|
| Court or enforcement step | **Implemented**: urgency is high, so Lane 3 |
| Landlord's termination received | **Implemented**: urgency is high (Art. 273 OR challenge period). The document type separates a landlord's termination from notice given by the tenant or a co-tenant. Scenario 10 (`docs/scenarios.md`) tests that a tenant's own planned notice is not read as a landlord's termination. |
| Violence, threats or coercion | **Partly implemented**. Violence raises the suggested vulnerability score to 9 (high), but Lane 3 then also needs urgency or severity at medium or above. **Proposal (implemented in v4 and v5):** a violence indicator sends the case to Lane 3 regardless of the other indices. |
| Exploitation or dependency | **Partly implemented**, as for violence. |
| Immediate danger | **Indirectly implemented**: the confirmed "immediate danger" warning sign makes severity and complexity high, so Lane 3. If the social worker unticks that warning sign, the lane no longer follows from it. 117 and 142 are added to the contacts either way. |
| Migration status connected to housing | **Indirectly implemented**: if the AI finds "migration" as another area of law in the client's words, code sets complexity high, so Lane 3. There is no separate trigger. |
| Deadline that cannot be dated | **Not a hard trigger.** A missing start date gives urgency medium and information high (Lane 2). A time limit the tool cannot determine for legal reasons (court or conciliation document) gives complexity high (Lane 3). The terms of use still tell the social worker to refer. |

## 5. Human-in-the-loop checkpoints

1. **Before scoring:** the social worker confirms or edits the facts and warning signs and sets the vulnerability rating. The lane is calculated only from confirmed facts. (v2 has no step for confirming deciding events.)
2. **Questions:** the AI writes up to three questions per legal issue; fixed questions are added for the documents the client received (and on marital status where special rules apply); an AI editing pass then removes some, and the removed questions are listed. The social worker records the client's answers ("I don't know" is allowed). The lane is recalculated.
3. **Lane:** the social worker can override the lane. A reason is asked for and recorded in the audit trail; if the field is left empty, "no reason given" is recorded. **[check]** whether the reason should be mandatory.
4. **Output:** the social worker reads the screen view and the handout before giving them to the client. The legal explanations are the reviewed article summaries (Apertus drafts reviewed against the German text: 109 of 235 drafts needed correction; not reviewed by a lawyer). The AI's choice of articles is checked only by fixed code guards (e.g. defect articles are dropped when no defect was found, termination-challenge articles when no termination was received, spouse articles when the client is not married), not article by article. When the client plans something risky (paying less rent, ignoring the letter, paying late), fixed reviewed warnings come first. AI-written actions that cite an article are checked by a further AI call against the official text and removed if unsupported, inapplicable or not checkable. The AI-written handout is checked by code: unknown articles and dates are removed, and client actions missing from it are flagged.
5. **Referral (Lane 3):** a human lawyer or specialist service decides. The expert brief is marked "AI draft - not yet checked by the social worker". **[check]** A three-step review status (AI draft, checked by the social worker, checked by a legal professional) is proposed but not implemented.

## 6. Principle: when uncertain, escalate

- Missing information is never proof that there is no risk (escalation.md rule 8). In code, an unknown start date counts as medium urgency and high information uncertainty. A notice whose recipient is "unclear" is treated as the client's.
- Lane 3 takes priority over Lane 2. A referral is never delayed to gather information (output.md §3).
- When a time limit cannot be determined for legal reasons, complexity is high, which means Lane 3.
- Overrides should normally move a case **up**. A move down needs a reason a reviewer can check.
