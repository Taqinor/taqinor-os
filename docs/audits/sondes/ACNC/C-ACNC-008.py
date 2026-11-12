# flake8: noqa  (sonde hôte PF9 « doubles clics, gestes rejoués, courses », groupe ACNC — sans Django, sans base)
"""C-ACNC-008 — un encaissement groupé envoyé deux fois convertit tout le virement en avance client (20 000 enregistrés pour 10 000).
Exécute la VRAIE `affecter_encaissement_groupe` (+ `enregistrer_paiement`, la porte AFAC9, ast ; ORM bouchonné) deux fois sur le même
virement de 10 000 réparti sur deux factures (6 000 + 4 000), puis lit `useFactureGestes.js` pour voir si l'appel porte une clé."""
SONDE = {"constat": "C-ACNC-008", "sha": "3acfee471",
         "attendu": "2e envoi : factures déjà soldées, aucun paiement de facture mais une avance de 10 000 ; total enregistré 20 000 "
                    "pour un virement de 10 000 ; l'écran n'envoie pas de clé d'idempotence"}
import ast, pathlib, re, sys, types
from contextlib import contextmanager
from decimal import Decimal
RACINE = pathlib.Path(__file__).resolve().parents[4]
FICHIER = RACINE / "backend/django_core/apps/ventes/domain/encaissements.py"
ECRAN = RACINE / "frontend/src/pages/ventes/factureList/useFactureGestes.js"
NOMS = ("_jour_encaissement", "motif_non_encaissable", "exiger_facture_encaissable", "_verifier_delai_acompte_domicile",
        "enregistrer_paiement", "_creer_paiement_groupe", "affecter_encaissement_groupe")


class FactureNonEncaissable(ValueError): pass
class AcompteAvantDelaiLegal(Exception): pass


def sonde(ctx=None):
    sys.dont_write_bytecode = True
    paiements, avances = [], []
    St = types.SimpleNamespace(BROUILLON="brouillon", EMISE="emise", EN_RETARD="en_retard", PAYEE="payee", ANNULEE="annulee")
    class Facture:
        Statut = St; TypeFacture = types.SimpleNamespace(ACOMPTE="acompte")
        def __init__(s, pk, ttc, echeance):
            s.pk = s.id = pk; s.total_ttc = Decimal(ttc); s.date_echeance = echeance; s.statut = St.EMISE
            s.company_id, s.client_id, s.reference = 1, 7, f"FAC-{pk}"; s.company = types.SimpleNamespace(id=1)
        montant_du = property(lambda s: s.total_ttc - sum((p.montant for p in paiements if p.facture is s), Decimal(0)))
        refresh_from_db = lambda s: None
    base = {1: Facture(1, "6000", 1), 2: Facture(2, "4000", 2)}
    Facture.objects = types.SimpleNamespace(select_for_update=lambda: types.SimpleNamespace(filter=lambda id__in: [base[i] for i in id__in], get=lambda pk: base[pk]))
    Paiement = type("Paiement", (), {"__init__": lambda s, **kw: s.__dict__.update(kw)})
    Paiement.objects = types.SimpleNamespace(create=lambda **kw: (paiements.append(Paiement(**kw)), paiements[-1])[1])
    def solder(f, **kw):
        if f.montant_du <= Decimal("0.01") and f.statut != St.PAYEE: f.statut = St.PAYEE
    mods = {"django": types.ModuleType("django"), "apps": types.ModuleType("apps"), "apps.ventes": types.ModuleType("apps.ventes"),
            "django.db": types.SimpleNamespace(transaction=types.SimpleNamespace(atomic=contextmanager(lambda: (yield)))),
            "apps.ventes.models": types.SimpleNamespace(Facture=Facture, Paiement=Paiement, AcompteAvantDelaiLegal=AcompteAvantDelaiLegal),
            "apps.ventes.activity": types.SimpleNamespace(log_facture_paiement=lambda *a: None), "core": types.ModuleType("core"),
            "core.events": types.SimpleNamespace(paiement_enregistre=types.SimpleNamespace(send=lambda **k: None)),
            "core.money": types.SimpleNamespace(quantize_mad=lambda x: Decimal(x).quantize(Decimal("0.01")))}
    mods["apps.ventes"].activity = mods["apps.ventes.activity"]
    sauve = {k: sys.modules.get(k) for k in mods}; sys.modules.update(mods)
    fonctions = [n for n in ast.parse(FICHIER.read_text(encoding="utf-8")).body if isinstance(n, ast.FunctionDef) and n.name in NOMS]
    ns = {"Decimal": Decimal, "TOLERANCE_CENTIME": Decimal("0.01"), "FactureNonEncaissable": FactureNonEncaissable,
          "MOTIF_NON_EMISE": "non émise", "MOTIF_ANNULEE": "annulée", "MOTIF_SOLDEE": "soldée", "marquer_facture_soldee": solder,
          "enregistrer_avance": lambda **kw: (avances.append(kw["montant"]), kw["montant"])[1], "logger": None}
    envois = []
    try:
        exec(compile(ast.Module(fonctions, []), str(FICHIER), "exec"), ns)
        for _ in range(2):
            try:
                ns["affecter_encaissement_groupe"](company=types.SimpleNamespace(id=1), client=types.SimpleNamespace(id=7), montant=Decimal("10000"),
                    mode="virement", date_paiement=None, user=None, factures=[base[1], base[2]], reference="VIR-1")
                envois.append(f"accepté : paiements de facture {sum(p.montant for p in paiements)}, avances {sum(avances, Decimal(0))}")
            except Exception as e: envois.append(f"refusé : {type(e).__name__} {e}")
    finally:
        for k, v in sauve.items(): sys.modules.pop(k, None) if v is None else sys.modules.__setitem__(k, v)
    total = sum((p.montant for p in paiements), Decimal(0)) + sum(avances, Decimal(0))
    appel = re.search(r"encaissementGroupeFactures\(\{.*?\}\)", ECRAN.read_text(encoding="utf-8"), re.S)
    ecran_sans_cle = bool(appel) and "idempotency_key" not in appel.group(0)
    return {"repro": total > Decimal("10000") and ecran_sans_cle, "observe": {
        "methode": "rejeu", "fonction": "affecter_encaissement_groupe (route POST factures/encaissement-groupe/)",
        "scenario": "virement de 10 000 sur F1 (6 000) + F2 (4 000), même envoi joué deux fois", "envois": envois,
        "total_enregistre": str(total), "avances_creees": [str(a) for a in avances], "statuts": [f.statut for f in base.values()],
        "ecran_envoie_idempotency_key": not ecran_sans_cle}}
