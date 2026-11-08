# Regulatory notes (v4, live)

> **Version:** v4 limited scope, the live and recommended version (branch `main`, i.e. `v4-scoped` plus one later fix, https://liit.bouveng.org).
> **PRELIMINARY, FOR REVIEW BY THE LEGAL TEAM.** Drafted 8 Nov 2026 by an AI assistant. This is not a legal opinion.
> Each note separates **Sources say** (text we opened, cited by article) from **Assessment** (our reading, to be checked).
> Facts assumed about the system: it runs Apertus 1.5 70B through the Public AI inference service, and **where Public AI processes data is not verified**. It is hosted on Vercel (region Frankfurt; Vercel is a US company). The server stores no case data. Phone numbers, e-mails, IBAN and AHV numbers are masked before text is sent to the AI. **Document photos are sent unmasked.** The social worker confirms the inputs and can override the lane. What the AI writes in v4: legal points, actions and client texts come from 9 pre-written situation modules, checked against the official German text in a second pass (not reviewed by a lawyer); the AI reads the description, suggests the situation, pre-fills some answers and writes a two-sentence situation summary and, on request, a translation of the handout.

## 1. Revised FADP (nDSG): does it apply?

**Sources say.** The DSG applies to processing of personal data of natural persons by (a) private persons and (b) federal bodies (Art. 2(1) DSG). It covers situations with effects in Switzerland, even if they are caused abroad (Art. 3(1)). The IDG ZH applies to "öffentliche Organe", which include authorities and administrative units of the municipalities (§ 2, § 3(1)(b) IDG).

**Assessment.** It depends on who deploys the tool:
- **Private deployer** (an NGO, LexTec, the team): the DSG applies directly.
- **Municipal social service**: the IDG ZH governs its processing, not the DSG, because it is neither a private person nor a federal body (see §5).

The private service providers (team, Public AI, Vercel) are probably bound by the DSG for their own processing in either case. We have not verified how the DSG and the IDG interact for private processors working for a cantonal or municipal body.

## 2. Sensitive personal data

**Sources say.** Art. 5 lit. c DSG lists data on health and the intimate sphere (no. 2), administrative or criminal proceedings and sanctions (no. 5) and **social assistance measures** (no. 6). Where consent is needed for such data, it must be express (Art. 6(7)(a)). A data protection impact assessment (DPIA) is required in particular for "umfangreiche Bearbeitung" of such data (Art. 22(1), (2)(a)). The IDG has an equivalent list, which includes "Massnahmen der sozialen Hilfe" (§ 3(4)(a) no. 3 IDG). The Zurich data protection commissioner's AI guidance says that processing besondere Personendaten with AI needs a sufficiently specific basis in a formal law.

**Assessment.** Case files will regularly contain sensitive data: social assistance status, illness, pregnancy, domestic violence and possibly criminal or police measures. Residence status is not listed as such; it may fall under no. 5 when proceedings are pending. Plan for a DPIA. For a public deployer, check the formal legal basis, for example in the cantonal social assistance law (Sozialhilfegesetz, SHG; not checked).

## 3. Processors (Art. 9 DSG)

**Sources say.**
- Processing may be transferred to a processor by contract if the processor processes the data only as the controller itself may, and if no legal or contractual secrecy duty forbids the transfer (Art. 9(1)).
- The controller must ensure that the processor can guarantee data security (Art. 9(2)).
- Sub-processing needs the controller's prior approval (Art. 9(3)).
- A private person who intentionally transfers processing without meeting Art. 9(1)–(2) can be fined up to CHF 250,000 (Art. 61(b)).
- Under the IDG, the public body may outsource processing but remains responsible (§ 6 IDG). According to the cantonal social assistance handbook, outsourcing needs a written contract (§ 25 IDV), and the superior body must approve the contract when besondere Personendaten are involved. We did not open the IDV itself.

**Assessment.** Public AI and Vercel are processors. A written data processing agreement must exist with each of them, including secrecy clauses, a sub-processor list and deletion terms. To our knowledge none has been concluded, so do not use the tool with real client data before then.

## 4. Cross-border disclosure (Art. 16–17 DSG)

**Sources say.**
- Data may go abroad if the Federal Council has found adequate protection (Art. 16(1)). Annex 1 DSV (version of 1 Dec 2025) lists **Germany**. It lists the **USA only for organisations certified under the Swiss-US Data Privacy Framework**.
- Otherwise, appropriate safeguards are needed, for example standard contractual clauses recognised by the FDPIC (Art. 16(2)(d)).
- Exceptions include explicit consent (Art. 17(1)(a)).
- The data subject must be told the destination state (Art. 19(4)).
- For public bodies: § 19 IDG.

**Assessment.**
- **Vercel (Frankfurt):** Germany is adequate. Whether US entities of Vercel can access the data, and whether Vercel is certified under the Data Privacy Framework, is **not verified**.
- **Public AI:** the processing location is **unknown**, so compliance with Art. 16 cannot currently be shown. Unmasked photos make this more serious.
- **Consent:** relying on Art. 17(1)(a) consent is weak where clients depend on the social service, because consent must be voluntary (Art. 6(6)).

## 5. Cantonal law: Zurich public social services (IDG ZH)

**Sources say.** Public bodies include authorities and administrative units of the municipalities (§ 3(1)(b) IDG), and private organisations entrusted with public tasks (§ 3(1)(c)). Public bodies must inform the people concerned when they collect personal data (§ 12). They may disclose besondere Personendaten only on a formal-law basis, with express consent in the individual case, or to avert danger (§ 17(1)). The Zurich data protection commissioner's AI guidance (April 2025) requires:
- documented use cases;
- a check of the legal basis (§ 8 IDG);
- a written outsourcing contract (§ 6 IDG, § 25 IDV);
- a DPIA and an information security and data protection concept (ISDS);
- submission for prior review where special risks remain (§ 10(2) IDG).

**Assessment.** A municipal social service is a public body under the IDG. Before a pilot it would have to complete these steps, possibly within the Innovation Sandbox AI. The cantonal law currently in force was checked: IDG version 125 (dated 1 July 2024, listed as current on zh.ch).

## 6. Official and professional secrecy (Art. 320 / 321 StGB)

**Sources say.**
- **Art. 320 StGB** punishes the disclosure of secrets entrusted to a member of an authority or an official ("Beamter"), including their auxiliary persons. "Beamte" include employees of a public administration (Art. 110(3)). Release requires the **written consent of the superior authority** (Art. 320(2)).
- **Art. 321** lists the professions it covers (clergy, lawyers, doctors, psychologists, nurses and others) and their auxiliaries. **Social workers are not listed.**
- Art. 62 DSG fines the intentional disclosure of secret personal data learned in a profession that requires knowing such data.
- The cantonal social assistance handbook applies official secrecy to social services and to private institutions with delegated tasks (§ 47 SHG, not opened by us). Contractors must be bound to secrecy by contract.

**Assessment.**
- **Public social workers:** covered by Art. 320 in their official capacity.
- **Private-NGO social workers:** not covered by Art. 320 or 321 as such. Art. 62 DSG may apply.
- **AI provider:** sending it case data may be "disclosure" unless it is bound as an auxiliary. Needs a lawyer's view.

## 7. Liability for AI-assisted information

**Sources say.**
- **Contract:** a debtor who does not perform properly is liable unless it proves it was not at fault (Art. 97(1) OR). A mandatary owes careful performance (Art. 398(2)) and is liable for its auxiliaries (Art. 101(1)).
- **Tort:** liability requires damage caused unlawfully and with fault (Art. 41(1)). Employers are liable for their staff (Art. 55).
- **Disclaimers:** an advance exclusion of liability for intent or gross negligence is void (Art. 100(1)).
- **Public bodies:** cantons may set their own rules (Art. 61(1)). Under the Zurich Haftungsgesetz, the state is liable for unlawful damage its employees cause in official functions (§ 6(1)); this also applies to municipalities (§ 2). We read the 2018 version only.

**Assessment.** "Information, not advice" narrows what is promised but cannot exclude liability for gross negligence. The main risk is a wrong deadline (e.g. the 30 days of Art. 273 OR). That pure economic loss in tort needs a breached protective norm is doctrine we did not source.

## 8. Transparency duties

**Sources say.**
- **Art. 19 DSG:** the controller must give the controller's identity, the purpose, the recipients and any foreign state.
- **Art. 21 DSG:** for decisions based *exclusively* on automated processing that have legal effects, the person must be informed and can request human review.
- **Art. 25(2)(f) DSG:** the right of access covers the logic of such decisions.
- **FDPIC (statement of 8 May 2025):** providers and users must disclose the purpose, functioning and data sources of AI processing. Users have a right to know whether they are talking to a machine and whether their inputs are used for training.
- **For public bodies:** § 12 IDG.

**Assessment.** The lane is not purely automated (the social worker confirms the inputs and can override it) and has no direct legal effect, so Art. 21 probably does not apply. The disclosures in `disclosure.md` address Art. 19 and the FDPIC statement. Open point: whether Public AI uses inputs for training (**not verified**). The client must be told if it does.

## 9. EU AI Act (Regulation (EU) 2024/1689) for cross-border users

**Sources say.**
- **Scope:** the Act covers providers and deployers in third countries "where the output produced by the AI system is used in the Union" (Art. 2(1)(c)), and affected persons located in the Union (Art. 2(1)(g)).
- **Annex III 5(a), high risk:** systems used by or for public authorities "to evaluate the eligibility of natural persons for essential public assistance benefits and services", or to grant, reduce, revoke or reclaim them.
- **Art. 6(3):** an Annex III system is not high-risk if it does, for example, a narrow procedural or preparatory task, but it is **always** high-risk if it profiles.
- **Art. 50 (duties of providers):** systems that interact with people must tell them they are dealing with AI, unless this is obvious (50(1)). Generated text must carry a machine-readable mark (50(2)).
- **Timeline (Digital Omnibus, Reg. (EU) 2026/1744, in force 27 Jul 2026):** Annex III obligations apply from **2 Dec 2027**. Art. 50 has applied since **2 Aug 2026** (Art. 113); for 50(2), systems on the market before then have until **2 Dec 2026**.

**Assessment.** The Act applies only if the tool or its output is used in the EU (for example, for a client living there). The tool probably falls outside 5(a): it gives information and referrals, not benefit decisions. That is less clear if a public service uses the lane to ration legal help. The automated vulnerability *suggestion* could count as profiling. Requiring the social worker to confirm it reduces that risk.

## Sources opened

- DSG (SR 235.1), version of 7 Jul 2025: https://www.fedlex.admin.ch/eli/cc/2022/491/de. Articles 2, 3, 5, 6, 9, 16, 17, 19–22, 25, 61 and 62 were read.
- DSV (SR 235.11), version of 1 Dec 2025, Annex 1: https://www.fedlex.admin.ch/eli/cc/2022/568/de
- StGB (SR 311.0), version of 1 Nov 2026, Articles 110, 320 and 321: https://www.fedlex.admin.ch/eli/cc/54/757_781_799/de
- OR (SR 220), version of 1 Oct 2026, Articles 41, 55, 61, 97, 100, 101 and 398, from the project corpus (`corpus/law_paragraphs.jsonl`, taken from Fedlex): https://www.fedlex.admin.ch/eli/cc/27/317_321_377/de
- IDG ZH (LS 170.4), version 125: https://www.zh.ch/de/politik-staat/gesetze-beschluesse/gesetzessammlung/zhlex-ls/erlass-170_4-2007_02_12-2008_10_01-125.html
- Haftungsgesetz ZH (LS 170.1), version 99 (as of 1 Jan 2018): https://www2.zhlex.zh.ch/appl/zhlex_r.nsf/0/EF2C714AD21CDE95C12581DE0029E359/$file/170.1_14.9.69_99.pdf
- Zurich social assistance handbook (Sozialhilfehandbuch), sections 5.2.01 and 5.2.08: https://www.zh.ch/de/soziales/sozialhilfe/sozialhilfehandbuch/flexdata-definition/5-allgemeines-zur-sozialhilfe/5-2-amtsgeheimnis-und-informationsaustausch/5-2-01-amtsgeheimnis-und-schweigepflicht.html and …/5-2-08-auslagerung-von-dienstleistungen--datenschutz.html
- Zurich data protection commissioner (Datenschutzbeauftragte), "Merkblatt Vorgehen beim Einsatz von KI bei öffentlichen Organen", V1.0, April 2025: https://docs.datenschutz.ch/u/d/publikationen/formulare-merkblaetter/Merkblatt-Vorgehen-beim-Einsatz-von-KI-in-oeffentlichen-Organen.pdf
- FDPIC (EDÖB), statement of 8 May 2025: https://www.edoeb.admin.ch/de/update-geltendes-datenschutzgesetz-ist-auf-ki-direkt-anwendbar. The cross-border page was also read: https://www.edoeb.admin.ch/en/cross-border-transfer-of-personal-data
- EU AI Act, Regulation (EU) 2024/1689 (Articles 2, 3(52), 6(3), 50 and 113; Annex III): https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX:32024R1689
- Digital Omnibus on AI, Regulation (EU) 2026/1744: https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX:32026R1744

**Not opened, cited only second-hand:** § 47 SHG, § 25 IDV, § 8 GG and § 51 Personalgesetz ZH (all cited in the handbook).
