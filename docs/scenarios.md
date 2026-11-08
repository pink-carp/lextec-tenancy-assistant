Draft for review by the legal team, 8 Nov 2026. Cases are dated as if asked today, **Sunday 8 Nov 2026**. Every tenancy citation below was checked against `corpus/law_paragraphs.jsonl`: OR as of 1 Oct 2026, ZGB and ZPO as of 1 Jul 2026. Citations from outside the corpus are marked **[outside corpus]**, with the source we opened.

---

CASE 10 - lane 1

Hi, I'm Jonas, 29. I rent a 2-room flat in **Winterthur** on my own since 2021. The contract has no end date. I'm not married and nobody else is on the lease. I found a new flat that starts on 1 April 2027, so I want to end my current lease at the end of March. My contract says the notice period is 3 months and that I can cancel to the end of any month except December. My rent is paid and there are no problems with the landlord. How do I cancel, and until when? Can I just send an email to the property management?

Follow up questions (optional; none of them blocks the answer):

- Who is named as landlord or property manager in your lease, and at which postal address? (The notice must reach that person.)
- Would you like to leave before 31 March, for example if the new flat is free earlier?

### Assigned lane: Lane 1 (AI assistance)

| Dimension | Finding | Level |
| ----- | ----- | ----- |
| Information uncertainty | The lease type, sole tenancy, marital status, notice period, termination dates and target date are all stated. Only the landlord's address is missing, and that does not affect the legal answer. | Low |
| Legal urgency | No notice from the landlord and no proceedings. The client's own latest receipt date is 31 Dec 2026, 53 days from today (provisional, see below). | Low |
| Severity of consequences | If the notice is late, the lease ends one month later (30 Apr 2027): one extra month's rent, not loss of housing. | Low |
| Personal vulnerability | None reported. Suggested score 2/10. | Low |
| Legal complexity | One tenancy question with standard rules. | Low |

**Why Lane 1:** no Lane 3 trigger applies and the material facts are available. Code rule: "Lane 1: straightforward, non-urgent, low vulnerability, enough information."

