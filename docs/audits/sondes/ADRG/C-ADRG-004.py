# flake8: noqa  (sonde HÔTE d'audit PF4 « droits de la grille », groupe ADRG — sans Django, sans base, sans Docker)
"""C-ADRG-004 — `POST imports/dry-run/` cible `products` : la VRAIE vue `apps/dataimport/views.py::dry_run` (garde
`@permission_classes` exécutée, puis son corps : `_refus_droit_cible` → `services.dry_run` → `_analyser_conflits` → `_doublon_produit` →
`_diff_fields`) est jouée par rôle livré sur deux fiches produit FAUSSES (prix d'achat 812.40 et 0) ; bouchons au chemin :
le modèle `Produit`, `Response` (capture) et `_options_import` (défauts)."""
SONDE = {"constat": "C-ADRG-004", "sha": "29787bc59",
         "attendu": "des rôles sans prix_achat_voir (can_view_buy_prices faux) reçoivent 200 et conflits[].ecrasements[] champ prix_achat, ancienne = 812.40 et 0"}
import ast, importlib, importlib.machinery, importlib.util, inspect, pathlib, runpy, sys, textwrap, types
RACINE = pathlib.Path(__file__).resolve().parents[4]
if not (RACINE / "backend/django_core").is_dir(): RACINE = pathlib.Path.cwd()  # copie hors dépôt : jouée depuis la racine
DJ = RACINE / "backend/django_core"
# ── Noyau (recopié dans chaque sonde ADRG) : VRAIS modules de vues + VRAIES gardes ; Django/DRF = bouchons ──
class _M(type):  # classe-bouchon : attribut, appel, itération, opérateurs permissifs
    def __getattr__(c, n):
        if n[:2] == "__": raise AttributeError(n)
        s = _M(n, (_S,), {"_bouchon": True}); setattr(c, n, s); return s
    def __call__(c, *a, **k):
        if "_bouchon" not in c.__dict__: return type.__call__(c, *a, **k)
        return a[0] if len(a) == 1 and not k and callable(a[0]) else c
    __iter__ = lambda c: iter(()); __len__ = lambda c: 0; __getitem__ = lambda c, k: c; __bool__ = lambda c: True
    __or__ = __ror__ = __and__ = __add__ = __radd__ = __sub__ = __mul__ = __truediv__ = __mod__ = lambda c, o: c
class _S(metaclass=_M): _bouchon = True; __init__ = lambda s, *a, **k: None
class _Mod(types.ModuleType):  # module-bouchon ; un sous-module connu est importé pour de vrai
    def __getattr__(m, n):
        if n[:2] == "__": raise AttributeError(n)
        if f"{m.__name__}.{n}" in _CONNUS: return importlib.import_module(f"{m.__name__}.{n}")
        s = _M(n, (_S,), {"_bouchon": True}); setattr(m, n, s); return s
def _cmp(nom, f): return _PM(nom, (BasePermission,), {"has_permission": lambda s, r, v: f(r, v)})
class _PM(_M):  # métaclasse de BasePermission (DRF) : | & ~
    def __or__(a, b): return _cmp(f"{a.__name__}|{b.__name__}", lambda r, v: a().has_permission(r, v) or b().has_permission(r, v))
    def __and__(a, b): return _cmp(f"{a.__name__}&{b.__name__}", lambda r, v: a().has_permission(r, v) and b().has_permission(r, v))
    def __invert__(a): return _cmp(f"~{a.__name__}", lambda r, v: not a().has_permission(r, v))
class BasePermission(metaclass=_PM): has_permission = lambda s, r, v: True; has_object_permission = lambda s, r, v, o: True
class APIView: permission_classes = []; get_permissions = lambda s: [p() for p in s.permission_classes]  # défaut DRF
def _mx(*noms): return type("Mixin", (), {n: lambda s, *a, **k: None for n in noms})
_C, _U, _D, _L, _R = _mx("create"), _mx("update", "partial_update"), _mx("destroy"), _mx("list"), _mx("retrieve")
GVS = type("GenericViewSet", (APIView,), {})
def _action(methods=None, detail=None, url_path=None, url_name=None, **kw):  # DRF : kwargs = initkwargs de la route
    def d(f): f.mapping, f.kwargs, f.methodes = type("Map", (dict,), {"__getattr__": lambda s, n: lambda g: g})(), kw, [m.upper() for m in methods or ["get"]]; return f
    return d
