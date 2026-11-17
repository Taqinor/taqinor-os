import re, json, sys, collections
src = open('docs/taches/travail/essai-plan/essai-F3.md', encoding='utf-8').read().splitlines()
tasks = {}
fusion = None
for l in src:
    m = re.match(r'^## Fusion (F\d)', l)
    if m: fusion = m.group(1); continue
    m = re.match(r'^- \[[ x]\] (TCH\d+) — (.*)', l)
    if not m: continue
    tid, rest = m.groups()
    after = re.search(r'@after:\s*([^)]*)\)', rest)
    after = [a.strip() for a in after.group(1).split(',')] if after else []
    lane = re.search(r'@lane:\s*([^)]*)\)', rest); lane = lane.group(1).strip() if lane else None
    model = re.search(r'@model:\s*([^)]*)\)', rest); model = model.group(1).strip() if model else None
    files = []
    if 'Files:' in rest:
        files = re.findall(r'`([^`]+)`', rest.rsplit('Files:',1)[1])
    acc = '@acceptation' in rest
    tasks[tid] = dict(id=tid, fusion=fusion, after=after, lane=lane, model=model, files=files, acc=acc, text=rest)
json.dump(tasks, open('docs/taches/travail/verifsq/tasks.json','w',encoding='utf-8'), ensure_ascii=False, indent=0)
print(len(tasks), collections.Counter(t['fusion'] for t in tasks.values()))
