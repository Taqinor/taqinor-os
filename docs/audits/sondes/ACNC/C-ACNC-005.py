# flake8: noqa  (sonde HÔTE d'audit PF9 « doubles clics, gestes rejoués, courses », groupe ACNC — sans Django, sans base, sans Docker)
"""C-ACNC-005 — un mouvement de stock manuel ou un transfert rejoué (réponse perdue, « Enregistrer » de nouveau) crée un 2e objet.
On extrait par ast la VRAIE `MouvementStockViewSet.perform_create` et la VRAIE `services.transfer_stock`, on les EXÉCUTE deux fois avec le
même corps (et la même clé d'idempotence glissée dans les porteurs plausibles) sur un faux ORM ; on compte les mouvements / transferts."""
SONDE = {"constat": "C-ACNC-005", "sha": "3acfee471",
         "attendu": "le même corps ENTRÉE 5 joué deux fois crée 2 mouvements (stock 100 -> 110) ; le même transfert de 3 joué deux fois crée 2 transferts (destination 6)"}
import ast, contextlib, pathlib, re, sys, types
sys.dont_write_bytecode = True
RACINE = pathlib.Path(__file__).resolve().parents[4]
DJ = RACINE / "backend/django_core"
CLE = "cle-rejeu-0001"


def fonction(chemin, nom, classe, ns):
    """Extrait par ast la VRAIE méthode/fonction `nom` (décorateurs ôtés) et la compile dans `ns`."""
    corps = ast.parse((DJ / chemin).read_text(encoding="utf-8")).body
    if classe: corps = next(n for n in corps if isinstance(n, ast.ClassDef) and n.name == classe).body
    f = next(n for n in corps if isinstance(n, ast.FunctionDef) and n.name == nom); f.decorator_list = []
    exec(compile(ast.Module([f], []), chemin, "exec"), ns); return ns[nom]


class Erreur(Exception): pass
atomic = lambda *a, **k: contextlib.nullcontext()


def rejeu_mouvement():
    base = {"stock": 100, "mouvements": []}
    class Produit:
        pk, company = 1, "C1"
        class objects:
            select_for_update = staticmethod(lambda: types.SimpleNamespace(get=lambda pk: types.SimpleNamespace(pk=1, company="C1", quantite_stock=base["stock"])))
    class MouvementStock:
        TypeMouvement = types.SimpleNamespace(ENTREE="entree", SORTIE="sortie", AJUSTEMENT="ajustement", TRANSFERT="transfert", REBUT="rebut")
        objects = types.SimpleNamespace(filter=lambda **k: types.SimpleNamespace(update=lambda **u: None))
    def record(**kw):
        base["mouvements"].append((kw["type_mouvement"], kw["quantite"], kw["quantite_avant"], kw["quantite_apres"])); base["stock"] = kw["quantite_apres"]
        return types.SimpleNamespace(pk=len(base["mouvements"]))
    sauve = {n: sys.modules.get(n) for n in ("rest_framework", "rest_framework.exceptions", "apps", "apps.stock", "apps.stock.services", "apps.stock.services_wms")}
    for n in sauve: sys.modules[n] = types.ModuleType(n)
    sys.modules["rest_framework.exceptions"].ValidationError = Erreur
    sys.modules["apps.stock.services"].record_stock_movement = record
    sys.modules["apps.stock.services_wms"].exiger_hors_quarantaine = lambda *a: None
    sys.modules["apps.stock.services_wms"].note_sortie_sans_lot = lambda c, p, n: n
    try:
        ns = dict(Produit=Produit, MouvementStock=MouvementStock, QUANTITE_MAX=2_000_000_000, ConflitEtat=Erreur, debordement_compteur_en_409=atomic,
                  __name__="apps.stock.views.mouvement", __package__="apps.stock.views")
        perform = fonction("apps/stock/views/mouvement.py", "perform_create", "MouvementStockViewSet", ns)
        for _ in range(2):  # même corps, même clé : deux envois du dialogue
            donnees = {"produit": Produit(), "quantite": 5, "type_mouvement": "entree", "note": "réception", "cle_idempotence": CLE, "idempotency_key": CLE}
            vue = types.SimpleNamespace(TYPES_REFUSES={}, request=types.SimpleNamespace(user="u", headers={"Idempotency-Key": CLE}, META={"HTTP_IDEMPOTENCY_KEY": CLE}))
            perform(vue, types.SimpleNamespace(validated_data=donnees, instance=None))
    finally:
        for n, m in sauve.items(): sys.modules.pop(n, None) if m is None else sys.modules.__setitem__(n, m)
    return base