def _deco(attr): return lambda val=None: lambda f: (setattr(f, attr, val), f)[1]
FAUX = {"rest_framework.permissions": dict(SAFE_METHODS=("GET", "HEAD", "OPTIONS"), BasePermission=BasePermission, AllowAny=BasePermission),
        "rest_framework.decorators": dict(action=_action, api_view=_deco("api_methods"), permission_classes=_deco("permission_classes")),
        "rest_framework.viewsets": dict(ModelViewSet=type("ModelViewSet", (_C, _R, _U, _D, _L, GVS), {}), GenericViewSet=GVS, ViewSet=GVS,
                                        ReadOnlyModelViewSet=type("ReadOnlyModelViewSet", (_R, _L, GVS), {})),
        "rest_framework.mixins": dict(CreateModelMixin=_C, UpdateModelMixin=_U, DestroyModelMixin=_D, ListModelMixin=_L, RetrieveModelMixin=_R),
        "rest_framework.views": dict(APIView=APIView)}
REELS = {n: n.replace(".", "/") + ".py" for n in ("authentication.permissions", "apps.roles.permissions", "core.permissions", "core.viewsets", "apps.stock.permissions")}
_CONNUS = set()
class _Chercheur:
    def find_spec(s, nom, path=None, target=None):
        if nom in REELS: return importlib.util.spec_from_file_location(nom, DJ / REELS[nom])
        return None if nom.split(".")[0] in sys.stdlib_module_names else importlib.machinery.ModuleSpec(nom, s, is_package=True)
    def create_module(s, spec): m = _Mod(spec.name); m.__dict__.update(FAUX.get(spec.name, {})); return m
    def exec_module(s, m): pass
def charger(noms):
    """Charge les modules RÉELS ``noms`` (+ gardes) ; rend (modules, registre vivant, Utilisateur, restaurer)."""
    REELS.update({n: n.replace(".", "/") + ".py" for n in noms}); _CONNUS.update(REELS, FAUX)
    gardes = {n: sys.modules.pop(n) for n in list(sys.modules) if n.split(".")[0] in ("apps", "authentication", "core", "django", "rest_framework")}
    avant, ch, pyc = set(sys.modules), _Chercheur(), sys.dont_write_bytecode; sys.meta_path.insert(0, ch); sys.dont_write_bytecode = True  # rien sur disque
    def restaurer(): sys.meta_path.remove(ch); [sys.modules.pop(n) for n in set(sys.modules) - avant]; sys.modules.update(gardes); sys.dont_write_bytecode = pyc
    try:
        reg = runpy.run_path(str(DJ / "apps/roles/permissions_registre.py"))
        auth = importlib.import_module("authentication.permissions")
        auth.enregistrer_registre_modules(reg["PERMISSION_MODULE"], octrois_lecture=reg["OCTROIS_LECTURE"])  # = RolesConfig.ready()
        APIView.permission_classes = [auth.IsAuthenticatedInterne]  # DEFAULT_PERMISSION_CLASSES du projet
        mods = {n: importlib.import_module(n) for n in noms}
        cu = next(n for n in ast.walk(ast.parse((DJ / "authentication/models.py").read_text(encoding="utf-8"))) if isinstance(n, ast.ClassDef) and n.name == "CustomUser")
        ns = {}; exec("class Utilisateur:\n ROLE_ADMIN, ROLE_RESPONSABLE = 'admin', 'responsable'\n" + "".join(  # VRAIES propriétés de CustomUser
            textwrap.indent(ast.unparse(f), " ") + "\n" for f in cu.body if isinstance(f, ast.FunctionDef) and f.name in
            ("is_responsable", "is_admin_role", "_role_grants_write", "has_erp_permission", "can_view_buy_prices")), ns)
    except Exception:
        restaurer(); raise
    return mods, reg, ns["Utilisateur"], restaurer
def roles(reg): return [(n, set(p)) for n, p in reg["CANONICAL_SYSTEM_ROLES"] if n not in dict(reg["CANONICAL_PORTAIL_ROLES"])]  # rôles LIVRÉS internes
def utilisateur(U, nom, perms):
    u = U(); u.__dict__.update(is_superuser=False, is_authenticated=True, portee="interne", role_id=1, role_legacy="normal", pk=1, id=1, company_id=1,
                               role=types.SimpleNamespace(nom=nom, permissions=sorted(perms), est_systeme=True), company=types.SimpleNamespace(id=1, pk=1))
    return u
def _h(Vue, nom): return next((k.__dict__[nom] for k in Vue.__mro__ if nom in k.__dict__), None)
def garde(Vue, action, methode, u, corps=None):
    """VRAIE résolution DRF : initkwargs de l'@action posés sur l'instance, puis la vraie get_permissions()."""
    v = object.__new__(Vue)
    for k, val in (getattr(_h(Vue, action), "kwargs", None) or {}).items(): setattr(v, k, val)
    v.action, v.kwargs, v.format_kwarg = action, {"pk": 1}, None
    v.request = types.SimpleNamespace(method=methode, user=u, data=corps or {}, query_params={})
    perms = v.get_permissions()
    inconnues = [p.__name__ for p in perms if isinstance(p, type)]  # classe non chargée : jamais comptée « passe »
    return not inconnues and all(p.has_permission(v.request, v) for p in perms), [type(p).__name__ for p in perms if not isinstance(p, type)] + inconnues
