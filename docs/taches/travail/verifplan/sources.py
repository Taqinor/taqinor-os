import json, os, re, collections
H = os.path.dirname(os.path.abspath(__file__))
tasks = json.load(open(os.path.join(H, 'tasks.json'), encoding='utf-8'))
pat = re.compile(r'\b(spec-\d[ab]?|s[1-6][ab]?\b|socle|A\d{1,2}(?:-[A-Z]+\d+)?|MAJ-\d+|verif-[\w-]+|design-s\d|R\d{1,2}\b|C\d{1,2}\b|I\d{1,2}\b|T\d{1,2}\b|min-\d+|IT\d+|CALX\d+|PACT\d+|module-playbook)')
cnt = collections.Counter(); per = {}
for t, d in tasks.items():
    m = re.search(r'Source : (.*?)(?:\. Nouveau fichier|\. \(|\. Contrat|\. Code net|\. Réservation|\. Et l|\. Geste|$)', d['body'])
    src = m.group(1) if m else ''
    hits = sorted(set(pat.findall(src + ' ' + d['body'])))
    per[t] = hits
    for h in hits: cnt[re.sub(r'\d.*','',h) if h.startswith(('A','R','C','I','T')) and len(h)<6 else h.split(' ')[0]] += 1
n_ext = sum(1 for t,h in per.items() if h)
print('tasks citing travail/ material:', n_ext, 'of', len(tasks))
print(cnt.most_common(40))
for t in ['TCH110','TCH114','TCH116','TCH46','TCH41','TCH55','TCH71','TCH133','TCH134','TCH90']:
    print(t, per[t])
