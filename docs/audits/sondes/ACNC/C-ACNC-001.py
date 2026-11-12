# flake8: noqa  (sonde hôte PF9 « doubles clics, gestes rejoués, courses », groupe ACNC — sans Django, sans base)
"""C-ACNC-001 — un paiement partiel envoyé deux fois est enregistré deux fois : l'écran n'envoie jamais de clé d'idempotence.
Exécute la VRAIE `encaisser_sur_facture` (+ `enregistrer_paiement`, la porte AFAC9, ast ; ORM bouchonné) deux fois sur le même
corps partiel, sans clé puis avec la même clé, et lit `PaiementDialog.jsx` pour voir si l'appel `enregistrerPaiement` porte une clé."""
SONDE = {"constat": "C-ACNC-001", "sha": "3acfee471",
         "attendu": "même corps partiel (5 000 sur 10 000) joué deux fois = 2 paiements, facture soldée ; "
                    "PaiementDialog n'envoie pas idempotency_key ; clé rejouée = IntegrityError et non le paiement déjà créé"}
import ast, pathlib, re, sys, types
from contextlib import contextmanager
from decimal import Decimal
RACINE = pathlib.Path(__file__).resolve().parents[4]
FICHIER = RACINE / "backend/django_core/apps/ventes/domain/encaissements.py"
RECTIF = RACINE / "backend/django_core/apps/facturation/views/facture_rectificatifs.py"
ECRAN = RACINE / "frontend/src/pages/ventes/PaiementDialog.jsx"
NOMS = ("_jour_encaissement", "motif_non_encaissable", "exiger_facture_encaissable", "_verifier_delai_acompte_domicile",
        "enregistrer_paiement", "encaisser_sur_facture")


class IntegrityError(Exception): pass
class EncaissementRefuse(Exception):
    def __init__(self, motif): super().__init__(motif); self.motif = motif
class FactureNonEncaissable(ValueError): pass
class AcompteAvantDelaiLegal(Exception): pass


def monde():
    paiements = []
    St = types.SimpleNamespace(BROUILLON="brouillon", EMISE="emise", EN_RETARD="en_retard", PAYEE="payee", ANNULEE="annulee")
    class Facture:
        Statut = St; TypeFacture = types.SimpleNamespace(ACOMPTE="acompte")
        def __init__(s, pk, ttc): s.pk = s.id = pk; s.total_ttc = Decimal(ttc); s.statut = St.EMISE; s.company = types.SimpleNamespace(id=1)
        montant_du = property(lambda s: s.total_ttc - sum((p.montant for p in paiements), Decimal(0)))
        escompte_applicable = lambda s, d: False
        refresh_from_db = lambda s: None
    base = {1: Facture(1, "10000")}
    Facture.objects = types.SimpleNamespace(select_for_update=lambda: types.SimpleNamespace(get=lambda pk: base[pk]))
    class Paiement:
        Mode = types.SimpleNamespace(VIREMENT="virement")
        def __init__(s, **kw): s.__dict__.update(kw)
    def creer(**kw):  # contrainte uniq_paiement_idempotency_par_societe, comme la base
        cle = kw.get("idempotency_key")
        if cle and any(getattr(p, "idempotency_key", None) == cle for p in paiements): raise IntegrityError("uniq_paiement_idempotency_par_societe")
        paiements.append(Paiement(**kw)); return paiements[-1]
    Paiement.objects = types.SimpleNamespace(create=creer)
    def solder(f, **kw):
        if f.montant_du <= Decimal("0.01") and f.statut != St.PAYEE: f.statut = St.PAYEE; return True
        return False
    mods = {"django": types.ModuleType("django"), "apps": types.ModuleType("apps"), "apps.ventes": types.ModuleType("apps.ventes"),
            "django.db": types.SimpleNamespace(transaction=types.SimpleNamespace(atomic=contextmanager(lambda: (yield)))),
            "apps.ventes.models": types.SimpleNamespace(Facture=Facture, Paiement=Paiement, AcompteAvantDelaiLegal=AcompteAvantDelaiLegal),
            "apps.ventes.activity": types.SimpleNamespace(log_facture_paiement=lambda *a: None),
            "core": types.ModuleType("core"), "core.events": types.SimpleNamespace(paiement_enregistre=types.SimpleNamespace(send=lambda **k: None)),
            "apps.parametres": types.ModuleType("apps.parametres"),
            "apps.parametres.models": types.SimpleNamespace(CompanyProfile=types.SimpleNamespace(get=lambda company: types.SimpleNamespace(tolerance_ecart_reglement=0)))}
    mods["apps.ventes"].activity = mods["apps.ventes.activity"]
    return Facture, base, paiements, mods, solder


def sonde(ctx=None):
    sys.dont_write_bytecode = True
    texte = FICHIER.read_text(encoding="utf-8")
    fonctions = [n for n in ast.parse(texte).body if isinstance(n, ast.FunctionDef) and n.name in NOMS]
    Facture, base, paiements, mods, solder = monde()
    sauve = {k: sys.modules.get(k) for k in mods}
    sys.modules.update(mods)
    try:
        ns = {"Decimal": Decimal, "TOLERANCE_CENTIME": Decimal("0.01"), "EncaissementRefuse": EncaissementRefuse,
              "FactureNonEncaissable": FactureNonEncaissable, "marquer_facture_soldee": solder, "_avoir_d_escompte": lambda *a: None,
              "proposer_arrondi_caisse": lambda *a, **k: {"applicable": False}, "logger": None}
        exec(compile(ast.Module(fonctions, []), str(FICHIER), "exec"), ns)
        corps = {"montant": Decimal("5000"), "date_paiement": None, "mode": "virement", "reference": "VIR-1"}
        sans_cle = []
        for _ in range(2):
            try: ns["encaisser_sur_facture"](facture=base[1], donnees=dict(corps), user=None); sans_cle.append("accepté")
            except EncaissementRefuse as e: sans_cle.append("refusé : " + e.motif)
        deux_sans_cle, statut = len(paiements), base[1].statut
        paiements.clear(); base[1].statut = "emise"
        avec_cle = []
        for _ in range(2):
            try: ns["encaisser_sur_facture"](facture=base[1], donnees={**corps, "idempotency_key": "k-1"}, user=None); avec_cle.append("accepté")
            except Exception as e: avec_cle.append(type(e).__name__)
    finally:
        for k, v in sauve.items(): sys.modules.pop(k, None) if v is None else sys.modules.__setitem__(k, v)
    appel = re.search(r"enregistrerPaiement\(facture\.id,\s*\{.*?\}\)", ECRAN.read_text(encoding="utf-8"), re.S)
    ecran_sans_cle = bool(appel) and "idempotency_key" not in appel.group(0)
    return {"repro": deux_sans_cle == 2 and ecran_sans_cle, "observe": {
        "methode": "rejeu", "fonction": "encaisser_sur_facture (route POST factures/{id}/enregistrer-paiement/)",
        "scenario": "même corps partiel 5 000 sur 10 000, deux envois", "reponses_sans_cle": sans_cle,
        "paiements_crees_sans_cle": deux_sans_cle, "statut_final": statut, "reponses_meme_cle": avec_cle,
        "paiements_crees_meme_cle": len(paiements), "PaiementDialog_envoie_idempotency_key": not ecran_sans_cle,
        "note_debit_avoir_retour_sans_cle (facture_rectificatifs.py, lecture)": "idempotency_key" not in RECTIF.read_text(encoding="utf-8")}}
