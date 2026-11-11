"""Journal des réglages (apps/parametres/views_audit.py::settings_audit_log) : palier responsable (IsAdminOrResponsableTier) sans le code
journal_activite_voir qui garde le Journal d'activité (apps/audit/views.py::CanViewActivityLog) ; même table SettingsAuditLog que
reporting/insights.py::audit_log. Constat GATÉ sur la décision D-ALEC-3 (le journal des réglages relève-t-il du « Journal d'activité » ?) :
la sonde prouve le FAIT observé, pas la décision. On EXÉCUTE le vrai IsAdminOrResponsableTier.has_permission (corps extrait par ast ;
le palier menu_tier est calculé par la vraie tier_for_role_fields de authentication/role_tiers.py) contre les rôles livrés."""
SONDE = {"constat": "C-ALEC-024", "sha": "ae5a7ae4c",
         "attendu": "des rôles livrés sans journal_activite_voir (Commercial responsable, Technicien responsable, Responsable, Admin RH, "
                    "Admin Ventes) franchissent la garde de settings_audit_log et settings_audit_sections"}
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
    P = "apps/parametres/views_audit.py"
    tiers = runpy.run_path(str(DJ / "authentication/role_tiers.py"))
    cu = types.SimpleNamespace(ROLE_ADMIN=tiers["ROLE_ADMIN"], ROLE_RESPONSABLE=tiers["ROLE_RESPONSABLE"])
    corps = classe_ast("authentication/permissions.py", "IsAdminOrResponsableTier")
    f = next(n for n in corps.body if isinstance(n, ast.FunctionDef) and n.name == "has_permission")
    f.body = [n for n in f.body if not isinstance(n, ast.ImportFrom)]       # `from .models import CustomUser` : remplacé par cu
    ns = {"CustomUser": cu}
    exec(compile(ast.Module([f], []), "permissions.py", "exec"), ns)
    garde = types.SimpleNamespace(has_permission=lambda req, view: ns["has_permission"](None, req, view))
    arbre = ast.parse((DJ / P).read_text(encoding="utf-8"))
    emplacements, passants = {}, None
    for nom in ("settings_audit_log", "settings_audit_sections"):
        fn = next(n for n in arbre.body if isinstance(n, ast.FunctionDef) and n.name == nom)
        deco = [ast.unparse(e) for d in fn.decorator_list if isinstance(d, ast.Call) and getattr(d.func, "id", "") == "permission_classes"
                for e in d.args[0].elts]
        emplacements[nom] = deco
    for u in roles.values():
        u.menu_tier = tiers["tier_for_role_fields"](u.role.nom, u.role.est_systeme, u.role.permissions)
    ok = [n for n, u in roles.items() if garde.has_permission(Req(u), None)]
    code_lu = "journal_activite_voir" in (DJ / P).read_text(encoding="utf-8") or "can_view_activity_log" in (DJ / P).read_text(encoding="utf-8")
    temoin = classe_ast("apps/audit/views.py", "CanViewActivityLog")
    temoin_lit = any(isinstance(n, ast.Constant) and n.value == "can_view_activity_log" for n in ast.walk(temoin))
    sans_code = sorted(n for n in ok if "journal_activite_voir" not in roles[n].role.permissions)
    repro = bool(sans_code and not code_lu and temoin_lit
                 and all(v == ["IsAdminOrResponsableTier"] for v in emplacements.values()))
    return {"repro": repro, "observe": {
        "methode": "exécution du vrai IsAdminOrResponsableTier.has_permission (ast) ; décorateurs lus par ast",
        "decision_en_attente": "D-ALEC-3 (le journal des réglages = Journal d'activité ?) : la sonde ne tranche pas",
        "emplacements_controles": len(emplacements), "gardes_declarees": emplacements,
        "code_journal_lu_dans_views_audit": code_lu, "temoin_audit_CanViewActivityLog_lit_can_view_activity_log": temoin_lit,
        "roles_qui_passent": ok, "roles_qui_passent_sans_journal_activite_voir": sans_code,
        "dont_palier_responsable_hors_administrateur": [n for n in sans_code if not roles[n].is_admin_role]}}


if __name__ == "__main__":
    import json
    print(json.dumps(sonde(), ensure_ascii=False, indent=1))
