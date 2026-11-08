# Disclosures, v5 OpenAI comparison version (draft for review by the legal team)

**Version:** v5, a **comparison and test version** (branch `v5-openai`, Vercel preview). It is used **only with invented cases**, never with real client data. AI service: **OpenAI** (a US company), model gpt-5.6-sol. Not the live version; see `docs/README.md`.
Status: draft, 8 Nov 2026. Points marked **[check]** depend on facts the team has not yet verified.

**What the user sees in v5:** AI-written text for each case, with no pre-written legal text: the follow-up questions, legal notes applying the law to each issue, the actions, the case summary, the client handout and the expert brief. Code limits what the AI may write about (from the confirmed deciding events) and removes sentences that fail its rules or one further OpenAI check.

## A. Client handout disclosure (print on every handout; max 90 words)

> **About this sheet**
> **Test version: for invented cases only.** This sheet was made with a computer tool that uses artificial intelligence (AI) from OpenAI, a US company. The AI wrote it. It may contain mistakes.
> This is general legal information, **not legal advice**. It does not replace a lawyer.
> Our tool does not save your case. Your information was sent to OpenAI in the USA, which may keep data.
> For advice on your own case, contact a service listed on this sheet. If a deadline is mentioned, act in time.

(87 words plus the three-word heading)

**[check]** The data sentence is cautious because the provider's terms are not verified. Our server keeps the case only in the browser until "End case". We have **not** verified whether or for how long OpenAI keeps API inputs, whether it uses them for training, or whether Vercel (the hosting provider) keeps logs. Check OpenAI's current API terms and data-usage policy before changing the sentence.

**[check]** The code (`app/outputs.py`, `CLIENT_DISCLOSURE`, same in all versions) prints a generic text that names neither OpenAI nor the USA and does not say it is a test version ("…sent to an AI service, which may keep data for a short time…"). For v5 it should print the text above. The v5 screen header already says "comparison version (OpenAI model, no pre-written text)".

## B. Social-worker terms of use (show before first use; max 250 words)

> **Terms of use: tenancy information assistant (test version)**
>
> 1. **What it is.** A comparison and test version: **use invented cases only, never real client data.** It drafts legal *information*, not legal advice, on residential tenancy law in the canton of Zurich. An OpenAI model writes everything shown; case text is sent to OpenAI in the USA. It can be wrong.
> 2. **Your responsibility.** You confirm the facts, warning signs, deciding facts and vulnerability rating (1–10) before the lane is calculated. You read every output. Automatic checks remove some errors, not all.
> 3. **Lanes.** You may change the lane. Give the reason; it is logged. If you are unsure, choose the higher lane.
> 4. **Always refer to a human professional, whatever the tool says,** if there is a court or enforcement step, a termination from the landlord, violence, threats or immediate danger (call 117 or 144 first), a residence-permit question linked to the housing, or a deadline you cannot date.
> 5. **Deadlines.** Calculated dates are provisional. Check them against the original document and the receipt date.
> 6. **Data.** Enter invented data only. Phone numbers, e-mail addresses, IBANs and AHV numbers are masked automatically. Names, addresses and **photos of documents are sent unmasked**: black out what is not needed. Nothing is stored on our server. Click "End case" when you finish. Your duties of secrecy still apply.
> 7. **Contacts.** Contact details come from a list checked once. Check opening hours and eligibility before passing them on.

(244 words including the heading)

Notes for the legal team:
- Point 1 and the handout name OpenAI and the USA because Art. 19(4) DSG requires telling the data subject the destination state; see regulatory.md §4 for the open cross-border questions (Swiss-US Data Privacy Framework, OpenAI's terms, confidentiality).
- Point 4 lists the referral rules from `framework.md`. In v5, court steps, a landlord's termination, violence, threats, exploitation, immediate danger and migration status always give Lane 3 in code. A deadline that cannot be dated gives at least Lane 2, and Lane 3 only when the time limit cannot be determined for legal reasons (see framework.md §4).
- Point 2, "not all": in the final blind comparison (one Claude reviewer, 11 known cases, not checked by a lawyer), a lawyer would spot a clear error in 10 of 11 v5 cases.
- Point 6, "Your duties of secrecy still apply": which secrecy duty applies depends on who employs the social worker (official secrecy under Art. 320 StGB for public social services). See regulatory.md §6.
- 144 is the Swiss ambulance number. resources.md lists only 117 (police) and 142 (victim support), so please confirm whether to name 144, 117 or both.
