# Disclosures, v3 generative (draft for review by the legal team)

**Version:** v3 generative, a comparison version (branch `v3-generative`, Vercel preview). AI model: Apertus 1.5 70B, through the Public AI service. Not the live version; see `docs/README.md`.
Status: draft, 8 Nov 2026. Points marked **[check]** depend on facts the team has not yet verified.

**What the user sees in v3:** AI-written text for each case: the follow-up questions, the actions, the case summary and the client handout. Code limits what the AI may write about (from the confirmed deciding events) and removes sentences that fail its rules or two further Apertus checks. AI notes applying the law to the case are switched off after measurement. General plain-language article summaries (reviewed against the official text) can be opened on screen.

## A. Client handout disclosure (print on every handout; max 90 words)

> **About this sheet**
> Your social worker made this sheet with a computer tool that uses artificial intelligence (AI). The AI wrote it from information your social worker checked. It may contain mistakes.
> This is general legal information, **not legal advice**. It does not replace a lawyer.
> Our tool does not save your case. Your information was sent to an AI service (Public AI), which may keep data for a short time.
> For advice on your own case, contact a service listed on this sheet. If a deadline is mentioned, act in time.

(89 words plus the three-word heading)

**[check]** The data sentence uses the cautious wording because the providers are not verified. Our server keeps the case only in the browser until "End case". We have **not** verified whether Public AI (the AI provider) or Vercel (the hosting provider) keeps logs, or where they process data. Only if both confirm that they keep no data may the sentence become: "The tool does not save your case. It is deleted when your social worker closes it."

**[check]** The code (`app/outputs.py`, `CLIENT_DISCLOSURE`, same in all versions) prints a generic text without the provider's name ("…made this sheet with a computer tool that uses artificial intelligence (AI)… sent to an AI service, which may keep data for a short time…"). Switch it to the text above once approved.

## B. Social-worker terms of use (show before first use; max 250 words)

> **Terms of use: tenancy information assistant**
>
> 1. **What it is.** The tool drafts legal *information*, not legal advice, on residential tenancy law in the canton of Zurich. An AI model (Apertus, via Public AI) writes the questions, actions, summary and handout for each case. It can be wrong.
> 2. **Your responsibility.** You confirm the facts, warning signs, deciding facts and vulnerability rating (1–10) before the lane is calculated. You read every output before the client gets it. Sentences that fail automatic checks are removed, but tests showed that wrong statements still get through.
> 3. **Lanes.** You may change the lane. Give the reason; it is logged. If you are unsure, choose the higher lane.
> 4. **Always refer to a human professional, whatever the tool says,** if there is a court or enforcement step, a termination from the landlord, violence, threats or immediate danger (call 117 or 144 first), a residence-permit question linked to the housing, or a deadline you cannot date.
> 5. **Deadlines.** Calculated dates are provisional. Check them against the original document and the receipt date.
> 6. **Data.** Enter only what the case needs. Phone numbers, e-mail addresses, IBANs and AHV numbers are masked automatically. Names, addresses and **photos of documents are sent unmasked**: black out what is not needed. Nothing is stored on our server. Click "End case" when you finish. Your duties of secrecy still apply.
> 7. **Contacts.** Contact details come from a list checked once. Check opening hours and eligibility before passing them on.

(248 words including the heading)

Notes for the legal team:
- Point 4 lists the proposed hard triggers from `framework.md`. In v3 only court steps and a landlord's termination always give Lane 3. Immediate danger and migration status give Lane 3 through the complexity index; violence, threats and exploitation raise vulnerability but give Lane 3 only together with medium urgency or severity (see framework.md §4).
- Point 2, "wrong statements still get through": in the final blind comparison (one Claude reviewer, 11 known cases, not checked by a lawyer), a lawyer would spot a clear error in 11 of 11 v3 cases.
- Point 6, "Your duties of secrecy still apply": which secrecy duty applies depends on who employs the social worker (official secrecy under Art. 320 StGB for public social services). See regulatory.md §6.
- 144 is the Swiss ambulance number. resources.md lists only 117 (police) and 142 (victim support), so please confirm whether to name 144, 117 or both.
