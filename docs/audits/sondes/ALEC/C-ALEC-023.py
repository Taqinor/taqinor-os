"""Fiche de performance technicien (apps/reporting/technicien_scorecard.py::technicien_scorecard) : docstring « JAMAIS visible par le
technicien lui-même », mais garde IsResponsableOrAdmin (qui laisse passer tout rôle à code d'écriture + reporting_voir) et lecture de
`?technicien=<id>` dans la société sans aucune comparaison avec l'appelant ni portée. On EXÉCUTE la vraie IsResponsableOrAdmin (vue du module
reporting) contre les codes des rôles livrés, et on lit par ast le décorateur, le corps (attributs lus sur request.user, portée) et la docstring."""
SONDE = {"constat": "C-ALEC-023", "sha": "ae5a7ae4c",
         "attendu": "le rôle Technicien franchit la garde ; le corps ne lit de request.user que la société et n'applique aucune portée "
                    "alors que la docstring promet « jamais visible par le technicien lui-même »"}
import ast, pathlib, runpy, sys, types
RACINE = pathlib.Path(__file__).resolve().parents[4]
DJ = RACINE / "backend/django_core"


def fonction(chemin, nom, classe=None, ns=None):
    """Extrait par ast la VRAIE fonction/méthode `nom` (décorateurs ôtés) et la compile dans `ns`."""
    corps = ast.parse((DJ / chemin).read_text(encoding="utf-8")).body
    if classe:
        corps = next(n for n in corps if isinstance(n, ast.ClassDef) and n.name == classe).body
    f = next(n for n in corps if isinstance(n, ast.FunctionDef) and n.name == nom)
    f.decorator_list = []
    ns = {} if ns is None else ns
    exec(compile(ast.Module([f], []), chemin, "exec"), ns)
    return ns[nom]


def constante(chemin, nom):
    for n in ast.parse((DJ / chemin).read_text(encoding="utf-8")).body:
        if isinstance(n, ast.Assign) and isinstance(n.targets[0], ast.Name) and n.targets[0].id == nom:
            return ast.literal_eval(n.value)


def monde():
    """Registre vivant des rôles + VRAIES classes de permission (authentication/permissions.py, rest_framework bouchonné)
    + faux utilisateurs dont is_responsable / is_admin_role / has_erp_permission sont les VRAIS corps de CustomUser."""
    reg = runpy.run_path(str(DJ / "apps/roles/permissions_registre.py"))
    sauve = {k: sys.modules.get(k) for k in ("rest_framework", "rest_framework.permissions")}
    perm = types.ModuleType("rest_framework.permissions")
    perm.SAFE_METHODS = ("GET", "HEAD", "OPTIONS"); perm.BasePermission = type("BasePermission", (), {})
    sys.modules["rest_framework"] = types.ModuleType("rest_framework"); sys.modules["rest_framework.permissions"] = perm
    try:
        g = runpy.run_path(str(DJ / "authentication/permissions.py"))
    finally:
        for k, v in sauve.items():
            sys.modules.pop(k, None) if v is None else sys.modules.__setitem__(k, v)
    g["enregistrer_registre_modules"](reg["PERMISSION_MODULE"], octrois_lecture=reg["OCTROIS_LECTURE"])
    M = "authentication/models.py"
    rgw, adm, resp, hep = (fonction(M, n, "CustomUser") for n in
                           ("_role_grants_write", "is_admin_role", "is_responsable", "has_erp_permission"))
    portail = {r[0] if isinstance(r, tuple) else r for r in reg["CANONICAL_PORTAIL_ROLES"]}

    class FauxUser:
        is_authenticated, is_superuser, company_id, id, portee, role_legacy = True, False, 1, 1, "interne", "normal"
        has_erp_permission = hep

        def __init__(s, nom, perms):
            s.role = types.SimpleNamespace(nom=nom, permissions=list(perms), est_systeme=True); s.role_id = 1
            s._role_grants_write = rgw
            s.is_admin_role, s.is_responsable = adm(s), resp(s)

    roles = {n: FauxUser(n, p) for n, p in reg["CANONICAL_SYSTEM_ROLES"] if n not in portail}
    return reg, g, roles


