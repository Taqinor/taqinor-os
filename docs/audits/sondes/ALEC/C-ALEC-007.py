"""Rejoue les deux emplacements du budget d'achat de programme : installations/views/controle_budgetaire.py::ControleBudgetaireCommandeView (permission_classes lue par ast puis exécutée, VRAIE get et VRAI selectors.controle_budgetaire_commande) et program.py::BudgetProjetViewSet.synthese (VRAIE get_permissions, corps lu par ast)."""
SONDE = {"constat": "C-ALEC-007", "sha": "ae5a7ae4c",
         "attendu": "tout rôle interne obtient reste_categorie / reste_total (budget d'achat restant) ; synthese rend les enveloppes budget/engagé sans masque aux rôles livrés sans prix_achat_voir"}
import ast, pathlib, runpy, sys, types
RACINE = pathlib.Path(__file__).resolve().parents[4]
if not (RACINE / "backend/django_core").is_dir(): RACINE = pathlib.Path.cwd()  # copie hors dépôt : jouée depuis la racine
DJ = RACINE / "backend/django_core"
NS = types.SimpleNamespace


def noeud(chemin, nom, classe=None):  # nœud AST (fonction, classe, affectation) d'un fichier du dépôt
    arbre = ast.parse((DJ / chemin).read_text(encoding="utf-8"))
    corps = arbre.body if not classe else next(n for n in arbre.body if isinstance(n, ast.ClassDef) and n.name == classe).body
    return next(n for n in corps if getattr(n, "name", None) == nom or (isinstance(n, ast.Assign) and getattr(n.targets[0], "id", None) == nom))


def reel(chemin, nom, classe=None, ns=None):  # CORPS RÉEL compilé (décorateurs et imports locaux retirés : leurs noms viennent de ns)
    n = noeud(chemin, nom, classe); ns = {} if ns is None else ns; n.decorator_list = []
    class Sans(ast.NodeTransformer):  # imports (même imbriqués) remplacés par pass
        visit_Import = visit_ImportFrom = lambda s, b: ast.Pass()
    n = Sans().visit(n)
    exec(compile(ast.fix_missing_locations(ast.Module(body=[n], type_ignores=[])), chemin, "exec"), ns)
    return ns[nom]


def constantes(chemin):  # constantes littérales de module (READ_ACTIONS…)
    sortie = {}
    for n in ast.parse((DJ / chemin).read_text(encoding="utf-8")).body:
        if isinstance(n, ast.Assign) and isinstance(n.targets[0], ast.Name):
            try: sortie[n.targets[0].id] = ast.literal_eval(n.value)
            except ValueError: pass
    return sortie


def noyau():  # (R, P, comptes) : registre vivant, VRAIES gardes d'authentication/permissions.py, vrais accesseurs de CustomUser, un compte par rôle LIVRÉ interne
    R = runpy.run_path(str(DJ / "apps/roles/permissions_registre.py"))
    rp = types.ModuleType("rest_framework.permissions"); rp.SAFE_METHODS, rp.BasePermission = ("GET", "HEAD", "OPTIONS"), type("BasePermission", (), {})
    avant = {n: sys.modules.get(n) for n in ("rest_framework", "rest_framework.permissions")}
    sys.modules.update({"rest_framework": types.ModuleType("rest_framework"), "rest_framework.permissions": rp})
    try:
        P = {"__name__": "authentication.permissions"}; exec(compile((DJ / "authentication/permissions.py").read_text(encoding="utf-8"), "permissions.py", "exec"), P)
    finally:
        for n, m in avant.items(): sys.modules.pop(n, None) if m is None else sys.modules.update({n: m})
    P["enregistrer_registre_modules"](R["PERMISSION_MODULE"], octrois_lecture=R["OCTROIS_LECTURE"])
    cls = ast.parse("class U:\n    pass").body[0]
    cls.body = [n for n in noeud("authentication/models.py", "CustomUser").body if getattr(n, "name", "") in (
        "is_admin_role", "is_responsable", "_role_grants_write", "has_erp_permission", "can_view_buy_prices", "can_view_marge", "can_view_activity_log")]
    U = {}; exec(compile(ast.fix_missing_locations(ast.Module(body=[cls], type_ignores=[])), "models.py", "exec"), U); U = U["U"]; U.ROLE_ADMIN, U.ROLE_RESPONSABLE = "admin", "responsable"
    comptes = {}
    for nom, perms in R["CANONICAL_SYSTEM_ROLES"]:
        if not nom.startswith("Portail"):
            c = U(); c.__dict__.update(is_superuser=False, is_authenticated=True, portee="interne", role_legacy="normal", role_id=1, id=len(comptes) + 1, role=NS(nom=nom, permissions=list(perms)))
            comptes[nom] = c
    return R, P, comptes


