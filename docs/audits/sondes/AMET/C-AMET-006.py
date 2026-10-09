# SONDE = {'constat': 'C-AMET-006', 'sha': 'f3716e3f0', 'attendu': "la garde beat accepte tout mot-clé company… : relance_reminders passe"}
# Sonde de la session audit-méthode du 09/10/2026 (R3), jouée dans le conteneur local en transaction annulée,
# backend mail en mémoire, Celery coupé. Rejouable par scripts/sonde.py (AMET93) ; jamais contre la prod.
import ast, sys, importlib.util, pathlib
D = pathlib.Path(sys.argv[1])
spec = importlib.util.spec_from_file_location('cbac', D / 'cbac_S.py'); m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
src = (D / 'scheduled_S.py').read_text(encoding='utf-8')
tree = ast.parse(src)
fns = {n.name: n for n in ast.walk(tree) if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))}
modeles = m.modeles_a_company(pathlib.Path(sys.argv[2]))
print('models with company FK found:', len(modeles), 'Facture' in modeles, 'RelanceLog' in modeles, 'PromessePaiement' in modeles)
flagged = {f for f, _, _ in m.check_balayage_global(D / 'scheduled_S.py', modeles)}
print('flagged by check_balayage_global in scheduled.py:', sorted(flagged))
for name in ['check_overdue_factures', '_check_promesses_expirees', 'relance_reminders', 'pre_echeance_reminders', 'releve_mensuel_reminders']:
    f = fns[name]
    scoped = m._fonction_filtre_societe(f)
    # which call made it "scoped"
    why = []
    for n in ast.walk(f):
        if isinstance(n, ast.Call):
            nom = m._callee_name(n) or ''
            kws = [k.arg for k in n.keywords if (k.arg or '').startswith('company')]
            if nom.split('.')[-1] in m._SELECTEURS_SOCIETE or kws:
                why.append(f"L{n.lineno} {nom}({','.join(kws)})")
    # first unscoped-looking global query (model query without company kw)
    first_q = []
    for n in ast.walk(f):
        if isinstance(n, ast.Call):
            nom = m._callee_name(n) or ''
            seg = nom.split('.')
            if len(seg) >= 3 and seg[-2] == 'objects' and seg[-3] in modeles and seg[-1] in m._METHODES_REQUETE:
                kws = [k.arg for k in n.keywords]
                first_q.append(f"L{n.lineno} {nom}({','.join(str(k) for k in kws)})")
    print(f"\n{name} (def L{f.lineno}) scoped_by_heuristic={scoped} flagged={name in flagged}")
    print('   scoping evidence:', why[:4])
    print('   model queries   :', first_q[:5])
