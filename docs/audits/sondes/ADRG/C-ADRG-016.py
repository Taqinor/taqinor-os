# flake8: noqa  (sonde hôte PF4 « droits de la grille », groupe ADRG — sans Django, sans base)
"""C-ADRG-016 — la synchronisation hors ligne enregistre les mesures d'une visite sans « Modifier » des visites.
Exécute la VRAIE garde de `POST /offlinesync/operations/batch/` (`OfflineSyncBatchView`) et de `…/resoudre/`, puis
le VRAI handler `h_visite_mesures` → VRAI service `visites/services.py::appliquer_mesures_hors_ligne` (ast ; ORM, gel,
enregistrement bouchonnés) par rôle LIVRÉ, visite d'un AUTRE commercial puis la sienne. Code attendu : `PERMISSIONS_ECRITURE['mesures']`."""
SONDE = {"constat": "C-ADRG-016", "sha": "29787bc59",
         "attendu": "Technicien responsable (sans visites_modifier) : batch passe et la mesure est enregistrée sur la "
                    "visite d'un autre ; d'autres rôles sans le code l'enregistrent sur leur propre visite"}
import ast, builtins, importlib.util, pathlib, sys, types
RACINE = pathlib.Path(__file__).resolve().parents[4]
if not (RACINE / "backend/django_core").is_dir(): RACINE = pathlib.Path.cwd()  # copie hors dépôt : jouée depuis la racine
DJ = RACINE / "backend/django_core"
BOUCHONS = ("rest_framework", "rest_framework.permissions", "django", "django.core", "django.core.exceptions",
            "authentication", "apps", "apps.roles")
CHARGES = (("apps.roles.permissions_registre", "apps/roles/permissions_registre.py"),
           ("authentication.permissions", "authentication/permissions.py"), ("apps.roles.permissions", "apps/roles/permissions.py"))
# ── noyau commun (recopié dans chaque sonde ADRG, aucune dépendance partagée) ──
class _MP(type):  # composition DRF : A | B, A & B
    def __or__(a, b): return _MP("Ou", (_BP,), {"has_permission": lambda s, r, v: a().has_permission(r, v) or b().has_permission(r, v)})
    def __and__(a, b): return _MP("Et", (_BP,), {"has_permission": lambda s, r, v: a().has_permission(r, v) and b().has_permission(r, v)})
class _BP(metaclass=_MP):  # rest_framework.permissions.BasePermission
    def has_permission(s, r, v): return True
    def has_object_permission(s, r, v, o): return True
def _arbre(rel, _c={}): return _c[rel] if rel in _c else _c.setdefault(rel, ast.parse((DJ / rel).read_text(encoding="utf-8")))
def _classe(rel, nom): return next(n for n in ast.walk(_arbre(rel)) if isinstance(n, ast.ClassDef) and n.name == nom)
def _fonction(rel, nom): return next(n for n in ast.walk(_arbre(rel)) if isinstance(n, ast.FunctionDef) and n.name == nom)
def _eval(noeud, rel, ns): _completer(noeud, rel, ns); return eval(compile(ast.Expression(noeud), rel, "eval"), ns)
def _exec(noeuds, ns, rel="x.py"): exec(compile(ast.Module(body=list(noeuds), type_ignores=[]), rel, "exec"), ns); return ns
def _completer(noeud, rel, ns):  # résout dans le fichier réel (et ses imports) les noms globaux libres du code exécuté
    locaux = {n.id for n in ast.walk(noeud) if isinstance(n, ast.Name) and isinstance(n.ctx, ast.Store)}
    locaux |= {a.arg for n in ast.walk(noeud) if isinstance(n, ast.arguments) for a in n.args + n.kwonlyargs}
    for n in ast.walk(noeud):
        if isinstance(n, ast.Name) and n.id not in ns and n.id not in locaux and not hasattr(builtins, n.id):
            try: ns[n.id] = _constante(n.id, rel, ns)
            except KeyError: pass
