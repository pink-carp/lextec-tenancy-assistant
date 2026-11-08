# Disclosures, v4 live (draft for review by the legal team)

**Version:** v4 limited scope, the live and recommended version (branch `main`, i.e. `v4-scoped` plus one later fix, https://liit.bouveng.org). AI model: Apertus 1.5 70B, through the Public AI service.
Status: draft, 8 Nov 2026. Points marked **[check]** depend on facts the team has not yet verified.

**What the user sees in v4:** legal points, actions and client texts are written in advance for 9 common situations and checked against the official German text in a second pass (not yet by a lawyer). They are shown only when the confirmed facts meet their conditions. The AI reads the description, suggests the situation, pre-fills some answers and writes a two-sentence situation summary. The handout is built from the checked client texts, the calculated deadlines and the contacts; it can optionally be translated by the AI.

## A. Client handout disclosure (print on every handout; max 90 words)

> **About this sheet**
> Your social worker made this sheet with a computer tool and checked it. Its legal texts were checked in advance; artificial intelligence (AI) wrote the summary. It may contain mistakes.
> This is general legal information, **not legal advice**. It does not replace a lawyer.
> Our tool does not save your case. Your information was sent to an AI service (Public AI), which may keep data for a short time.
> For advice on your own case, contact a service on this sheet. If a deadline is mentioned, act in time.

(89 words plus the three-word heading)

**[check]** The data sentence uses the cautious wording because the providers are not verified. Our server keeps the case only in the browser until "End case". We have **not** verified whether Public AI (the AI provider) or Vercel (the hosting provider) keeps logs, or where they process data. Only if both confirm that they keep no data may the sentence become: "The tool does not save your case. It is deleted when your social worker closes it."

**[check]** The code (`app/outputs.py`, `CLIENT_DISCLOSURE`) still prints the earlier generic text ("…made this sheet with a computer tool that uses artificial intelligence (AI)… sent to an AI service, which may keep data for a short time…"). Switch it to the text above once approved.

**[check]** Translation: if the social worker translates the handout, the translation (including this disclosure) is written by the AI; code checks only that all numbers survive. Decide whether the translated sheet should say so.

**[check]** "checked": the module texts were checked in a second pass against the official text, not by a lawyer. If the legal team prefers, write "checked (not yet by a lawyer)".

## B. Social-worker terms of use (show before first use; max 250 words)

> **Terms of use: tenancy information assistant**
>
> 1. **What it is.** The tool gives legal *information*, not legal advice, on residential tenancy law in the canton of Zurich, with checked guidance for 9 situations only. An external AI service (Public AI, model Apertus) suggests the situation, pre-fills answers and writes a short summary. It can be wrong.
> 2. **Your responsibility.** You confirm the facts, warning signs, situation and vulnerability rating (1–10) before the lane is calculated. You check pre-filled answers and read every output before the client gets it.
> 3. **Lanes.** You may change the lane. Give the reason; it is logged. If you are unsure, choose the higher lane. If no situation fits, refer the client.
> 4. **Always refer to a human professional, whatever the tool says,** if there is a court or enforcement step, a termination from the landlord, violence, threats or immediate danger (call 117 or 144 first), a residence-permit question linked to the housing, or a deadline you cannot date.
> 5. **Deadlines.** Calculated dates are provisional. Check them against the original document and the receipt date.
> 6. **Data.** Enter only what the case needs. Phone numbers, e-mail addresses, IBANs and AHV numbers are masked automatically. Names, addresses and **photos of documents are sent unmasked**: black out what is not needed. Nothing is stored on our server. Click "End case" when you finish. Your duties of secrecy still apply.
> 7. **Contacts.** Contact details come from a list checked once. Check opening hours and eligibility before passing them on.

(250 words including the heading)

Notes for the legal team:
- Point 4 lists the referral rules from `framework.md`. In v4, court steps, a landlord's termination, violence, threats, exploitation, immediate danger and migration status always give Lane 3 in code. A deadline that cannot be dated is not a hard rule: it gives at least Lane 2, and Lane 3 only when the time limit cannot be determined for legal reasons (see framework.md §4).
- Point 6, "Your duties of secrecy still apply": which secrecy duty applies depends on who employs the social worker (official secrecy under Art. 320 StGB for public social services). See regulatory.md §6.
- 144 is the Swiss ambulance number. resources.md lists only 117 (police) and 142 (victim support), so please confirm whether to name 144, 117 or both.
