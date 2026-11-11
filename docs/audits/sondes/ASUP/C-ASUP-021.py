"""Rejoue stock/services.py::cheapest_prix_fournisseur et exiger_fournisseur_commandable : le fournisseur le moins cher peut être un fournisseur archivé, et la garde d'achat ne refuse pas un fournisseur archivé."""
SONDE = {"constat": "C-ASUP-021", "sha": "3acfee471",
         "attendu": "cheapest_prix_fournisseur rend le fournisseur archivé (1 200) et exiger_fournisseur_commandable ne lève pas pour lui"}
import ast, datetime, pathlib, sys, types
sys.dont_write_bytecode = True
RACINE = pathlib.Path(__file__).resolve().parents[4]
if not (RACINE / "backend/django_core").is_dir(): RACINE = pathlib.Path.cwd()
DJ = RACINE / "backend/django_core"


class Obj:
    def __init__(self, **kw): self.__dict__.update(kw)


class Q:
    def __init__(self, **kw): self.kw = kw
    def __or__(self, o): return QOu(self, o)
    def __call__(self, o): return all(_ok(o, k, v) for k, v in self.kw.items())


class QOu:
    def __init__(self, a, b): self.a, self.b = a, b
    def __or__(self, o): return QOu(self, o)
    def __call__(self, o): return self.a(o) or self.b(o)


def _ok(o, k, v):
    base, _, op = k.rpartition("__")
    a = getattr(o, base if op in ("gt", "gte", "lte", "isnull") else k, None)
    return {"gt": lambda: a > v, "gte": lambda: a is not None and a >= v, "lte": lambda: a is not None and a <= v,
            "isnull": lambda: (a is None) == v}.get(op, lambda: a == v)()


class QS:
    def __init__(self, items): self.items = list(items)
    def filter(self, *a, **kw):
        return QS(o for o in self.items if all(f(o) for f in a) and all(_ok(o, k, v) for k, v in kw.items()))
    def select_related(self, *a): return self
    def order_by(self, champ): return QS(sorted(self.items, key=lambda o: getattr(o, champ)))
    def first(self): return self.items[0] if self.items else None


def source(nom):
    class SansRelatif(ast.NodeTransformer):
        def visit_ImportFrom(self, n): return ast.Pass() if n.level else n
    arbre = ast.parse((DJ / "apps/stock/services.py").read_text(encoding="utf-8"))
    n = next(x for x in arbre.body if isinstance(x, ast.FunctionDef) and x.name == nom)
    n.decorator_list = []
    return ast.unparse(ast.fix_missing_locations(SansRelatif().visit(n)))


def sonde(ctx=None):
    arch, actif = Obj(pk=1, nom="Solaire Nord", is_archived=True, statut="actif"), Obj(pk=2, nom="Atlas", is_archived=False, statut="actif")
    mk = lambda f, p: Obj(fournisseur=f, prix_achat=p, date_debut=None, date_fin=None)
    produit = Obj(prix_fournisseurs=QS([mk(arch, 1200), mk(actif, 1350)]))
    dj, db, du, tz = (types.ModuleType(n) for n in ("django", "django.db", "django.utils", "django.utils.timezone"))
    db.models = types.SimpleNamespace(Q=Q); tz.localdate = lambda: datetime.date(2026, 11, 11); du.timezone = tz
    mods = {"django": dj, "django.db": db, "django.db.models": db.models, "django.utils": du, "django.utils.timezone": tz}
    avant = {n: sys.modules.get(n) for n in mods}
    sys.modules.update(mods)
    try:
        class EtatIncompatible(ValueError): pass
        ns = {"EtatIncompatible": EtatIncompatible,
              "Fournisseur": types.SimpleNamespace(Statut=types.SimpleNamespace(BLOQUE_COMMANDES="bc", BLOQUE_TOTAL="bt"))}
        ns["fournisseur_peut_recevoir_bcf"] = lambda company, pk: (True, "")  # onboarding_fournisseur_obligatoire OFF par défaut
        for nom in ("cheapest_prix_fournisseur", "check_fournisseur_statut_commande", "exiger_fournisseur_commandable"):
            exec(source(nom), ns)
        meilleur = ns["cheapest_prix_fournisseur"](produit)
        try: ns["exiger_fournisseur_commandable"](Obj(), arch); garde = "accepte"
        except EtatIncompatible as e: garde = f"refuse ({e})"
    finally:
        for n, m in avant.items():
            if m is None: sys.modules.pop(n, None)
            else: sys.modules[n] = m
    propose_archive = meilleur is not None and meilleur.fournisseur.is_archived
    return {"repro": propose_archive or garde == "accepte", "observe": {
        "moins_cher": {"fournisseur": meilleur.fournisseur.nom, "archive": meilleur.fournisseur.is_archived, "prix": meilleur.prix_achat} if meilleur else None,
        "garde_exiger_fournisseur_commandable_sur_archive": garde, "methode": "execution"}}


if __name__ == "__main__":
    print(sonde())
