# When must the AI step back? Escalation framework (v3, generative)

**Version:** v3 generative, a comparison version (branch `v3-generative`, Vercel preview). AI model: Apertus 1.5 70B via Public AI. Not the live version; see `docs/README.md`.
Draft for jury and legal review, 8 Nov 2026. Sources: `output.md`, `escalation.md`, `app/scoring.py`, `app/pipeline.py` (`score`, `severity_level`, `complexity_level`) and `app/writer.py` on branch `v3-generative`.

## 1. Three lanes (output.md §2)

| Lane | When | What the system does |
|---|---|---|
| **1 AI assistance** | Straightforward, not urgent, limited consequences, low vulnerability, enough information | Assesses the case and gives supported recommendations |
| **2 Assistance with clarification** | Material information missing, unclear or contradictory; no Lane 3 concern | Keeps assessing what it can; asks only the questions that matter |
| **3 Human referral** | Urgency, serious consequences, vulnerability or complexity require a human | Explains the referral, names suitable services, gives the immediate steps it can support, drafts an expert brief |

In v3 the AI writes the questions, the actions, the summary and the handout. Code limits what it may write about (from the confirmed deciding events) and checks what it wrote. AI notes applying the law to the case are switched off after measurement. The lane uses only the five indices and the rules in §3: the hard triggers and extra adjustments of v4 and v5 do not exist in v3.

## 2. Five indices and how each is scored

| Index | Scored by | High | Medium | Low |
|---|---|---|---|---|
| **Urgency** | Code (`scoring.urgency`) from confirmed signals and calculated deadlines | Court or enforcement step; termination notice received; client deadline ≤ 10 days or possibly passed | Payment demand or other running deadline; client deadline ≤ 30 days; a deadline whose start date is unknown | Otherwise |
| **Information** | Code (`scoring.information`) | Urgent question unanswered, or a deadline cannot be dated for missing facts | Core question unanswered, or a disputed fact | Otherwise |
| **Severity** | Code (`pipeline.severity_level`) from the confirmed warning signs and from the documents and situations the AI found in the client's words (each must quote the client) | Landlord's termination or court step; immediate danger; no heating, water or power; payment demand and the client says they cannot pay in time | A payment demand, termination, notice, rent increase or court document, or any identified tenancy situation | None |
| **Vulnerability** | **Social worker**, 1–10. The system suggests a score from the escalation.md indicators found in the client's words: 0 → 2, 1 → 4, 2 → 7, 3+ → 8, and violence/threats or exploitation → 9 | ≥ 7 | 4–6 | ≤ 3 |
| **Complexity** | Code (`pipeline.complexity_level`) from the other areas of law the AI found in the client's words, disputes and deadlines | Another area of law needing specialist advice (migration, debt enforcement, criminal); immediate danger; a time limit that cannot be determined (court or conciliation document) | Any other area of law; disputed facts that need evidence; several tenants involved (a co-tenant left or gave notice) | Otherwise |

*Not in v3:* the v4/v5 adjustments (violence or danger sets urgency and severity to high; no heating, water or power sets urgency to at least medium) and v4's rule that a confirmed "urgent" answer raises urgency and severity.

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

| Trigger | Status in v3 |
|---|---|
| Court or enforcement step | **Implemented**: urgency is high, so Lane 3 |
| Landlord's termination received | **Implemented**: urgency is high (Art. 273 OR challenge period). The document type separates a landlord's termination from notice given by the tenant or a co-tenant. Scenario 10 (`docs/scenarios.md`) tests that a tenant's own planned notice is not read as a landlord's termination. |
| Violence, threats or coercion | **Partly implemented**. Violence raises the suggested vulnerability score to 9 (high), but Lane 3 then also needs urgency or severity at medium or above. **Proposal (implemented in v4 and v5):** a violence indicator sends the case to Lane 3 regardless of the other indices. |
| Exploitation or dependency | **Partly implemented**, as for violence. |
| Immediate danger | **Indirectly implemented**: the confirmed "immediate danger" warning sign makes severity and complexity high, so Lane 3. If the social worker unticks that warning sign, the lane no longer follows from it. 117 and 142 are added to the contacts either way. |
| Migration status connected to housing | **Indirectly implemented**: if the AI finds "migration" as another area of law in the client's words, code sets complexity high, so Lane 3. There is no separate trigger. |
| Deadline that cannot be dated | **Not a hard trigger.** A missing start date gives urgency medium and information high (Lane 2). A time limit the tool cannot determine for legal reasons (court or conciliation document) gives complexity high (Lane 3). The terms of use still tell the social worker to refer. |

In the final blind comparison (one Claude reviewer, 11 known cases, not checked by a lawyer), v3's lanes were appropriate in 9 of 11 cases.

## 5. Human-in-the-loop checkpoints

1. **Before scoring:** the social worker confirms or edits the facts, the warning signs and the deciding events, and sets the vulnerability rating. The lane is calculated only from confirmed facts.
2. **Questions:** the AI writes one question per fact that decides the rules at issue, limited by code to those facts. The social worker records the client's answers ("I don't know" is allowed). The lane is recalculated.
3. **Lane:** the social worker can override the lane. A reason is asked for and recorded in the audit trail; if the field is left empty, "no reason given" is recorded. **[check]** whether the reason should be mandatory.
4. **Output:** the social worker reads the screen view and the handout before giving them to the client. Every AI action that relies on a paragraph must cite it; code removes unknown articles and dates and actions that rest on a rule whose conditions are not met, and two further Apertus checks (in English and German) remove flagged sentences. General plain-language article summaries (reviewed against the official text) can be opened on screen. These checks do not make the text reliable: in the final blind comparison, 7 of 47 v3 actions were wrong or inapplicable, 6 of its questions were legally wrong, and a lawyer would spot a clear error in 11 of 11 cases.
5. **Referral (Lane 3):** a human lawyer or specialist service decides. The expert brief is marked "AI draft - not yet checked by the social worker". **[check]** A three-step review status (AI draft, checked by the social worker, checked by a legal professional) is proposed but not implemented.

## 6. Principle: when uncertain, escalate

- Missing information is never proof that there is no risk (escalation.md rule 8). In code, an unknown start date counts as medium urgency and high information uncertainty. A notice whose recipient is "unclear" is treated as the client's.
- Lane 3 takes priority over Lane 2. A referral is never delayed to gather information (output.md §3).
- When a time limit cannot be determined for legal reasons, complexity is high, which means Lane 3.
- Overrides should normally move a case **up**. A move down needs a reason a reviewer can check.
