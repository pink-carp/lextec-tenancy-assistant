// Verknüpft dokumentierte Bewertungen. Keine Freitextsubsumtion, Fristberechnung oder Weiterleitung.
const states=new Set(['satisfied','not_satisfied','unknown','disputed','legal_review_required']);
const definitive=s=>s==='satisfied'||s==='not_satisfied';
const unique=a=>[...new Set(a)];
const openState=a=>['legal_review_required','disputed','unknown'].find(x=>a.includes(x))||'unknown';
export function expressionRefs(x){
 if(!x||typeof x!=='object'||Array.isArray(x)||Object.keys(x).length!==1)throw Error('Invalid expression');
 if('element'in x){if(typeof x.element!=='string')throw Error('Invalid element reference');return [x.element];}
 if('not'in x)return expressionRefs(x.not);
 const a=x.all||x.any;if(!Array.isArray(a)||!a.length)throw Error('Invalid expression group');return unique(a.flatMap(expressionRefs));
}
export function evaluateExpression(x,lookup){
 expressionRefs(x);
 if(x.element){const s=lookup(x.element);if(!states.has(s))throw Error('Invalid state');return {status:s,leaves:[x.element],open:definitive(s)?[]:[x.element]};}
 if(x.not){const r=evaluateExpression(x.not,lookup);return {...r,status:r.status==='satisfied'?'not_satisfied':r.status==='not_satisfied'?'satisfied':r.status};}
 const op=x.all?'all':'any', r=x[op].map(e=>evaluateExpression(e,lookup)),ss=r.map(t=>t.status);
 const status=op==='all'?(ss.includes('not_satisfied')?'not_satisfied':ss.every(s=>s==='satisfied')?'satisfied':openState(ss)):(ss.includes('satisfied')?'satisfied':ss.every(s=>s==='not_satisfied')?'not_satisfied':openState(ss));
 return {status,leaves:unique(r.flatMap(t=>t.leaves)),open:unique(r.flatMap(t=>t.open))};
}
export function evaluate(module,binding,record,{core,sourceModuleSha256}){
 const fail=s=>{throw Error(s);};
 if(core.core_id!=='LIIT-CORE'||core.version!=='2.0.0'||binding.target_core!=='LIIT-CORE@2.0.0')fail('Core mismatch');
 if(module.module_id!==binding.source_module.id||module.version!==binding.source_module.version||sourceModuleSha256!==binding.source_module.sha256)fail('Module binding mismatch');
 if(record.module_id!==module.module_id||record.module_version!==module.version||!record.case_id||!record.selection_reason||!Number.isInteger(record.case_revision)||record.case_revision<1)fail('Invalid case identity or selection');
 if(!Array.isArray(record.selected_outcome_ids)||!record.selected_outcome_ids.length||unique(record.selected_outcome_ids).length!==record.selected_outcome_ids.length)fail('Explicit unique outcome selection required');
 const elements=new Map(module.elements.map(e=>[e.id,e])), outcomes=new Map(module.outcomes.map(o=>[o.id,o]));
 const boundElements=new Map(binding.elements.map(e=>[e.id,e])),boundOutcomes=new Map(binding.outcomes.map(o=>[o.id,o]));
 if(elements.size!==module.elements.length||boundElements.size!==elements.size||outcomes.size!==module.outcomes.length||boundOutcomes.size!==outcomes.size)fail('Duplicate or incomplete binding');
 const allContext=new Set(binding.context_dependencies);if(!allContext.size)fail('Missing context requirements');
 function verifyDependencies(x){if(!x||!Array.isArray(x.context_dependencies)||!x.context_dependencies.length||x.context_dependencies.some(k=>!allContext.has(k)))fail('Invalid applicability binding');}
 module.elements.forEach(e=>{verifyDependencies(boundElements.get(e.id));if(e.assessment.mode==='derived')expressionRefs(e.assessment.expression).forEach(id=>{if(!elements.has(id))fail('Unknown derived reference');});});
 module.outcomes.forEach(o=>{verifyDependencies(boundOutcomes.get(o.id));expressionRefs(o.when).forEach(id=>{if(!elements.has(id))fail('Unknown outcome reference');});});
 const facts=record.facts||{}, evidence=record.evidence_registry||{}, raw=record.element_assessments||{}, context=record.context_checks||{};
 function evidenceCheck(refs){if(!Array.isArray(refs))fail('Evidence list required');for(const id of refs)if(!evidence[id])fail('Unknown evidence '+id);}
 for(const [id,f]of Object.entries(facts)){if(!['verified','asserted','disputed','unknown'].includes(f.status)||!Number.isInteger(f.revision)||f.revision<1)fail('Invalid fact '+id);evidenceCheck(f.evidence_refs);if(f.status==='verified'&&!f.evidence_refs.length)fail('Verified fact without evidence');}
 function checkAssessment(a,id){if(!states.has(a.status)||!a.reasoning||!a.assessor||!a.evaluated_at||!Array.isArray(a.fact_refs))fail('Invalid assessment '+id);evidenceCheck(a.evidence_refs);if(definitive(a.status)&&(!a.evidence_refs.length||!a.fact_refs.length))fail('Definitive assessment requires facts and evidence '+id);for(const f of a.fact_refs)if(!facts[f.id])fail('Unknown fact '+f.id);}
 for(const [id,a]of Object.entries(raw)){if(!elements.has(id)||elements.get(id).assessment.mode==='derived')fail('Unknown or manually overridden derived element '+id);checkAssessment(a,id);if(elements.get(id).assessment.mode==='external_service'&&definitive(a.status)){if(!a.external_response_ref||!record.service_responses.some(s=>s.response_id===a.external_response_ref&&s.status==='calculated'))fail('Missing confirmed external answer '+id);}}
 for(const [id,a]of Object.entries(context)){if(!allContext.has(id))fail('Unknown context '+id);checkAssessment(a,id);}
 const partyIds=record.parties.map(p=>p.id);if(unique(partyIds).length!==partyIds.length)fail('Duplicate party');
 const requestIds=record.service_requests.map(x=>x.request_id);if(unique(requestIds).length!==requestIds.length)fail('Duplicate service request');
 const responseIds=record.service_responses.map(x=>x.response_id);if(unique(responseIds).length!==responseIds.length)fail('Duplicate service response');
 for(const s of record.service_responses){if(!requestIds.includes(s.request_id))fail('Unknown service request');evidenceCheck(s.evidence_refs);if(s.status==='calculated'&&!s.evidence_refs.some(id=>evidence[id].kind==='service_response'))fail('Calculated result needs service response evidence');}
 const dutyIds=record.rights_duties.map(x=>x.id),eventIds=record.events.map(x=>x.id);
 if(unique(dutyIds).length!==dutyIds.length||unique(eventIds).length!==eventIds.length)fail('Duplicate duty or event');
 for(const d of record.rights_duties){for(const id of [d.holder_party_id,d.obligated_party_id])if(id!==null&&!partyIds.includes(id))fail('Unknown party in duty');evidenceCheck(d.contract_evidence_refs);}
 for(const e of record.events)for(const id of e.observed_fact_refs)if(!facts[id])fail('Unknown event fact');
 for(const r of record.remedies){if(!record.selected_outcome_ids.includes(r.outcome_id))fail('Unselected remedy');for(const id of r.related_rights_duties)if(!dutyIds.includes(id))fail('Unknown related duty');for(const id of r.related_events)if(!eventIds.includes(id))fail('Unknown related event');}
 for(const p of record.procedure_checks){if(!record.selected_outcome_ids.includes(p.outcome_id))fail('Unselected procedure outcome');evidenceCheck(p.evidence_refs);}
 for(const r of record.service_requests){if(!eventIds.includes(r.event_id))fail('Unknown service event');if(r.recipient_id!==null&&!partyIds.includes(r.recipient_id))fail('Unknown service recipient');}
 for(const r of record.service_responses)if(r.status==='calculated'&&!['sent','acknowledged'].includes(record.service_requests.find(x=>x.request_id===r.request_id).status))fail('Unsent request cannot have confirmed calculation');
 for(const [id,a]of Object.entries(raw))if(a.external_response_ref){const response=record.service_responses.find(s=>s.response_id===a.external_response_ref);if(!response)fail('Unknown external response');if(elements.get(id).assessment.mode==='external_service'&&record.service_requests.find(r=>r.request_id===response.request_id).service!=='deadline')fail('Wrong external service');}
 for(const id of Object.keys(record.remedy_details))if(!record.selected_outcome_ids.includes(id))fail('Unselected remedy details');
 const stageIds=record.stage_records.map(s=>s.stage_id);if(unique(stageIds).length!==stageIds.length||stageIds.some(id=>!core.stages.some(s=>s.id===id)))fail('Invalid stage coverage');
 function normalize(a){
  if(!a)return {status:'unknown',assumed:false,stale:false,fact_refs:[],evidence_refs:[]};
  const stale=a.fact_refs.some(r=>r.revision!==facts[r.id].revision),ss=a.fact_refs.map(r=>facts[r.id].status);
  let status=a.status;if(stale)status='unknown';else if(definitive(status)&&ss.includes('disputed'))status='disputed';else if(definitive(status)&&ss.includes('unknown'))status='unknown';
  return {...a,status,stale,assumed:a.epistemic_basis==='assumed_for_orientation'||ss.includes('asserted')};
 }
 const contexts=Object.fromEntries([...allContext].map(k=>[k,normalize(context[k])]));
 function applicability(deps){const checks=deps.map(k=>contexts[k]);return checks.some(c=>c.status==='not_satisfied'&&!c.assumed)?'excluded':checks.every(c=>c.status==='satisfied'&&!c.assumed)?'applicable':'conditional';}
 const memo=new Map(),visiting=new Set();
 function node(id){if(memo.has(id))return memo.get(id);if(visiting.has(id))fail('Cyclic derived rule');visiting.add(id);const e=elements.get(id);if(!e)fail('Unknown element '+id);let r;
  if(e.assessment.mode==='derived'){const x=evaluateExpression(e.assessment.expression,k=>node(k).status),sub=x.leaves.map(node);r={status:x.status,assumed:sub.some(t=>t.assumed),stale:sub.some(t=>t.stale),fact_refs:sub.flatMap(t=>t.fact_refs),evidence_refs:unique(sub.flatMap(t=>t.evidence_refs)),leaf_ids:unique(sub.flatMap(t=>t.leaf_ids)),reasoning:'Abgeleitet aus expliziten Untermerkmalen.'};}
  else r={...normalize(raw[id]),leaf_ids:[id]};
  const b=boundElements.get(id);r={...r,id,applicability:applicability(b.context_dependencies),context_dependencies:b.context_dependencies,legal_basis:e.legal_basis,source_refs:e.source_refs};visiting.delete(id);memo.set(id,r);return r;
 }
 const stages=core.stages.map(s=>{const r=record.stage_records.find(x=>x.stage_id===s.id);return r||{stage_id:s.id,status:'partial',reason:'Noch nicht dokumentiert.'};});
 const workflowDocumented=stages.every(s=>s.status!=='partial');
 const detailFields=core.result_contract.per_remedy;
 function details(id){const supplied=record.remedy_details[id]||{},r={};for(const k of detailFields){const d=supplied[k]||{status:'unknown',value:null,evidence_refs:[]};evidenceCheck(d.evidence_refs);if(d.status==='verified'&&(!d.evidence_refs.length||d.value===null))fail('Verified detail requires evidence and value');if(['entitled_party','obligated_party'].includes(k)&&d.value!==null&&!partyIds.includes(d.value))fail('Unknown party in remedy detail');if(['starts_at','ends_at'].includes(k)&&d.status==='verified'&&!d.evidence_refs.some(e=>['document','service_response'].includes(evidence[e].kind)))fail('Date needs document or external service evidence');r[k]=d;}return r;}
 const results=[];
 for(const id of record.selected_outcome_ids){const o=outcomes.get(id);if(!o)fail('Unknown selected outcome '+id);const b=boundOutcomes.get(id),exp=evaluateExpression(o.when,k=>node(k).status),leaves=unique(exp.leaves.flatMap(k=>node(k).leaf_ids)),items=leaves.map(node),app=applicability(b.context_dependencies),assumed=items.some(t=>t.assumed);
  let status=app==='excluded'?'not_applicable':app==='conditional'?'conditional_applicability':!definitive(exp.status)?'unresolved':assumed?'conditional_facts':exp.status==='satisfied'?'rule_conditions_supported':'rule_conditions_not_supported';
  const open=items.filter(t=>!definitive(t.status)).map(t=>t.id),dt=details(id),openDetails=detailFields.filter(k=>dt[k].status!=='verified');
  results.push({id,status,expression_status:exp.status,applicability:app,rule_effect:status==='rule_conditions_supported'?o.legal_effect:null,hypothetical_effect:app!=='excluded'&&exp.status==='satisfied'&&['conditional_applicability','conditional_facts'].includes(status)?{text:o.legal_effect,context_requirements:b.context_dependencies.filter(k=>contexts[k].status!=='satisfied'||contexts[k].assumed),assumed_element_ids:items.filter(x=>x.assumed).map(x=>x.id)}:null,legal_basis:o.legal_basis,qualification:o.qualification,element_refs:leaves,open_elements:open,structured_details:dt,open_detail_fields:openDetails,case_conclusion_complete:status==='rule_conditions_supported'&&openDetails.length===0&&workflowDocumented,source_refs:unique(items.flatMap(x=>x.source_refs))});
 }
 for(const id of record.review_element_ids||[])node(id);
 const questions=[...memo.values()].filter(x=>!definitive(x.status)&&elements.get(x.id).assessment.mode!=='derived').map(x=>({kind:'element',id:x.id,status:x.status,question:elements.get(x.id).assessment.question,affected_outcomes:results.filter(r=>r.element_refs.includes(x.id)).map(r=>r.id)}));
 for(const [id,c]of Object.entries(contexts))if(!definitive(c.status)||c.assumed)questions.push({kind:'context',id,status:c.status,question:'Anwendbarkeit für '+id+' klären und belegen.',affected_outcomes:results.filter(r=>boundOutcomes.get(r.id).context_dependencies.includes(id)).map(r=>r.id)});
 return {case_id:record.case_id,case_revision:record.case_revision,core_id:core.core_id,core_version:core.version,module_id:module.module_id,module_version:module.version,binding_id:binding.binding_id,workflow_status:stages.every(s=>s.status!=='partial')?'documented':'partial',stage_records:stages,factual_findings:Object.entries(facts).map(([id,f])=>({id,...f})),element_results:[...memo.values()].map(r=>({id:r.id,status:r.status,applicability:r.applicability,assumed:r.assumed,stale:r.stale,reasoning:r.reasoning||'Keine Bewertung vorhanden.',fact_refs:r.fact_refs,evidence_refs:r.evidence_refs,legal_basis:r.legal_basis,source_refs:r.source_refs})),outcome_results:results,open_questions:questions,next_questions:questions.map(q=>({kind:q.kind,id:q.id,question:q.question,affected_outcomes:q.affected_outcomes})),service_request_refs:requestIds,service_response_refs:responseIds};
}
