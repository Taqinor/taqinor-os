"""Répertoire des tiers (apps/tiers/views.py::TiersViewSet) : read_permission = None => tout compte interne lit les tiers, et le miroir
crm/tiers_bridge.py::mirror_client_to_tiers y recopie CIN, téléphone, e-mail, adresse du client. On EXÉCUTE le vrai
ScopedPermission.has_permission (corps extrait par ast de core/permissions.py) avec les attributs réels de la vue, contre les codes des
rôles livrés ; le sérialiseur et le miroir sont lus par ast (le sérialiseur n'a aucun masque, le miroir passe cin/telephone/email/adresse)."""
SONDE = {"constat": "C-ALEC-018", "sha": "ae5a7ae4c",
         "attendu": "list/retrieve des tiers franchis par tous les rôles internes ; cin, telephone, email, adresse servis sans client_pii_voir "
                    "ni portée ; le miroir Client => Tiers recopie ces champs"}
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
    V = "apps/tiers/views.py"
    lecture, _ = attribut_classe(V, "TiersViewSet", "read_permission")
    ecriture, _ = attribut_classe(V, "TiersViewSet", "write_permission")
    ns = {"SAFE_METHODS": ("GET", "HEAD", "OPTIONS"), "getattr": getattr, "_user_has_or_legacy": lambda u, c: u.has_erp_permission(c)}
    has_perm = fonction("core/permissions.py", "has_permission", "ScopedPermission", ns)
    garde = type("ScopedPermission", (), {"has_permission": has_perm})()
    vue = types.SimpleNamespace(read_permission=lecture, write_permission=ecriture)
    ok = [n for n, u in roles.items() if garde.has_permission(Req(u), vue)]
    cls = classe_ast(V, "TiersViewSet")
    surcharges = sorted(f.name for f in cls.body if isinstance(f, ast.FunctionDef) and f.name in ("get_queryset", "get_permissions"))
    ser = classe_ast("apps/tiers/serializers.py", "TiersSerializer")
    meta = next(m for m in ser.body if isinstance(m, ast.ClassDef) and m.name == "Meta")
    champs = next(ast.literal_eval(m.value) for m in meta.body if isinstance(m, ast.Assign) and m.targets[0].id == "fields")
    masque = sorted(f.name for f in ser.body if isinstance(f, ast.FunctionDef) and f.name in ("to_representation",))
    pii_vus = [c for c in ("telephone", "email", "adresse", "cin", "rib") if c in champs]
    arbre = ast.parse((DJ / "apps/crm/tiers_bridge.py").read_text(encoding="utf-8"))
    f = next(n for n in arbre.body if isinstance(n, ast.FunctionDef) and n.name == "mirror_client_to_tiers")
    copies = sorted({k.arg for n in ast.walk(f) if isinstance(n, ast.Call) and getattr(n.func, "attr", "") == "attacher_ou_creer_tiers"
                     for k in n.keywords})
    P = {n: set(u.role.permissions) for n, u in roles.items()}
    sans_pii = sorted(n for n in ok if "client_pii_voir" not in P[n])
    a_portee = sorted(n for n in ok if {reg["SCOPE_SELF"], reg["SCOPE_SUBTREE"], reg["SCOPE_TEAM"]} & P[n] and not roles[n].is_admin_role)
    repro = bool(lecture is None and ok and sans_pii and a_portee and not surcharges and not masque
                 and {"cin", "telephone", "email", "adresse"} <= set(copies) and {"cin", "telephone", "email"} <= set(pii_vus))
    return {"repro": repro, "observe": {
        "methode": "exécution du vrai ScopedPermission.has_permission (ast) ; vue, sérialiseur et miroir lus par ast",
        "route": "apps/tiers/views.py::TiersViewSet (GET /api/django/tiers/tiers/)", "read_permission": lecture,
        "surcharges_get_queryset_ou_get_permissions": surcharges, "to_representation_dans_TiersSerializer": masque,
        "champs_personnels_servis": pii_vus, "champs_recopies_par_le_miroir": copies,
        "roles_qui_lisent": ok, "code_attendu": "client_pii_voir (+ records_scope_* pour les clients des collègues)",
        "roles_qui_lisent_sans_client_pii_voir": sans_pii, "roles_a_portee_qui_lisent_tout": a_portee}}


if __name__ == "__main__":
    import json
    print(json.dumps(sonde(), ensure_ascii=False, indent=1))
