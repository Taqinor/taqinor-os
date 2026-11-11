"""GED (apps/ged/views.py::DocumentViewSet.get_permissions) : lecture ouverte à tout compte interne (IsAnyRole), sans droit de module
ged_* ni client_pii_voir ni portée de rôle ; apps/ged/selectors.py::documents_visible_to_user ne filtre que société + coffre-fort +
corbeille. On EXÉCUTE le vrai get_permissions (extrait par ast, bouchons rest_framework) puis les VRAIES classes de permission contre
des faux utilisateurs portant les codes réels de chaque rôle livré ; le sélecteur est lu par ast (le queryset Django n'est pas rejoué)."""
SONDE = {"constat": "C-ALEC-016", "sha": "ae5a7ae4c",
         "attendu": "list/retrieve/recherche/... et DepotPublicViewSet list : des rôles livrés sans aucun code ged_* ou sans "
                    "client_pii_voir franchissent la garde ; le sélecteur n'a ni droit de module ni portée"}
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


def sonde(ctx=None):
    reg, g, roles = monde()
    V = "apps/ged/views.py"
    ns = {"READ_ACTIONS": constante(V, "READ_ACTIONS"), "GED_GERER": constante(V, "GED_GERER"),
          "GED_GOUVERNANCE": constante(V, "GED_GOUVERNANCE"), "GOUVERNANCE_ACTIONS": constante(V, "GOUVERNANCE_ACTIONS"),
          "Mapping": dict, "IsAnyRole": g["IsAnyRole"], "HasPermissionOrLegacy": g["HasPermissionOrLegacy"],
          "IsResponsableOrAdmin": g["IsResponsableOrAdmin"]}
    gp_doc = fonction(V, "get_permissions", "DocumentViewSet", dict(ns))
    gp_depot = fonction(V, "get_permissions", "DepotPublicViewSet", dict(ns))
    vue_doc = type("DocumentViewSet", (), {"__module__": "apps.ged.views"})()
    vue_dep = type("DepotPublicViewSet", (), {"__module__": "apps.ged.views"})()
    emplacements, sans_ged, sans_pii = {}, set(), set()
    for action in ("list", "retrieve", "recherche", "semantique", "historique", "timeline", "docqa"):
        s = types.SimpleNamespace(action=action, request=Req(None))
        gardes = gp_doc(s)
        ok = passent(gardes, roles, vue_doc)
        emplacements[f"DocumentViewSet.{action}"] = {"gardes": [type(x).__name__ for x in gardes], "rôles_qui_passent": len(ok)}
        sans_ged |= {n for n in ok if not any(c.startswith("ged_") for c in roles[n].role.permissions)}
        sans_pii |= {n for n in ok if "client_pii_voir" not in roles[n].role.permissions}
    s = types.SimpleNamespace(action="list", request=Req(None))
    ok_dep = passent(gp_depot(s), roles, vue_dep)
    # sélecteur : filtres posés et appels de portée / de droit
    f = next(n for n in ast.parse((DJ / "apps/ged/selectors.py").read_text(encoding="utf-8")).body
             if isinstance(n, ast.FunctionDef) and n.name == "documents_visible_to_user")
    filtres = sorted({k.arg for n in ast.walk(f) if isinstance(n, ast.Call) for k in n.keywords if k.arg})
    mots = {n.id for n in ast.walk(f) if isinstance(n, ast.Name)} | {n.attr for n in ast.walk(f) if isinstance(n, ast.Attribute)}
    textes = {n.value for n in ast.walk(f) if isinstance(n, ast.Constant) and isinstance(n.value, str)}
    portee_ou_droit = sorted(m for m in mots | textes if "scope" in m or "_voir" in m or "pii" in m or "has_erp" in m)
    scope = reg["SCOPE_SELF"], reg["SCOPE_SUBTREE"], reg["SCOPE_TEAM"]
    a_portee = sorted(n for n, u in roles.items() if set(scope) & set(u.role.permissions) and not u.is_admin_role)
    repro = bool(sans_ged and sans_pii and not portee_ou_droit and a_portee and ok_dep)
    return {"repro": repro, "observe": {
        "methode": "exécution du vrai get_permissions (ast + bouchons DRF) puis des vraies classes de permission ; sélecteur lu par ast",
        "emplacements_controles": len(emplacements) + 1, "emplacements": emplacements,
        "DepotPublicViewSet.list": {"rôles_qui_passent": ok_dep},
        "code_attendu": "ged_voir (module) + client_pii_voir (coordonnées) + records_scope_* (portée)",
        "roles_livres_qui_passent_sans_aucun_code_ged": sorted(sans_ged),
        "roles_livres_qui_passent_sans_client_pii_voir": sorted(sans_pii),
        "selecteur_filtres": filtres, "selecteur_references_portee_ou_droit": portee_ou_droit,
        "roles_a_portee_servis_sur_toute_la_societe": a_portee}}


if __name__ == "__main__":
    import json
    print(json.dumps(sonde(), ensure_ascii=False, indent=1))
