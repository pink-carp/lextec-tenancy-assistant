# Disclosures (draft for review by the legal team)

Status: draft, 8 Nov 2026. Points marked **[check]** depend on facts the team has not yet verified.

## A. Client handout disclosure (print on every handout; max 90 words)

> **About this sheet**
> Your social worker made this sheet with a computer tool that uses artificial intelligence (AI). Your social worker checked it, but it may contain mistakes.
> This sheet gives general legal information. It is **not legal advice** and does not replace a lawyer.
> The tool does not save your case. It is deleted when your social worker closes it. To make it, your information was sent to an AI service. **[check]**
> For advice on your own case, contact a service listed on this sheet. If a deadline is mentioned, act in time.

(90 words plus the three-word heading)

**[check]** "does not save your case" is true for our server, which keeps the case only in the browser until "End case". We have **not** verified whether the AI provider (Public AI) or the hosting provider (Vercel) keeps logs, or where they process data. Keep the sentence only if both providers confirm that they do not keep the data. Otherwise, change it to: "Our tool does not save your case. The AI service may keep data for a short time; see [link]."

## B. Social-worker terms of use (show before first use; max 250 words)

> **Terms of use: tenancy information assistant**
>
> 1. **What it is.** The tool drafts legal *information*, not legal advice, on residential tenancy law in the canton of Zurich. It runs on an AI model (Apertus) through an external service. Its output can be wrong or incomplete.
> 2. **Your responsibility.** You confirm the facts, the warning signs and the vulnerability rating (1–10) before the lane is calculated. You read every output before the client gets it. Legal statements the official article text does not support are removed automatically. That check does not replace your judgement.
> 3. **Lanes.** You may change the lane. Give the reason; it is logged. If you are unsure, choose the higher lane.
> 4. **Always refer to a human professional, whatever the tool says,** if there is a court or enforcement step, a termination from the landlord, violence, threats or immediate danger (call 117 or 144 first), a residence-permit question linked to the housing, or a deadline you cannot date.
> 5. **Deadlines.** Calculated dates are provisional. Check them against the original document and the receipt date.
> 6. **Data.** Enter only what the case needs. Phone numbers, e-mail addresses, IBANs and AHV numbers are masked automatically. Names, addresses and **photos of documents are sent unmasked**: black out what is not needed. Nothing is stored on our server. Click "End case" when you finish. Your duties of secrecy still apply.
> 7. **Contacts.** Contact details come from a list checked once. Check opening hours and eligibility before passing them on.

(248 words including the heading)

Notes for the legal team:
- Point 4 lists the proposed hard triggers from `framework.md`. Some of them are not yet hard rules in the code (see framework.md §4).
- Point 6, "Your duties of secrecy still apply": which secrecy duty applies depends on who employs the social worker (official secrecy under Art. 320 StGB for public social services). See regulatory.md §6.
- 144 is the Swiss ambulance number. resources.md lists only 117 (police) and 142 (victim support), so please confirm whether to name 144, 117 or both.
