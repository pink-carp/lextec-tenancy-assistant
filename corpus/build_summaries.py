"""Plain-English summaries of the statute paragraphs the tenancy assistant cites.

Step 1: Apertus drafts one summary per paragraph from the official German text alone.
Step 2: every draft was reviewed by Claude against the German text; corrections are in REVIEW below.

Run: python corpus/build_summaries.py
Drafts already present in paragraph_summaries.json are reused, so only missing paragraphs call the API.
"""
import json
import re
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from app.llm import chat  # noqa: E402

SRC = ROOT / "corpus" / "law_paragraphs.jsonl"
OUT = ROOT / "corpus" / "paragraph_summaries.json"

OR_EXTRA = {"76", "77", "78", "97", "143", "144", "148", "544"}
ZPO_ARTS = {"113", "243", "257"} | {str(n) for n in range(197, 213)}
VMWG_ARTS = {"19", "20"}
SAMSTAG_ARTS = {"1"}

PROMPT = ("Rewrite this Swiss statute paragraph in one or two plain English sentences for a social worker. "
          "Add NOTHING the text does not say; keep every condition, exception, number and party exactly; "
          "do not generalise (e.g. a spouse or registered partner is not a cohabiting partner). "
          "Answer with the sentences only.\n\nTEXT ({id}): {text}")


def selected(p):
    art = p["article"]
    m = re.match(r"\d+", art)
    num = int(m.group()) if m else -1
    law = p["law"]
    return ((law == "OR" and (253 <= num <= 274 or art in OR_EXTRA))
            or (law == "ZPO" and art in ZPO_ARTS)
            or (law == "VMWG" and art in VMWG_ARTS)
            or (law == "Samstagsgesetz" and art in SAMSTAG_ARTS))


def load_paragraphs():
    rows = [json.loads(line) for line in SRC.read_text(encoding="utf-8").splitlines() if line.strip()]
    keep = []
    for p in rows:
        text = p["text"].strip()
        if selected(p) and text and not text.startswith("Aufgehoben"):
            keep.append(p)
    return keep


def draft_all(paras, existing):
    todo = [p for p in paras if p["id"] not in existing]
    trace = []

    def one(p):
        msg = [{"role": "user", "content": PROMPT.format(id=p["id"], text=p["text"])}]
        return p["id"], chat(msg, max_tokens=220, trace=trace, step=f"summary {p['id']}").strip()

    drafts = dict(existing)
    with ThreadPoolExecutor(max_workers=3) as pool:
        for pid, text in pool.map(one, todo):
            drafts[pid] = text
    cost = sum(t["cost_usd"] for t in trace)
    tok_in = sum(t["prompt_tokens"] or 0 for t in trace)
    tok_out = sum(t["completion_tokens"] or 0 for t in trace)
    print(f"{len(todo)} API calls, {tok_in} prompt + {tok_out} completion tokens, USD {cost:.4f}")
    return drafts


