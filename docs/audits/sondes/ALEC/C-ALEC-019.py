"""Journal hors ligne (apps/offlinesync/views.py::OfflineOperationViewSet) : lecture IsAnyRole + queryset société seule => les notes de leads
et mesures de visite mises en file par TOUS les utilisateurs sont lisibles par tout compte interne, portée ignorée. On lit par ast la
permission_classes réelle de la vue et le corps réel de get_queryset (filtres, références à l'utilisateur), on EXÉCUTE la vraie classe
IsAnyRole contre les codes des rôles livrés, et on lit la liste de champs du sérialiseur (payload, resultat)."""
SONDE = {"constat": "C-ALEC-019", "sha": "ae5a7ae4c",
         "attendu": "les rôles livrés à portée (Commercial, Commercial responsable, Technicien(s), Viewer) lisent le journal de toute la société ; "
                    "get_queryset ne filtre pas sur l'utilisateur ; payload et resultat sont servis"}
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
    V, VS = "apps/offlinesync/views.py", "OfflineOperationViewSet"
    noms, porteuse = attribut_classe(V, VS, "permission_classes")
    vue = type(VS, (), {"__module__": "apps.offlinesync.views"})()
    ok = passent([g[n]() for n in noms], roles, vue)
    gq = next(f for f in classe_ast(V, VS).body if isinstance(f, ast.FunctionDef) and f.name == "get_queryset")
    filtres = sorted({k.arg for n in ast.walk(gq) if isinstance(n, ast.Call) for k in n.keywords if k.arg})
    sur_utilisateur = sorted({n.attr for n in ast.walk(gq) if isinstance(n, ast.Attribute) and n.attr in ("user", "user_id", "company")}
                             | {n.id for n in ast.walk(gq) if isinstance(n, ast.Name) and "scope" in n.id.lower()})
    meta = next(m for m in classe_ast("apps/offlinesync/serializers.py", "OfflineOperationSerializer").body
                if isinstance(m, ast.ClassDef) and m.name == "Meta")
    champs = next(ast.literal_eval(m.value) for m in meta.body if isinstance(m, ast.Assign) and m.targets[0].id == "fields")
    scope = {reg["SCOPE_SELF"], reg["SCOPE_SUBTREE"], reg["SCOPE_TEAM"]}
    a_portee = sorted(n for n in ok if scope & set(roles[n].role.permissions) and not roles[n].is_admin_role)
    # producteurs (le lot s'écrit par OfflineSyncBatchView, IsResponsableOrAdmin) : montre que d'autres comptes alimentent le journal
    noms_p, _ = attribut_classe(V, "OfflineSyncBatchView", "permission_classes")
    producteurs = passent([g[n]() for n in noms_p], roles, type("OfflineSyncBatchView", (), {"__module__": "apps.offlinesync.views"})(), "POST")
    repro = bool(noms == ["IsAnyRole"] and a_portee and not any("scope" in x.lower() or x == "user" for x in sur_utilisateur)
                 and "user" not in filtres and {"payload", "resultat"} <= set(champs))
    return {"repro": repro, "observe": {
        "methode": "exécution de la vraie classe IsAnyRole ; permission_classes, get_queryset et champs du sérialiseur lus par ast",
        "route": "apps/offlinesync/views.py::OfflineOperationViewSet (GET /api/django/offlinesync/operations/)",
        "garde": noms, "declaree_dans": porteuse, "filtres_de_get_queryset": filtres,
        "references_utilisateur_ou_portee_dans_get_queryset": sur_utilisateur,
        "champs_sensibles_servis": [c for c in ("payload", "resultat", "erreur") if c in champs],
        "roles_qui_lisent": ok, "roles_a_portee_qui_lisent_les_ops_des_autres": a_portee,
        "roles_qui_alimentent_le_journal_par_batch": producteurs}}


if __name__ == "__main__":
    import json
    print(json.dumps(sonde(), ensure_ascii=False, indent=1))
