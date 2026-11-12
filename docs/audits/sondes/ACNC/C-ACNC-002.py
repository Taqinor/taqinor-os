# flake8: noqa  (sonde hôte PF9 « doubles clics, gestes rejoués, courses », groupe ACNC — sans Django, sans base)
"""C-ACNC-002 — « Supprimer » un brouillon pendant que son « Émettre » est en vol efface une facture émise.
Rejeu ENTRELACÉ de la VRAIE `FactureViewSet.perform_destroy` (ast ; modèle, verrou de ligne et transaction bouchonnés) : un fil
d'émission tient le verrou de ligne et passe la facture à « émise / FAC-… », un fil de suppression arrive avec l'instance chargée
avant (« brouillon / BROUILLON-7 »), attend le verrou, puis le fil d'émission valide."""
SONDE = {"constat": "C-ACNC-002", "sha": "3acfee471",
         "attendu": "perform_destroy lit statut et référence sur l'instance chargée : la suppression, débloquée par l'émission, "
                    "efface la ligne alors qu'elle est « émise » (aucun 409)"}
import ast, pathlib, sys, threading, time, types
RACINE = pathlib.Path(__file__).resolve().parents[4]
FICHIER = RACINE / "backend/django_core/apps/facturation/views/facture.py"


class ConflitEtat(Exception): pass
class ProtectedError(Exception): pass
class PasTrouve(Exception): pass


def monde():
    row = {"pk": 7, "statut": "brouillon", "reference": "BROUILLON-7", "vivant": True}
    verrou, tl, supprimees = threading.Lock(), threading.local(), []
    def prendre():  # verrou de ligne, tenu jusqu'à la fin de la transaction du fil (hors transaction : le temps de l'instruction)
        if getattr(tl, "tient", False): return False
        if not verrou.acquire(timeout=5): raise TimeoutError("verrou de ligne")
        tl.tient = True; return True
    def lacher(): tl.tient = False; verrou.release()
    class Inst:
        paiements = types.SimpleNamespace(exists=lambda: False)
        def __init__(s): s.pk = row["pk"]; s.statut = row["statut"]; s.reference = row["reference"]
        def refresh_from_db(s): s.statut, s.reference = row["statut"], row["reference"]
        def delete(s):
            mien = prendre()
            try:
                if row["vivant"]: supprimees.append((row["statut"], row["reference"])); row["vivant"] = False
            finally:
                if mien and not getattr(tl, "tx", 0): lacher()
    class Req:
        def __init__(s, verrouille=False, **filtres): s.v, s.f = verrouille, filtres
        def _lire(s):
            mien = s.v and prendre()
            try: return mien, (Inst() if row["vivant"] and all(row.get(k) == v for k, v in s.f.items()) else None)
            finally:
                if mien and not getattr(tl, "tx", 0): lacher()
        def get(s, **kw): return Req(s.v, **{**s.f, **kw}).first(raise_=True)
        def first(s, raise_=False):
            o = s._lire()[1]
            if o is None and raise_: raise PasTrouve()
            return o
        def filter(s, **kw): return Req(s.v, **{**s.f, **kw})
        def select_for_update(s, **kw): return Req(True, **s.f)
        def exists(s): return s.first() is not None
        def delete(s):
            mien = s.v and prendre()
            try:
                if row["vivant"] and all(row.get(k) == v for k, v in s.f.items()): supprimees.append((row["statut"], row["reference"])); row["vivant"] = False
            finally:
                if mien and not getattr(tl, "tx", 0): lacher()
    class Atomic:
        def __enter__(s): tl.tx = getattr(tl, "tx", 0) + 1
        def __exit__(s, *e):
            tl.tx -= 1
            if not tl.tx and getattr(tl, "tient", False): lacher()
    Facture = type("Facture", (), {"Statut": types.SimpleNamespace(BROUILLON="brouillon"), "objects": Req(),
                                   "DoesNotExist": PasTrouve})
    return row, verrou, supprimees, Inst, Facture, Atomic


def sonde(ctx=None):
    sys.dont_write_bytecode = True
    arbre = ast.parse(FICHIER.read_text(encoding="utf-8"))
    classe = next(n for n in arbre.body if isinstance(n, ast.ClassDef) and n.name == "FactureViewSet")
    f = next(n for n in classe.body if isinstance(n, ast.FunctionDef) and n.name == "perform_destroy"); f.decorator_list = []
    row, verrou, supprimees, Inst, Facture, Atomic = monde()
    mods = {"django": types.ModuleType("django"), "django.db": types.SimpleNamespace(transaction=types.SimpleNamespace(atomic=Atomic)),
            "django.db.models": types.SimpleNamespace(ProtectedError=ProtectedError), "core": types.ModuleType("core"),
            "core.numbering": types.SimpleNamespace(est_reference_provisoire=lambda r: str(r or "").startswith("BROUILLON-"))}
    sauve = {k: sys.modules.get(k) for k in mods}; sys.modules.update(mods)
    ns = {"Facture": Facture, "ConflitEtat": ConflitEtat, "transaction": mods["django.db"].transaction}
    exec(compile(ast.Module([f], []), str(FICHIER), "exec"), ns)
    destroy, issue = ns["perform_destroy"], []
    try:
        perimee = Inst()  # chargée par get_object() AVANT l'émission : brouillon / BROUILLON-7
        pris, fin = threading.Event(), threading.Event()
        def emission():
            with verrou:
                row.update(statut="emise", reference="FAC-2026-0001"); pris.set(); fin.wait(5)  # le commit libère le verrou
        def suppression():
            try: destroy(None, perimee); issue.append("supprimé (aucune exception)")
            except ConflitEtat: issue.append("ConflitEtat (409)")
            except Exception as e: issue.append(type(e).__name__)
        e, d = threading.Thread(target=emission), threading.Thread(target=suppression)
        e.start(); pris.wait(5); d.start(); time.sleep(0.4); fin.set(); e.join(6); d.join(6)
    finally:
        for k, v in sauve.items(): sys.modules.pop(k, None) if v is None else sys.modules.__setitem__(k, v)
    return {"repro": any(s != "brouillon" for s, _ in supprimees), "observe": {
        "methode": "rejeu", "fonction": "FactureViewSet.perform_destroy (DELETE factures/{id}/)",
        "scenario": "émission valide pendant que la suppression, partie d'une instance « brouillon », attend le verrou de ligne",
        "issue_du_fil_suppression": issue, "lignes_supprimees (statut, référence au moment du DELETE)": supprimees,
        "ligne_encore_en_base": row["vivant"], "autres_emplacements_non_rejoues": ["facturation_vente.modifier_montant_tranche",
        "remise_encaissement.perform_destroy/cloturer", "recouvrement.rejeter_paiement", "bon_commande.confirmer/annuler"]}}
