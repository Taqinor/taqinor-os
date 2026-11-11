"""Agrégats sans portée de rôle : reporting/views.py::dashboard, ventes/dashboard_view.py::dashboard_quote_to_cash et
crm/clients_views.py::ObjectifCommercialViewSet.attainment_list. On EXÉCUTE les vraies gardes (IsResponsableOrAdmin ; LectureFactures =
LectureDuModule à module figé « ventes », relu par ast ; get_permissions réel de la vue Objectifs) contre les codes des rôles livrés,
puis on lit par ast les corps des fonctions pour constater qu'aucun appel de portée (records_scope_*, leads_visibles, scoper…) n'y figure."""
SONDE = {"constat": "C-ALEC-020", "sha": "ae5a7ae4c",
         "attendu": "des rôles livrés à portée (Commercial soi, Commercial responsable sous-arbre, Technicien équipe, Viewer) "
                    "franchissent les 3 gardes et les corps de fonction n'appliquent aucune portée"}
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


def corps(chemin, nom, classe=None):
    c = ast.parse((DJ / chemin).read_text(encoding="utf-8")).body
    if classe:
        c = next(n for n in c if isinstance(n, ast.ClassDef) and n.name == classe).body
    return next(n for n in c if isinstance(n, ast.FunctionDef) and n.name == nom)


def mots_de_portee(*fns):
    m = {n.id for f in fns for n in ast.walk(f) if isinstance(n, ast.Name)} | {n.attr for f in fns for n in ast.walk(f) if isinstance(n, ast.Attribute)}
    return sorted(x for x in m if any(k in x.lower() for k in ("scope", "portee", "visibles", "scoper", "en_portee", "visible_user")))


def decorateur_permissions(f):
    for d in f.decorator_list:
        if isinstance(d, ast.Call) and getattr(d.func, "id", "") == "permission_classes":
            return [e.id for e in d.args[0].elts]


def sonde(ctx=None):
    reg, g, roles = monde()
    scope = {reg["SCOPE_SELF"], reg["SCOPE_SUBTREE"], reg["SCOPE_TEAM"]}
    a_portee = [n for n, u in roles.items() if scope & set(u.role.permissions) and not u.is_admin_role]
    vue = lambda mod, nom: type(nom, (), {"__module__": mod})()
    obs = {}
    # 1. reporting/views.py::dashboard — @permission_classes([IsResponsableOrAdmin])
    f1 = corps("apps/reporting/views.py", "dashboard")
    d1 = decorateur_permissions(f1)
    ok1 = passent([g[x]() for x in d1], roles, vue("apps.reporting.views", "dashboard"))
    obs["reporting.dashboard"] = {"garde": d1, "portee_dans_le_corps": mots_de_portee(f1), "passent": ok1}
    # 2. ventes/dashboard_view.py::dashboard_quote_to_cash — LectureFactures(LectureVentes(LectureDuModule), module_fige='ventes')
    G = "apps/ventes/gardes_lecture.py"
    cls = {n.name: n for n in ast.parse((DJ / G).read_text(encoding="utf-8")).body if isinstance(n, ast.ClassDef)}
    fige = next(s.value.value for s in cls["LectureVentes"].body if isinstance(s, ast.Assign) and s.targets[0].id == "module_fige")
    f2 = corps("apps/ventes/dashboard_view.py", "dashboard_quote_to_cash")
    d2 = decorateur_permissions(f2)
    chaine = (d2 == ["LectureFactures"] and cls["LectureFactures"].bases[0].id == "LectureVentes"
              and cls["LectureVentes"].bases[0].id == "LectureDuModule")
    LF = type("LectureFactures", (g["LectureDuModule"],), {"module_fige": fige})
    ok2 = passent([LF()], roles, vue("apps.ventes.dashboard_view", "dashboard_quote_to_cash")) if chaine else []
    obs["ventes.dashboard_quote_to_cash"] = {"garde": d2, "module_fige": fige, "chaine_de_classes_confirmee": chaine,
                                            "portee_dans_le_corps": mots_de_portee(f2), "passent": ok2}
    # 3. crm/clients_views.py::ObjectifCommercialViewSet.attainment_list — get_permissions réel (écrase le décorateur @action)
    C = "apps/crm/clients_views.py"
    ns = {"READ_ACTIONS": constante("apps/crm/actions_crud.py", "READ_ACTIONS"), "LectureDuModule": g["LectureDuModule"],
          "IsAnyRole": g["IsAnyRole"], "IsAdminRole": g["IsAdminRole"]}
    gp = fonction(C, "get_permissions", "ObjectifCommercialViewSet", ns)
    gardes3 = gp(types.SimpleNamespace(action="attainment_list"))
    ok3 = passent(gardes3, roles, vue("apps.crm.clients_views", "ObjectifCommercialViewSet"))
    fs = [corps(C, n, "ObjectifCommercialViewSet") for n in ("attainment_list", "get_queryset")]
    obs["crm.ObjectifCommercialViewSet.attainment_list"] = {"garde": [type(x).__name__ for x in gardes3],
                                                           "portee_dans_attainment_list_et_get_queryset": mots_de_portee(*fs), "passent": ok3}
    sans_portee = all(not v["portee_dans_le_corps"] if "portee_dans_le_corps" in v else not v["portee_dans_attainment_list_et_get_queryset"] for v in obs.values())
    scopes_servis = {k: sorted(set(v["passent"]) & set(a_portee)) for k, v in obs.items()}
    repro = bool(sans_portee and all(scopes_servis.values()))
    return {"repro": repro, "observe": {
        "methode": "exécution des vraies gardes (get_permissions extrait par ast, LectureFactures reconstruite d'après le fichier) ; "
                   "corps de fonction lus par ast",
        "emplacements_controles": len(obs), "emplacements": obs, "roles_livres_a_portee": a_portee,
        "roles_a_portee_qui_passent_par_emplacement": scopes_servis}}


if __name__ == "__main__":
    import json
    print(json.dumps(sonde(), ensure_ascii=False, indent=1))