# Claude's review of every draft against the German text: id -> (final summary, what was fixed).
# Paragraphs not listed here kept the Apertus draft unchanged.
REVIEW = {
    "OR Art. 76 Abs. 1": (
        "If a time is set for the beginning or the end of a month, this means the first or the last day of that month.",
        "Draft was circular ('set to begin or end on the first or last day ... is the first or last day')."),
    "OR Art. 77 Abs. 1": (
        "If an obligation is to be performed (or another legal act done) when a set period after the contract was concluded expires, the date is: 1. for a period in days, the last day of the period, not counting the day the contract was concluded; a period of 8 or 15 days means a full 8 or 15 days, not one or two weeks; 2. for a period in weeks, the day of the last week with the same weekday name as the day the contract was concluded; 3. for a period in months or a multi-month period (year, half-year, quarter), the day of the last month with the same date number as the day the contract was concluded, or the last day of that month if it has no such date. A 'half month' counts as 15 days, counted last when a period is stated as one or more months and a half.",
        "'Signed' replaced by 'concluded' (the text speaks of conclusion, not signature); wording tightened."),
    "OR Art. 78 Abs. 2": (
        "The parties may agree otherwise.",
        "Draft 'No alternative agreements are excluded' was garbled; the text reserves different agreements."),
    "OR Art. 97 Abs. 1": (
        "If an obligation is not performed at all or not properly, the debtor must pay compensation for the resulting damage unless they prove that they were not at fault in any way.",
        "Draft said the debtor 'cannot fulfil'; the text covers any non-performance or improper performance."),
    "OR Art. 97 Abs. 2": (
        "Enforcement is governed by the Federal Act of 11 April 1889 on Debt Enforcement and Bankruptcy and the Civil Procedure Code of 19 December 2008 (ZPO).",
        "Name of the ZPO corrected ('Civil Procedure Code', abbreviation added)."),
    "OR Art. 143 Abs. 1": (
        "Several debtors become jointly and severally liable when they declare that each of them will be individually liable to the creditor for the whole debt.",
        "Removed an added sentence and the added word 'only'; named the concept (joint and several liability)."),
    "OR Art. 143 Abs. 2": (
        "Without such a declaration, joint and several liability arises only in cases set by law.",
        "Terminology aligned ('solidarity' -> joint and several liability)."),
    "OR Art. 144 Abs. 1": (
        "The creditor may choose to demand the whole debt, or only part of it, from each of the jointly and severally liable debtors.",
        "Removed an added sentence that was confusing ('applies to all joint debtors collectively')."),
    "OR Art. 144 Abs. 2": (
        "All the debtors remain bound until the whole claim has been paid.",
        "Removed invented reference to spouses or registered partners."),
    "OR Art. 253a Abs. 1": (
        "The rules on renting residential and business premises also apply to things that the landlord lets the tenant use together with those premises.",
        "Removed a redundant added sentence."),
    "OR Art. 253a Abs. 2": (
        "The rules on renting residential and business premises do not apply to holiday homes rented for three months or less.",
        "'They' replaced by what it refers to, so the summary stands alone."),
    "OR Art. 253b Abs. 2": (
        "The rules protecting against abusive rents do not apply to the rental of luxury flats and single-family houses with six or more living rooms (not counting the kitchen).",
        "'They' replaced by what it refers to, so the summary stands alone."),
    "OR Art. 254": (
        "A tied transaction linked to the rental of residential or business premises is void if concluding or continuing the lease is made conditional on it and the tenant thereby takes on an obligation to the landlord or a third party that is not directly connected with the use of the rented property.",
        "Draft said the lease is void; the text makes the tied transaction void, not the lease."),
    "OR Art. 255 Abs. 2": (
        "A lease is fixed-term if it is meant to end, without notice of termination, when the agreed period expires.",
        "Rephrased as the definition it is; removed an added sentence."),
    "OR Art. 255 Abs. 3": (
        "All other leases are of indefinite duration.",
        "Removed an invented condition about a three-month notice period."),
    "OR Art. 256 Abs. 1": (
        "The landlord must hand over the property at the agreed time in a condition fit for the intended use, and keep it in that condition.",
        "Removed an invented exception ('unless otherwise agreed or required by law'); Abs. 2 limits deviating agreements."),
    "OR Art. 256 Abs. 2": (
        "Agreements that depart from this duty to the tenant's disadvantage are void if they are contained in: a. pre-formulated general terms and conditions; b. leases of residential or business premises.",
        "Draft dropped that only agreements deviating from Abs. 1 are meant ('any agreement that disadvantages the tenant' was too wide)."),
    "OR Art. 256a Abs. 2": (
        "Likewise, the tenant may ask to be told the rent paid under the previous tenancy.",
        "Removed a redundant added sentence."),
    "OR Art. 256b": (
        "The landlord bears the charges and public levies connected with the property.",
        "Removed an invented exception (lease making the tenant responsible)."),
    "OR Art. 257": (
        "Rent is the payment the tenant owes the landlord for being given the use of the property.",
        "Removed an invented exception ('unless otherwise agreed in writing or by law'); kept as a definition."),
    "OR Art. 257a Abs. 1": (
        "Ancillary costs are the payment for services of the landlord or a third party that are connected with the use of the property.",
        "Draft added 'The tenant must pay additional costs', which contradicts Abs. 2 (only if specially agreed); it is a definition."),
    "OR Art. 257b Abs. 2": (
        "On request, the landlord must let the tenant inspect the supporting documents (receipts).",
        "Removed an invented limitation; 'Belege' are the receipts for the ancillary costs."),
    "OR Art. 257d Abs. 2": (
        "If the tenant does not pay within the deadline, the landlord may terminate the lease without notice; for residential and business premises, with at least 30 days' notice to the end of a month.",
        "Draft merged the two cases wrongly ('terminate immediately for residential premises, but only after 30 days' notice'): immediate termination applies to other things; residential/business premises need 30 days to month-end."),
    "OR Art. 257e Abs. 2": (
        "For residential premises, the landlord may demand at most three months' rent as security.",
        "Removed a redundant added sentence."),
    "OR Art. 257f Abs. 1": (
        "The tenant must use the property with care.",
        "Removed an invented exception."),
    "OR Art. 257f Abs. 2": (
        "The tenant of immovable property must show consideration for other residents of the building and for neighbours.",
        "Removed an invented exception (landlord's permission)."),
    "OR Art. 257f Abs. 3": (
        "If, despite a written warning from the landlord, the tenant keeps breaching the duty of care or consideration so that the landlord or the other residents can no longer reasonably be expected to continue the lease, the landlord may terminate without notice; for residential and business premises, with at least 30 days' notice to the end of a month.",
        "Same error as 257d Abs. 2: draft merged immediate termination and the 30-day rule for residential/business premises."),
    "OR Art. 257g Abs. 1": (
        "The tenant must report to the landlord defects that the tenant does not have to remedy themselves.",
        "Removed a redundant added sentence."),
    "OR Art. 257g Abs. 2": (
        "If the tenant fails to report such a defect, the tenant is liable for the resulting damage to the landlord.",
        "'Something' replaced by 'such a defect' (the duty concerns defects under Abs. 1)."),
    "OR Art. 259a Abs. 2": (
        "A tenant of immovable property may also deposit the rent.",
        "Removed an invented condition about the landlord being a natural person or a property company."),
    "OR Art. 259d": (
        "If the fitness of the property for its intended use is impaired or reduced, the tenant may demand that the landlord reduce the rent accordingly, from the time the landlord learned of the defect until it is remedied.",
        "Wrong party: the reduction runs from when the LANDLORD learned of the defect ('er' = Vermieter), not the tenant; 'accordingly' (proportionate) restored."),
    "OR Art. 259g Abs. 2": (
        "Once deposited, the rent counts as paid.",
        "Removed an invented condition ('only if the landlord has not yet received the rent')."),
    "OR Art. 259h Abs. 2": (
        "As soon as the tenant has announced the deposit, the landlord may ask the conciliation authority to release to the landlord any rent that was wrongly deposited.",
        "'Return' was ambiguous about who receives the money; Herausgabe is release to the landlord."),
    "OR Art. 259i": (
        "The procedure is governed by the Civil Procedure Code (ZPO).",
        "Removed an added sentence ('There are no exceptions')."),
    "OR Art. 260a Abs. 1": (
        "The tenant may renovate or alter the property only with the landlord's written consent.",
        "Removed a redundant added sentence."),
    "OR Art. 261 Abs. 1": (
        "If the landlord transfers ownership of the property after the lease was concluded, or loses it in debt enforcement or bankruptcy proceedings, the lease passes to the new owner together with ownership.",
        "'Sells'/'signed' replaced: Veräusserung covers any transfer of ownership, and the lease is 'concluded'."),
    "OR Art. 261 Abs. 2": (
        "The new owner may, however: a. for residential and business premises, terminate the lease with the statutory notice period for the next statutory date if they claim an urgent need for themselves, close relatives or relatives by marriage; b. for other things, terminate the lease with the statutory notice period for the next statutory date if the contract does not allow earlier termination.",
        "Kept letters a/b; 'item' replaced by 'things'."),
    "OR Art. 261a": (
        "The rules on transfer of the property apply by analogy when the landlord grants a third party a limited right in rem and this amounts to a change of ownership.",
        "Removed a redundant added sentence."),
    "OR Art. 261b Abs. 1": (
        "For the lease of real property (Grundstück), the parties may agree to have the lease noted (vorgemerkt) in the land register.",
        "'Plot of land' was too narrow: Grundstück in Swiss law includes buildings and condominium units."),
    "OR Art. 261b Abs. 2": (
        "The annotation means that every new owner must let the tenant use the property as the lease provides.",
        "'Notice' replaced by 'annotation' to avoid confusion with a notice of termination."),
    "OR Art. 262 Abs. 3": (
        "The tenant is liable to the landlord for ensuring that the subtenant uses the property only as the tenant is permitted to. The landlord may require this of the subtenant directly.",
        "Draft dropped the tenant's liability to the landlord, the core of the rule."),
    "OR Art. 263 Abs. 2": (
        "The landlord may refuse consent to the transfer only for good cause (wichtiger Grund).",
        "Draft said 'sublease'; this article is about transfer of a business lease, not subletting."),
    "OR Art. 263 Abs. 4": (
        "The original tenant is released from their obligations to the landlord, but remains jointly and severally liable with the third party until the lease ends, or could be ended, under the contract or the law, and for at most two years.",
        "Draft dropped 'or could be ended' and restated the cap loosely."),
    "OR Art. 265": (
        "The landlord and the tenant cannot waive in advance the right to set off claims and debts arising from the lease against each other.",
        "Removed a redundant added sentence."),
    "OR Art. 266 Abs. 2": (
        "If the parties tacitly continue the lease, it is treated as a lease of indefinite duration.",
        "Terminology ('tacitly', 'indefinite duration')."),
    "OR Art. 266a Abs. 2": (
        "If a party does not observe the notice period or the termination date, the notice takes effect for the next possible termination date.",
        "'Appointment' was a mistranslation of Termin (termination date)."),
    "OR Art. 266e": (
        "For furnished rooms and separately rented parking spaces or similar facilities, the parties may terminate with two weeks' notice to the end of a one-month rental period.",
        "Removed a redundant added sentence."),
    "OR Art. 266g Abs. 1": (
        "For important reasons that make continuing the contract unreasonable for them, the parties may terminate the lease with the statutory notice period, to take effect on any date.",
        "'At any time' clarified: the notice may take effect on any date, but the statutory notice period still applies."),
    "OR Art. 266g Abs. 2": (
        "The court decides the financial consequences of the early termination, taking all circumstances into account.",
        "Removed an invented condition about fault of a spouse or registered partner."),
    "OR Art. 266l Abs. 1": (
        "Landlords and tenants of residential and business premises must give notice of termination in writing.",
        "Removed a redundant added sentence."),
    "OR Art. 266m Abs. 2": (
        "If a spouse cannot obtain this consent, or it is refused without good reason, that spouse may apply to the court.",
        "'Appeal to the judge' suggested an appeal; den Richter anrufen means applying to the court."),
    "OR Art. 266n": (
        "The landlord's notice of termination and any payment deadline with a threat of termination (Art. 257d) must be served separately on the tenant and on the tenant's spouse or registered partner.",
        "Removed 'cohabiting partner': the text covers only spouses and registered partners."),
    "OR Art. 266o": (
        "A notice of termination that does not comply with Articles 266l–266n is void.",
        "'Invalid' replaced by 'void' (nichtig), the exact legal consequence."),
    "OR Art. 267 Abs. 1": (
        "The tenant must return the property in the condition that results from use in line with the contract.",
        "Removed invented exceptions (wear and tear, circumstances beyond control) that are not in the text."),
    "OR Art. 267a Abs. 1": (
        "When the property is returned, the landlord must check its condition and immediately notify the tenant of defects the tenant is responsible for.",
        "'When returning the property' wrongly suggested the landlord returns it."),
    "OR Art. 267a Abs. 3": (
        "If the landlord discovers such (hidden) defects later, the landlord must notify the tenant immediately.",
        "Restored 'such': the rule refers to defects not detectable in a customary inspection (Abs. 2)."),
    "OR Art. 268 Abs. 1": (
        "The landlord of business premises has a right of retention over movable things in the rented premises that serve to furnish or use them, as security for one year's rent that has fallen due and the current half-year's rent.",
        "'Defaulted annual rent' clarified (one year's rent already due); removed a redundant added sentence."),
    "OR Art. 268 Abs. 3": (
        "The right of retention does not cover things that the tenant's creditors could not seize.",
        "Draft garbled the subject ('the creditor of a tenant cannot exercise'); the limit is on the landlord's retention right."),
    "OR Art. 268a Abs. 1": (
        "Third-party rights take priority over the landlord's right of retention for things the landlord knew or should have known did not belong to the tenant, and for stolen, lost or otherwise missing things.",
        "'Misappropriated' replaced: abhanden gekommen means lost/gone missing, not embezzled."),
    "OR Art. 268b Abs. 1": (
        "If the tenant intends to move out or remove the things in the rented premises, the landlord may, with the help of the competent official office, retain as many items as are needed to cover the landlord's claim.",
        "Restored 'intends to' (will); the right applies before the move, not only after."),
    "OR Art. 268b Abs. 2": (
        "Items removed secretly or by force may be brought back into the rented premises with police help within ten days of their removal.",
        "Translated the German word 'Heimlich' left in the draft (secretly)."),
    "OR Art. 269a": (
        "As a rule, rents are not abusive in particular if they: a. are within the range of rents usual in the locality or neighbourhood; b. are justified by cost increases or additional services of the landlord; c. for newer buildings, are within a cost-covering gross return; d. only offset a rent reduction previously granted by restructuring standard market financing costs, and are set out in a payment plan disclosed to the tenant in advance; e. only offset inflation on the risk-bearing capital; f. do not exceed what landlord and tenant associations, or organisations with similar interests, recommend in their framework agreements.",
        "Draft was in German (not translated); translated with letters a–f."),
    "OR Art. 269d Abs. 1": (
        "The landlord may increase the rent at any time, with effect from the next possible termination date. The landlord must notify and justify the increase to the tenant on a form approved by the canton at least ten days before the notice period begins.",
        "Clarified 'raise to the next termination date' as 'with effect from'; 'provide a reason' -> notify and justify."),
    "OR Art. 269d Abs. 4": (
        "For notice of a rent increase or other unilateral contract change, a mechanically reproduced signature on the prescribed form is sufficient.",
        "Removed a redundant added sentence."),
    "OR Art. 270 Abs. 1": (
        "Within 30 days of taking over the property, the tenant may challenge the initial rent before the conciliation authority as abusive under Articles 269 and 269a and demand a reduction, if: a. the tenant felt forced to conclude the contract because of personal or family hardship or the situation on the local market for residential and business premises; or b. the landlord significantly increased the initial rent compared with the previous rent for the same property.",
        "Restored the conciliation authority as forum and the reference to Art. 269/269a; 'sign' -> 'conclude'."),
    "OR Art. 270c": (
        "Apart from challenging the initial rent, a party can only argue before the conciliation authority that the rent increase or reduction demanded by the other party is not justified by a corresponding change in the index.",
        "Draft reversed the reservation ('provided the initial rent is not being contested'); 'unter Vorbehalt' means the initial-rent challenge remains available."),
    "OR Art. 270d": (
        "Apart from challenging the initial rent, the tenant cannot contest stepped (graduated) rents.",
        "Draft reversed the reservation ('provided that the initial rent is subject to challenge')."),
    "OR Art. 271 Abs. 1": (
        "A notice of termination can be challenged if it breaches the principle of good faith.",
        "Wording ('notice of termination' as the act being challenged)."),
    "OR Art. 271 Abs. 2": (
        "On request, the reasons for the termination must be given.",
        "Draft limited it to the landlord and added 'written'; the text applies to either party and sets no written form."),
    "OR Art. 271a Abs. 1": (
        "A landlord's notice of termination can be challenged in particular if it is given: a. because the tenant asserts claims under the lease in good faith; b. because the landlord wants to impose a unilateral change to the tenant's detriment or a rent adjustment; c. solely to make the tenant buy the rented flat; d. during conciliation or court proceedings connected with the lease, unless the tenant started them abusively; e. within three years after the end of conciliation or court proceedings connected with the lease in which the landlord: 1. lost to a significant extent; 2. withdrew or substantially reduced the claim or action; 3. decided not to go to court; 4. reached a settlement or other agreement with the tenant; f. because of changes in the tenant's family situation that cause the landlord no significant disadvantage.",
        "Restored 'in particular' (the list is not exhaustive) and letters a–f; fixed 'waived to call upon the judge'."),
    "OR Art. 272 Abs. 2": (
        "When weighing the interests, the competent authority considers in particular: a. the circumstances in which the contract was concluded and its content; b. the duration of the lease; c. the personal, family and financial circumstances of the parties and their conduct; d. any need of the landlord to use the premises for themselves, close relatives or relatives by marriage, and how urgent that need is; e. the situation on the local market for residential and business premises.",
        "'Any owner's need' corrected to the landlord's own need; restored 'when weighing the interests'."),
    "OR Art. 272c Abs. 1": (
        "Either party may ask that the contract be adapted to changed circumstances in the extension decision.",
        "Removed a redundant added sentence."),
    "OR Art. 273a Abs. 1": (
        "If the rented property is the family home, the tenant's spouse may also challenge the termination, request an extension of the lease or exercise the other rights the tenant has on termination.",
        "Restored 'also': the spouse acts in addition to, not instead of, the tenant."),
    "OR Art. 273a Abs. 2": (
        "Agreements on extending the lease are valid only if concluded with both spouses.",
        "Serious mistranslation: draft said 'visitation rights'; Erstreckung is the extension of the lease."),
    "OR Art. 273b Abs. 1": (
        "The section on protection against termination applies to a sublease as long as the main lease has not ended. A sublease can be extended only for as long as the main lease runs.",
        "'This section' identified (protection against termination of residential and business leases)."),
    "OR Art. 273c Abs. 1": (
        "The tenant can waive rights under the section on protection against termination only where this is expressly provided for.",
        "'This section' identified so the summary stands alone."),
    "OR Art. 273c Abs. 2": (
        "Agreements to the contrary are void.",
        "'Not valid' replaced by 'void' (nichtig)."),
    "OR Art. 544 Abs. 1": (
        "Things, rights in rem or claims transferred to or acquired for the simple partnership belong to the partners jointly, as set out in the partnership agreement.",
        "Draft left German words untranslated, called the simple partnership a 'company', and added a redundant sentence."),
    "ZPO Art. 113 Abs. 1": (
        "No party compensation (for the other side's costs) is awarded in conciliation proceedings. This does not affect the canton's payment of a legal-aid lawyer appointed free of charge.",
        "'Unpaid legal representative' mistranslated unentgeltlicher Rechtsbeistand (legal-aid counsel); 'may compensate' replaced by the reservation the text makes."),
    "ZPO Art. 197": (
        "Court proceedings are preceded by an attempt at conciliation before a conciliation authority.",
        "Removed an invented CHF 10,000 threshold and invented exceptions (exceptions are in Art. 198–199)."),
    "ZPO Art. 198": (
        "There is no conciliation procedure: a. in summary proceedings; abis. in actions for violence, threats or stalking under Art. 28b ZGB or concerning electronic monitoring under Art. 28c ZGB; b. in actions on civil status; bbis. in actions on maintenance of minor or adult children and other child matters; c. in divorce proceedings; d. in proceedings to dissolve or annul a registered partnership; e. in these debt-enforcement (SchKG) actions: 1. action to deny the debt (Art. 83 para. 2), 2. declaratory action (Art. 85a), 3. third-party ownership action (Art. 106–109), 4. action to join a seizure (Art. 111), 5. actions to separate or add assets to the bankruptcy estate (Art. 242), 6. action contesting the schedule of claims (Art. 148 and 250), 7. action to establish new assets (Art. 265a), 8. action to return retained items (Art. 284); f. in disputes for which a single cantonal instance is competent under Art. 7; g. for principal intervention, counterclaims and third-party actions; h. where the court has set a deadline for an action, and for actions joined to it if they are factually connected; i. in actions before the Federal Patent Court.",
        "Draft was truncated (items e8 and f–i missing), added 'out-of-court', and mistranslated Anschlussklage (as 'counterclaim') and Art. 242 actions."),
    "ZPO Art. 199 Abs. 1": (
        "In financial (pecuniary) disputes with a value in dispute of at least CHF 100,000, the parties may jointly waive the conciliation procedure.",
        "'Property rights' mistranslated vermögensrechtlich (pecuniary)."),
    "ZPO Art. 200 Abs. 1": (
        "In disputes over the rental or lease of residential and business premises, the conciliation authority consists of a chair and equal (parity) representation of both sides.",
        "'One parity representative' was wrong: paritätische Vertretung means equal representation of both sides."),
    "ZPO Art. 201 Abs. 1": (
        "The conciliation authority tries to reconcile the parties in an informal hearing. If it helps settle the dispute, a settlement may also include disputed issues between the parties outside the proceedings.",
        "'Negotiation' -> hearing (Verhandlung)."),
    "ZPO Art. 202 Abs. 3": (
        "The conciliation authority serves the request on the other party without delay and at the same time summons the parties to the conciliation hearing.",
        "'Mediation' replaced (this is the conciliation hearing, not mediation, which the ZPO treats separately)."),
    "ZPO Art. 202 Abs. 4": (
        "In matters under Article 200, the conciliation authority may exceptionally order an exchange of written submissions if a decision proposal under Article 210 or a decision under Article 212 is possible.",
        "'She' replaced by the conciliation authority; 'at issue' -> possible (in Frage kommt)."),
    "ZPO Art. 203 Abs. 4": (
        "With the parties' consent, the conciliation authority may hold further hearings. The proceedings must be concluded within twelve months at the latest.",
        "'Negotiations' -> hearings; 'twelve months later' had no reference point."),
    "ZPO Art. 204 Abs. 2": (
        "The parties may be accompanied by a legal adviser or a person they trust.",
        "Rechtsbeiständin/Rechtsbeistand are the female and male forms of one term, not two kinds of adviser."),
    "ZPO Art. 204 Abs. 4": (
        "The other party must be informed in advance about the representation.",
        "Removed an added sentence."),
    "ZPO Art. 205 Abs. 2": (
        "The statements may, however, be used if the conciliation authority makes a decision proposal or a decision.",
        "Clarified that the reservation is an exception to Abs. 1 (use is allowed in these cases)."),
    "ZPO Art. 206 Abs. 4": (
        "A party in default may be given a disciplinary fine of up to CHF 1,000.",
        "'Fails to meet a deadline' was too narrow/wrong; Säumnis here is default (e.g. not appearing)."),
    "ZPO Art. 207 Abs. 2": (
        "When the action is filed in court, the conciliation costs are added to the costs of the main case.",
        "Removed an invented exception ('unless the court decides otherwise')."),
    "ZPO Art. 209 Abs. 3": (
        "Once notified, the authorisation to sue allows the action to be filed in court within three months.",
        "'After the authority issues' -> after notification (Eröffnung)."),
    "ZPO Art. 209 Abs. 4": (
        "In disputes over the rental or lease of residential and business premises and over agricultural leases, the deadline for filing the action in court is 30 days.",
        "Clarified what the 30-day period is (deadline to file in court after the authorisation)."),
    "ZPO Art. 210 Abs. 1": (
        "The conciliation authority may submit a decision proposal to the parties in: a. disputes under the Gender Equality Act of 24 March 1995; b. disputes over the rental or lease of residential and business premises and agricultural leases, where the deposit of rent, protection against abusive rents, protection against termination or extension of the lease is concerned; c. other financial disputes with a value in dispute of up to CHF 10,000.",
        "'Abusive rent and lease terms' corrected to abusive rents."),
    "ZPO Art. 211 Abs. 1": (
        "The decision proposal is deemed accepted and has the effect of a final decision if no party rejects it within 20 days of its written notification. A rejection needs no reasons.",
        "Removed the added requirement that the rejection be 'in writing' (the text puts 'written' on the notification)."),
    "ZPO Art. 211 Abs. 2": (
        "After receiving a rejection, the conciliation authority issues the authorisation to sue: a. in matters under Article 210 para. 1 letter b, to the party that rejected the proposal; b. in all other cases, to the claimant.",
        "'Statement of claim' mistranslated Klagebewilligung (authorisation to sue)."),
    "ZPO Art. 211 Abs. 3": (
        "In matters under Article 210 para. 1 letter b, if the action is not filed in time, the decision proposal is deemed accepted and has the effect of a final decision.",
        "'Settlement proposal' corrected to decision proposal (Entscheidvorschlag)."),
    "ZPO Art. 211 Abs. 4": (
        "The decision proposal must inform the parties of the effects set out in paragraphs 1–3.",
        "'Settlement proposal' corrected to decision proposal."),
    "ZPO Art. 212 Abs. 1": (
        "In financial disputes with a value in dispute of up to CHF 2,000, the conciliation authority may decide the case if the claimant requests it.",
        "'Property disputes' mistranslated vermögensrechtlich (pecuniary)."),
    "ZPO Art. 212 Abs. 2": (
        "The procedure is oral.",
        "Removed an invented exception."),
    "ZPO Art. 212 Abs. 3": (
        "When it decides under paragraph 1, the conciliation authority sets the court costs and the party compensation.",
        "Terminology (Parteientschädigung = party compensation)."),
    "ZPO Art. 243 Abs. 1": (
        "The simplified procedure applies to financial disputes with a value in dispute of up to CHF 30,000.",
        "'Property disputes' mistranslated vermögensrechtlich (pecuniary)."),
    "ZPO Art. 243 Abs. 2": (
        "Regardless of the value in dispute, the simplified procedure applies to disputes: a. under the Gender Equality Act of 24 March 1995; b. over violence, threats or stalking under Art. 28b ZGB or electronic monitoring under Art. 28c ZGB; c. over the rental or lease of residential and business premises and agricultural leases, where the deposit of rent, protection against abusive rents, protection against termination or extension of the lease is concerned; d. to enforce the right of access under Art. 25 of the Data Protection Act (DSG); e. under the Participation Act of 17 December 1993; f. over supplementary insurance to social health insurance under the Federal Health Insurance Act of 18 March 1994.",
        "'Abusive rent and lease terms' corrected to abusive rents."),
    "ZPO Art. 243 Abs. 3": (
        "The simplified procedure does not apply in disputes before the single cantonal instance under Articles 5 and 8 or before the commercial court under Article 6.",
        "'This provision' replaced by the simplified procedure; 'authority' -> instance (a court)."),
    "ZPO Art. 257 Abs. 2": (
        "This protection is not available if the matter is subject to the ex officio principle (Offizialgrundsatz).",
        "'Official principle' was not a recognisable term."),
    "ZPO Art. 257 Abs. 3": (
        "If this protection cannot be granted, the court does not consider the application (it is dismissed without a ruling on the merits).",
        "'Will not enter into the request' was a literal translation of Nichteintreten."),
    "VMWG Art. 19 Abs. 1": (
        "The form for notifying rent increases and other unilateral contract changes under Art. 269d OR must contain: a. for rent increases: 1. the previous rent and the tenant's previous ancillary-cost charges; 2. the new rent and the tenant's new ancillary-cost charges; 3. the date the increase takes effect; 4. clear reasons for the increase, with a separate amount for each reason if several are given; 5. for additional services, whether the landlord receives subsidies for value-enhancing improvements; b. for other unilateral changes: 1. a description of the demand; 2. the date it takes effect; 3. clear reasons for it; c. in both cases: 1. the legal requirements for challenging it; 2. the list of conciliation authorities and their local competence.",
        "'Previous tenant's' could be read as the former tenant; 'legal grounds for contesting' -> legal requirements; kept the a/b/c structure."),
    "VMWG Art. 19 Abs. 1bis": (
        "If the reasons are given in an accompanying letter, the landlord must expressly say so on the form.",
        "Serious mistranslation: Begründung means the reasons, not 'establishment of a maintenance obligation'."),
}


def main():
    paras = load_paragraphs()
    existing = {}
    if OUT.exists():
        existing = {k: v["draft"] for k, v in json.loads(OUT.read_text(encoding="utf-8")).items()
                    if k != "_meta"}
    drafts = draft_all(paras, existing)
    unknown = set(REVIEW) - {p["id"] for p in paras}
    assert not unknown, f"REVIEW has ids that are not selected: {unknown}"
    out = {"_meta": {
        "method": "Draft by Apertus 1.5 70B from the official text alone; every summary reviewed against "
                  "the official German text by Claude; changes recorded",
        "date": "2026-11-08"}}
    for p in paras:
        d = drafts[p["id"]]
        if p["id"] in REVIEW:
            fixed, note = REVIEW[p["id"]]
            out[p["id"]] = {"summary": fixed, "draft": d, "changed": True, "change_note": note}
        else:
            out[p["id"]] = {"summary": d, "draft": d, "changed": False, "change_note": ""}
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"{len(paras)} paragraphs, {len(REVIEW)} changed -> {OUT}")


if __name__ == "__main__":
    main()
