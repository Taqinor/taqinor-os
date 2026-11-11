"""Lignes de factures (apps/facturation/views/ligne_facture.py::LigneFactureViewSet, 2 routes) : lecture LectureFactures + queryset
`facture__company` seul, alors que le jumeau FactureViewSet.get_queryset applique scope_queryset(..., ['created_by']). On EXÉCUTE le vrai
get_permissions (ast + vraies classes ; LectureFactures reconstruite d'après gardes_lecture.py) contre les rôles livrés, puis on lit le
vrai get_queryset par ast (aucune portée) et le get_queryset du jumeau (portée présente), et on compte les routes montées."""
SONDE = {"constat": "C-ALEC-021", "sha": "ae5a7ae4c",
         "attendu": "Commercial, Commercial responsable et Viewer lisent les lignes de toutes les factures de la société ; "
                    "le get_queryset des lignes n'applique aucune portée alors que celui des factures le fait"}
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


def mots_portee(f):
    m = {n.id for n in ast.walk(f) if isinstance(n, ast.Name)} | {n.attr for n in ast.walk(f) if isinstance(n, ast.Attribute)}
    return sorted(x for x in m if "scope" in x.lower() or "portee" in x.lower() or "visibles" in x.lower())


def sonde(ctx=None):
    reg, g, roles = monde()
    V, VS = "apps/facturation/views/ligne_facture.py", "LigneFactureViewSet"
    G = "apps/ventes/gardes_lecture.py"
    cls = {n.name: n for n in ast.parse((DJ / G).read_text(encoding="utf-8")).body if isinstance(n, ast.ClassDef)}
    fige = next(s.value.value for s in cls["LectureVentes"].body if isinstance(s, ast.Assign) and s.targets[0].id == "module_fige")
    LF = type("LectureFactures", (g["LectureDuModule"],), {"module_fige": fige})
    ns = {"READ_ACTIONS": constante(V, "READ_ACTIONS"), "WRITE_ACTIONS": constante(V, "WRITE_ACTIONS"), "LectureFactures": LF,
          "IsResponsableOrAdmin": g["IsResponsableOrAdmin"], "IsAdminRole": g["IsAdminRole"]}
    gp = fonction(V, "get_permissions", VS, ns)
    gardes = gp(types.SimpleNamespace(action="list"))
    vue = type(VS, (), {"__module__": "apps.facturation.views.ligne_facture"})()
    ok = passent(gardes, roles, vue)
    f = next(m for m in classe_ast(V, VS).body if isinstance(m, ast.FunctionDef) and m.name == "get_queryset")
    jumeau = next(m for m in classe_ast("apps/facturation/views/facture.py", "FactureViewSet").body
                  if isinstance(m, ast.FunctionDef) and m.name == "get_queryset")
    filtres = sorted({k.arg for n in ast.walk(f) if isinstance(n, ast.Call) for k in n.keywords if k.arg})
    routes = [p for p in ("apps/ventes/urls.py", "apps/facturation/urls.py")
              if "factures-lignes" in (DJ / p).read_text(encoding="utf-8")]
    scope = {reg["SCOPE_SELF"], reg["SCOPE_SUBTREE"], reg["SCOPE_TEAM"]}
    a_portee = sorted(n for n in ok if scope & set(roles[n].role.permissions) and not roles[n].is_admin_role)
    repro = bool(a_portee and not mots_portee(f) and mots_portee(jumeau) and len(routes) == 2)
    return {"repro": repro, "observe": {
        "methode": "exécution du vrai get_permissions (ast) + vraies classes de permission ; get_queryset lus par ast",
        "route": "apps/facturation/views/ligne_facture.py::LigneFactureViewSet.get_permissions",
        "emplacements_controles": len(routes), "routes_montees": routes, "garde_lecture": [type(x).__name__ for x in gardes],
        "module_fige": fige, "filtres_get_queryset_lignes": filtres, "portee_dans_get_queryset_lignes": mots_portee(f),
        "portee_dans_get_queryset_FactureViewSet(jumeau)": mots_portee(jumeau),
        "roles_qui_lisent": ok, "code_attendu": "records_scope_* appliqué comme sur les factures",
        "roles_a_portee_qui_lisent_toutes_les_lignes": a_portee}}


if __name__ == "__main__":
    import json
    print(json.dumps(sonde(), ensure_ascii=False, indent=1))
