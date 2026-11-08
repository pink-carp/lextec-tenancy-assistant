# Disclosures, v2 baseline (draft for review by the legal team)

**Version:** v2 baseline, an earlier version kept for comparison (branch `v2-baseline`, Vercel preview behind a Vercel login). AI model: Apertus 1.5 70B, through the Public AI service. Not the live version; see `docs/README.md`.
Status: draft, 8 Nov 2026. Points marked **[check]** depend on facts the team has not yet verified.

**What the user sees in v2:** the AI chooses the legal issues and articles (code adds the articles for the identified situation). The screen explains them with plain-language article summaries reviewed against the official German text (not by a lawyer). The AI writes most questions, the case summary, up to five actions and the client handout; a few questions and warnings are fixed, reviewed texts. AI sentences that cite an article are checked against it by a further AI call.

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
> 1. **What it is.** The tool drafts legal *information*, not legal advice, on residential tenancy law in the canton of Zurich. An AI model (Apertus, via Public AI) chooses the articles and writes the questions, actions, summary and handout. It can be wrong.
> 2. **Your responsibility.** You confirm the facts, warning signs and vulnerability rating (1–10) before the lane is calculated. You read every output before the client gets it. Article summaries were reviewed; AI sentences citing an article are checked automatically. That does not replace your judgement.
> 3. **Lanes.** You may change the lane. Give the reason; it is logged. If you are unsure, choose the higher lane.
> 4. **Always refer to a human professional, whatever the tool says,** if there is a court or enforcement step, a termination from the landlord, violence, threats or immediate danger (call 117 or 144 first), a residence-permit question linked to the housing, or a deadline you cannot date.
> 5. **Deadlines.** Calculated dates are provisional. Check them against the original document and the receipt date.
> 6. **Data.** Enter only what the case needs. Phone numbers, e-mail addresses, IBANs and AHV numbers are masked automatically. Names, addresses and **photos of documents are sent unmasked**: black out what is not needed. Nothing is stored on our server. Click "End case" when you finish. Your duties of secrecy still apply.
> 7. **Contacts.** Contact details come from a list checked once. Check opening hours and eligibility before passing them on.

(249 words including the heading)

Notes for the legal team:
- Point 4 lists the proposed hard triggers from `framework.md`. In v2 only court steps and a landlord's termination always give Lane 3. Immediate danger and migration status give Lane 3 through the complexity index; violence, threats and exploitation raise vulnerability but give Lane 3 only together with medium urgency or severity (see framework.md §4).
- Point 6, "Your duties of secrecy still apply": which secrecy duty applies depends on who employs the social worker (official secrecy under Art. 320 StGB for public social services). See regulatory.md §6.
- 144 is the Swiss ambulance number. resources.md lists only 117 (police) and 142 (victim support), so please confirm whether to name 144, 117 or both.
