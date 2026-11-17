import json, os, re
H = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(H, '..', '..', '..', '..'))
tasks = json.load(open(os.path.join(H, 'tasks.json'), encoding='utf-8'))
plan = open(os.path.join(ROOT, 'docs/plans/PLAN_TACHES.md'), encoding='utf-8').read()
head = plan.split('**Qui construit ce plan.**')[0]
# expand {a,b} in header
def expand(s):
    m = re.search(r'\{([^}]*)\}', s)
    if not m: return [s]
    out=[]
    for part in m.group(1).split(','):
        out += expand(s[:m.start()] + part.strip() + s[m.end():])
    return out
cited=set()
for tok in re.findall(r'`([^`]+)`', head.replace('\n>', '').replace('\n', '')):
    for e in expand(tok.replace(' ', '')):
        cited.add(e)
own = ('backend/django_core/apps/taches/','frontend/src/features/taches/','frontend/src/pages/taches/','frontend/src/api/tachesApi','frontend/src/styles/taches/','frontend/e2e/taches-','docs/taches/','docs/claude-memory/taches', 'frontend/e2e/acceptation/tch')
for t, d in tasks.items():
    for f in d['files']:
        if f.startswith(own) or f.startswith('docs/plans/PLAN_TACHES'): continue
        if f not in cited and not any(c.endswith('*') and f.startswith(c[:-1]) for c in cited):
            print(t, f)
