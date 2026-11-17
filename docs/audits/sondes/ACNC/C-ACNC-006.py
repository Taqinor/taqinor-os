# flake8: noqa  (sonde HÔTE d'audit PF9 « doubles clics, gestes rejoués, courses », groupe ACNC — sans Django, sans base, sans Docker)
"""C-ACNC-006 — la variation de prix « +10 % » en masse rejouée donne +21 %, et une panne à mi-boucle laisse un catalogue incohérent.
On extrait par ast la VRAIE vue `stock/views/produit.py::ProduitViewSet.bulk` (c'est elle qui porte `transaction.atomic` et l'appel
`_avec_idempotence` depuis ACNC24 ; `apply_product_bulk` n'ouvre plus de transaction), le VRAI `core/idempotency.py::_avec_idempotence`
et la VRAIE `apps/stock/services.py::apply_product_bulk` (+ `_dec`, bornes), et on les EXÉCUTE sur un faux ORM : (1) deux envois du
même corps `{mode: percent, valeur: 10}` sous la même `Idempotency-Key` ; (2) panne au 3e produit puis nouvel essai. Le faux
`transaction.atomic` (décorateur ou contexte) annule vraiment sur exception ; la table des clés est en mémoire (bouchon de `_reserver`)."""
SONDE = {"constat": "C-ACNC-006", "sha": "3acfee471",
         "attendu": "1 000 -> 1 100 -> 1 210 au second envoi ; après panne au 3e produit puis nouvel essai : certains produits à +21 %, d'autres à +10 %"}
import ast, contextlib, decimal, logging, pathlib, sys, types
from decimal import Decimal
sys.dont_write_bytecode = True
RACINE = pathlib.Path(__file__).resolve().parents[4]
DJ = RACINE / "backend/django_core"
CLE = "cle-bulk-0001"  # en-tête Idempotency-Key rejoué à chaque envoi : le serveur doit le reconnaître
CORPS = {"action": "set_price", "mode": "percent", "valeur": "10"}


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
    class atomic:  # décorateur (`atomic(f)(...)`) OU contexte ; annule vraiment : une boucle dans une transaction doit faire repro False
        def __init__(s, fn=None): s.fn = fn
        def __enter__(s): s.avant = dict(db); return s
        def __exit__(s, t, v, tb):
            if t: db.clear(); db.update(s.avant)
            return False
        def __call__(s, *a, **k):
            with atomic(): return s.fn(*a, **k)
    cles = {}  # table des clés d'idempotence (bouchon en mémoire de IdempotencyRecord)
    class Conflit(Exception): pass
    class Reponse:
        def __init__(s, data=None, status=200, **k): s.data, s.status_code = data, status
    etat = types.SimpleNamespace(TERMINE="termine", EN_COURS="en_cours")
    def _reserver(company, endpoint, key, fingerprint):
        if (company.id, endpoint, key) in cles:
            ex = cles[(company.id, endpoint, key)]
            if ex.request_fingerprint != fingerprint: raise Conflit()
            if ex.etat == etat.TERMINE: return Reponse(ex.response_body, status=ex.response_status)
            raise Conflit()
        ex = types.SimpleNamespace(etat=etat.EN_COURS, request_fingerprint=fingerprint, save=lambda **k: None)
        cles[(company.id, endpoint, key)] = ex; return ex
    def _liberer(res):
        for k, v in list(cles.items()):
            if v is res: del cles[k]
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

    class SansImport(ast.NodeTransformer):  # imports (même imbriqués) -> pass : leurs noms viennent de ns
        visit_Import = visit_ImportFrom = lambda s, n: ast.Pass()

    def methodes(rel, classe, noms):
        corps = next(n for n in ast.parse((DJ / rel).read_text(encoding="utf-8")).body if isinstance(n, ast.ClassDef) and n.name == classe).body
        return [n for n in corps if isinstance(n, ast.FunctionDef) and n.name in noms]

    def fonctions(rel, noms):
        return [n for n in ast.parse((DJ / rel).read_text(encoding="utf-8")).body if isinstance(n, ast.FunctionDef) and n.name in noms]
    corps_vue = methodes("core/idempotency.py", "IdempotentCreateMixin", {"_idempotency_key", "_idempotency_endpoint", "_avec_idempotence"}) \
        + methodes("apps/stock/views/produit.py", "ProduitViewSet", {"bulk"})
    for f in corps_vue: f.decorator_list = []
    tout = fonctions("core/idempotency.py", {"_fingerprint"}) + fonctions("apps/stock/views/produit.py", {"_params_bulk"}) \
        + [ast.ClassDef(name="Vue", bases=[], keywords=[], body=corps_vue, decorator_list=[], type_params=[])]
    ns.update(Response=Reponse, status=types.SimpleNamespace(HTTP_400_BAD_REQUEST=400, HTTP_403_FORBIDDEN=403, HTTP_404_NOT_FOUND=404),
              corps_objet=lambda r: r.data, peut_modifier_prix_catalogue=lambda u: True, ValidationError=ValueError,
              VALEUR_BULK=types.SimpleNamespace(run_validation=lambda v: v), entier_ou_400=lambda v, c, **k: int(v),
              _reserver=_reserver, _liberer=_liberer, IdempotencyRecord=types.SimpleNamespace(Etat=etat), json=__import__("json"),
              hashlib=__import__("hashlib"), IDEMPOTENCY_KEY_HEADER="HTTP_IDEMPOTENCY_KEY", __name__="apps.stock.views.produit")
    exec(compile(ast.fix_missing_locations(SansImport().visit(ast.Module(tout, []))), "vue_bulk", "exec"), ns)
    return ns["Vue"](), cles, sauve


