"""Rejoue apps/accessreview/services.py::attester (révocation d'une revue d'accès) : elle appelle
apps/roles/services.py::remove_role_from_user sans authentication/role_tiers.py::peut_gerer ni garde « compte protégé » /
« dernier propriétaire » ; un Directeur rétrograde le fondateur protégé puis lui-même → plus aucun administrateur."""
SONDE = {"constat": "C-APUB-002", "sha": "ae5a7ae4c",
         "attendu": "peut_gerer(directeur2, fondateur) = refus ; attester rétrograde quand même le fondateur protégé ; admins restants = []"}
import ast, datetime, importlib.util, pathlib, sys, types
RACINE = pathlib.Path(__file__).resolve().parents[4]
if not (RACINE / "backend/django_core").is_dir(): RACINE = pathlib.Path.cwd()  # copie hors dépôt : jouée depuis la racine
DJ = RACINE / "backend/django_core"
MODS = ("django", "django.utils", "django.utils.timezone", "apps", "apps.roles", "apps.accessreview", "authentication",
        "authentication.models", "apps.roles.permissions_registre", "authentication.role_tiers", "apps.roles.models",
        "apps.accessreview.models", "apps.roles.services", "apps.accessreview.services")


def charger(nom, chemin):
    spec = importlib.util.spec_from_file_location(nom, DJ / chemin)
    m = importlib.util.module_from_spec(spec); sys.modules[nom] = m; spec.loader.exec_module(m); return m


def paquet(nom):
    m = types.ModuleType(nom); m.__path__ = []; sys.modules[nom] = m; return m


