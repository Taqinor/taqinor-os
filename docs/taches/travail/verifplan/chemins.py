import re, os, sys, collections
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))
plan = open(os.path.join(ROOT, 'docs/plans/PLAN_TACHES.md'), encoding='utf-8').read().splitlines()
tasks = {}
for l in plan:
    m = re.match(r'- \[ \] (TCH\d+) — (.*)', l)
    if not m: continue
    tid, body = m.groups()
    files = []
    fm = re.search(r'Files: (.*)$', body)
    if fm: files = re.findall(r'`([^`]+)`', fm.group(1))
    after = re.findall(r'\(@after: ([^)]*)\)', body)
    after = [a.strip() for a in after[0].split(',')] if after else []
    lane = re.search(r'\(@lane: ([^)]*)\)', body)
    maq = re.findall(r'docs/taches/maquettes/[\w\-\.]+', body)
    tasks[tid] = dict(files=files, after=after, lane=lane.group(1) if lane else None, maq=maq, gated='[GATED' in body, body=body)
print('tasks', len(tasks))
order = list(tasks)
# lanes
lanes = collections.OrderedDict()
for t in order: lanes.setdefault(tasks[t]['lane'], []).append(t)
for k,v in lanes.items(): print('LANE', k, v)
# creators: first task in plan order mentioning file and file doesn't exist
existing = {}
writers = collections.defaultdict(list)
for t in order:
    for f in tasks[t]['files']:
        writers[f].append(t)
print('\n== Files existing in repo (should be foreign or modified) ==')
for f, ts in writers.items():
    p = os.path.join(ROOT, f)
    if os.path.exists(p):
        print('EXISTS', f, ts)
print('\n== Foreign-looking files that DO NOT exist ==')
for f, ts in writers.items():
    p = os.path.join(ROOT, f)
    own = f.startswith(('backend/django_core/apps/taches/','frontend/src/features/taches/','frontend/src/pages/taches/','frontend/src/api/tachesApi','frontend/src/styles/taches/','frontend/e2e/taches-','docs/taches/','docs/claude-memory/taches'))
    if not own and not os.path.exists(p):
        print('MISSING', f, ts)
print('\n== Files written by >1 task (lanes) ==')
for f, ts in writers.items():
    if len(ts)>1:
        ls = sorted(set(tasks[t]['lane'] for t in ts))
        print(f, ts, ls if len(ls)>1 else '')
print('\n== maquettes ==')
for t in order:
    for m in tasks[t]['maq']:
        if not os.path.exists(os.path.join(ROOT, m)): print('MAQ MISSING', t, m)
print('\n== @after referencing later/unknown ==')
idx = {t:i for i,t in enumerate(order)}
for t in order:
    for a in tasks[t]['after']:
        if a not in tasks: print('UNKNOWN', t, a)
import json
json.dump(tasks, open(os.path.join(os.path.dirname(__file__),'tasks.json'),'w',encoding='utf-8'), ensure_ascii=False, indent=0)
