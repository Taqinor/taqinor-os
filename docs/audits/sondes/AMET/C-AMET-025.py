# SONDE = {'constat': 'C-AMET-025', 'sha': 'f3716e3f0', 'attendu': "résolution des 52 ancres fichier::symbole de la table PA4 (mesure parcours)"}
# Sonde de la session audit-méthode du 09/10/2026 (R3), jouée dans le conteneur local en transaction annulée,
# backend mail en mémoire, Celery coupé. Rejouable par scripts/sonde.py (AMET93) ; jamais contre la prod.
import json, re, sys, ast, pathlib
SP = pathlib.Path(sys.argv[1]).parent
table = json.load(open(sys.argv[1], encoding='utf-8'))
sample = set(sys.argv[2].split(','))
def anchors_in(o, acc):
    if isinstance(o, dict):
        for v in o.values(): anchors_in(v, acc)
    elif isinstance(o, list):
        for v in o: anchors_in(v, acc)
    elif isinstance(o, str):
        for m in re.finditer(r'((?:backend|frontend|scripts|apps)/[\w/\[\].-]+\.(?:py|jsx?|ts|astro))::([\w.]+)', o):
            acc.add((m.group(1), m.group(2)))
def resolve_py(path, sym):
    tree = ast.parse(pathlib.Path(path).read_text(encoding='utf-8'))
    node = tree
    for seg in sym.split('.'):
        found = None
        for ch in ast.iter_child_nodes(node):
            if isinstance(ch, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)) and ch.name == seg:
                found = ch; break
            if isinstance(ch, (ast.Assign, ast.AnnAssign)):
                tg = ch.targets if isinstance(ch, ast.Assign) else [ch.target]
                for t in tg:
                    if isinstance(t, ast.Name) and t.id == seg: found = ch
                if found: break
        if found is None: return False, None
        node = found
    return True, getattr(node, 'lineno', None)
for e in table['etapes']:
    if e['id'] not in sample: continue
    acc = set()
    for k in ('declencheur', 'fonction_entree', 'checkpoint', 'regle_aval', 'compensation', 'portes'):
        anchors_in(e.get(k), acc)
    for path, sym in sorted(acc):
        if path.endswith('.py'):
            ok, ln = resolve_py(path, sym)
            print(e['id'], 'SCOPED-OK' if ok else 'SCOPED-KO', f'{path}::{sym}', ln)
        else:
            src = pathlib.Path(path).read_text(encoding='utf-8')
            ok = re.search(r'\b%s\b' % re.escape(sym.split('.')[-1]), src) is not None
            print(e['id'], 'JS-OK' if ok else 'JS-KO', f'{path}::{sym}')
