import json, collections
T = json.load(open('docs/taches/travail/verifsq/tasks.json',encoding='utf-8'))
n = lambda t: int(t[3:])
fo = {'F1':1,'F2':2,'F3':3}
print('== @after ordre/fusion')
for t in T.values():
    for a in t['after']:
        if a not in T: print('INCONNU', t['id'], a); continue
        if n(a) >= n(t['id']): print('APRES', t['id'], '->', a)
        if fo[T[a]['fusion']] > fo[t['fusion']]: print('FUSION ULTERIEURE', t['id'], a)
# cycles
import sys
sys.setrecursionlimit(10000)
state={}
def dfs(u,path):
    state[u]=1
    for v in T[u]['after']:
        if v not in T: continue
        if state.get(v)==1: print('CYCLE', path+[v])
        elif not state.get(v): dfs(v,path+[v])
    state[u]=2
for u in T:
    if not state.get(u): dfs(u,[u])
print('== fichiers partagés entre lanes, même fusion')
APPEND = ['module.config.jsx','contractSamples.js','check_api_shapes.py','index.css','tokens.css','ownership.yml']
for f in ['F1','F2','F3']:
    by = collections.defaultdict(set)
    for t in T.values():
        if t['fusion']!=f or t['acc']: continue
        for p in t['files']: by[p].add(t['lane'])
    for p,ls in sorted(by.items()):
        if len(ls)>1: print(f, p, sorted(ls))
print('== fichiers écrits par plusieurs lanes au fil des fusions (non append)')
by = collections.defaultdict(set)
for t in T.values():
    for p in t['files']: by[p].add((t['fusion'],t['lane'],t['id']))
for p,s in sorted(by.items()):
    lanes = {x[1] for x in s}
    if len(lanes)>1 and not any(a in p for a in APPEND):
        print(p, sorted(s))