def corps_lit(Vue, noms, marques):
    """Le corps de l'action (ou de son perform_*) lit-il le droit ? (garde éventuelle hors permission_classes)"""
    src = [inspect.getsource(h) for h in (n if callable(n) else _h(Vue, n) for n in noms) if callable(h) and getattr(h, "__module__", "") in REELS]
    return any(m in s for s in src for m in marques)
def routes(Vue):
    """Routes d'écriture servies : CRUD présents (``http_method_names`` respecté) + @action d'écriture."""
    if "_fn" in Vue.__dict__: return [(None, m) for m in Vue._fn if m != "GET"]  # vue-fonction @api_view
    hm = next((k.__dict__["http_method_names"] for k in Vue.__mro__ if "http_method_names" in k.__dict__), None)
    out, acts = [(a, m) for a, m in (("create", "POST"), ("update", "PUT"), ("partial_update", "PATCH"), ("destroy", "DELETE")) if _h(Vue, a)], {}
    for k in reversed(Vue.__mro__): acts.update({n: f for n, f in k.__dict__.items() if isinstance(getattr(f, "methodes", None), list)})
    out += [(n, next(m for m in f.methodes if m != "GET")) for n, f in acts.items() if set(f.methodes) - {"GET"}]
    return [(a, m) for a, m in out if not isinstance(hm, (list, tuple)) or m.lower() in hm]
def vue_fonction(f):  # @api_view : DRF fabrique WrappedAPIView (__module__ = celui de la fonction, permission_classes du décorateur)
    return type(f.__name__, (APIView,), {"__module__": f.__module__, "_fn": f.api_methods, "_fobj": f, "permission_classes": getattr(f, "permission_classes", APIView.permission_classes)})
PERFORM = {"create": "perform_create", "update": "perform_update", "partial_update": "perform_update", "destroy": "perform_destroy"}
from decimal import Decimal
NOMMES = {"Commercial responsable", "Commercial", "Commercial terrain", "Technicien responsable", "Technicien", "Responsable", "Admin RH", "Admin Ventes"}
CSV = b"sku,nom,prix_achat,prix_vente\nPV-450,Panneau PV-450,999,1500\nPV-000,Panneau PV-000,5,1500\n"

class Produit:  # fiche existante (fausse) de la société
    _meta = types.SimpleNamespace(label_lower="stock.produit")
    def __init__(s, sku, prix): s.pk, s.sku, s.nom, s.prix_achat, s.prix_vente = hash(sku) % 97, sku, f"Panneau {sku}", prix, Decimal("1500")
    def __str__(s): return s.nom
CATALOGUE = {"PV-450": Produit("PV-450", Decimal("812.40")), "PV-000": Produit("PV-000", Decimal("0"))}
Produit.objects = types.SimpleNamespace(filter=lambda **kw: types.SimpleNamespace(first=lambda: CATALOGUE.get(kw.get("sku"))))

def sonde(ctx=None):
    mods, reg, U, restaurer = charger(["apps.dataimport.views", "apps.dataimport.services", "apps.dataimport.parsing"])
    try:
        V = mods["apps.dataimport.views"]
        importlib.import_module("apps.stock.models").Produit = Produit
        V.Response = lambda data=None, status=200, **k: types.SimpleNamespace(data=data, status_code=status)
        V._options_import = lambda request, options: {}; Vue, sortie, g = vue_fonction(V.dry_run), {}, None  # options : défauts (mode creer)
        for nom, perms in roles(reg):
            u = utilisateur(U, nom, perms)
            ok, g = garde(Vue, None, "POST", u)
            if not ok: continue
            fichier = types.SimpleNamespace(name="produits.csv", size=len(CSV), read=lambda: CSV)
            r = V.dry_run(types.SimpleNamespace(method="POST", user=u, FILES={"file": fichier}, data={"target": "products"}))
            vus = [e["ancienne"] for c in (r.data or {}).get("conflits", []) for e in c.get("ecrasements", []) if e.get("champ") == "prix_achat"]
            sortie[nom] = {"statut": r.status_code, "prix_achat_actuel_rendu": vus, "can_view_buy_prices": u.can_view_buy_prices}
    finally:
        restaurer()
    fuite = sorted(n for n, s in sortie.items() if s["statut"] == 200 and s["prix_achat_actuel_rendu"] and not s["can_view_buy_prices"])
    return {"repro": bool(NOMMES & set(fuite)), "observe": {
        "methode": "exécution de la vraie vue dry_run (garde + corps + services réels), rôles du registre vivant", "route": "POST imports/dry-run/ target=products", "garde_executee": g, "droit_attendu": "prix_achat_voir",
        "roles_sans_le_droit_qui_recoivent_le_prix_achat": fuite, "detail_par_role": sortie}}

if __name__ == "__main__":
    import json
    print(json.dumps(sonde(), ensure_ascii=False, indent=1))
