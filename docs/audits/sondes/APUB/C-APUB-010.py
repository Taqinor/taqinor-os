"""Rejoue les vraies gardes d'écriture de apps/tiers/views.py::TiersViewSet (write_permission = None, lue par la vraie ScopedPermission) et de core/views.py::DashboardViewSet / ::SavedQueryViewSet (vraie IsAuthenticatedInterne) : les rôles livrés en lecture seule écrivent, et un collègue modifie ou supprime l'objet partagé d'un autre (vrais get_queryset / perform_update / perform_destroy)."""
SONDE = {"constat": "C-APUB-010", "sha": "ae5a7ae4c",
         "attendu": "Viewer et Utilisateur passent POST/PATCH/DELETE sur les 3 viewsets ; alice modifie et supprime le tableau et la requête partagés de bob"}
import ast, builtins, pathlib, runpy, types
RACINE = pathlib.Path(__file__).resolve().parents[4]
if not (RACINE / "backend/django_core").is_dir(): RACINE = pathlib.Path.cwd()  # copie hors dépôt : jouée depuis la racine
DJ = RACINE / "backend/django_core"
METHODES = {"POST": "create", "PATCH": "partial_update", "DELETE": "destroy"}


class A:  # objet permissif : décorateurs @action/@extend_schema, sérialiseurs, querysets
    def __init__(s, *a, **k): pass
    def __call__(s, *a, **k): return a[0] if len(a) == 1 and callable(a[0]) and not k else A()
    def __getattr__(s, n): return A()


class Refus(Exception): pass


class Q:  # django.db.models.Q réduit à ce que les get_queryset utilisent (égalité, __isnull, |)
    def __init__(s, **kw): s.kw, s.ou = kw, []
    def __or__(s, autre): r = Q(); r.ou = [s, autre]; return r
    def __call__(s, o):
        if s.ou: return any(q(o) for q in s.ou)
        return all((getattr(o, k[:-8]) is None) == v if k.endswith("__isnull") else getattr(o, k) == v for k, v in s.kw.items())


class QS(list):
    def filter(s, *qs, **kw): return QS(o for o in s if all(q(o) for q in qs) and all(getattr(o, k) == v for k, v in kw.items()))
    def distinct(s): return s


def executer(chemin, noms, ns, classe=None):
    """Exécute dans ``ns`` les définitions ``noms`` (de premier niveau, ou méthodes de ``classe``) du vrai fichier."""
    arbre = ast.parse((DJ / chemin).read_text(encoding="utf-8"))
    corps = next(n for n in arbre.body if isinstance(n, ast.ClassDef) and n.name == classe).body if classe else arbre.body
    garde = [n for n in corps if getattr(n, "name", None) in noms]
    for x in (x for n in garde for x in ast.walk(n)):
        if isinstance(x, ast.Name) and isinstance(x.ctx, ast.Load) and x.id not in ns and not hasattr(builtins, x.id):
            ns[x.id] = A()
    exec(compile(ast.Module(body=garde, type_ignores=[]), chemin, "exec"), ns)
    return ns


def charger(donnees):
    perms = executer("core/permissions.py", {"_user_has_or_legacy", "ScopedPermission", "declared_action_permissions",
                                             "WriteScopedPermissionMixin"},
                     {"SAFE_METHODS": ("GET", "HEAD", "OPTIONS"), "BasePermission": object})
    auth = executer("authentication/permissions.py", {"IsAuthenticatedInterne"}, {"BasePermission": object})
    user = executer("authentication/models.py", {"has_erp_permission", "_role_grants_write"}, {}, classe="CustomUser")

    class TenantMixin:  # core/mixins.py : queryset déjà filtré par société
        def get_queryset(self): return QS(o for o in donnees if o.company == self.request.user.company)

    class ModelViewSet:  # défauts DRF : get_permissions, get_object, perform_destroy
        permission_classes = []
        def get_permissions(self): return [p() for p in self.permission_classes]
        def get_object(self): return next(o for o in self.get_queryset() if o.pk == self.kwargs["pk"])
        def perform_destroy(self, instance): instance.delete()
    base = {"TenantMixin": TenantMixin, "viewsets": types.SimpleNamespace(ModelViewSet=ModelViewSet), "Q": Q,
            "PermissionDenied": Refus, "WriteScopedPermissionMixin": perms["WriteScopedPermissionMixin"],
            "IsAuthenticatedInterne": auth["IsAuthenticatedInterne"]}
    vues = executer("apps/tiers/views.py", {"TiersViewSet"}, dict(base))
    vues = executer("core/views.py", {"DashboardViewSet", "SavedQueryViewSet"}, dict(base, TiersViewSet=vues["TiersViewSet"]))
    return vues, user


