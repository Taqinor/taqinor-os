"""Calepinage (apps/calepinage/selectors.py::restreindre_aux_siens, prédicat de toutes les routes via calepinages_visibles) : la « vue
restreinte » ne regarde que responsable / cree_par, jamais records_scope_*, et le calepinage porte nom + ville de son lead. Constat GATÉ
sur D-ALEC-4 ; état prod du réglage `vue_restreinte_au_responsable` NON LU : la sonde EXÉCUTE la vraie restreindre_aux_siens (corps extrait
par ast, bouchons Q / queryset) réglage ÉTEINT puis ALLUMÉ, pour chaque rôle livré qui lit le calepinage (calepinage_voir, via le vrai
_user_has_or_legacy), et lit par ast la portée absente et le contenu de _lead_apercu."""
SONDE = {"constat": "C-ALEC-025", "sha": "ae5a7ae4c",
         "attendu": "réglage éteint : aucun filtre pour Commercial, Commercial responsable, Viewer ; réglage allumé : filtre responsable|cree_par "
                    "sans portée de rôle ; nom et ville du lead servis"}
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


class Q:
    def __init__(s, **k): s.k = k
    def __or__(s, o): return "|".join(sorted(list(s.k) + list(o.k)))


class Lignes:
    def __init__(s): s.filtre = None
    def filter(s, q): r = Lignes(); r.filtre = q; return r


def sonde(ctx=None):
    reg, g, roles = monde()
    S, PM = "apps/calepinage/selectors.py", "apps/calepinage/permissions.py"
    etat = {"on": False}
    ns = {"Q": Q, "vue_restreinte_au_responsable": lambda company: etat["on"], "CAL_APPROUVER": constante(PM, "CAL_APPROUVER")}
    ns["_user_has_or_legacy"] = fonction("core/permissions.py", "_user_has_or_legacy", None, {})
    f = next(n for n in ast.parse((DJ / S).read_text(encoding="utf-8")).body if isinstance(n, ast.FunctionDef) and n.name == "restreindre_aux_siens")
    f.body = [n for n in f.body if not isinstance(n, ast.ImportFrom)]       # imports locaux remplacés par les bouchons de ns
    exec(compile(ast.Module([f], []), S, "exec"), ns)
    lisent = [n for n, u in roles.items() if u.has_erp_permission(constante(PM, "CAL_VOIR"))]   # read_permission de la vue (ScopedPermission)
    scope = {reg["SCOPE_SELF"], reg["SCOPE_SUBTREE"], reg["SCOPE_TEAM"]}
    resultat = {}
    for nom_etat, on in (("reglage_eteint", False), ("reglage_allume", True)):
        etat["on"] = on
        resultat[nom_etat] = {n: (ns["restreindre_aux_siens"](Lignes(), roles[n]).filtre or "aucun filtre") for n in lisent}
    a_portee = sorted(n for n in lisent if scope & set(roles[n].role.permissions) and not roles[n].is_admin_role)
    mots = {x.id for x in ast.walk(f) if isinstance(x, ast.Name)} | {x.attr for x in ast.walk(f) if isinstance(x, ast.Attribute)}
    portee_dans_fonction = sorted(m for m in mots if "scope" in m.lower() or "portee" in m.lower() or "visible_user" in m)
    apercu = next(n for n in ast.parse((DJ / "apps/calepinage/serializers.py").read_text(encoding="utf-8")).body
                  if isinstance(n, ast.FunctionDef) and n.name == "_lead_apercu")
    cles = sorted({k.value for n in ast.walk(apercu) if isinstance(n, ast.Dict) for k in n.keys if isinstance(k, ast.Constant)})
    ouvert_eteint = [n for n in a_portee if resultat["reglage_eteint"][n] == "aucun filtre"]
    portee_ignoree_allume = [n for n in a_portee if resultat["reglage_allume"][n] == "cree_par|responsable"]
    repro = bool(ouvert_eteint and portee_ignoree_allume and not portee_dans_fonction and {"nom", "ville"} <= set(cles))
    return {"repro": repro, "observe": {
        "methode": "exécution de la vraie restreindre_aux_siens (ast + bouchons Q / queryset / _user_has_or_legacy réel) ; serializers lus par ast",
        "decision_en_attente": "D-ALEC-4 ; réglage vue_restreinte_au_responsable en prod NON LU : la sonde montre les deux états",
        "roles_qui_lisent_le_calepinage": lisent, "filtre_reglage_eteint": resultat["reglage_eteint"],
        "filtre_reglage_allume": resultat["reglage_allume"], "references_a_la_portee_dans_la_fonction": portee_dans_fonction,
        "cles_du_lead_servies_par__lead_apercu": cles,
        "roles_a_portee_servis_sans_filtre_si_reglage_eteint": ouvert_eteint,
        "roles_a_portee_filtres_par_responsable_seulement_si_reglage_allume": portee_ignoree_allume}}


if __name__ == "__main__":
    import json
    print(json.dumps(sonde(), ensure_ascii=False, indent=1))
