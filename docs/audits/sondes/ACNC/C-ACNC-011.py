# flake8: noqa  (sonde HÔTE d'audit PF9 « doubles clics, gestes rejoués, courses », groupe ACNC — sans Django, sans base, sans Docker)
"""C-ACNC-011 — SAV : la pièce (« Retirer ») et le prêt (« Retourner ») sont lus HORS verrou. On extrait par ast la VRAIE `TicketViewSet.supprimer_piece`
et la VRAIE `services.retourner_pret_equipement` et on les EXÉCUTE en deux threads croisés (lectures avant tout commit) sur un faux monde READ COMMITTED
avec un faux verrou de ligne produit tenu jusqu'au commit ; on lit le stock final."""
SONDE = {"constat": "C-ACNC-011", "sha": "3acfee471",
         "attendu": "deux « Retirer » croisés d'une pièce ×3 sur stock 10 -> 16 (au lieu de 13) ; deux « Retourner » croisés d'un prêt sur stock 9 -> 11 (au lieu de 10)"}
import ast, contextlib, pathlib, sys, threading, types
sys.dont_write_bytecode = True
RACINE = pathlib.Path(__file__).resolve().parents[4]
DJ = RACINE / "backend/django_core"


def fonction(chemin, nom, classe, ns):
    corps = ast.parse((DJ / chemin).read_text(encoding="utf-8")).body
    if classe: corps = next(n for n in corps if isinstance(n, ast.ClassDef) and n.name == classe).body
    f = next(n for n in corps if isinstance(n, ast.FunctionDef) and n.name == nom); f.decorator_list = []
    exec(compile(ast.Module([f], []), chemin, "exec"), ns); return ns[nom]


def installer(**mods):
    sauve = {n: sys.modules.get(n) for n in ("apps", "apps.stock", "apps.sav", *mods)}
    for n in sauve: sys.modules[n] = types.ModuleType(n)
    for n, attrs in mods.items(): sys.modules[n].__dict__.update(attrs)
    return sauve


def restaurer(sauve):
    for n, m in sauve.items(): sys.modules.pop(n, None) if m is None else sys.modules.__setitem__(n, m)


def croiser(fns):
    out, ts = [], [threading.Thread(target=lambda f=f: out.append(f())) for f in fns]
    [t.start() for t in ts]; [t.join(15) for t in ts]; return out


def attendre(b):
    try: b.wait(timeout=3)  # les deux lectures précèdent tout commit ; un correctif qui relit sous verrou casse la barrière : on continue
    except threading.BrokenBarrierError: pass


def piece():
    st, verrou, tl, b = types.SimpleNamespace(stock=10, vivante=True, mouvements=[]), threading.Lock(), threading.local(), threading.Barrier(2)
    class Existe(Exception): pass
    class Piece:
        id, quantite, stock_decremente, produit_id, produit = 7, 3, True, 1, types.SimpleNamespace(nom="Panneau")
        def delete(s): tl.suppr = True  # visible au COMMIT seulement
    class Qs:
        def select_related(s, *a): return s
        def select_for_update(s): return s
        def get(s, pk):
            visible = st.vivante; attendre(b)
            if not visible: raise PieceConsommee.DoesNotExist()
            return Piece()
    class PieceConsommee: DoesNotExist = Existe
    @contextlib.contextmanager
    def atomic():
        tl.suppr = False
        try: yield
        finally:  # COMMIT
            if tl.suppr: st.vivante = False
            if getattr(tl, "tient", False): tl.tient = False; verrou.release()
    def verrouiller(pk):
        verrou.acquire(); tl.tient = True; return types.SimpleNamespace(quantite_stock=st.stock)  # relu frais sous verrou
    def record(**kw): st.mouvements.append(kw["quantite_apres"]); st.stock = kw["quantite_apres"]
    sauve = installer(**{"apps.stock.services": dict(mouvement_type_entree=lambda: "entree", record_stock_movement=record, verrouiller_produit=verrouiller)})
    try:
        ns = dict(PieceConsommee=PieceConsommee, transaction=types.SimpleNamespace(atomic=atomic), activity=types.SimpleNamespace(log_note=lambda *a, **k: None),
                  Response=lambda data=None, status=200: status, PermissionDenied=Exception,
                  DroitDeLaGrille=lambda c: (lambda: types.SimpleNamespace(has_permission=lambda r, v: True, message="")))
        f = fonction("apps/sav/views.py", "supprimer_piece", "TicketViewSet", ns)
        vue = types.SimpleNamespace(get_object=lambda: types.SimpleNamespace(company="C", reference="SAV-1", pieces=Qs()))
        sorties = croiser([lambda: f(vue, types.SimpleNamespace(user="u"), pk=1, piece_id="7")] * 2)
    finally: restaurer(sauve)
    return {"statuts": sorted(sorties), "mouvements_entree": len(st.mouvements), "stock_final": st.stock, "attendu": 13}


