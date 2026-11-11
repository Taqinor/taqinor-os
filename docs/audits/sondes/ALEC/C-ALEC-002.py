"""Rejoue stock/views/kit.py::KitProduitViewSet.structure : la VRAIE get_permissions (LectureDuModule) puis la VRAIE action, dont le masque coût/marge ne s'appuie que sur IsResponsableOrAdmin, pas sur prix_achat_voir / marge_voir."""
SONDE = {"constat": "C-ALEC-002", "sha": "ae5a7ae4c",
         "attendu": "des rôles livrés sans prix_achat_voir ni marge_voir lisent la structure d'un kit AVEC cout_total_roll_up, marge et cout_unitaire/cout_total par composant"}
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


CHEMIN = "apps/stock/views/kit.py"


def sonde(ctx=None):
    R, P, comptes = noyau()
    v = vue(CHEMIN)
    lisent = passent(comptes, gardes(P, CHEMIN, "KitProduitViewSet", "structure"), v)
    donnees = lambda: {"composants": [{"cout_unitaire": "900", "cout_total": "900"}], "cout_total_roll_up": 900, "marge": 100}
    ns = {"structure_kit": lambda kit: donnees(), "KitCycleError": ValueError, "Response": lambda d, **k: d, "status": NS(HTTP_400_BAD_REQUEST=400),
          "IsResponsableOrAdmin": P["IsResponsableOrAdmin"]}
    structure = reel(CHEMIN, "structure", "KitProduitViewSet", ns)
    v.get_object = lambda: object()
    voient = {}
    for nom in lisent:
        r = structure(v, NS(user=comptes[nom], method="GET"))
        voient[nom] = sorted(k for k in ("cout_total_roll_up", "marge") if k in r) + sorted(k for k in r["composants"][0] if k.startswith("cout"))
    fuient = [n for n in lisent if voient[n] and (set(comptes[n].role.permissions) & {"prix_achat_voir", "marge_voir"}) != {"prix_achat_voir", "marge_voir"}]
    produit = ast.unparse(noeud("apps/stock/services.py", "structure_kit"))  # la donnée servie contient bien coûts et marge
    return {"repro": bool(fuient) and "cout_total_roll_up" in produit and "'marge'" in produit, "observe": {
        "methode": "VRAIE get_permissions + VRAIE action structure exécutées ; structure_kit bouchonné (clés vérifiées par ast)",
        "route": "GET stock/kits/<id>/structure/", "garde": [type(g).__name__ for g in gardes(P, CHEMIN, "KitProduitViewSet", "structure")],
        "code_attendu": "prix_achat_voir (coûts) + marge_voir (marge)", "roles_livres_qui_lisent": lisent,
        "roles_livres_qui_voient_cout_ou_marge_sans_le_code": fuient, "cles_vues": {n: voient[n] for n in fuient}}}


if __name__ == "__main__":
    import json
    print(json.dumps(sonde(), ensure_ascii=False, indent=1, default=str))
