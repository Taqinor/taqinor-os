# flake8: noqa  (sonde hôte PF9 « doubles clics, gestes rejoués, courses », groupe ACNC — sans Django, sans base)
"""C-ACNC-003 — deux annulations simultanées de deux factures émises d'une même vente (acompte et solde) ne rendent jamais la sortie de stock.
Rejeu ENTRELACÉ de la VRAIE `annuler_facture` + `_retourner_stock_de_la_vente` (ast ; ORM, transaction à écritures visibles au commit,
verrous de ligne par facture et par vente bouchonnés ; garde préalable / contre-passation / liens bouchonnés). Les deux fils se
retrouvent à un point de rendez-vous juste avant le retour de stock : atteint seulement si rien n'a sérialisé les deux annulations."""
SONDE = {"constat": "C-ACNC-003", "sha": "3acfee471",
         "attendu": "les deux factures finissent annulées et le stock de la vente (sortie de 8) n'est rentré 0 fois au lieu d'1"}
import ast, pathlib, sys, threading, types
from decimal import Decimal
RACINE = pathlib.Path(__file__).resolve().parents[4]
FICHIER = RACINE / "backend/django_core/apps/ventes/domain/annulation_facture.py"
ANN, EMI = "annulee", "emise"


class AnnulationRefusee(Exception): pass


def monde():
    tl, etat, verrous = threading.local(), threading.Lock(), {}
    statuts = {1: EMI, 2: EMI}
    mouv = [(10, "sortie", 8)]  # la sortie de stock de l'émission (somme déjà validée)
    rdv = threading.Barrier(2, timeout=1.2)
    def attendre():  # point de rendez-vous : juste avant la lecture « une autre facture vit-elle ? », puis juste après
        try: rdv.wait()
        except threading.BrokenBarrierError: pass
    def pris(nom):  # verrou de ligne (("f", pk) ou ("v", devis)), tenu jusqu'au commit du fil
        h = tl.__dict__.setdefault("tenus", [])
        if nom in h: return
        with etat: v = verrous.setdefault(nom, threading.Lock())
        if not v.acquire(timeout=5): raise TimeoutError(nom)
        h.append(nom)
    class Atomic:
        def __enter__(s): tl.prof = getattr(tl, "prof", 0) + 1; tl.ecr = getattr(tl, "ecr", {}); tl.mv = getattr(tl, "mv", [])
        def __exit__(s, t, v, tb):
            tl.prof -= 1
            if tl.prof: return
            with etat:
                if t is None: statuts.update(tl.ecr); mouv.extend(tl.mv)
            tl.ecr, tl.mv = {}, []
            for n in tl.__dict__.pop("tenus", []): verrous[n].release()
    lire = lambda pk: tl.ecr.get(pk, statuts[pk]) if hasattr(tl, "ecr") else statuts[pk]
    devis = types.SimpleNamespace(reference="DEV-1", pk=1, company_id=1)
    class F:
        pk = id = property(lambda s: s._pk)
        statut = property(lambda s: lire(s._pk), lambda s, v: tl.ecr.__setitem__(s._pk, v))
        def __init__(s, pk): s._pk = pk; s.devis = devis; s.company = types.SimpleNamespace(id=1); s.reference = f"FAC-{pk}"
        paiements = types.SimpleNamespace(all=lambda: [])
        retenues_subies = types.SimpleNamespace(filter=lambda **k: types.SimpleNamespace(
            values_list=lambda *a, **k: [], update=lambda **k: 0))
    class Req:
        def __init__(s, f=None): s.f = f or []
        def select_for_update(s, **k): return s
        def get(s, pk): pris(("f", pk)); return F(pk)
        def filter(s, **k): return s
        def exclude(s, **k): return Req(s.f + [k])
        def exists(s):
            sauf = next(k["pk"] for k in s.f if "pk" in k)
            vit = any(lire(p) not in ("brouillon", ANN) for p in statuts if p != sauf)
            attendre()  # aucun fil n'a encore validé quand l'autre a lu
            return vit
    Facture = type("Facture", (), {"Statut": types.SimpleNamespace(BROUILLON="brouillon", ANNULEE=ANN, PAYEE="payee", EMISE=EMI), "objects": Req()})
    Facture.devis_commun = devis
    class Mvts:
        def __getattr__(s, n): return lambda *a, **k: s
        def __iter__(s):
            net = {}
            for p, t, q in mouv + getattr(tl, "mv", []): net[(p, t)] = net.get((p, t), 0) + q
            return iter([{"produit_id": p, "type_mouvement": t, "t": q} for (p, t), q in net.items()])
    def mouvement(**k): tl.mv.append((k["produit"].pk, k["type_mouvement"], k["quantite"]))
    def liens(facture, statut): attendre()
    M = types.ModuleType
    mods = {"django": M("django"), "django.db": types.SimpleNamespace(transaction=types.SimpleNamespace(atomic=Atomic)),
            "django.db.models": types.SimpleNamespace(Sum=lambda c: c), "core": M("core"),
            "core.events": types.SimpleNamespace(facture_annulee=types.SimpleNamespace(send=lambda **k: None)),
            "apps": M("apps"), "apps.ventes": M("apps.ventes"), "apps.ventes.domain": M("apps.ventes.domain"), "apps.stock": M("apps.stock"),
            "apps.ventes.models": types.SimpleNamespace(Facture=Facture, Paiement=types.SimpleNamespace(STATUTS_NON_COMPTES=()),
                PaymentLink=types.SimpleNamespace(Statut=types.SimpleNamespace(ANNULE="annule")),
                FactureActivity=types.SimpleNamespace(Kind=types.SimpleNamespace(MODIFICATION="m"), objects=types.SimpleNamespace(create=lambda **k: None))),
            "apps.ventes.activity": M("a"), "apps.ventes.domain.encaissements": types.SimpleNamespace(fermer_liens_paiement=liens),
            "apps.ventes.domain.facturation_vente": types.SimpleNamespace(verrouiller_vente=lambda d: (pris(("v", d.pk)), [d])[1]),
            "apps.stock.selectors": types.SimpleNamespace(mouvements_par_reference=lambda c, r: Mvts()),
            "apps.stock.services": types.SimpleNamespace(mouvement_type_entree=lambda: "entree", mouvement_type_sortie=lambda: "sortie",
                record_stock_movement=mouvement, verrouiller_produit=lambda pid: types.SimpleNamespace(pk=pid, quantite_stock=0))}
    mods["apps.ventes"].activity = mods["apps.ventes.activity"]
    return Facture, statuts, mouv, mods


