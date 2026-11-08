# Situation modules: format and rules

A module is the reviewed content for one common tenancy situation. The app shows an item only when its
`show_if` conditions hold for the confirmed facts of the case, so every item must be correct whenever its
conditions are met. Content is written once, checked against the official German text
(`corpus/law_paragraphs.jsonl`), and is the same for every client in that situation.

Audience: social workers in the canton of Zurich, not lawyers. Use plain English, short sentences, and no legal
jargon (or explain it in brackets). It is legal information, not advice: say what the law provides and what
the options are. Never promise an outcome.

## File: one JSON file per module, `corpus/modules/<id>.json`

```json
{
  "id": "payment_demand",
  "title": "Unpaid rent and a payment demand",
  "triggers": ["situation:rent_arrears", "doc:payment_demand_with_termination_warning", "E3=A"],
  "summary_for_sw": "One or two sentences: what this situation is about.",
  "questions": [
    {"id": "pd_deadline_in_letter", "text": "What payment deadline does the letter give, and what amount does it ask for?",
     "why": "The deadline in the letter decides by when the full amount must be paid.",
     "input": "short_text", "show_if": [], "basis": ["OR Art. 257d Abs. 1"], "prefill": true}
  ],
  "points": [
    {"id": "pd_full_payment", "text": "If the full amount is paid within the deadline in the letter, the landlord cannot terminate for these arrears.",
     "client_text": "If you pay the full amount by the date in the letter, the landlord cannot end your lease because of these arrears.",
     "basis": ["OR Art. 257d Abs. 1", "OR Art. 257d Abs. 2"], "show_if": ["E3=A"]}
  ],
  "actions": [
    {"id": "pd_check_funds", "text": "Check with the client today whether the full amount can be raised before the deadline (savings, family, social services).",
     "client_text": "Check today whether you can raise the full amount before the deadline, for example from savings, family or social services.",
     "who": "social_worker", "group": "immediate", "basis": ["OR Art. 257d Abs. 1"], "show_if": ["E3=A"], "deadline": "payment_demand"}
  ],
  "lawyer_questions": [{"text": "Does the payment demand meet the requirements of Art. 257d (period, termination warning, separate notice to the spouse)?", "show_if": ["E3=A"]}],
  "deadlines": ["payment_demand"]
}
```

### Fields
- `triggers`: any one of them suggests the module. The social worker confirms the choice. Atoms:
  - `situation:<id>`, using these ids: defect_in_flat, no_heating_water_or_power, deposit_return,
    co_tenant_left_or_gave_notice, house_rules_or_pets, neighbour_disturbance, rent_increase, rent_arrears,
    termination, moving_out_or_early_departure, subletting, ancillary_costs;
  - `doc:<type>`, using these types: payment_demand_with_termination_warning, termination_by_landlord,
    notice_given_by_tenant_or_cotenant, rent_increase_notice, court_or_conciliation_document;
  - an event atom (see below).
- `show_if`: a list of conditions. All must hold, and an empty list means always shown. Atoms:
  - `E<n>=A|B|C` or `E<n>!=A|B|C`. These are events from `corpus/article_requirements.json` → `events`
    (A = yes, B = no, C = unknown). Examples: E1 landlord gave notice, E2 tenant gave or decided to give notice,
    E3 payment demand under 257d, E4 defect, E5 rent increase, E6 moved out, E7 tenancy ended, E8 married and
    family home, E9 rent arrears, E10 257d deadline passed, E13 deposit given, E14 fixed-term lease, E15 co-tenant.
  - `q:<question_id>=yes|no|unknown|answered`, or with `!=`. `answered` means any value was given.
  - `deadline:<kind>`: a deadline of that kind was calculated.
- `questions`: at most 6 per module, ordered by priority. `text` is addressed to the client ("you").
  - `why` is one everyday sentence and states no rule beyond what `basis` says.
  - `input` is one of: date, yes_no_unknown, number, short_text, upload.
  - `prefill`: true if the client's own description might already answer it; the app then tries to read the
    answer from the description, and the social worker confirms.
  - Optional fields:
    - `sets_event`: `"E8"`, meaning a yes or no answer sets that event to A or B;
    - `fact`: one of `desired_end_date`, `notice_months`, `receipt_date:<doc type>` (used by the code to
      calculate deadlines);
    - `urgent`: true.
- `points`: the key legal points, 3–6 per module.
  - `text` is for the social worker and `client_text` for the client handout (use `null` to leave it out).
  - Each point is self-contained and correct whenever its `show_if` holds.
  - Use conditional wording ("If …") whenever a fact could be unknown.
  - Put article references in `basis` (paragraph ids exactly as in law_paragraphs.jsonl, e.g. "OR Art. 257d Abs. 1"),
    not in the text.
- `actions`: 3–5 per module.
  - `who` is one of: client, social_worker, professional.
  - `group` is one of: referral, immediate, now, needs_clarification.
  - `deadline` is optional and names a deadline kind to show with the action.
  - Write no dates: they come from code.
- `lawyer_questions`: 1–3 open questions for the lawyer in the expert brief. They state no conclusions.
- `deadlines`: deadline kinds the code may calculate for this module:
  - `payment_demand` (257d, 30 days from receipt; the date in the letter governs);
  - `termination_challenge` (273 Abs. 1, 30 days from receipt);
  - `rent_increase_challenge` (270b Abs. 1, 30 days from receipt);
  - `tenant_notice` (the latest day the tenant's notice must reach the landlord, from `desired_end_date` and
    `notice_months`).

## Content rules (these are where earlier AI drafts failed)
- Withholding rent is not allowed. A tenant may only **deposit** future rent with the office designated by the
  canton, after setting the landlord a written deadline and announcing the deposit (259g). Unilateral rent cuts
  risk a 257d payment demand and termination. Every defect module must say this whenever the client considers
  paying less (`situation` or question).
- The 259d rent reduction runs from when the **landlord** learned of the defect.
- 257d: for flats, the payment period is at least 30 days, and termination then requires at least 30 days'
  notice to the end of a month. It is never "immediate" for flats.
- 272a: an extension is excluded after a termination for arrears (257d), among other grounds. It is not excluded
  after every termination.
- 266l Abs. 2: only the **landlord** must use the official cantonal form. A tenant terminates with a signed
  letter (266l Abs. 1); an e-mail without a qualified signature is risky.
- 266m/266n/266o: for a married couple or registered partners living in the family home, the tenant can terminate
  only with the spouse's express consent ("ausdrücklich"; the text does not require writing), and the landlord must send termination notices and 257d demands
  **separately** to both. A notice that breaks these rules is void (266o). Boyfriends and girlfriends are not covered.
- 271/271a: a termination can be challenged within 30 days of receipt (273 Abs. 1), even if no reason was given.
  A retaliatory termination is challengeable, not automatically void.
- 264: the replacement-tenant rules apply only when the tenant returns the flat early, without observing notice.
- 257e Abs. 3: the tenant can ask the bank alone for the deposit only after one year from the end of the tenancy,
  if the landlord has not legally asserted a claim. Before that, both must agree or there must be a final
  payment order or judgment.
- 269d: a rent increase must be on the official form, with reasons, and must arrive at least 10 days before the
  notice period starts. It takes effect at the earliest at the next possible termination date.
- When unsure, leave a point out. A missing point is better than a wrong one.

Each module also gets `"review": [{"item": "<id>", "checked_against": ["<para ids>"], "note": "..."}]` from the
second pass, and `"status": "drafted by Claude from the German text, checked by a second Claude pass; not reviewed by a lawyer"`.
