"""Rejoue ventes/domain/recouvrement.py::_nudge_suppressed (avec les vrais get_company_lead et peut_contacter du CRM) : la relance d'un devis envoyé n'est pas supprimée pour un lead archivé ou perdu, seulement pour un opposé."""
SONDE = {"constat": "C-ASUP-016", "sha": "3acfee471",
         "attendu": "lead archivé ou perdu : _nudge_suppressed rend False (la relance part) alors que l'opposé rend True"}
import ast, datetime, logging, pathlib, sys, types
sys.dont_write_bytecode = True
RACINE = pathlib.Path(__file__).resolve().parents[4]
if not (RACINE / "backend/django_core").is_dir(): RACINE = pathlib.Path.cwd()
DJ = RACINE / "backend/django_core"


class Obj:
    def __init__(self, **kw): self.__dict__.update(kw)


class QS:
    def __init__(self, items): self.items = list(items)
    def filter(self, *a, **kw): return QS(o for o in self.items if all(getattr(o, k, None) == v for k, v in kw.items()))
    def order_by(self, *a): return self
    def first(self): return self.items[0] if self.items else None


def extraire(rel, qual):
    class SansRelatif(ast.NodeTransformer):
        def visit_ImportFrom(self, n): return ast.Pass() if n.level else n
    nodes = ast.parse((DJ / rel).read_text(encoding="utf-8")).body
    for p in qual.split("."):
        n = next(x for x in nodes if isinstance(x, (ast.FunctionDef, ast.ClassDef)) and x.name == p); nodes = n.body
    n.decorator_list = []
    return ast.unparse(ast.fix_missing_locations(SansRelatif().visit(n)))


class Lead: objects = QS([])


def _jouer(f, co, **etat):
    lead = Lead(); lead.__dict__.update(pk=5, company=co, relance_date=None, **etat)
    Lead.objects = QS([lead])
    return f(Obj(pk=99, lead_id=5, company=co), datetime.date(2026, 11, 11))


def sonde(ctx=None):
    ns = {"Lead": Lead}
    for rel, nom in (("apps/crm/fiche_selectors.py", "get_company_lead"), ("apps/crm/portee_selectors.py", "peut_contacter")):
        exec(extraire(rel, nom), ns)
    mods = {n: types.ModuleType(n) for n in ("apps", "apps.crm", "apps.crm.selectors", "apps.ventes", "apps.ventes.models")}
    sel = mods["apps.crm.selectors"]
    sel.get_company_lead, sel.peut_contacter = ns["get_company_lead"], ns["peut_contacter"]
    sel.devis_a_cadence_active = lambda pk: False
    mods["apps.crm"].selectors = sel; mods["apps"].crm = mods["apps.crm"]
    mods["apps.ventes.models"].ShareLink = type("ShareLink", (), {"objects": QS([])})
    avant = {n: sys.modules.get(n) for n in mods}
    sys.modules.update(mods)
    try:
        g = {"logger": logging.getLogger("sonde")}
        exec(extraire("apps/ventes/domain/recouvrement.py", "_nudge_suppressed"), g)
        if "def _lead_ecarte" in (DJ / "apps/ventes/domain/recouvrement.py").read_text(encoding="utf-8"):
            exec(extraire("apps/ventes/domain/recouvrement.py", "_lead_ecarte"), g)  # ASUP42 — garde extraite
        f, co = g["_nudge_suppressed"], Obj(pk=1)
        base = dict(is_archived=False, perdu=False, ne_plus_contacter=False)
        r = {nom: _jouer(f, co, **{**base, **kw}) for nom, kw in (
            ("archive", {"is_archived": True}), ("perdu", {"perdu": True}),
            ("oppose_temoin", {"ne_plus_contacter": True}), ("normal", {}))}
    finally:
        for n, m in avant.items():
            if m is None: sys.modules.pop(n, None)
            else: sys.modules[n] = m
    return {"repro": r["oppose_temoin"] is True and (r["archive"] is False or r["perdu"] is False),
            "observe": {"supprimee": r, "attendu_metier": "True pour archive, perdu, oppose", "methode": "execution"}}


if __name__ == "__main__":
    print(sonde())