def scenario():
    for p in ("django", "django.utils", "apps", "apps.roles", "apps.accessreview", "authentication"): paquet(p)
    tz = types.ModuleType("django.utils.timezone"); tz.now = datetime.datetime.now; sys.modules["django.utils.timezone"] = tz
    sys.modules["django.utils"].timezone = tz
    REG = charger("apps.roles.permissions_registre", "apps/roles/permissions_registre.py")
    RT = charger("authentication.role_tiers", "authentication/role_tiers.py")
    USERS, ROLES = [], []

    class QS(list):
        def order_by(s, *a): return QS(sorted(s, key=lambda r: r.id))
        def first(s): return s[0] if s else None
        def exclude(s, pk=None): return QS(u for u in s if u.pk != pk)
        def exists(s): return bool(s)

    class Role:
        def __init__(s, company, nom, permissions, est_systeme=True):
            s.pk = s.id = len(ROLES) + 1; s.company, s.nom, s.permissions, s.est_systeme = company, nom, list(permissions), est_systeme
            ROLES.append(s)
    Role.objects = types.SimpleNamespace(
        filter=lambda company=None, nom=None, **k: QS(r for r in ROLES if r.company is company and nom in (None, r.nom)),
        create=lambda **k: Role(k["company"], k["nom"], k["permissions"], k.get("est_systeme", True)))
    sys.modules["apps.roles.models"] = types.SimpleNamespace(Role=Role)

    class Item:
        Decision = types.SimpleNamespace(EN_ATTENTE="en_attente", MAINTENU="maintenu", REVOQUE="revoque")
        def __init__(s, user):
            s.user, s.decision, s.role_snapshot = user, "en_attente", {"role_id": user.role_id, "role_nom": user.role.nom}
            s.campagne = types.SimpleNamespace(statut="ouverte", company=user.company)
        def save(s, update_fields=None): pass
    sys.modules["apps.accessreview.models"] = types.SimpleNamespace(AccessReviewItem=Item)

    # vraies méthodes de CustomUser (ast) ; admins_actifs_qs = même prédicat que le vrai (roles_gerer | legacy admin | superuser)
    cls = next(n for n in ast.parse((DJ / "authentication/models.py").read_text(encoding="utf-8")).body
               if isinstance(n, ast.ClassDef) and n.name == "CustomUser")
    voulu = {"is_admin_role", "menu_tier", "tier_for_role", "est_dernier_proprietaire"}
    corps = [f for f in cls.body if isinstance(f, ast.FunctionDef) and f.name in voulu]
    ns = {}
    exec(compile(ast.fix_missing_locations(ast.Module(body=[ast.ClassDef(
        name="_M", bases=[], keywords=[], body=corps, decorator_list=[], type_params=[])], type_ignores=[])), "models.py", "exec"), ns)

    class User(ns["_M"]):
        ROLE_ADMIN, ROLE_RESPONSABLE, ROLE_NORMAL = "admin", "responsable", "normal"
        def __init__(s, username, company, role, is_protected=False):
            s.pk = s.id = len(USERS) + 1; s.username, s.company, s.role = username, company, role
            s.is_protected, s.is_superuser, s.is_active, s.is_staff = is_protected, False, True, False
            s.role_legacy = "admin" if "roles_gerer" in role.permissions else "normal"; USERS.append(s)
        role_id = property(lambda s: s.role.pk if s.role else None)
        company_id = property(lambda s: id(s.company))
        def save(s, update_fields=None): pass
        @staticmethod
        def admins_actifs_qs(company):
            return QS(u for u in USERS if u.is_active and u.company is company and (
                (u.role and "roles_gerer" in (u.role.permissions or [])) or (u.role is None and u.role_legacy == "admin")
                or u.is_superuser))
    ns["CustomUser"] = User
    am = types.ModuleType("authentication.models"); am.CustomUser = User; sys.modules["authentication.models"] = am
    charger("apps.roles.services", "apps/roles/services.py")
    SV = charger("apps.accessreview.services", "apps/accessreview/services.py")

    livres = dict(REG.CANONICAL_SYSTEM_ROLES)
    admin_roles = sorted(n for n, p in livres.items() if "roles_gerer" in p)  # = IsAdminRole (accessreview/views.py)
    CO = object()
    R = {n: Role(CO, n, livres[n]) for n in ("Directeur", "Commercial", "Commercial responsable", "Utilisateur")}
    owner = User("fondateur", CO, R["Directeur"], is_protected=True)
    pair = User("directeur2", CO, R["Directeur"])
    User("com1", CO, R["Commercial"]); User("com2", CO, R["Commercial"]); User("comresp", CO, R["Commercial responsable"])
    items = {u.username: Item(u) for u in USERS}
    ecran = RT.peut_gerer(pair, owner)
    refus = {}
    for cible in ("fondateur", "directeur2"):
        try: SV.attester(items[cible], decision="revoque", reviewer=pair)
        except Exception as e: refus[cible] = type(e).__name__  # noqa: BLE001 — un refus levé = garde présente
    src = (DJ / "apps/accessreview/services.py").read_text(encoding="utf-8")
    att = ast.unparse(next(n for n in ast.parse(src).body if isinstance(n, ast.FunctionDef) and n.name == "attester"))
    reste = [u.username for u in User.admins_actifs_qs(CO)]
    return {"roles_livres_IsAdminRole": admin_roles,
            "peut_gerer_directeur2_vers_fondateur": list(ecran),
            "attester_appelle_une_garde": any(k in att for k in ("peut_gerer", "is_protected", "est_dernier")),
            "refus_leves_par_attester": refus,
            "fondateur_apres_revue": {"role": owner.role.nom, "is_admin_role": owner.is_admin_role, "is_protected": owner.is_protected},
            "directeur2_apres_revue": pair.role.nom, "admins_restants": reste}


def sonde(ctx=None):
    sauve = {n: sys.modules.get(n) for n in MODS}
    try:
        o = scenario()
    finally:
        for n, m in sauve.items():
            if m is None: sys.modules.pop(n, None)
            else: sys.modules[n] = m
    repro = (not o["fondateur_apres_revue"]["is_admin_role"]) or not o["admins_restants"]
    return {"repro": repro, "observe": {"methode": "exécution (attester, remove_role_from_user, role_utilisateur, peut_gerer, "
                                        "méthodes CustomUser extraites par ast, registre vivant)", **o}}


if __name__ == "__main__":
    import json
    print(json.dumps(sonde(), ensure_ascii=False, indent=1))
