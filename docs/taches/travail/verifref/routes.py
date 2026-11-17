"""Extrait les routes de api.md (tables §3 et §7) et les compare. Jetable."""
import re, sys, pathlib
ref = pathlib.Path(__file__).resolve().parents[2] / 'reference'
api = (ref / 'api.md').read_text(encoding='utf-8')
lines = api.splitlines()
# §3 table rows
sec3 = []
in3 = False
for l in lines:
    if l.startswith('## 3.'): in3 = True
    elif l.startswith('## 4.'): in3 = False
    if in3 and l.startswith('| ') and '/api/django/taches' in l:
        cells = [c.strip() for c in l.strip('|').split('|')]
        meth, path = cells[0], cells[1]
        sec3.append((meth, path, cells[3] if len(cells) > 3 else ''))
def norm(p):
    p = p.strip('`').split('?')[0]
    p = p.replace('/api/django/taches/', '')
    return p
couples = set()
for meth, path, auth in sec3:
    ms = [m.strip() for m in meth.split('·')]
    raw = path.strip('`')
    # explode "a/ · …/b/" forms
    parts = [x.strip().strip('`') for x in re.split(r'`\s*·\s*`', path)]
    base = norm(parts[0])
    variants = [base]
    for x in parts[1:]:
        if x.startswith('…/'):
            stem = base.rsplit('/', 2)[0] + '/'
            variants.append(stem + x[2:])
        else:
            variants.append(norm(x))
    # [{id}/] and + POST …/{id}/reordonner/
    out = []
    for v in variants:
        if '[{id}/]' in v:
            b = v.split('[')[0]
            out += [(b, False), (b + '{id}/', True)]
        else:
            out.append((v, None))
    extra = re.findall(r'\+ `POST …/\{id\}/reordonner/`', path)
    for v, is_det in out:
        for m in ms:
            if is_det is False and m in ('PATCH', 'DELETE'):
                continue
            if is_det is True and m == 'POST':
                continue
            couples.add((m, v))
    if extra:
        b = out[0][0]
        couples.add(('POST', b + '{id}/reordonner/'))
print('couples methode x chemin (§3):', len(couples))
for c in sorted(couples, key=lambda x: (x[1], x[0])):
    print('  ', c[0], c[1])
# §7 actions
sec7 = re.findall(r'\| `(taches\.[a-z_.]+)` [✎⟲]? ?\| (GET|POST|PATCH|DELETE|PUT) `([^`]+)`', api)
print('\nactions §7:', len(sec7))
bad = []
for key, m, p in sec7:
    p2 = norm(p).split(' ')[0]
    if (m, p2) not in couples:
        bad.append((key, m, p2))
print('actions absentes de §3 :', bad or 'aucune')
# routes cited anywhere in prose of api.md vs table
cited = set(re.findall(r'`((?:GET|POST|PATCH|DELETE|PUT) )?(?:/api/django/taches/)?([a-z0-9\-_{}]+/(?:[a-z0-9\-_{}]+/)*)`', api))
paths3 = {c[1] for c in couples}
miss = sorted({p for _, p in cited if p not in paths3 and not p.startswith(('records','auth','api','frontend','apps','core','notifications'))})
print('\nchemins cités en prose absents de §3 :', miss)
