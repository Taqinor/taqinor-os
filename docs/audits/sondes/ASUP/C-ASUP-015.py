"""Rejoue crm/leads_attribution.py::_leads_ouverts_count : la charge d'un commercial (rotation équilibrée) compte ses leads archivés, seul is_deleted étant filtré par le manager."""
SONDE = {"constat": "C-ASUP-015", "sha": "3acfee471",
         "attendu": "3 leads archivés + 1 lead ouvert (+1 supprimé) du même commercial : _leads_ouverts_count rend 4 au lieu de 1"}
import ast, pathlib, sys, types
sys.dont_write_bytecode = True
RACINE = pathlib.Path(__file__).resolve().parents[4]
if not (RACINE / "backend/django_core").is_dir(): RACINE = pathlib.Path.cwd()
DJ = RACINE / "backend/django_core"


class Obj:
    def __init__(self, **kw): self.__dict__.update(kw)


def _ok(o, k, v):
    if k.endswith("__in"): return getattr(o, k[:-4], None) in v
    return getattr(o, k, None) == v


class QS:
    def __init__(self, items): self.items = list(items)
    def filter(self, *a, **kw): return QS(o for o in self.items if all(_ok(o, k, v) for k, v in kw.items()))
    def exclude(self, *a, **kw): return QS(o for o in self.items if not all(_ok(o, k, v) for k, v in kw.items()))
    def count(self): return len(self.items)


def extraire(rel, qual):
    nodes = ast.parse((DJ / rel).read_text(encoding="utf-8")).body
    for p in qual.split("."):
        n = next(x for x in nodes if isinstance(x, (ast.FunctionDef, ast.ClassDef)) and x.name == p); nodes = n.body
    n.decorator_list = []
    return ast.unparse(n)


def lire_etapes():  # STAGES.py lu par ast : aucune étape écrite ici
    ns = {}; exec(compile(ast.parse((RACINE / "STAGES.py").read_text(encoding="utf-8")), "STAGES.py", "exec"), ns)
    return types.SimpleNamespace(**{k: v for k, v in ns.items() if k.isupper()})


def sonde(ctx=None):
    st = lire_etapes(); ouvert = st.STAGES[0]
    u = Obj(pk=7)
    mk = lambda arch, supp: Obj(owner=u, perdu=False, stage=ouvert, is_archived=arch, is_deleted=supp)
    leads = [mk(True, False) for _ in range(3)] + [mk(False, False), mk(False, True)]

    class Lead:  # core/models.py::SoftDeleteManager : objects = leads non supprimés
        objects = QS(l for l in leads if not l.is_deleted)
    mgr = (DJ / "core/models.py").read_text(encoding="utf-8")
    ns = {"Lead": Lead, "stages": st}
    exec(extraire("apps/crm/leads_attribution.py", "_leads_ouverts_count"), ns)
    n = ns["_leads_ouverts_count"](u)
    return {"repro": n > 1 and "is_archived=False" not in mgr, "observe": {
        "leads_ouverts_comptes": n, "attendu_metier": 1, "archives_dans_le_lot": 3,
        "manager_filtre_is_deleted": "is_deleted=False" in mgr, "methode": "execution"}}


if __name__ == "__main__":
    print(sonde())
