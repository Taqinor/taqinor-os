"""Rejoue les deux emplacements d'installations/views/kitting.py::OrdreAssemblageViewSet : (1) cout_soustraitance (VRAIE get_permissions puis VRAIE action) ; (2) depuis_devis, dont le sérialiseur est construit sans context (ast) : le VRAI MasqueMontantsAchatMixin ne masque alors pas cout_prevu (même cause qu'ADRG100)."""
SONDE = {"constat": "C-ALEC-008", "sha": "ae5a7ae4c",
         "attendu": "cout_soustraitance rend cout_composite à des rôles livrés sans prix_achat_voir ; depuis_devis rend cout_prevu (somme des prix d'achat) faute de context"}
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
    kit = "apps/installations/views/kitting.py"
    # Emplacement 1 : cout_soustraitance
    g1 = gardes(P, kit, "OrdreAssemblageViewSet", "cout_soustraitance")
    r1 = passent(comptes, g1, vue(kit), "GET")
    ns = {"cout_composite_soustraite": lambda ordre: __import__("decimal").Decimal("5400.00"), "Response": lambda d, **k: d, "status": NS(HTTP_404_NOT_FOUND=404)}
    v = vue(kit); v.get_object = lambda: NS(id=4)
    rendu = reel(kit, "cout_soustraitance", "OrdreAssemblageViewSet", ns)(v, NS(user=None), pk=4)
    fuient1 = [n for n in r1 if "prix_achat_voir" not in comptes[n].role.permissions]
    # Emplacement 2 : depuis_devis — sérialiseur instancié sans context
    g2 = gardes(P, kit, "OrdreAssemblageViewSet", "depuis_devis")
    r2 = passent(comptes, g2, vue(kit), "POST")
    appels = [c for c in ast.walk(noeud(kit, "depuis_devis", "OrdreAssemblageViewSet")) if isinstance(c, ast.Call) and getattr(c.func, "id", "") == "OrdreAssemblageSerializer"]
    sans_contexte = bool(appels) and all(not any(k.arg == "context" for k in c.keywords) for c in appels)
    ns2 = {"BasePermission": P["BasePermission"]}
    reel("apps/stock/permissions.py", "PeutVoirPrixAchat", None, ns2)
    Mixin = reel("apps/stock/permissions.py", "MasqueMontantsAchatMixin", None, ns2)
    masque_bloc = reel("apps/installations/serializers_blocs.py", "MasqueCoutPrevu", None, {"MasqueMontantsAchatMixin": Mixin})

    class Base:
        context = {}  # un sérialiseur instancié sans context= n'a aucune requête (DRF : context vide)
        def to_representation(self, instance): return {"id": 1, "cout_prevu": "5400.00"}

    class Sortie(masque_bloc, Base): pass
    sortie = Sortie().to_representation(None)
    fuient2 = [n for n in r2 if "prix_achat_voir" not in comptes[n].role.permissions]
    return {"repro": bool(fuient1 and "cout_composite" in rendu) or bool(fuient2 and sans_contexte and "cout_prevu" in sortie), "observe": {
        "methode": "VRAIES get_permissions, action cout_soustraitance et mixin de masque exécutés ; appel du sérialiseur dans depuis_devis lu par ast",
        "emplacements_controles": 2,
        "cout_soustraitance": {"route": "GET installations/ordres-assemblage/<id>/cout-soustraitance/", "garde": [type(x).__name__ for x in g1], "reponse": rendu, "roles_livres_sans_le_code_qui_lisent": fuient1},
        "depuis_devis": {"route": "POST installations/ordres-assemblage/depuis-devis/", "garde": [type(x).__name__ for x in g2], "serializer_sans_context": sans_contexte, "champ_rendu": sortie, "roles_livres_sans_le_code_qui_lisent": fuient2},
        "code_attendu": "prix_achat_voir"}}


if __name__ == "__main__":
    import json
    print(json.dumps(sonde(), ensure_ascii=False, indent=1, default=str))
