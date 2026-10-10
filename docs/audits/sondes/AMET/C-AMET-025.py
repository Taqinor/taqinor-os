"""Sonde statique de la session audit-méthode du 09/10/2026 : résout des ancres fichier::symbole, ne touche pas la base.
Entrées : ctx['args'] = [table JSON du parcours, ids d'étapes séparés par des virgules] ; sans elles → STATIQUE."""
SONDE = {
    'constat': 'C-AMET-025',
    'sha': 'f3716e3f0',
    'attendu': 'résolution des 52 ancres fichier::symbole de la table PA4 (mesure parcours)',
}


def sonde(ctx):
    import ast
    import json
    import pathlib
    import re
    args = ctx.get('args')
    if not args:
        return ('STATIQUE : entrées absentes (table du parcours) ; rejouer en local avec '
                'ctx["args"] = [table.json, "E1,E2,…"]')
    table = json.load(open(args[0], encoding='utf-8'))
    sample = set(args[1].split(','))
    motif = r'((?:backend|frontend|scripts|apps)/[\w/\[\].-]+\.(?:py|jsx?|ts|astro))::([\w.]+)'

    def anchors_in(o, acc):
        if isinstance(o, dict):
            for v in o.values():
                anchors_in(v, acc)
        elif isinstance(o, list):
            for v in o:
                anchors_in(v, acc)
        elif isinstance(o, str):
            for m in re.finditer(motif, o):
                acc.add((m.group(1), m.group(2)))

    def resolve_py(path, sym):
        node = ast.parse(pathlib.Path(path).read_text(encoding='utf-8'))
        for seg in sym.split('.'):
            found = None
            for ch in ast.iter_child_nodes(node):
                if isinstance(ch, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)) and ch.name == seg:
                    found = ch
                    break
                if isinstance(ch, (ast.Assign, ast.AnnAssign)):
                    tg = ch.targets if isinstance(ch, ast.Assign) else [ch.target]
                    if any(isinstance(t, ast.Name) and t.id == seg for t in tg):
                        found = ch
                        break
            if found is None:
                return False, None
            node = found
        return True, getattr(node, 'lineno', None)

    ko = 0
    for e in table['etapes']:
        if e['id'] not in sample:
            continue
        acc = set()
        for k in ('declencheur', 'fonction_entree', 'checkpoint', 'regle_aval', 'compensation', 'portes'):
            anchors_in(e.get(k), acc)
        for path, sym in sorted(acc):
            if path.endswith('.py'):
                ok, ln = resolve_py(path, sym)
            else:
                src = pathlib.Path(path).read_text(encoding='utf-8')
                ok, ln = re.search(r'\b%s\b' % re.escape(sym.split('.')[-1]), src) is not None, None
            ko += 0 if ok else 1
            print(e['id'], 'OK' if ok else 'KO', '%s::%s' % (path, sym), ln)
    return {'repro': True, 'ancres_ko': ko}
