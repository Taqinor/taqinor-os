"""Rejoue installations/views/approbation_bcf.py::ApprobationBCFViewSet : VRAIE get_permissions de la liste (LectureDuModule du module installations), sérialiseur ApprobationBCFSerializer lu par ast (montant_approuve servi, aucun masque, aucun to_representation)."""
SONDE = {"constat": "C-ALEC-006", "sha": "ae5a7ae4c",
         "attendu": "des rôles livrés sans prix_achat_voir lisent montant_approuve (total d'achat HT du BCF) ; le même total est masqué ailleurs (MasqueMontantsAchatMixin sur le BCF)"}
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
    vues = "apps/installations/views/approbation_bcf.py"; sers = "apps/installations/serializers.py"
    g = gardes(P, vues, "ApprobationBCFViewSet", "list")
    lisent = passent(comptes, g, vue(vues))
    ser = noeud(sers, "ApprobationBCFSerializer")
    champs = ast.literal_eval(next(b for b in noeud(sers, "Meta", "ApprobationBCFSerializer").body if getattr(b.targets[0], "id", "") == "fields").value)
    bases = [ast.unparse(b) for b in ser.bases]
    masque = any("Masque" in b for b in bases) or any(getattr(b, "name", "") == "to_representation" for b in ser.body)
    montant_achat = "bcf_montant_achat" in ast.unparse(noeud(vues, "ApprobationBCFViewSet"))  # la valeur figée est le total d'ACHAT du BCF
    fuient = [n for n in lisent if "prix_achat_voir" not in comptes[n].role.permissions]
    return {"repro": bool(fuient) and "montant_approuve" in champs and not masque and montant_achat, "observe": {
        "methode": "VRAIE get_permissions exécutée ; sérialiseur lu par ast (methode ast pour la sortie)",
        "route": "GET installations/approbations-bcf/", "garde": [type(x).__name__ for x in g], "champ_servi": "montant_approuve",
        "bases_du_serializer": bases, "masque_present": masque, "valeur_figee_via_bcf_montant_achat": montant_achat, "code_attendu": "prix_achat_voir",
        "roles_livres_sans_le_code_qui_lisent": fuient}}


if __name__ == "__main__":
    import json
    print(json.dumps(sonde(), ensure_ascii=False, indent=1, default=str))
