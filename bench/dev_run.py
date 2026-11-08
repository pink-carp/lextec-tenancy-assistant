"""Developer run: one case through the full pipeline, with a readable summary."""
import json, sys, time
from datetime import date
sys.path.insert(0, '.')
from app import pipeline as P

cases = json.load(open('bench/cases.json'))
c = cases[int(sys.argv[1]) - 1]
t = time.time()
case = P.new_case(c['prompt'], today=date(2026, 11, 8))
for step in (P.understand, P.gather_sources, P.questions, P.assess, P.score, P.write, P.verify):
    t1 = time.time(); step(case); print(f"{step.__name__}: {time.time()-t1:.1f}s")
print('TOTAL %.1fs' % (time.time() - t), 'cost $%.4f' % sum(x['cost_usd'] for x in case['trace']))
u = case['understanding']
print('ISSUES', [(i['issue'][:60], i['articles']) for i in u['issues']])
print('EXPANDED', list(case['articles_expanded']))
print('SIGNALS', [(s['index'], s['kind'], s['tense'], s['description'][:50]) for s in case['signals']])
print('VULN', u['vulnerability'], 'topics', u['topics'])
print('Qs'); [print(' ', q['id'], q['priority'], q['input_type'], q['question'][:110], q['legal_basis']) for q in case['questions']]
print('DEADLINES'); [print(' ', d['id'], d['action'][:60], d['earliest'], d['precautionary'], d['legal_basis'], d['steps'][-1][:110]) for d in case['deadlines']]
print('RUBRIC', {k: v['level'] for k, v in case['rubric'].items()})
print('INDICES', case['indices'], 'LANE', case['lane'], case['lane_rule'], '| expected', c['expected_lane'])
print('CONTACTS', [x['id'] for x in case['contacts']])
s = case['screen']
for a in s['actions']: print(' A', a['group'], a['who'], a['what'][:120], '|', a['when'][:60])
for i in s['issues']:
    print(' ISSUE', i['issue'][:80])
    for r in i['rules']: print('   R', r.get('check'), r['statement'][:120], r['sources'])
print('REMOVED', json.dumps(case['verification']['removed'], ensure_ascii=False)[:1500])
json.dump(P.to_jsonable(case), open(f'bench/results/dev_case{c["case_no"]}.json', 'w'), ensure_ascii=False, indent=1)