def restaurer(sauve):
    for n, m in sauve.items(): sys.modules.pop(n, None) if m is None else sys.modules.__setitem__(n, m)


def sonde(ctx=None):
    co, user, casse = types.SimpleNamespace(id=1), types.SimpleNamespace(username="u"), {"id": None}
    db = {1: Decimal("1000.00"), 2: Decimal("2000.00"), 3: Decimal("500.00")}
    vue, cles, sauve = charger(db, casse)
    user.company = co

    def envoi():  # le VRAI geste : POST produits/bulk/ avec son en-tête Idempotency-Key (vue réelle, ast)
        req = types.SimpleNamespace(user=user, data=dict(CORPS, ids=sorted(db)), META={"HTTP_IDEMPOTENCY_KEY": CLE},
                                    headers={"Idempotency-Key": CLE})
        return vue.bulk(req)
    try:
        envoi(); apres1 = dict(db)
        try: envoi()
        except Exception: pass  # un correctif peut refuser le rejeu : l'état reste alors celui du 1er envoi
        apres2 = dict(db)
        cles.clear(); db.clear(); db.update({1: Decimal("1000.00"), 2: Decimal("2000.00"), 3: Decimal("500.00"), 4: Decimal("800.00")})
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
        "methode": "rejeu (vraie vue bulk + vrai _avec_idempotence + vraie apply_product_bulk extraites par ast, faux ORM, faux atomic qui annule)", "route": "POST produits/bulk/ op=set_price mode=percent valeur=10",
        "prix_produit_1": {"initial": "1000.00", "apres_envoi_1": str(apres1[1]), "apres_envoi_2_meme_corps": str(apres2[1])},
        "panne_au_3e_produit": {"etat_apres_panne": {k: str(v) for k, v in apres_panne.items()}, "etat_apres_nouvel_essai": {k: str(v) for k, v in final.items()}},
        "rejeu_donne_plus_21_pour_cent": rejeu_double, "catalogue_incoherent_apres_panne_et_essai": incoherent}}


if __name__ == "__main__":
    import json
    print(json.dumps(sonde(), ensure_ascii=False, indent=1, default=str))