def compte(nom, permissions, user_ns):
    u = types.SimpleNamespace(pk=nom, username=nom, is_authenticated=True, is_superuser=False, portee="interne",
                              is_responsable=False, company="C", role=types.SimpleNamespace(permissions=list(permissions)))
    u.has_erp_permission = lambda code: user_ns["has_erp_permission"](u, code)
    return u


def vue(vues, cls, user, methode, pk=None):
    v = vues[cls](); v.action, v.kwargs = METHODES[methode], {"pk": pk}
    v.request = types.SimpleNamespace(method=methode, user=user, data={})
    return v, all(p.has_permission(v.request, v) for p in v.get_permissions())


def sonde(ctx=None):
    reg = runpy.run_path(str(DJ / "apps/roles/permissions_registre.py"))
    vues, user_ns = charger([])
    lecture_seule = [(n, p) for n, p in reg["CANONICAL_SYSTEM_ROLES"]
                     if not user_ns["_role_grants_write"](p) and not all(c.startswith("portail_") for c in p)]
    ecritures = {n: {f"{c}:{m}": vue(vues, c, compte(n, p, user_ns), m)[1]
                     for c in ("TiersViewSet", "DashboardViewSet", "SavedQueryViewSet") for m in METHODES}
                 for n, p in lecture_seule}
    lecteurs_qui_ecrivent = [n for n, ok in ecritures.items() if any(ok.values())]
    autrui = {}
    for cls in ("DashboardViewSet", "SavedQueryViewSet"):
        traces = []
        bob = types.SimpleNamespace(pk="bob")
        objet = types.SimpleNamespace(pk=1, owner=bob, owner_id="bob", partage=True, company="C",
                                      delete=lambda: traces.append("supprimé"))
        vues, _ = charger([objet])
        alice = compte("alice", dict(reg["CANONICAL_SYSTEM_ROLES"])["Commercial"], user_ns)  # rôle livré
        res = {}
        for methode in ("PATCH", "DELETE"):
            v, _ok = vue(vues, cls, alice, methode, pk=1)
            try:
                if methode == "PATCH":
                    v.perform_update(types.SimpleNamespace(instance=objet, save=lambda **kw: traces.append("modifié")))
                else:
                    v.perform_destroy(v.get_object())
                res[methode] = "écrit"
            except Refus as exc:
                res[methode] = f"refusé ({exc})"
        autrui[cls] = {"visible_dans_get_queryset": objet in v.get_queryset(), **res, "effets": traces}
    objet_autrui = any(r[m] == "écrit" for r in autrui.values() for m in ("PATCH", "DELETE"))
    return {"repro": bool(lecteurs_qui_ecrivent) or objet_autrui, "observe": {
        "methode": "exécution (vraies ScopedPermission, IsAuthenticatedInterne, has_erp_permission, _role_grants_write, "
                   "classes de vue par ast ; TenantMixin/ModelViewSet DRF bouchonnés)",
        "routes": "/api/django/tiers/tiers/, /api/django/core/dashboards/, /api/django/core/saved-queries/",
        "write_permission_TiersViewSet": getattr(vues["TiersViewSet"], "write_permission", None),
        "roles_livres_lecture_seule": [n for n, _ in lecture_seule],
        "lecture_seule_qui_ecrivent": lecteurs_qui_ecrivent, "detail_ecritures": ecritures,
        "objet_partage_de_bob_par_alice (Commercial)": autrui}}


if __name__ == "__main__":
    import json
    print(json.dumps(sonde(), ensure_ascii=False, indent=1))
