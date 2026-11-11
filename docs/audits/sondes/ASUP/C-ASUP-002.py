"""Rejoue stock/views/produit.py::ProduitViewSet.force_delete (et _references_vivantes) : supprimer définitivement un produit archivé dont les seules traces sont des mouvements efface ces MouvementStock par QuerySet.delete(), sans retour."""
SONDE = {"constat": "C-ASUP-002", "sha": "3acfee471",
         "attendu": "force_delete d'un produit archivé à 2 mouvements rend 200 et efface les 2 MouvementStock puis le produit"}
import ast, contextlib, pathlib, sys, types
sys.dont_write_bytecode = True
RACINE = pathlib.Path(__file__).resolve().parents[4]
if not (RACINE / "backend/django_core").is_dir(): RACINE = pathlib.Path.cwd()
FICHIER = RACINE / "backend/django_core/apps/stock/views/produit.py"


class ProtectedError(Exception):
    def __init__(self, msg, objs):
        super().__init__(msg); self.protected_objects = objs


class Meta:
    def __init__(self, v): self.verbose_name, self.verbose_name_plural = v, v + "s"


class MouvementStock: _meta = Meta("mouvement de stock")
class LigneDevis: _meta = Meta("ligne de devis")
class QuerySet: pass


ETAT = {}


class Produit:
    _meta = Meta("produit")

    def __init__(self, archive, protege=None):
        self.is_archived, self.nom, self.sku, self.protege = archive, "Câble", "SKU-1", protege or []
        self.mvts = [MouvementStock(), MouvementStock()]
        prod = self

        class QS:
            def count(s): return len(prod.mvts)
            def all(s): return s
            def delete(s): ETAT["journal"].append(("MouvementStock.delete", len(prod.mvts)))
        self.mouvements = QS()

    def delete(self):
        if self.protege: raise ProtectedError("protégé", self.protege)
        ETAT["journal"].append(("Produit.delete",))


class NestedObjects:  # Django : PROTECT -> protected, CASCADE -> model_objs
    def __init__(self, using=None): self.model_objs, self.field_updates, self.protected = {}, {}, set()
    def collect(self, objs):
        p = objs[0]; self.model_objs[Produit] = {p}; self.protected.update(p.mvts); self.protected.update(p.protege)


@contextlib.contextmanager
def atomic():
    avant = list(ETAT["journal"])
    try: yield
    except Exception:
        ETAT["journal"] = avant + [("ROLLBACK",)]; raise


def _charger():
    fns = {}
    for n in ast.parse(FICHIER.read_text(encoding="utf-8")).body:
        if isinstance(n, ast.FunctionDef) and n.name in ("_references_vivantes", "_texte_references"): fns[n.name] = n
        if isinstance(n, ast.ClassDef) and n.name == "ProduitViewSet":
            for s in n.body:
                if isinstance(s, ast.FunctionDef) and s.name == "force_delete": s.decorator_list = []; fns["force_delete"] = s
    adm = types.ModuleType("django.contrib.admin.utils"); adm.NestedObjects = NestedObjects
    db = types.ModuleType("django.db"); db.router = types.SimpleNamespace(db_for_write=lambda m: "default")
    for nom in ("django", "django.contrib", "django.contrib.admin"): sys.modules.setdefault(nom, types.ModuleType(nom))
    sys.modules["django.contrib.admin.utils"], sys.modules["django.db"] = adm, db

    class Resp:
        def __init__(self, data, status=None): self.data, self.status_code = data, status
    ns = dict(Response=Resp, status=types.SimpleNamespace(HTTP_409_CONFLICT=409, HTTP_200_OK=200, HTTP_204_NO_CONTENT=204),
              transaction=types.SimpleNamespace(atomic=atomic), ProtectedError=ProtectedError,
              MouvementStock=MouvementStock, Produit=Produit, QuerySet=QuerySet)
    for nom, n in fns.items(): exec(compile(ast.Module([n], []), nom, "exec"), ns)
    return ns["force_delete"]


def _jouer(force_delete, p):
    ETAT["journal"] = []
    vue = type("V", (), {"get_object": lambda s: p})()
    try: code = force_delete(vue, request=None).status_code
    except Exception as e: code = type(e).__name__
    return code, list(ETAT["journal"])


def sonde(ctx=None):
    fd = _charger()
    c1, j1 = _jouer(fd, Produit(True))
    c2, j2 = _jouer(fd, Produit(False))
    c3, j3 = _jouer(fd, Produit(True, protege=[LigneDevis()]))
    repro = ("MouvementStock.delete", 2) in j1 and ("Produit.delete",) in j1
    return {"repro": repro, "observe": {
        "geste": "Stock > Archivés > Supprimer (StockList, admin) -> DELETE /stock/produits/<id>/force-delete/",
        "archive_seuls_mouvements": {"http": c1, "journal": j1},
        "non_archive": {"http": c2, "journal": j2},
        "archive_avec_ligne_de_devis": {"http": c3, "journal": j3}}}


if __name__ == "__main__":
    print(sonde())