def vue(chemin): return type("Vue", (), {"__module__": chemin[:-3].replace("/", ".")})()  # vue factice : seul le MODULE Python réel compte (module_de_la_vue)


def gardes(P, chemin, classe, action):  # exécute la VRAIE get_permissions de la classe pour ``action``
    return reel(chemin, "get_permissions", classe, {**P, **constantes(chemin)})(NS(action=action))


def passent(comptes, liste, v, methode="GET"):  # rôles LIVRÉS qui franchissent TOUTES les gardes (vraies classes) sur la vue v
    return sorted(n for n, c in comptes.items() if all(g.has_permission(NS(user=c, method=methode), v) for g in liste))


def sonde(ctx=None):
    R, P, comptes = noyau()
    vc = "apps/installations/views/controle_budgetaire.py"; sel = "apps/installations/selectors.py"
    noms = [ast.unparse(e) for e in noeud(vc, "permission_classes", "ControleBudgetaireCommandeView").value.elts]
    g1 = [P[n]() for n in noms]
    r1 = passent(comptes, g1, vue(vc))
    synthese = {"budget": {"materiel": 50000, "total": 50000}, "engage": {"materiel": 12000, "total": 12000}}
    ns = {"Decimal": __import__("decimal").Decimal, "BudgetProjet": NS(objects=NS(filter=lambda **k: NS(select_related=lambda *a: NS(first=lambda: object())))),
          "_dec": lambda x: __import__("decimal").Decimal(str(x)), "budget_projet_synthese": lambda b: synthese}
    reel(sel, "controle_budgetaire_commande", None, ns)
    nsv = {"selectors": NS(controle_budgetaire_commande=lambda company, montant, **k: ns["controle_budgetaire_commande"](company, montant, **k)), "Decimal": ns["Decimal"],
           "nombre_ou_400": lambda v, n, defaut=0, mini=0: float(v or defaut), "oa": NS(id_requete=lambda r, n: 7), "Response": lambda d, **k: d,
           "status": NS(HTTP_200_OK=200, HTTP_400_BAD_REQUEST=400), "CATEGORIES": ("materiel", "main_oeuvre", "sous_traitance", "divers")}
    reponse = reel(vc, "get", "ControleBudgetaireCommandeView", nsv)(NS(), NS(user=NS(company="c"), query_params={"montant": "0"}))
    fuient1 = [n for n in r1 if "prix_achat_voir" not in comptes[n].role.permissions]
    pg = "apps/installations/views/program.py"
    g2 = gardes(P, pg, "BudgetProjetViewSet", "synthese")
    r2 = passent(comptes, g2, vue(pg))
    corps = ast.unparse(noeud(pg, "synthese", "BudgetProjetViewSet"))
    masque2 = any(m in corps for m in ("can_view_buy_prices", "PeutVoirPrixAchat", "prix_achat_voir", "Masque"))
    fuient2 = [n for n in r2 if "prix_achat_voir" not in comptes[n].role.permissions]
    return {"repro": bool(fuient1 and reponse.get("reste_categorie") is not None) or bool(fuient2 and not masque2), "observe": {
        "methode": "gardes exécutées (permission_classes lue par ast pour la vue APIView, VRAIE get_permissions pour synthese) ; VRAIE get + VRAI sélecteur exécutés ; corps de synthese lu par ast",
        "emplacements_controles": 2, "controle_budgetaire": {"route": "GET installations/controle-budgetaire/?projet=&montant=0", "garde": noms, "reponse": reponse, "roles_livres_sans_le_code_qui_lisent": fuient1},
        "synthese": {"route": "GET installations/programme-budgets/<id>/synthese/", "garde": [type(x).__name__ for x in g2], "masque_dans_la_vue": masque2, "roles_livres_sans_le_code_qui_lisent": fuient2},
        "code_attendu": "prix_achat_voir"}}


if __name__ == "__main__":
    import json
    print(json.dumps(sonde(), ensure_ascii=False, indent=1, default=str))