def _constante(nom, rel, ns):
    for n in _arbre(rel).body:
        if isinstance(n, ast.Assign) and any(getattr(t, "id", None) == nom for t in n.targets): return _eval(n.value, rel, ns)
        if isinstance(n, ast.FunctionDef) and n.name == nom: return _exec([n], dict(ns), rel)[nom]
        if isinstance(n, ast.ImportFrom) and any((a.asname or a.name) == nom for a in n.names):
            base = pathlib.Path(rel).parent if n.level else pathlib.Path()
            for _ in range(max(n.level - 1, 0)): base = base.parent
            chemin = base.joinpath(*(n.module or "").split("."))
            for cand in (chemin.with_suffix(".py"), chemin / "__init__.py"):
                if (DJ / cand).is_file(): return _constante(next(a.name for a in n.names if (a.asname or a.name) == nom), cand.as_posix(), ns)
    raise KeyError(nom)
def noyau():  # registre vivant + VRAIES classes de permission sous bouchons DRF minimaux → (registre, espace, sauvegarde)
    sauve = {n: sys.modules.get(n) for n in BOUCHONS + tuple(n for n, _ in CHARGES)}
    for n in BOUCHONS: sys.modules[n] = types.ModuleType(n)
    sys.modules["rest_framework.permissions"].__dict__.update(SAFE_METHODS=("GET", "HEAD", "OPTIONS"), BasePermission=_BP)
    sys.modules["django.core.exceptions"].ImproperlyConfigured = RuntimeError
    mods = []
    for nom, rel in CHARGES:
        spec = importlib.util.spec_from_file_location(nom, DJ / rel); m = importlib.util.module_from_spec(spec)
        sys.modules[nom] = m; spec.loader.exec_module(m); mods.append(m)
    reg, ap, rp = mods
    ap.enregistrer_registre_modules(reg.PERMISSION_MODULE, octrois_lecture=reg.OCTROIS_LECTURE)
    return reg, {k: v for m in (ap, rp) for k, v in vars(m).items() if not k.startswith("__")}, sauve
def restaurer(sauve):
    for n, m in sauve.items(): sys.modules.pop(n, None) if m is None else sys.modules.__setitem__(n, m)
def roles(reg):  # rôles internes LIVRÉS, tels que le registre les sème
    portail = {n for n, _ in reg.CANONICAL_PORTAIL_ROLES}; return [(n, list(p)) for n, p in reg.CANONICAL_SYSTEM_ROLES if n not in portail]
def compte(reg, nom, perms, uid=7):  # faux compte ; propriétés RÉELLES de CustomUser (is_responsable, is_admin_role…)
    cls = _classe("authentication/models.py", "CustomUser")
    d = _exec([n for n in cls.body if isinstance(n, ast.FunctionDef) and (n.name in (
        "is_responsable", "is_admin_role", "_role_grants_write", "has_erp_permission") or n.name.startswith("can_view_"))], {})
    d.update({t.targets[0].id: t.value.value for t in cls.body if isinstance(t, ast.Assign)
              and getattr(t.targets[0], "id", "").startswith("ROLE_") and isinstance(t.value, ast.Constant)})
    u = type("Compte", (), {k: v for k, v in d.items() if not k.startswith("__")})()
    role = types.SimpleNamespace(id=1, pk=1, nom=nom, permissions=list(perms), est_systeme=True,
                                 perimetre=reg.SYSTEM_ROLE_PERIMETRES.get(nom), entites_visibles=["E1"])
    u.__dict__.update(id=uid, pk=uid, is_superuser=False, is_authenticated=True, portee="interne", role=role, role_id=1,
                      role_legacy="normal", company=types.SimpleNamespace(id=1), company_id=1)
    return u
def gardes(rel, classe, action, req, ns):  # comme DRF : garde de l'@action sur l'instance, puis VRAIE get_permissions
    cls, ns = _classe(rel, classe), dict(ns)
    corps = {n.name: n for n in cls.body if isinstance(n, ast.FunctionDef)}
    attrs = {n.targets[0].id: _eval(n.value, rel, ns) for n in cls.body if isinstance(n, ast.Assign)
             and getattr(n.targets[0], "id", "") in ("permission_classes", "permission_module")}
    decl = [_eval(kw.value, rel, ns) for d in getattr(corps.get(action), "decorator_list", [])
            for kw in getattr(d, "keywords", []) if kw.arg == "permission_classes"]
    attrs.setdefault("permission_classes", [ns["IsAuthenticatedInterne"]])  # défaut projet (ASEC51)
    v = type(classe, (), {"__module__": rel[:-3].replace("/", "."), **attrs})()
    v.action, v.request = action, req
    if decl:
        h = lambda *a, **k: None; h.kwargs = {"permission_classes": decl[0]}; setattr(v, action, h); v.permission_classes = decl[0]
    if "get_permissions" in corps:
        _completer(corps["get_permissions"], rel, ns); return _exec([corps["get_permissions"]], ns, rel)["get_permissions"](v), v
    return [c() for c in v.permission_classes], v
