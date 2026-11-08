# When must the AI step back? Escalation framework

Draft for jury and legal review, 8 Nov 2026. Sources: `output.md`, `escalation.md`, `app/scoring.py`, `app/pipeline.py`.

## 1. Three lanes (output.md §2)

| Lane | When | What the system does |
|---|---|---|
| **1 AI assistance** | Straightforward, not urgent, limited consequences, low vulnerability, enough information | Assesses the case and gives supported recommendations |
| **2 Assistance with clarification** | Material information missing, unclear or contradictory; no Lane 3 concern | Keeps assessing what it can; asks only the questions that matter |
| **3 Human referral** | Urgency, serious consequences, vulnerability or complexity require a human | Explains the referral, names suitable services, gives the immediate steps it can support, drafts an expert brief |

## 2. Five indices and how each is scored

| Index | Scored by | High | Medium | Low |
|---|---|---|---|---|
| **Urgency** | Code (`scoring.urgency`) from confirmed signals and calculated deadlines | Court or enforcement step; termination notice received; client deadline ≤ 10 days or possibly passed | Payment demand or other running deadline; client deadline ≤ 30 days; a deadline whose start date is unknown | Otherwise |
| **Information** | Code (`scoring.information`) | Urgent question unanswered, or a deadline cannot be dated for missing facts | Core question unanswered, or a disputed fact | Otherwise |
| **Severity** | The AI ticks consequences, a second AI pass checks each one against the client's own sentences, and code sets the level (`pipeline.severity_level`) | Landlord termination received; eviction or court step; payment demand and the client cannot pay; no heating, water or electricity | Any other current or future consequence | None |
| **Vulnerability** | **Social worker**, 1–10. The system suggests a score from the escalation.md indicators: 0 → 2, 1 → 4, 2 → 6, 3+ → 8, and violence or exploitation → at least 8 | ≥ 7 | 4–6 | ≤ 3 |
| **Complexity** | AI rubric (`pipeline.assess`); code sets it to high if a deadline cannot be determined because of legal uncertainty | Outcome depends on another area of law needing specialist advice (migration status, debt enforcement, divorce), conflicting rules, unclear jurisdiction, non-standard accommodation | Contested facts needing evidence (e.g. suspected retaliation), several tenancy issues interacting | Otherwise |

## 3. Lane rules as implemented (`app/scoring.py`, `decide_lane`, checked in this order)

```
if u == "high":                                       Lane 3: legal urgency is high.
if c == "high":                                       Lane 3: legal complexity is high.
if s == "high" and (u >= medium or v >= medium):      Lane 3: severity is high and urgency or vulnerability is at least medium.
if v == "high" and (u >= medium or s >= medium):      Lane 3: personal vulnerability is high and urgency or severity is at least medium.
if i >= medium:                                       Lane 2: material information is missing, unclear or disputed.
otherwise                                             Lane 1: straightforward, non-urgent, low vulnerability, enough information.
```

## 4. Proposed hard triggers: always Lane 3

| Trigger | Status in code today |
|---|---|
| Court or enforcement step | **Implemented**: urgency is high, so Lane 3 |
| Landlord's termination received | **Implemented**: urgency is high (Art. 273 OR challenge period). *Caveat:* the signal type `termination_notice` does not record who gave notice. A tenant's own planned notice could be misread as one (Scenario 10 tests this). |
| Violence, threats or immediate danger | **Partly implemented**. Violence raises the suggested vulnerability score to 8, but Lane 3 then also needs urgency or severity at medium or above. `immediate_danger` adds 117/142 to the contacts but does not change the lane. **Proposal:** a confirmed violence indicator or immediate danger sends the case to Lane 3 regardless of the other indices. |
| Migration status connected to housing | **Not deterministic**: it counts only through the AI complexity rubric. **Proposal:** a confirmed `migration` signal sends the case to Lane 3. |

## 5. Human-in-the-loop checkpoints

1. **Before scoring:** the social worker confirms or edits the facts and warning signs and sets the vulnerability rating. The lane is calculated only from confirmed facts.
2. **Questions:** the social worker records the client's answers ("I don't know" is allowed). The lane is recalculated.
3. **Lane:** the social worker can override the lane. A reason is required and logged.
4. **Output:** the social worker reads the screen view and the handout before giving them to the client. Legal statements the cited article text does not support have already been removed.
5. **Referral (Lane 3):** a human lawyer or specialist service decides. The expert brief carries a review status (AI draft, checked by the social worker, checked by a legal professional).

## 6. Principle: when uncertain, escalate

- Missing information is never proof that there is no risk (escalation.md rule 8). In code, an unknown start date counts as medium urgency and high information uncertainty. A notice whose recipient is "unclear" is treated as the client's.
- Lane 3 takes priority over Lane 2. A referral is never delayed to gather information (output.md §3).
- When the system cannot tell which legal rule applies, it rates complexity high, which means Lane 3.
- Overrides should normally move a case **up**. A move down needs a reason a reviewer can check.
