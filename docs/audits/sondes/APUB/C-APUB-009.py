"""Rejoue la vraie garde d'écriture de apps/adsengine/views.py::FlightPlanViewSet et ::FlightPhaseViewSet (héritée d'AdsengineViewSet, lue par la vraie core/permissions.py::ScopedPermission) contre les rôles LIVRÉS du registre vivant : `adsengine_manage` suffit, `adsengine_flightplan_manage` n'est exigé par aucune route."""
SONDE = {"constat": "C-APUB-009", "sha": "ae5a7ae4c",
         "attendu": "Commercial, Technicien, Responsable (sans adsengine_flightplan_manage) passent POST/PATCH/DELETE ; Viewer refusé ; 0 route hors registre n'exige le code"}
import ast, builtins, pathlib, runpy, types
RACINE = pathlib.Path(__file__).resolve().parents[4]
if not (RACINE / "backend/django_core").is_dir(): RACINE = pathlib.Path.cwd()  # copie hors dépôt : jouée depuis la racine
DJ = RACINE / "backend/django_core"
CODE = "adsengine_flightplan_manage"
VUES = ("FlightPlanViewSet", "FlightPhaseViewSet")
METHODES = {"POST": "create", "PATCH": "partial_update", "DELETE": "destroy"}


class A:  # objet permissif : décorateurs @action/@extend_schema, sérialiseurs, querysets
    def __init__(s, *a, **k): pass
    def __call__(s, *a, **k): return a[0] if len(a) == 1 and callable(a[0]) and not k else A()
    def __getattr__(s, n): return A()


def executer(chemin, noms, ns, classe=None):
    """Exécute dans ``ns`` les définitions de premier niveau ``noms`` (ou les méthodes ``noms`` de ``classe``) du vrai fichier."""
    arbre = ast.parse((DJ / chemin).read_text(encoding="utf-8"))
    corps = next(n for n in arbre.body if isinstance(n, ast.ClassDef) and n.name == classe).body if classe else arbre.body
    garde = [n for n in corps if getattr(n, "name", None) in noms]
    for n in garde:
        for x in ast.walk(n):
            if isinstance(x, ast.Name) and isinstance(x.ctx, ast.Load) and x.id not in ns and not hasattr(builtins, x.id):
                ns[x.id] = A()
    for n in garde: ns.pop(n.name, None)
    exec(compile(ast.Module(body=garde, type_ignores=[]), chemin, "exec"), ns)
    return ns


def garde_reelle():
    perms = executer("core/permissions.py", {"_user_has_or_legacy", "ScopedPermission", "declared_action_permissions",
                                             "WriteScopedPermissionMixin"},
                     {"SAFE_METHODS": ("GET", "HEAD", "OPTIONS"), "BasePermission": object})
    user_ns = executer("authentication/models.py", {"has_erp_permission"}, {}, classe="CustomUser")

    class CompanyScopedModelViewSet:  # core/viewsets.py : permission_classes = [ScopedPermission], get_permissions DRF
        permission_classes = [perms["ScopedPermission"]]
        def get_permissions(self): return [p() for p in self.permission_classes]
    vues = executer("apps/adsengine/views.py", {"AdsengineViewSet", *VUES},
                    {"CompanyScopedModelViewSet": CompanyScopedModelViewSet})
    return vues, user_ns["has_erp_permission"]


def passe(vue_cls, has_perm, permissions, methode):
    user = types.SimpleNamespace(is_authenticated=True, is_superuser=False, portee="interne", is_responsable=False,
                                 role=types.SimpleNamespace(permissions=list(permissions)))
    user.has_erp_permission = lambda code: has_perm(user, code)
    vue = vue_cls(); vue.action = METHODES[methode]
    req = types.SimpleNamespace(method=methode, user=user)
    return all(p.has_permission(req, vue) for p in vue.get_permissions())


def routes_exigeant_le_code():
    trouve = []
    for p in sorted((DJ / "apps").rglob("*.py")):
        rel = p.relative_to(DJ).as_posix()
        if "/tests" in rel or "/migrations/" in rel or p.name.startswith("test") or rel.endswith("permissions_registre.py"):
            continue
        if CODE in p.read_text(encoding="utf-8", errors="ignore"): trouve.append(rel)
    return trouve


def sonde(ctx=None):
    reg = runpy.run_path(str(DJ / "apps/roles/permissions_registre.py"))
    vues, has_perm = garde_reelle()
    internes = [(n, p) for n, p in reg["CANONICAL_SYSTEM_ROLES"] if not all(c.startswith("portail_") for c in p)]
    matrice, touches = {}, []
    for nom, p in internes:
        ok = {f"{v}:{m}": passe(vues[v], has_perm, p, m) for v in VUES for m in METHODES}
        matrice[nom] = {"a_le_code": CODE in p, "ecrit": all(ok.values())}
        if any(ok.values()) and CODE not in p: touches.append(nom)
    exigeants = routes_exigeant_le_code()
    write_perm = {v: getattr(vues[v], "write_permission", None) for v in VUES}
    repro = bool(touches) and not exigeants
    return {"repro": repro, "observe": {
        "methode": "exécution (vraies ScopedPermission/_user_has_or_legacy/has_erp_permission + vraies classes de vue par ast ; "
                   "rôles = CANONICAL_SYSTEM_ROLES du registre vivant)",
        "routes": "POST/PATCH/DELETE /api/django/adsengine/plans-vol/ et phases-vol/ (CRUD ModelViewSet)",
        "write_permission_effectif": write_perm,
        "roles_livres_qui_ecrivent_sans_le_code": touches,
        "matrice_par_role": matrice,
        "fichiers_hors_registre_et_tests_citant_le_code": exigeants,
        "regle_3": "aucun appel Meta sur ce chemin (CRUD pur, non rejoué ici)"}}


if __name__ == "__main__":
    import json
    print(json.dumps(sonde(), ensure_ascii=False, indent=1))