**Reassess if:** Jonas is married or in a registered partnership and the flat is the family home (spouse's consent required, see below). Also reassess if the lease is fixed-term, if someone else signed it, or if he asks after about 21 Dec 2026, when the receipt date is less than 10 days away and the code sets urgency to high.

**Legal information**

**You can end the lease on 31 March 2027. Send a signed letter, not just an e-mail, and make sure the landlord receives it by 31 December 2026 at the latest.**

1. **Which rules apply.** An open-ended lease can be terminated with the statutory notice periods and dates, unless a longer period or other dates were agreed (**Art. 266a(1) OR**). For flats, the statutory notice period is three months (**Art. 266c OR**). Your lease (three months, to the end of any month except December) is such an agreement. The end of March is a permitted date.
2. **Form.** Termination of a residential lease must be in writing (**Art. 266l(1) OR**). Written form requires your signature (**Art. 13(1), 14(1) OR**). A qualified electronic signature with a qualified time stamp counts as a handwritten one (**Art. 14(2bis) OR**). An ordinary e-mail has no such signature, so do not rely on it. Only the landlord must use an official form (**Art. 266l(2) OR**); you do not need one.
3. **Timing.** The three months must run in full before 31 March. So the notice must **reach** the landlord before 1 January 2027, i.e. by **31 December 2026**. *This date is provisional:* it is counted backwards from the termination date (deadlines.md §3) and is not moved to a later working day. What counts is when the landlord receives the letter, not when you post it. If a registered letter is not collected, it generally counts as received when it could first be collected (deadlines.md §2). Offices are often closed between Christmas and New Year, so **send it by registered post in the first half of December** (a precautionary planning date, not a legal deadline).
4. **If you are late.** The termination is not void. It takes effect on the next possible date (**Art. 266a(2) OR**), which under your lease is 30 April 2027. You would owe one more month's rent.
5. **Spouse.** You are not married, so no consent is needed. A married tenant could terminate a family home only with the spouse's express consent (**Art. 266m(1) OR; Art. 169(1) ZGB**).
6. **Leaving earlier.** If you move out before the lease ends, you are released early only if you propose a new tenant the landlord can reasonably accept, who is solvent and willing to take over the lease on the same terms (**Art. 264(1) OR**). Otherwise you owe rent until the lease ends (**Art. 264(2) OR**).

**What to do**

1. Write a short letter: your name, the flat's address, "I terminate the lease for 31 March 2027", the date and your handwritten signature. Keep a copy.
2. Send it by registered post to the landlord or manager named in the lease, in the first half of December 2026. Keep the receipt and the tracking record.
3. Ask for written confirmation and an appointment for the handover.

**What this scenario tests in the system**

- The client's *own* planned notice must not be recorded as signal type `termination_notice`. The code sets urgency to high for that type whatever the direction (`scoring.urgency`), which would send this case to Lane 3 by mistake.
- The deadline must be calculated **backwards** from a quoted period (Art. 266c OR: "Frist von drei Monaten"), with no shift to the next working day.
- Borderline for the legal team: the urgency rule ignores stakes. Asked on 22 Dec, this low-stakes case would go to Lane 3 (deadline within 10 days). Is that intended?

RELEVANT CLAUSES: Art. 266a, 266c, 266l, 266m, 264, 13, 14 OR; Art. 169 ZGB

---

CASE 11 - lane 3

Hello, I am Amina, I live in **Zurich-Schwamendingen** with my husband and our two children (3 and 7). On Saturday night my husband hit me again and the police came. They gave him a paper that he cannot come home for 14 days. The lease is only in his name. Now he writes me messages that he will cancel the flat so me and the kids are on the street, and that he will stop paying the rent. My B permit is because of him, I am scared I lose it if I leave him. The rent for December is due soon. What can I do? Please don't tell him I asked.

Follow up questions (ask the first two now; the referral does not wait for the rest):

- **Are you and the children safe right now?** Is he keeping away and not contacting you, apart from the messages? (If not, call 117.)
- **What date does the police paper give for the start and end of the measures?** Do you have the paper with you? (A request to extend the measures must be made within a few days.)
- Are you legally married to him (in Switzerland, or abroad with the marriage registered here)? (The protection for a family home depends on marriage.)
- Has the landlord or property manager sent you or him any letter about rent or termination? If yes, when did it arrive?
- Since when have you had your B permit, and since when have you lived together in Switzerland as a married couple? (For the migration specialist; you do not need to know the legal answer.)
- Can you pay the December rent yourself or with help? Do you already receive support from the social service?

### Assigned lane: Lane 3 (Human referral)

**Why:** several proposed hard triggers apply at once: violence and threats, migration status linked to the housing, and a short protective-measure deadline. Under output.md §3, Lane 3 takes priority over Lane 2, and the referral is not delayed to collect the missing facts.

| Dimension | Finding | Level |
| ----- | ----- | ----- |
| Legal urgency | Police protective measures since Saturday 7 Nov. An extension request must be made within 8 days of their start (§ 6(1) GSG ZH **[outside corpus]**), i.e. around **15 Nov 2026**. *Provisional:* the start date is on the police order. December rent is due soon. | High |
| Severity of consequences | He threatens to terminate the lease and stop paying, which could lead to loss of the family's home. Her residence status may be affected. | High (by code: medium, from `termination_threatened`) |
| Personal vulnerability | Domestic violence, two young children, residence permit dependent on the husband, possible language barrier. Suggested score ≥ 8/10 because violence is present. | High |
| Legal complexity | Tenancy, marriage and family-home rules, violence protection (civil and cantonal police law) and migration law interact. | High |
| Information uncertainty | Marital status, lease terms, landlord letters, the order's dates and the permit basis are unknown. | High |

**Expected code path:** complexity high (migration in the AI rubric) → "Lane 3: legal complexity is high"; otherwise vulnerability high and severity medium → rule 4. `immediate_danger` should be set if threats are ongoing, which adds 117 and 142. **Gap:** the GSG deadline is not in the corpus or in deadlines.md, so the code drops it (`period_is_grounded`) and urgency will **not** reflect it. That is why violence and migration should be hard triggers (framework.md §4).

**Immediate actions (social worker)**

1. **Safety first.** If there is danger: 117 (police). Victim support around the clock: 142. Refer today to **Opferberatung Zürich** (044 299 40 50) or **BIF** (044 278 99 99), who can also help with the extension of the police measures and with safe accommodation.
2. **Protective-measure deadline.** Check the start date on the police order today. An extension request goes to the court within 8 days of the start; it can extend the measures to at most three months in total (§ 6(1), (3) GSG ZH **[outside corpus]**).
3. **Referral to a lawyer** (family and tenancy law): protective measures for the marriage, use of the flat, possible transfer of the lease, rent. Send the expert brief.
4. **Migration counselling.** Do **not** answer the permit question with the tool. Refer to Infodona (City of Zurich residents, 044 412 84 00) or FIZ (migrant women affected by violence). Contact details are from resources.md; check them before passing them on.
5. **Rent.** Check whether urgent financial help is possible so that the December rent is paid. Ask the client to bring any landlord letter immediately.
6. **Confidentiality.** Do not contact the husband. Ask the client whether it is safe to take a printed handout home.

**Legal information (for the social worker; the lawyer must confirm)**

**If you are married, your husband cannot validly end the lease of the family home on his own, and the landlord must send you your own copy of any termination or rent warning. Your residence permit is a separate question for a migration specialist.**

1. **He cannot simply cancel the family home.** If the flat is the family home, a spouse can terminate the lease only with the other spouse's express consent (**Art. 169(1) ZGB; Art. 266m(1) OR**). A termination that does not comply with Art. 266l–266n OR is void (**Art. 266o OR**). *Open point:* whether the flat keeps its family-home status after the police removal and a possible separation is for the lawyer (no decision checked).
2. **The landlord must inform you too.** The landlord's termination and any payment demand with a termination warning must be delivered separately to the tenant **and** the spouse (**Art. 266n OR**). Otherwise they are void (**Art. 266o OR**). As the spouse, you can challenge a termination yourself or request an extension (**Art. 273a(1) OR**). A challenge must reach the conciliation authority within 30 days of receipt (**Art. 273(1) OR**).
3. **Rent arrears are the main risk.** If rent is unpaid, the landlord can set a written deadline of at least 30 days with a termination warning (**Art. 257d(1) OR**) and then terminate with 30 days' notice to the end of a month (**Art. 257d(2) OR**). After such a termination, no extension is possible (**Art. 272a(1)(a) OR**). Keeping the rent paid protects the home, whoever pays it. *Whether a payment by the wife or the social service discharges the husband's debt was not checked.*
4. **Civil protection and the lease.** A court can order a violent person to leave the shared home for a set period, which can be extended once for important reasons (**Art. 28b(2) ZGB**). With the landlord's consent, it can transfer the lease to the victim alone (**Art. 28b(3) no. 2 ZGB**). In marriage-protection proceedings, the court regulates the use of the home and sets maintenance (**Art. 176(1) nos. 1–2 ZGB**); the violence-protection rule applies by analogy (**Art. 172(3) ZGB**). Art. 28b claims need no conciliation attempt (**Art. 198 lit. a^bis ZPO**) and follow the simplified procedure (**Art. 243(2)(b) ZPO**).
5. **Police measures (cantonal).** Each canton names a body that can exclude a violent person from the home immediately in a crisis (**Art. 28b(4) ZGB**). In Zurich, the police can exclude the person for 14 days from notification (§ 3(2)(a), (3) GSG). The protected person can ask the court to extend this within 8 days of the start (§ 6(1) GSG), up to three months in total (§ 6(3) GSG). **[outside corpus: GSG ZH, LS 351, PDF version 125 on zh.ch, opened 8 Nov 2026]**
6. **Residence permit (for the specialist only).** After the marriage or family life ends, the spouse can keep the permit if the marriage lasted at least three years and the integration criteria are met, or if important personal reasons require it (**Art. 50(1) AIG**). Being a victim of domestic violence can be such a reason; the authorities consider, among other things, police protective measures, confirmations from specialist counselling services and medical reports (**Art. 50(2)(a) AIG**). **[outside corpus: AIG SR 142.20, Fedlex version of 1 Nov 2026]** The tool must not assess her chances. Advise her to keep the police order, medical reports and counselling confirmations.

**What this scenario tests in the system**

- Mixed areas (tenancy, family, violence protection, migration) must end in Lane 3 even though the most urgent deadline is outside the corpus.
- A threat by the **husband** to cancel the lease is not a landlord's termination (`termination_threatened`, not `termination_notice`).
- Migration questions get a referral, not an answer.
- The client's request for confidentiality is respected in the handout and in the actions.

RELEVANT CLAUSES: Art. 266m, 266n, 266o, 273, 273a, 257d, 272a OR; Art. 28b, 169, 172, 176 ZGB; Art. 198, 243 ZPO; [outside corpus] § 3, 6 GSG ZH; Art. 50 AIG
