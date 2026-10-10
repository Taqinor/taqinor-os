"""Sonde statique (AST) de la session audit-méthode du 09/10/2026 : lit des sources, ne touche pas la base.
Entrées : ctx['args'] = [dossier contenant cbac_S.py et scheduled_S.py, dossier des modèles] ; sans elles → STATIQUE."""
SONDE = {
    'constat': 'C-AMET-006',
    'sha': 'f3716e3f0',
    'attendu': 'la garde beat accepte tout mot-clé company… : relance_reminders passe',
}


def sonde(ctx):
    import ast
    import importlib.util
    import pathlib
    args = ctx.get('args')
    if not args:
        return ('STATIQUE : entrées absentes (cbac_S.py, scheduled_S.py) ; rejouer en local avec '
                'ctx["args"] = [dossier, modèles]')
    D = pathlib.Path(args[0])
    spec = importlib.util.spec_from_file_location('cbac', D / 'cbac_S.py')
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    src = (D / 'scheduled_S.py').read_text(encoding='utf-8')
    tree = ast.parse(src)
    fns = {n.name: n for n in ast.walk(tree) if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))}
    modeles = m.modeles_a_company(pathlib.Path(args[1]))
    print('models with company FK found:', len(modeles), 'Facture' in modeles, 'RelanceLog' in modeles,
          'PromessePaiement' in modeles)
    flagged = {f for f, _, _ in m.check_balayage_global(D / 'scheduled_S.py', modeles)}
    print('flagged by check_balayage_global in scheduled.py:', sorted(flagged))
    for name in ['check_overdue_factures', '_check_promesses_expirees', 'relance_reminders',
                 'pre_echeance_reminders', 'releve_mensuel_reminders']:
        f = fns[name]
        scoped = m._fonction_filtre_societe(f)
        why = []
        first_q = []
        for n in ast.walk(f):
            if not isinstance(n, ast.Call):
                continue
            nom = m._callee_name(n) or ''
            kws = [k.arg for k in n.keywords if (k.arg or '').startswith('company')]
            if nom.split('.')[-1] in m._SELECTEURS_SOCIETE or kws:
                why.append('L%s %s(%s)' % (n.lineno, nom, ','.join(kws)))
            seg = nom.split('.')
            if len(seg) >= 3 and seg[-2] == 'objects' and seg[-3] in modeles and seg[-1] in m._METHODES_REQUETE:
                first_q.append('L%s %s(%s)' % (n.lineno, nom, ','.join(str(k.arg) for k in n.keywords)))
        print('\n%s (def L%s) scoped_by_heuristic=%s flagged=%s' % (name, f.lineno, scoped, name in flagged))
        print('   scoping evidence:', why[:4])
        print('   model queries   :', first_q[:5])
    return {'repro': 'relance_reminders' not in flagged}