class Req:
    def __init__(s, user, method="GET", data=None):
        s.user, s.method, s.data, s.query_params = user, method, data or {}, {}


def passent(gardes, roles, vue, methode="GET"):
    """Rôles livrés qui franchissent TOUTES les gardes (vraies classes) pour cette vue."""
    return [n for n, u in roles.items() if all(p.has_permission(Req(u, methode), vue) for p in gardes)]


def classe_ast(chemin, nom):
    return next(n for n in ast.parse((DJ / chemin).read_text(encoding="utf-8")).body if isinstance(n, ast.ClassDef) and n.name == nom)


def attribut_classe(chemin, nom, attr):
    """Valeur littérale de `attr` dans la classe `nom`, en remontant les bases du même fichier ; (valeur, classe porteuse)."""
    c = classe_ast(chemin, nom)
    for s in c.body:
        if isinstance(s, ast.Assign) and isinstance(s.targets[0], ast.Name) and s.targets[0].id == attr:
            v = s.value
            return ([e.id if isinstance(e, ast.Name) else ast.literal_eval(e) for e in v.elts] if isinstance(v, ast.List)
                    else ast.literal_eval(v)), nom
    for b in c.bases:
        try:
            return attribut_classe(chemin, b.id, attr)
        except (StopIteration, AttributeError):
            pass
    raise StopIteration(attr)


def sonde(ctx=None):
    reg, g, roles = monde()
    F = "apps/reporting/technicien_scorecard.py"
    arbre = ast.parse((DJ / F).read_text(encoding="utf-8"))
    f = next(n for n in arbre.body if isinstance(n, ast.FunctionDef) and n.name == "technicien_scorecard")
    deco = next(d for d in f.decorator_list if isinstance(d, ast.Call) and getattr(d.func, "id", "") == "permission_classes")
    gardes_noms = [ast.unparse(e) for e in deco.args[0].elts]
    vue = type("technicien_scorecard", (), {"__module__": "apps.reporting.technicien_scorecard"})()
    ok = passent([g["IsResponsableOrAdmin"]()], roles, vue)   # 2e garde = DroitDeLaGrille('reporting_export', export=('xlsx',)) : True sans ?export
    attrs_user = sorted({n.attr for n in ast.walk(f) if isinstance(n, ast.Attribute) and isinstance(n.value, ast.Attribute)
                         and n.value.attr == "user" and isinstance(n.value.value, ast.Name) and n.value.value.id == "request"})
    comparaisons = [ast.unparse(n) for n in ast.walk(f) if isinstance(n, ast.Compare) and "request.user" in ast.unparse(n)]
    mots = {n.id for n in ast.walk(f) if isinstance(n, ast.Name)} | {n.attr for n in ast.walk(f) if isinstance(n, ast.Attribute)}
    portee = sorted(x for x in mots if "scope" in x or "visible" in x or "subtree" in x)
    promesse = "JAMAIS visible par le technicien" in " ".join((ast.get_docstring(arbre) or "").split())
    portees = {n: u.role.permissions for n, u in roles.items() if n in ("Technicien", "Technicien responsable")}
    scope = {reg["SCOPE_SELF"], reg["SCOPE_SUBTREE"], reg["SCOPE_TEAM"]}
    tech_a_portee = sorted(n for n in ok if n.startswith("Technicien") and scope & set(portees[n]))
    repro = bool("Technicien" in ok and promesse and attrs_user == ["company"] and not comparaisons and not portee)
    return {"repro": repro, "observe": {
        "methode": "exécution de la vraie IsResponsableOrAdmin ; décorateur, corps et docstring lus par ast",
        "route": "GET /api/django/reporting/insights/technicien-scorecard/?technicien=<id>",
        "gardes_declarees": gardes_noms, "docstring_promet_jamais_visible_par_le_technicien": promesse,
        "attributs_lus_sur_request.user": attrs_user, "comparaisons_avec_l_appelant": comparaisons, "portee_dans_le_corps": portee,
        "roles_qui_passent": ok, "techniciens_a_portee_qui_lisent_un_collegue": tech_a_portee}}


if __name__ == "__main__":
    import json
    print(json.dumps(sonde(), ensure_ascii=False, indent=1))
