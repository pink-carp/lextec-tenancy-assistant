# When must the AI step back? Escalation framework (v4, live)

**Version:** v4 limited scope, the live and recommended version (branch `main`, i.e. `v4-scoped` plus one later fix, https://liit.bouveng.org). AI model: Apertus 1.5 70B via Public AI.
Draft for jury and legal review, 8 Nov 2026. Sources: `output.md`, `escalation.md`, `app/scoring.py`, `app/pipeline.py` (`score`, `severity_level`, `complexity_level`), `corpus/modules/`.

## 1. Three lanes (output.md §2)

| Lane | When | What the system does |
|---|---|---|
| **1 AI assistance** | Straightforward, not urgent, limited consequences, low vulnerability, enough information | Assesses the case and gives supported recommendations |
| **2 Assistance with clarification** | Material information missing, unclear or contradictory; no Lane 3 concern | Keeps assessing what it can; asks only the questions that matter |
| **3 Human referral** | Urgency, serious consequences, vulnerability or complexity require a human | Explains the referral, names suitable services, gives the immediate steps it can support, drafts an expert brief |

In v4 all legal content in every lane comes from 9 checked situation modules (unpaid rent and payment demands, termination by the landlord, the tenant's own notice, defects, rent increase, pets and house rules, deposit return, a co-tenant leaving, family home protection). The modules were drafted from the official German text and checked in a second pass; they are not reviewed by a lawyer. If no module fits, the tool gives no legal guidance and the case goes to at least Lane 2 (§4).

## 2. Five indices and how each is scored

| Index | Scored by | High | Medium | Low |
|---|---|---|---|---|
| **Urgency** | Code (`scoring.urgency`) from confirmed signals and calculated deadlines | Court or enforcement step; termination notice received; client deadline ≤ 10 days or possibly passed | Payment demand or other running deadline; client deadline ≤ 30 days; a deadline whose start date is unknown | Otherwise |
| **Information** | Code (`scoring.information`) | Urgent question unanswered, or a deadline cannot be dated for missing facts | Core question unanswered, or a disputed fact | Otherwise |
| **Severity** | Code (`pipeline.severity_level`) from the confirmed warning signs and from the documents and situations the AI found in the client's words (each must quote the client) | Landlord's termination or court step; immediate danger; no heating, water or power; payment demand and the client says they cannot pay in time | A payment demand, termination, notice, rent increase or court document, or any identified tenancy situation | None |
| **Vulnerability** | **Social worker**, 1–10. The system suggests a score from the escalation.md indicators found in the client's words: 0 → 2, 1 → 4, 2 → 7, 3+ → 8, and violence/threats or exploitation → 9 | ≥ 7 | 4–6 | ≤ 3 |
| **Complexity** | Code (`pipeline.complexity_level`) from the other areas of law the AI found in the client's words, disputes and deadlines | Another area of law needing specialist advice (migration, debt enforcement, criminal); immediate danger; a time limit that cannot be determined (court or conciliation document) | Any other area of law; disputed facts that need evidence; several tenants involved (a co-tenant left or gave notice) | Otherwise |

**Adjustments before the lane rules (v4, `pipeline.score`):**
- Violence, threats or coercion, or immediate danger: urgency and severity are set to **high**.
- No heating, water or power: urgency is at least **medium**.
- A **confirmed "urgent" answer** raises the indices the module names to **high**. Today one module question does this: in the defects module, "Is the heating or hot water not working during the cold months, or do children (or people with health problems) live in the flat?" answered "yes" raises urgency and severity.

## 3. Lane rules as implemented (`app/scoring.py`, `decide_lane`, checked in this order)

```
if u == "high":                                       Lane 3: legal urgency is high.
if c == "high":                                       Lane 3: legal complexity is high.
if s == "high" and (u >= medium or v >= medium):      Lane 3: severity is high and urgency or vulnerability is at least medium.
if v == "high" and (u >= medium or s >= medium):      Lane 3: personal vulnerability is high and urgency or severity is at least medium.
if i >= medium:                                       Lane 2: material information is missing, unclear or disputed.
otherwise                                             Lane 1: straightforward, non-urgent, low vulnerability, enough information.
```

After `decide_lane`, `pipeline.score` applies, in this order:
1. **Hard triggers** (§4): if any is present, Lane 3.
2. **No module:** if the social worker confirmed no situation module, at least Lane 2 ("this tool has no checked guidance for this situation").
3. **Override:** the social worker's lane, with the reason, replaces the result.

## 4. Hard triggers: always Lane 3

| Trigger | Status in v4 |
|---|---|
| Court or enforcement step | **Implemented**: urgency is high, so Lane 3 |
| Landlord's termination received | **Implemented**: urgency is high (Art. 273 OR challenge period). The document type separates a landlord's termination from notice given by the tenant or a co-tenant. Scenario 10 (`docs/scenarios.md`) tests that a tenant's own planned notice is not read as a landlord's termination; v4 gives it Lane 1, as expected. |
| Violence, threats or coercion | **Implemented** as a hard trigger. Urgency and severity are also set to high, and the suggested vulnerability score is 9. |
| Exploitation or dependency | **Implemented** as a hard trigger. |
| Immediate danger | **Implemented** as a hard trigger. 117 and 142 are added to the contacts. |
| Migration status connected to housing | **Implemented** as a hard trigger (the AI finds "migration" as another area of law in the client's words). Complexity is also high. |
| Deadline that cannot be dated | **Not a hard trigger.** A missing start date gives urgency medium and information high (Lane 2). A time limit the tool cannot determine for legal reasons (court or conciliation document) gives complexity high (Lane 3). The terms of use still tell the social worker to refer. |
| No checked module for the situation | **Implemented**: at least Lane 2 (not Lane 3). |

*Caveat:* the violence, exploitation, danger and migration triggers fire on what the AI found in the client's words (code drops any item whose quote is not in the text). Unticking the matching warning sign in step 2 does not remove the trigger; only a lane override does. **[check]** whether this is the intended behaviour.

## 5. Human-in-the-loop checkpoints

1. **Before scoring:** the social worker confirms or edits the facts, the warning signs, the deciding events and the situation(s) (modules) the AI suggested, and sets the vulnerability rating. The lane is calculated only from confirmed facts (except the caveat in §4).
2. **Questions:** the questions come from the confirmed modules. The AI pre-fills free-text, date and number answers that the description already gives, with the sentence it took them from; yes/no questions are never pre-filled. The social worker confirms or corrects each answer ("I don't know" is allowed). The lane is recalculated.
3. **Lane:** the social worker can override the lane. A reason is asked for and recorded in the audit trail; if the field is left empty, "no reason given" is recorded. **[check]** whether the reason should be mandatory.
4. **Output:** the social worker reads the screen view and the handout before giving them to the client. Legal points and client texts are checked module texts, shown only when the confirmed facts meet their conditions. The only AI-written text is a two-sentence situation summary (and an optional translation of the handout); code removes article references and dates that are not in the case, and checks that all numbers survive the translation.
5. **Referral (Lane 3):** a human lawyer or specialist service decides. The expert brief is marked "Draft from the tool - please check before sending". **[check]** A three-step review status (AI draft, checked by the social worker, checked by a legal professional) is proposed but not implemented.

## 6. Principle: when uncertain, escalate

- Missing information is never proof that there is no risk (escalation.md rule 8). In code, an unknown start date counts as medium urgency and high information uncertainty. A notice whose recipient is "unclear" is treated as the client's.
- Lane 3 takes priority over Lane 2. A referral is never delayed to gather information (output.md §3).
- When a time limit cannot be determined for legal reasons, complexity is high, which means Lane 3.
- When the tool has no checked guidance for the situation, it does not improvise: at least Lane 2, with a referral to the tenant association or another listed advice service.
- Overrides should normally move a case **up**. A move down needs a reason a reviewer can check.