def pret():
    base, verrou, tl, b = {"stock": 9, "pret": dict(statut="en_cours", stock_sorti=True, stock_reintegre=False), "n": 0}, threading.Lock(), threading.local(), threading.Barrier(2)
    class Ligne:
        def __init__(s): s.__dict__.update(base["pret"], id=1, pk=1, company="C", ticket=types.SimpleNamespace(reference="SAV-1"), produit=Prod())
        def save(s, update_fields=None): tl.ecrit = {c: getattr(s, c) for c in update_fields or []}
    class Prod:
        pk = 1
        def refresh_from_db(s, *a, **k): s.quantite_stock = tl.stock if hasattr(tl, "stock") else base["stock"]
    def prendre():
        if not getattr(tl, "tient", False): verrou.acquire(); tl.tient = True
    def record(**kw): prendre(); base["n"] += 1; tl.stock = kw["quantite_apres"]
    class PretEquipement:
        Statut = types.SimpleNamespace(EN_COURS="en_cours", RETOURNE="retourne")
        class objects:
            @staticmethod
            def select_for_update(): prendre(); return types.SimpleNamespace(get=lambda **k: Ligne(), filter=lambda **k: types.SimpleNamespace(first=lambda: Ligne()))
    sauve = installer(**{"apps.stock.services": dict(mouvement_type_entree=lambda: "entree", record_stock_movement=record), "apps.sav.models": dict(PretEquipement=PretEquipement)})
    try:
        retourner = fonction("apps/sav/services.py", "retourner_pret_equipement", None, dict(__name__="apps.sav.services", __package__="apps.sav"))
        def requete():
            tl.__dict__.clear(); pret_charge = Ligne(); attendre(b)  # la vue charge le prêt (lecture validée, sans verrou) avant le commit de l'autre
            retourner(pret=pret_charge, date_retour_reelle=None, user="u")
            if hasattr(tl, "stock"): base["stock"] = tl.stock; base["pret"].update(tl.ecrit)  # COMMIT
            if getattr(tl, "tient", False): verrou.release()
        croiser([requete] * 2)
    finally: restaurer(sauve)
    return {"mouvements_entree": base["n"], "stock_final": base["stock"], "attendu": 10, "note": "11 si la 2e lecture suit le commit, 10 (mise à jour perdue) sinon : le critère est le nombre de mouvements (1 attendu)"}


def sonde(ctx=None):
    p, r = piece(), pret()
    return {"repro": p["mouvements_entree"] != 1 or r["mouvements_entree"] != 1, "observe": {
        "methode": "rejeu (vraies supprimer_piece et retourner_pret_equipement extraites par ast, threads croisés, faux verrou de ligne produit)",
        "retirer_piece_x3_stock_10": p, "retourner_pret_stock_9": r,
        "latent": "0 pièce SAV et 0 prêt en prod ; creer_pret_equipement (stock lu avant verrou) et pieces (pose sans clé) non rejoués ici"}}
