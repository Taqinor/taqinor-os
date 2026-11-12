# flake8: noqa  (sonde HÔTE d'audit PF9 « doubles clics, gestes rejoués, courses », groupe ACNC — sans Django, sans base, sans Docker)
"""C-ACNC-006 — la variation de prix « +10 % » en masse rejouée donne +21 %, et une panne à mi-boucle laisse un catalogue incohérent.
On extrait par ast la VRAIE `stock/services.py::apply_product_bulk` (+ `_dec`, bornes) et on l'EXÉCUTE sur un faux ORM : (1) deux envois du
même corps `{mode: percent, valeur: 10}` ; (2) panne au 3e produit puis nouvel essai. Le faux `transaction.atomic` annule vraiment sur exception."""
SONDE = {"constat": "C-ACNC-006", "sha": "3acfee471",
         "attendu": "1 000 -> 1 100 -> 1 210 au second envoi ; après panne au 3e produit puis nouvel essai : certains produits à +21 %, d'autres à +10 %"}
import ast, contextlib, decimal, logging, pathlib, sys, types
from decimal import Decimal
sys.dont_write_bytecode = True
RACINE = pathlib.Path(__file__).resolve().parents[4]
DJ = RACINE / "backend/django_core"
CORPS = {"mode": "percent", "valeur": "10", "cle_idempotence": "cle-bulk-0001"}  # la même clé est rejouée : un correctif par clé doit la reconnaître


def charger(db, casse):
    """Compile les VRAIS noeuds d'apply_product_bulk dans un espace où l'ORM est faux ; `db` = {id: prix} (autocommit sauf `atomic`)."""
    src = (DJ / "apps/stock/services.py").read_text(encoding="utf-8")
    noeuds = [n for n in ast.parse(src).body if (isinstance(n, ast.FunctionDef) and n.name in ("_dec", "apply_product_bulk"))
              or (isinstance(n, ast.Assign) and getattr(n.targets[0], "id", "") in ("BULK_ACTIONS", "BULK_VALEUR_MAX"))]
    class Introuvable(Exception): pass
    class P:
        def __init__(s, i): s.id, s.nom, s.prix_vente = i, f"P{i}", db[i]
        def save(s, update_fields=None):
            if s.id == casse["id"]: raise RuntimeError("panne à mi-boucle")
            db[s.id] = s.prix_vente
    class Qs:
        def filter(s, **k): return s
        def select_for_update(s): return s
        def __iter__(s): return iter([P(i) for i in sorted(db)])
    @contextlib.contextmanager
    def atomic(*a, **k):  # annule vraiment : le correctif « boucle dans une transaction » doit faire repro False
        avant = dict(db)
        try: yield
        except BaseException: db.clear(); db.update(avant); raise
    modeles = types.ModuleType("apps.stock.models"); modeles.Produit = type("Produit", (), {"objects": Qs()}); modeles.Categorie = modeles.Produit
    vue = types.ModuleType("apps.stock.views.produit")
    vue._champs_modifies, vue._instantane_suivi, vue.emettre_produit_modifie = (lambda a, p: {"prix_vente"}), (lambda p: {}), (lambda *a: None)
    dj = types.ModuleType("django"); dj.db = types.ModuleType("django.db"); dj.db.transaction = types.SimpleNamespace(atomic=atomic)
    sauve = {n: sys.modules.get(n) for n in ("django", "django.db", "apps", "apps.stock", "apps.stock.models", "apps.stock.views", "apps.stock.views.produit")}
    for n in sauve: sys.modules[n] = types.ModuleType(n)
    sys.modules.update({"django": dj, "django.db": dj.db, "apps.stock.models": modeles, "apps.stock.views.produit": vue})
    ns = dict(Decimal=Decimal, InvalidOperation=decimal.InvalidOperation, IntrouvableMetier=Introuvable, logger=logging.getLogger("sonde"),
              transaction=dj.db.transaction, __name__="apps.stock.services", __package__="apps.stock")
    exec(compile(ast.Module(noeuds, []), "apps/stock/services.py", "exec"), ns)
    return ns["apply_product_bulk"], sauve


def restaurer(sauve):
    for n, m in sauve.items(): sys.modules.pop(n, None) if m is None else sys.modules.__setitem__(n, m)


def sonde(ctx=None):
    co, user, casse = types.SimpleNamespace(id=1), types.SimpleNamespace(username="u"), {"id": None}
    db = {1: Decimal("1000.00"), 2: Decimal("2000.00"), 3: Decimal("500.00")}
    bulk, sauve = charger(db, casse)
    envoi = lambda: bulk(company=co, user=user, ids=sorted(db), op="set_price", params=dict(CORPS))
    try:
        envoi(); apres1 = dict(db)
        try: envoi()
        except Exception: pass  # un correctif peut refuser le rejeu : l'état reste alors celui du 1er envoi
        apres2 = dict(db)
        db.clear(); db.update({1: Decimal("1000.00"), 2: Decimal("2000.00"), 3: Decimal("500.00"), 4: Decimal("800.00")})
        casse["id"] = 3
        try: envoi()
        except RuntimeError: pass
        casse["id"] = None; apres_panne = dict(db)
        try: envoi()
        except Exception: pass
        final = dict(db)
    finally:
        restaurer(sauve)
    rejeu_double = apres2[1] == Decimal("1210.00")
    incoherent = len({(final[i] / v).quantize(Decimal("0.01")) for i, v in {1: 1000, 2: 2000, 3: 500, 4: 800}.items()}) > 1
    return {"repro": rejeu_double or incoherent, "observe": {
        "methode": "rejeu (vraie apply_product_bulk extraite par ast, faux ORM, faux atomic qui annule)", "route": "POST produits/bulk/ op=set_price mode=percent valeur=10",
        "prix_produit_1": {"initial": "1000.00", "apres_envoi_1": str(apres1[1]), "apres_envoi_2_meme_corps": str(apres2[1])},
        "panne_au_3e_produit": {"etat_apres_panne": {k: str(v) for k, v in apres_panne.items()}, "etat_apres_nouvel_essai": {k: str(v) for k, v in final.items()}},
        "rejeu_donne_plus_21_pour_cent": rejeu_double, "catalogue_incoherent_apres_panne_et_essai": incoherent}}
