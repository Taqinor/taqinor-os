"""Rejoue notifications/views.py::NotificationViewSet (get_queryset, unread_count, mark_all_read) après le balayage de purge : le badge et « tout marquer lu » comptent les notifications archivées que la liste cache."""
SONDE = {"constat": "C-ASUP-017", "sha": "3acfee471",
         "attendu": "12 non lues archivées (70 j) + 3 récentes : la liste en montre 3, unread-count et read-all en comptent 15"}
import ast, datetime, pathlib, sys, types
sys.dont_write_bytecode = True
RACINE = pathlib.Path(__file__).resolve().parents[4]
if not (RACINE / "backend/django_core").is_dir(): RACINE = pathlib.Path.cwd()
DJ = RACINE / "backend/django_core"
NOW = datetime.datetime(2026, 11, 11, 12, 0)


class Obj:
    def __init__(self, **kw): self.__dict__.update(kw)


_OPS = {"gte": lambda a, b: a is not None and a >= b, "isnull": lambda a, b: (a is None) == b, "in": lambda a, b: a in b}


def _ok(o, k, v):
    base, _, op = k.rpartition("__")
    return _OPS[op](getattr(o, base, None), v) if base and op in _OPS else getattr(o, k, None) == v


class QS:
    def __init__(self, items): self.items = list(items)
    def filter(self, *a, **kw): return QS(o for o in self.items if all(_ok(o, k, v) for k, v in kw.items()))
    def count(self): return len(self.items)
    def values_list(self, champ, flat=False): return [getattr(o, champ) for o in self.items]
    def update(self, **kw):
        for o in self.items: o.__dict__.update(kw)
        return len(self.items)
    def __len__(self): return len(self.items)


def methode(nom):
    nodes = ast.parse((DJ / "apps/notifications/views.py").read_text(encoding="utf-8")).body
    cls = next(n for n in nodes if isinstance(n, ast.ClassDef) and n.name == "NotificationViewSet")
    n = next(m for m in cls.body if isinstance(m, ast.FunctionDef) and m.name == nom)
    n.decorator_list = []
    src = ast.unparse(n).replace("super().get_queryset()", "Base.get_queryset(self)")
    return src.replace("from . import severity as severity_module", "pass")


def sonde(ctx=None):
    me = Obj(pk=1)
    mk = lambda i, age: Obj(id=i, recipient=me, programmee_pour=None, read=False, archived=False,
                            created_at=NOW - datetime.timedelta(days=age), event_type="devis_nudge_due")
    notifs = [mk(i, 70) for i in range(12)] + [mk(i, 2) for i in range(12, 15)]
    for n in notifs:  # effet du balayage notifications-purge-anciennes : non lues > 60 j -> archived
        if n.created_at < NOW - datetime.timedelta(days=60): n.archived = True

    class Base:
        def get_queryset(self): return QS(notifs)
    ns = {"Base": Base, "timezone": types.SimpleNamespace(now=lambda: NOW), "choix_ou_400": lambda r, k, e: None,
          "_UNREAD_ENUM": (), "Response": dict, "severity_module": types.SimpleNamespace(is_action=lambda e: True)}
    for nom in ("get_queryset", "unread_count", "mark_all_read"): exec(methode(nom), ns)
    V = type("V", (Base,), {k: ns[k] for k in ("get_queryset", "unread_count", "mark_all_read")})
    v = V(); v.request = Obj(user=me, query_params={})
    v.action = "list"; liste = len(v.get_queryset())
    v.action = "unread_count"; badge = v.unread_count(v.request)["unread"]
    v.action = "mark_all_read"; lues = v.mark_all_read(v.request)["updated"]
    return {"repro": badge > liste or lues > liste, "observe": {
        "liste_visible": liste, "badge_unread_count": badge, "tout_marquer_lu_touche": lues,
        "archivees_par_le_balayage": sum(n.archived for n in notifs), "methode": "execution"}}


if __name__ == "__main__":
    print(sonde())
