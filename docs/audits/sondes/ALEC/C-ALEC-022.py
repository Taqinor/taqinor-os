"""Tournée préventive (apps/sav/maintenance.py::tournee_preventive, servie par ContratMaintenanceViewSet.tournee) : tickets préventifs de
TOUTE la société, avec nom du client, GPS du chantier et technicien, sans la portée appliquée par le jumeau sav/views.py::_tickets_visibles.
On EXÉCUTE le vrai get_permissions (ast + vraie LectureDuModule) pour l'action `tournee`, puis on lit par ast la signature, les filtres et
les clés de sortie de tournee_preventive, l'appel fait par l'action, et la portée du jumeau."""
SONDE = {"constat": "C-ALEC-022", "sha": "ae5a7ae4c",
         "attendu": "des rôles livrés à portée (Commercial, Commercial responsable, Technicien(s), Viewer) franchissent LectureDuModule(sav) ; "
                    "tournee_preventive ne reçoit que la société et rend client_nom, gps_lat, gps_lng, technicien"}
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
    M, VS = "apps/sav/maintenance.py", "ContratMaintenanceViewSet"
    ns = {"LectureDuModule": g["LectureDuModule"], "IsResponsableOrAdmin": g["IsResponsableOrAdmin"]}
    gardes = fonction(M, "get_permissions", VS, ns)(types.SimpleNamespace(action="tournee"))
    vue = type(VS, (), {"__module__": "apps.sav.maintenance"})()
    ok = passent(gardes, roles, vue)
    arbre = ast.parse((DJ / M).read_text(encoding="utf-8"))
    f = next(n for n in arbre.body if isinstance(n, ast.FunctionDef) and n.name == "tournee_preventive")
    params = [a.arg for a in f.args.args]
    filtres = sorted({k.arg for n in ast.walk(f) if isinstance(n, ast.Call) for k in n.keywords if k.arg in
                      ("company", "type", "statut__in", "annule", "created_by", "technicien_responsable")})
    cles = sorted({k.value for n in ast.walk(f) if isinstance(n, ast.Dict) for k in n.keys if isinstance(k, ast.Constant)})
    appel = next(ast.unparse(n.args[0]) for n in ast.walk(classe_ast(M, VS)) if isinstance(n, ast.Call)
                 and getattr(n.func, "id", "") == "tournee_preventive")
    scoped = [n for n in ast.walk(f) if isinstance(n, ast.Name) and "scope" in n.id.lower()]
    jumeau = next(n for n in ast.parse((DJ / "apps/sav/views.py").read_text(encoding="utf-8")).body
                  if isinstance(n, ast.FunctionDef) and n.name == "_tickets_visibles")
    jumeau_scope = sorted({n.id for n in ast.walk(jumeau) if isinstance(n, ast.Name) and "scope" in n.id.lower()})
    scope = {reg["SCOPE_SELF"], reg["SCOPE_SUBTREE"], reg["SCOPE_TEAM"]}
    a_portee = sorted(n for n in ok if scope & set(roles[n].role.permissions) and not roles[n].is_admin_role)
    sorties = [c for c in ("client_nom", "gps_lat", "gps_lng", "technicien") if c in cles]
    repro = bool(a_portee and params == ["company", "origin_lat", "origin_lng"] and not scoped and jumeau_scope
                 and len(sorties) == 4 and appel == "request.user.company")
    return {"repro": repro, "observe": {
        "methode": "exécution du vrai get_permissions (ast) + vraie LectureDuModule ; tournee_preventive lue par ast",
        "route": "GET /api/django/sav/contrats-maintenance/tournee/ (ContratMaintenanceViewSet.tournee)",
        "garde": [type(x).__name__ for x in gardes], "parametres_tournee_preventive": params,
        "argument_passe_par_l_action": appel, "filtres_ticket": filtres, "portee_dans_tournee_preventive": len(scoped),
        "portee_du_jumeau__tickets_visibles": jumeau_scope, "champs_nominatifs_rendus": sorties,
        "roles_qui_lisent": ok, "roles_a_portee_qui_voient_toute_la_societe": a_portee}}


if __name__ == "__main__":
    import json
    print(json.dumps(sonde(), ensure_ascii=False, indent=1))
