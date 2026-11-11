"""Rejoue stock/views/fournisseur.py::FournisseurViewSet.portail_tokens : VRAIE get_permissions (stock_modifier) puis VRAIE action GET, avec le sérialiseur simulé sur ses Meta.fields réels (lus par ast) ; la route publique qui accepte ce jeton est lue par ast (AllowAny, jeton seul)."""
SONDE = {"constat": "C-ALEC-010", "sha": "ae5a7ae4c",
         "attendu": "le GET rend le champ token en clair à des rôles livrés sans prix_achat_voir ; ce jeton ouvre sans authentification la route publique des documents fournisseur (factures, solde)"}
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
    fou = "apps/stock/views/fournisseur.py"; pub = "apps/stock/public_views.py"
    g = gardes(P, fou, "FournisseurViewSet", "portail_tokens")
    lisent = passent(comptes, g, vue(fou), "GET")
    champs = ast.literal_eval(next(b for b in noeud("apps/stock/serializers.py", "Meta", "PortailFournisseurTokenSerializer").body if getattr(b.targets[0], "id", "") == "fields").value)
    jeton = NS(id=1, fournisseur=2, token="JETON-PORTAIL-FOURNISSEUR", expires_at=None, revoked=False, est_valide=True, created_at=None, last_used_at=None)
    serialiseur = lambda objets, many=False: NS(data=[{c: getattr(o, c, None) for c in champs} for o in objets])  # DRF : ce que Meta.fields déclare est servi
    v = vue(fou); v.get_object = lambda: NS(portail_tokens=NS(order_by=lambda c: [jeton]))
    rendu = reel(fou, "portail_tokens", "FournisseurViewSet", {"PortailFournisseurTokenSerializer": serialiseur, "Response": lambda d, **k: d})(v, NS(method="GET", user=None))
    fuient = [n for n in lisent if "prix_achat_voir" not in comptes[n].role.permissions]
    deco = [ast.unparse(d) for d in noeud(pub, "portail_fournisseur_documents_view").decorator_list]
    donnees = ast.unparse(noeud("apps/stock/services.py", "portail_fournisseur_documents"))
    public = "permission_classes([AllowAny])" in deco and "authentication_classes([])" in deco and "'factures'" in donnees
    return {"repro": bool(fuient) and bool(rendu) and rendu[0].get("token") == "JETON-PORTAIL-FOURNISSEUR" and public, "observe": {
        "methode": "VRAIE get_permissions + VRAIE action portail_tokens exécutées (sérialiseur simulé sur Meta.fields réel) ; route publique lue par ast",
        "route": "GET stock/fournisseurs/<id>/portail-tokens/", "garde": [type(x).__name__ for x in g], "champs_servis": champs, "token_en_clair": rendu[0].get("token"),
        "route_publique": {"fonction": "portail_fournisseur_documents_view", "decorateurs": [d for d in deco if d.startswith(("permission_classes", "authentication_classes"))], "renvoie_les_factures": "'factures'" in donnees},
        "code_attendu": "prix_achat_voir", "roles_livres_sans_le_code_qui_lisent": fuient}}


if __name__ == "__main__":
    import json
    print(json.dumps(sonde(), ensure_ascii=False, indent=1, default=str))