def sonde(ctx=None):
    sys.dont_write_bytecode = True
    arbre = ast.parse(FICHIER.read_text(encoding="utf-8"))
    corps = [n for n in arbre.body if (isinstance(n, ast.FunctionDef) and n.name in ("annuler_facture", "_retourner_stock_de_la_vente"))
             or (isinstance(n, ast.Assign) and isinstance(n.value, ast.Constant))
             or (isinstance(n, ast.ImportFrom) and "facturation_vente" in (n.module or ""))]
    Facture, statuts, mouv, mods = monde()
    sauve = {k: sys.modules.get(k) for k in mods}; sys.modules.update(mods)
    ns = {"__name__": "apps.ventes.domain.annulation_facture", "__package__": "apps.ventes.domain", "json": __import__("json"),
          "Decimal": Decimal, "transaction": mods["django.db"].transaction, "AnnulationRefusee": AnnulationRefusee,
          "_refus_prealable": lambda *a, **k: None, "_payes_hors_escompte": lambda *a: Decimal(0), "_refuser_si_argent": lambda *a: None,
          "_contre_passer": lambda locked, user, motif="": setattr(locked, "statut", ANN)}
    erreurs = []
    try:
        exec(compile(ast.Module(corps, []), str(FICHIER), "exec"), ns)
        def annuler(pk):
            try: ns["annuler_facture"](types.SimpleNamespace(pk=pk, devis=Facture.devis_commun), user=None)
            except Exception as e: erreurs.append(f"F{pk} : {type(e).__name__} {e}")
        fils = [threading.Thread(target=annuler, args=(pk,)) for pk in (1, 2)]
        [t.start() for t in fils]; [t.join(15) for t in fils]
    finally:
        for k, v in sauve.items(): sys.modules.pop(k, None) if v is None else sys.modules.__setitem__(k, v)
    entrees = [m for m in mouv if m[1] == "entree"]
    return {"repro": all(s == ANN for s in statuts.values()) and not entrees, "observe": {
        "methode": "rejeu", "fonction": "annuler_facture -> _retourner_stock_de_la_vente",
        "scenario": "acompte (F1) et solde (F2) émis d'une même vente, sortie de stock de 8 ; annulations simultanées, une par fil",
        "statuts_finaux": dict(statuts), "entrees_de_stock_creees": entrees, "stock_a_rentrer": 8, "erreurs": erreurs}}
