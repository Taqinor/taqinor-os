"""Documents de chantier (apps/documents/views.py : PV de réception, bon de livraison, dossier de remise, attestation) : garde
IsAnyRole (+ IsResponsableOrAdmin pour l'attestation), module `documents` sans codes au registre => aucun droit de module exigé (jumeau
d'APFS105). On lit par ast la liste permission_classes effective de chaque vue réelle, puis on EXÉCUTE les vraies classes de permission
contre les codes des rôles livrés, avec la vue rattachée au module apps.documents.views (module_du_chemin => None)."""
SONDE = {"constat": "C-ALEC-017", "sha": "ae5a7ae4c",
         "attendu": "Commercial terrain et Admin RH (sans installation_voir ni client_pii_voir) franchissent les 4 vues PDF de chantier"}
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
    V = "apps/documents/views.py"
    vues = ["PVReceptionView", "BonLivraisonView", "DossierRemiseView", "AttestationView"]
    module = g["module_du_chemin"]("apps.documents.views")
    par_vue, tous = {}, None
    for nom in vues:
        noms, porteuse = attribut_classe(V, nom, "permission_classes")
        vue = type(nom, (), {"__module__": "apps.documents.views"})()
        ok = passent([g[n]() for n in noms], roles, vue)
        par_vue[nom] = {"garde": noms, "declaree_dans": porteuse, "passent": ok}
        tous = set(ok) if tous is None else tous & set(ok)
    P = {n: set(u.role.permissions) for n, u in roles.items()}
    sans_module = sorted(n for n in tous if "installation_voir" not in P[n] and "ventes_voir" not in P[n])   # hors octroi D-APFS-4
    sans_pii = sorted(n for n in tous if "client_pii_voir" not in P[n])
    pdf = (DJ / "apps/documents/builders.py").read_text(encoding="utf-8")
    bloc_client = "def _client_block" in pdf
    repro = bool(module is None and sans_module and sans_pii)
    return {"repro": repro, "observe": {
        "methode": "exécution des vraies classes de permission (IsAnyRole, IsResponsableOrAdmin) ; permission_classes lues par ast",
        "module_du_chemin(apps.documents.views)": module, "vues_controlees": len(vues), "vues": par_vue,
        "code_attendu": "installation_voir (module chantier) ; coordonnées : client_pii_voir",
        "roles_qui_passent_les_4_vues_sans_installation_voir_ni_ventes_voir": sans_module,
        "roles_qui_passent_les_4_vues_sans_client_pii_voir": sans_pii,
        "builders._client_block_present": bloc_client}}


if __name__ == "__main__":
    import json
    print(json.dumps(sonde(), ensure_ascii=False, indent=1))
