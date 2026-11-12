# flake8: noqa  (sonde hôte PF9 « doubles clics, gestes rejoués, courses », groupe ACNC — sans Django, sans base)
"""C-ACNC-004 — deux acheteurs sur le même bon de commande fournisseur : le second enregistrement écrase le premier.
Rejeu de la VRAIE `BonCommandeFournisseurSerializer.update` + `_upsert_lignes` (ast ; ORM bouchonné, lignes et statut en mémoire) par
un second onglet resté sur l'état chargé AVANT l'autre geste, avec le jeton `lock_version` qu'il avait lu : (1) l'autre a ajouté la
ligne 3 ; (2) l'autre a cliqué « Envoyer » (statut envoyé commité), le second enregistre un simple commentaire."""
SONDE = {"constat": "C-ACNC-004", "sha": "3acfee471",
         "attendu": "(1) la ligne 3 ajoutée par l'autre est supprimée en silence ; (2) le statut « envoyé » est réécrit en « brouillon » "
                    "par le save() complet de l'instance périmée ; aucun 409"}
import ast, pathlib, sys, types
RACINE = pathlib.Path(__file__).resolve().parents[4]
FICHIER = RACINE / "backend/django_core/apps/stock/serializers.py"


class ConflitEtat(Exception): pass


def sonde(ctx=None):
    sys.dont_write_bytecode = True
    arbre = ast.parse(FICHIER.read_text(encoding="utf-8"))
    cls = next(n for n in arbre.body if isinstance(n, ast.ClassDef) and n.name == "BonCommandeFournisseurSerializer")
    garde = [n for n in cls.body if (isinstance(n, ast.FunctionDef) and (n.name in ("update", "_upsert_lignes", "_devise_depuis_mad")
             or n.name.startswith("_verif") or n.name.startswith("_version") or n.name.startswith("_relire")))
             or (isinstance(n, ast.Assign) and any(getattr(t, "id", "") == "CHAMPS_LIGNE_MODIFIABLES" for t in n.targets))]
    for n in garde:
        if isinstance(n, ast.FunctionDef) and not any(getattr(d, "id", "") == "staticmethod" for d in n.decorator_list): n.decorator_list = []
    mod = ast.Module([ast.ClassDef(name="S", bases=[], keywords=[], body=garde, decorator_list=[], type_params=[])], [])
    ast.fix_missing_locations(mod)
    ligne_base = lambda i, p, q: {"id": i, "produit": p, "designation": "", "quantite": q, "prix_achat_unitaire": 100}
    ROW, LIGNES = {"statut": "brouillon", "notes": "", "lock_version": 0}, {}
    class Ligne:
        def __init__(s, id, **kw): s.id = id; s.frais_annexes = 0; s.prix_achat_unitaire_devise = None; s.__dict__.update(kw)
        def save(s, **k): LIGNES[s.id] = s
        def delete(s): LIGNES.pop(s.id, None)
    class Gest:
        nxt = 10
        def create(s, bon_commande, **kw): Gest.nxt += 1; LIGNES[Gest.nxt] = Ligne(Gest.nxt, **kw)
    class Bon:
        Statut = types.SimpleNamespace(BROUILLON="brouillon", ENVOYE="envoye")
        def __init__(s):
            s.__dict__.update(ROW); s.pk = 1; s.devise = None; s.taux_change = None  # instance chargée par l'onglet
            s.lignes = types.SimpleNamespace(all=lambda: list(LIGNES.values()), filter=lambda **k: [])
        def save(s, update_fields=None, **k):  # save() complet : écrit TOUS les champs de l'instance chargée
            for c in (update_fields or ROW): ROW[c] = getattr(s, c)
    class Req:
        def select_for_update(s, **k): return s
        def get(s, **k): return Bon()
        filter = lambda s, **k: s
        first = lambda s: Bon()
    Bon.objects = Req()
    atomic = type("A", (), {"__enter__": lambda s: None, "__exit__": lambda s, *a: False})
    mods = {"apps": types.ModuleType("apps"), "apps.stock": types.ModuleType("apps.stock"),
            "apps.stock.services": types.SimpleNamespace(apply_devise_ligne_bcf=lambda *a: None),
            "apps.stock.models": types.SimpleNamespace(DeviseAchat=types.SimpleNamespace(MAD="MAD"))}
    mods["apps.stock"].__path__ = []
    sauve = {k: sys.modules.get(k) for k in mods}; sys.modules.update(mods)
    ns = {"__name__": "apps.stock.serializers", "__package__": "apps.stock", "LigneBonCommandeFournisseur": types.SimpleNamespace(objects=Gest()),
          "BonCommandeFournisseur": Bon, "ConflitEtat": ConflitEtat, "transaction": types.SimpleNamespace(atomic=lambda *a, **k: atomic())}
    res = {}
    try:
        exec(compile(mod, str(FICHIER), "exec"), ns)
        enregistrer = lambda inst, **v: ns["S"]().update(inst, v)
        def tenter(inst, **v):
            try: enregistrer(inst, **v); return "accepté"
            except Exception as e: return f"{type(e).__name__} (refus)"
        for i, p, q in ((1, "P1", 5), (2, "P2", 3)): LIGNES[i] = Ligne(i, **{k: v for k, v in ligne_base(i, p, q).items() if k != "id"})
        onglet_b = Bon()  # chargé avant le geste de l'autre acheteur : lignes 1, 2, jeton 0, brouillon
        LIGNES[3] = Ligne(3, **{k: v for k, v in ligne_base(3, "P3", 7).items() if k != "id"}); ROW["lock_version"] = 1  # l'autre ajoute la ligne 3
        res["lignes"] = tenter(onglet_b, lignes=[ligne_base(1, "P1", 5), ligne_base(2, "P2", 4)], lock_version=0)
        res["ligne_3_conservee"] = 3 in LIGNES
        ROW.update(statut="brouillon", lock_version=0); onglet_c = Bon()  # un autre onglet chargé en brouillon
        ROW.update(statut="envoye", lock_version=1)  # l'autre acheteur clique « Envoyer » (commité)
        res["commentaire"] = tenter(onglet_c, notes="relance", lock_version=0)
        res["statut_final"] = ROW["statut"]
    finally:
        for k, v in sauve.items(): sys.modules.pop(k, None) if v is None else sys.modules.__setitem__(k, v)
    ecrase = res["lignes"] == "accepté" and not res["ligne_3_conservee"]
    regresse = res["statut_final"] == "brouillon" and res["commentaire"] == "accepté"
    return {"repro": ecrase or regresse, "observe": {
        "methode": "rejeu", "fonction": "BonCommandeFournisseurSerializer.update -> _upsert_lignes (PATCH bons-commande-fournisseur/{id}/)",
        "scenario": "second onglet périmé avec son jeton lock_version : (1) ligne 3 ajoutée ailleurs ; (2) « Envoyer » commité ailleurs",
        "reponse_onglet_perime_lignes": res["lignes"], "ligne_3_P3x7_conservee": res["ligne_3_conservee"],
        "reponse_onglet_perime_commentaire": res["commentaire"], "statut_final_en_base": res["statut_final"],
        "limite": "seuls update/_upsert_lignes/helpers `_verif*` du sérialiseur sont chargés ; un correctif porté par un mixin ou la vue n'est pas rejoué"}}