def rejeu_transfert():
    etat = {"transferts": [], "dest": 0}
    principal, dest = types.SimpleNamespace(id=1, nom="Principal", is_principal=True), types.SimpleNamespace(id=2, nom="Dépôt B", is_principal=False)
    produit = types.SimpleNamespace(id=1, quantite_stock=100, stocks_emplacement=types.SimpleNamespace(select_for_update=lambda: []))
    se = types.SimpleNamespace(quantite=0, save=lambda update_fields=None: etat.__setitem__("dest", se.quantite))
    class Produit: objects = types.SimpleNamespace(select_for_update=lambda: types.SimpleNamespace(filter=lambda **k: types.SimpleNamespace(first=lambda: produit)))
    class EmplacementStock: objects = types.SimpleNamespace(filter=lambda **k: [principal, dest])
    class StockEmplacement: objects = types.SimpleNamespace(select_for_update=lambda: types.SimpleNamespace(get_or_create=lambda **k: (se, False)), get_or_create=lambda **k: (se, False))
    class TransfertStock: objects = types.SimpleNamespace(create=lambda **k: etat["transferts"].append(k) or k)
    sauve = {n: sys.modules.get(n) for n in ("django", "django.db", "apps", "apps.stock", "apps.stock.models")}
    for n in sauve: sys.modules[n] = types.ModuleType(n)
    sys.modules["django.db"].transaction = types.SimpleNamespace(atomic=atomic)
    sys.modules["apps.stock.models"].__dict__.update(Produit=Produit, EmplacementStock=EmplacementStock, StockEmplacement=StockEmplacement, TransfertStock=TransfertStock)
    try:
        ns = dict(ensure_emplacements=lambda c: None, transfert_exige_approbation=lambda *a, **k: False, quantite_en_transit=lambda c, p: 0, EtatIncompatible=Erreur,
                  logger=types.SimpleNamespace(info=lambda *a, **k: None), __name__="apps.stock.services", __package__="apps.stock")
        transfer = fonction("apps/stock/services.py", "transfer_stock", None, ns)
        for _ in range(2):
            transfer(company=types.SimpleNamespace(id=1), user=None, produit_id=1, source_id=1, destination_id=2, quantite=3, note="")
    finally:
        for n, m in sauve.items(): sys.modules.pop(n, None) if m is None else sys.modules.__setitem__(n, m)
    return etat


def sonde(ctx=None):
    mv, tr = rejeu_mouvement(), rejeu_transfert()
    src = (DJ / "apps/stock/models.py").read_text(encoding="utf-8")
    classe = next(n for n in ast.parse(src).body if isinstance(n, ast.ClassDef) and n.name == "MouvementStock")
    cle_modele = [t.id for n in ast.walk(classe) if isinstance(n, ast.Assign) for t in n.targets if isinstance(t, ast.Name) and re.search(r"idempot|^cle", t.id)]
    return {"repro": (len(mv["mouvements"]) == 2 or len(tr["transferts"]) == 2) and not cle_modele, "observe": {
        "methode": "rejeu (vraies perform_create et transfer_stock extraites par ast, faux ORM, 2 appels au même corps et à la même clé)",
        "mouvement": {"mouvements_crees": len(mv["mouvements"]), "stock_final_depuis_100": mv["stock"]},
        "transfert": {"transferts_crees": len(tr["transferts"]), "quantite_destination": tr["dest"]},
        "colonne_de_cle_sur_MouvementStock": cle_modele, "cle_rejouee": CLE,
        "autres_emplacements_latents": "reception partielle BCF, reglement / acompte / facture fournisseur : meme absence de cle (non rejoues ici)"}}
