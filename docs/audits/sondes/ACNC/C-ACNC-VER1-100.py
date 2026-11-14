# flake8: noqa  (sonde HÔTE de contre-visite « vérifie ACNC » — sans Django, sans base, sans Docker)
"""C-ACNC-VER1-100 — jumeau d'ACNC30 resté ouvert : « Annuler » une livraison expédiée lit `stock_mouvemente` sur l'instance de
`get_object()` SANS verrou ; deux « Annuler » croisés (deux copies chargées avant le commit de l'autre) font chacun le contre-transfert
camionnette → dépôt. On extrait par ast la VRAIE `LivraisonViewSet.annuler` (views/livraison.py) et la VRAIE
`contre_transferer_stock_livraison` (services.py) ; `transfer_stock` est un faux qui déplace la quantité si la source suffit."""
SONDE = {"constat": "C-ACNC-VER1-100", "sha": "47f925be1",
         "attendu": "camionnette partagée (5 de cette livraison + 5 d'une autre) : deux Annuler sur copies périmées = 2 contre-transferts, "
                    "dépôt 10 au lieu de 5, camionnette 0 au lieu de 5 (stock par emplacement faux)"}
import ast, pathlib, sys, types
sys.dont_write_bytecode = True
RACINE = pathlib.Path(__file__).resolve().parents[4]
VUE = "backend/django_core/apps/installations/views/livraison.py"
SERVICE = "backend/django_core/apps/installations/services.py"


def _fonction(chemin, nom, classe=None):
    arbre = ast.parse((RACINE / chemin).read_text(encoding="utf-8"))
    noeuds = arbre.body
    if classe:
        noeuds = next(n for n in arbre.body if isinstance(n, ast.ClassDef) and n.name == classe).body
    n = next(n for n in noeuds if isinstance(n, ast.FunctionDef) and n.name == nom)
    n.decorator_list = []
    return n


def sonde(ctx=None):
    stock = {"van": 10, "depot": 0}  # 5 de CETTE livraison + 5 d'une autre livraison expédiée (camionnette unique par société)
    transferts = []

    def transfer_stock(*, company, user, produit_id, source_id, destination_id, quantite, note="", **kw):
        if stock[source_id] < quantite:
            raise ValueError("stock insuffisant")
        stock[source_id] -= quantite; stock[destination_id] += quantite; transferts.append(quantite)

    faux = types.ModuleType("apps.stock.services"); faux.transfer_stock = transfer_stock
    sauve = {k: sys.modules.get(k) for k in ("apps", "apps.stock", "apps.stock.services")}
    sys.modules.update({"apps": types.ModuleType("apps"), "apps.stock": types.ModuleType("apps.stock"), "apps.stock.services": faux})
    St = types.SimpleNamespace(EN_TRANSIT="en_transit", ANNULEE="annulee", LIVREE="livree")
    base = {"statut": St.EN_TRANSIT, "stock_mouvemente": True}  # la ligne en base (commit)

    class Copie:  # ce que rend get_object() : une copie lue SANS verrou
        def __init__(s):
            s.__dict__.update(base); s.company = "co"; s.depot_id = "depot"; s.reference = "LIV-1"
            s.lignes = types.SimpleNamespace(select_related=lambda *a: types.SimpleNamespace(
                all=lambda: [types.SimpleNamespace(produit_id=1, quantite=5)]))
        def save(s, update_fields=None):
            for f in update_fields or ("statut", "stock_mouvemente"): base[f] = getattr(s, f)

    def exiger(liv, cible):
        if liv.statut == St.ANNULEE: raise ValueError("transition refusée")

    g = {"__builtins__": __builtins__, "Livraison": types.SimpleNamespace(Statut=St), "_exiger_transition_livraison": exiger,
         "_emplacement_van": lambda company: types.SimpleNamespace(id="van"),
         "logger": types.SimpleNamespace(warning=lambda *a, **k: None)}
    try:
        for chemin, nom, classe in ((SERVICE, "contre_transferer_stock_livraison", None), (VUE, "annuler", "LivraisonViewSet")):
            n = _fonction(chemin, nom, classe)
            exec(compile(ast.Module([n], []), chemin, "exec"), g)
        source_annuler = ast.unparse(_fonction(VUE, "annuler", "LivraisonViewSet"))
        copies = {}

        class Vue:
            def get_object(s): return copies["courante"]
            def _set_statut(s, request, statut):
                liv = copies["courante"]; liv.statut = statut; liv.save(update_fields=["statut"]); return statut
        a, b = Copie(), Copie()  # deux « Annuler » croisés : chacun a chargé la ligne avant le commit de l'autre
        reponses = []
        for c in (a, b):
            copies["courante"] = c
            try: reponses.append(g["annuler"](Vue(), types.SimpleNamespace(user="u")))
            except ValueError as e: reponses.append("refus : " + str(e))
    finally:
        for k, v in sauve.items(): sys.modules.pop(k, None) if v is None else sys.modules.__setitem__(k, v)
    return {"repro": len(transferts) == 2, "observe": {
        "methode": "rejeu (vraies LivraisonViewSet.annuler et contre_transferer_stock_livraison extraites par ast, faux transfer_stock, deux copies périmées)",
        "scenario": "livraison expédiée (5 unités ventilées), camionnette partagée à 10, deux « Annuler » croisés",
        "reponses": reponses, "contre_transferts": len(transferts), "stock_final": dict(stock), "attendu_sain": {"van": 5, "depot": 5},
        "annuler_relit_sous_verrou": "select_for_update" in source_annuler,
        "latent": "route POST installations/livraisons/<id>/annuler/ servie, aucun écran (installationsApi.js sans appelant) ; aucune tâche ACNC ne la porte"}}


if __name__ == "__main__":
    import json
    print(json.dumps(sonde(), ensure_ascii=False, indent=1, default=str))