def gardes_fonction(rel, nom, req, ns):  # vue @api_view : DRF pose WrappedAPIView.__module__ = func.__module__
    f = _fonction(rel, nom)
    pc = next(d.args[0] for d in f.decorator_list if isinstance(d, ast.Call) and getattr(d.func, "id", "") == "permission_classes")
    v = type("WrappedAPIView", (), {"__module__": rel[:-3].replace("/", ".")})(); v.request = req
    return [c() for c in _eval(pc, rel, dict(ns))], v
def passe(liste_v, req, obj=None):
    liste, v = liste_v
    ok = all(p.has_permission(req, v) for p in liste)
    return ok and (obj is None or all(p.has_object_permission(req, v, obj) for p in liste))
def requete(reg, nom, perms, methode="GET", corps=None, query=None):
    return types.SimpleNamespace(user=compte(reg, nom, perms), method=methode, data=corps or {}, query_params=query or {})
# ── fin du noyau commun ──
def sonde(ctx=None):
    reg, ns, sauve = noyau()
    attendu = next(ast.literal_eval(n.value) for n in ast.walk(_arbre("apps/visites/views.py")) if isinstance(n, ast.Assign)
                   and getattr(n.targets[0], "id", "") == "PERMISSIONS_ECRITURE")["mesures"]
    autres = ("core", "core.permissions", "apps.visites", "apps.visites.models", "apps.visites.services")
    sauve.update({n: sys.modules.get(n) for n in autres})
    ecrit = []
    try:
        for n in autres: sys.modules[n] = types.ModuleType(n)
        sys.modules["core.permissions"]._user_has_or_legacy = _exec([_fonction("core/permissions.py", "_user_has_or_legacy")], {})["_user_has_or_legacy"]
        visite = types.SimpleNamespace(id=42, commercial_id=999, modifiable=True, raison_lecture_seule="", mesures={})
        qs = types.SimpleNamespace(first=lambda: visite)
        sys.modules["apps.visites.models"].VisiteTerrain = types.SimpleNamespace(objects=types.SimpleNamespace(filter=lambda **k: qs))
        def enregistrer(v, cat, val): ecrit.append(cat); v.mesures[cat] = val; return v, {}
        sns = {"__name__": "apps.visites.services", "__package__": "apps.visites", "enregistrer_mesures": enregistrer,
               "refus_transition": lambda v, a: None, "_MESSAGE_TERMINEE": "terminée"}
        sys.modules["apps.visites.services"].appliquer_mesures_hors_ligne = _exec(
            [_fonction("apps/visites/services.py", "appliquer_mesures_hors_ligne")], sns)["appliquer_mesures_hors_ligne"]
        class OfflineOpError(Exception): pass
        handler = _exec([_fonction("apps/offlinesync/handlers.py", "h_visite_mesures")], {"OfflineOpError": OfflineOpError})["h_visite_mesures"]
        res, garde = {"toute_visite": [], "sa_visite_seulement": []}, {}
        for nom, perms in roles(reg):
            req, ok = requete(reg, nom, perms, "POST", {"operations": []}), {}
            for c in ("OfflineSyncBatchView.post", "OfflineOperationViewSet.resoudre"):
                g = gardes("apps/offlinesync/views.py", *c.split("."), req, ns); garde[c] = [type(p).__name__ for p in g[0]]; ok[c] = passe(g, req)
            if not ok["OfflineSyncBatchView.post"] or attendu in perms: continue
            for cle, commercial in (("toute_visite", 999), ("sa_visite_seulement", req.user.id)):
                visite.commercial_id, avant = commercial, len(ecrit)
                try: handler(req.user.company, req.user, {"visite": 42, "categorie": "toiture", "valeurs": {"pente": 30}})
                except OfflineOpError: continue
                if len(ecrit) > avant: res[cle].append(nom); break
    finally:
        restaurer(sauve)
    return {"repro": bool(res["toute_visite"]), "observe": {
        "methode": "exécution de la vraie garde + vrai handler + vrai service (ast)", "code_attendu": attendu,
        "gardes_trouvees": garde, "roles_livres_sans_le_code_dont_la_mesure_est_enregistree": res,
        "emplacements_controles": 2}}
