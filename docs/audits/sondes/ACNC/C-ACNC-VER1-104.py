# flake8: noqa  (sonde HÔTE de contre-visite « vérifie ACNC » — sans Django, sans base, sans Docker)
"""C-ACNC-VER1-104 — ACNC7 resté ouvert sur le BC : « Annuler » (`BonCommandeViewSet.annuler`) lit l'état du BC et la facture
vivante SANS verrou ni transaction, puis `bc.save()` ; « Créer la facture » (`BonCommandeViewSet.creer_facture`) relit le BC sous
`select_for_update` et rejoue la porte. Le verrou n'est pris que d'un côté : l'annulation peut lire « aucune facture », laisser la
création verrouiller / créer / valider, puis écrire `annule` par-dessus. On extrait par ast les VRAIS corps des deux actions
(views/bon_commande.py) et la VRAIE `porte_facture_bc` (selectors_facturation.py) ; la base est un faux à deux couches (lignes
validées / écritures en attente de la transaction du fil) avec un vrai verrou de ligne (threading.Lock) tenu jusqu'à la fin de
`transaction.atomic`. Deux fils jouent les deux requêtes ; le seul point d'ordonnancement est l'intervalle « annuler a lu la facture
→ annuler écrit » (attente bornée de l'évènement « création validée »). Contrôle : la MÊME annulation, réécrite par ast pour relire
le BC sous `select_for_update` dans `transaction.atomic` (verrou partagé), doit rendre repro False."""
SONDE = {"constat": "C-ACNC-VER1-104", "sha": "8544b3672",
         "attendu": "BC confirmé, « Annuler » et « Créer la facture » croisés : 200 + 201, BC `annule` en base avec une facture vivante"}
import ast, copy, pathlib, sys, threading, types
sys.dont_write_bytecode = True
RACINE = pathlib.Path(__file__).resolve().parents[4]
VUE = "backend/django_core/apps/ventes/views/bon_commande.py"
SEL = "backend/django_core/apps/ventes/selectors_facturation.py"


def _fonction(chemin, nom, classe=None):
    arbre = ast.parse((RACINE / chemin).read_text(encoding="utf-8"))
    noeuds = arbre.body
    if classe:
        noeuds = next(n for n in arbre.body if isinstance(n, ast.ClassDef) and n.name == classe).body
    n = next(n for n in noeuds if isinstance(n, ast.FunctionDef) and n.name == nom)
    n.decorator_list = []
    return n


def _avec_verrou_partage(fn):
    """Contrôle : `bc = self.get_object()` puis TOUT le reste sous `with transaction.atomic():` après
    `bc = BonCommande.objects.select_for_update().get(pk=bc.pk)` — le correctif minimal attendu."""
    fn = copy.deepcopy(fn)
    i = next(k for k, s in enumerate(fn.body) if isinstance(s, ast.Assign) and ast.unparse(s) == "bc = self.get_object()")
    gabarit = ast.parse("with transaction.atomic():\n    bc = BonCommande.objects.select_for_update().get(pk=bc.pk)\n").body[0]
    gabarit.body.extend(fn.body[i + 1:])
    fn.body = fn.body[:i + 1] + [gabarit]
    ast.fix_missing_locations(fn)
    return fn


def _jouer(annuler_ast, creer_ast, porte_ast):
    St = types.SimpleNamespace(EN_ATTENTE="en_attente", CONFIRME="confirme", LIVRE="livre", ANNULE="annule")
    FSt = types.SimpleNamespace(BROUILLON="brouillon", ANNULEE="annulee")
    base = {"bc": {"statut": St.CONFIRME}, "factures": []}  # lignes VALIDÉES
    verrou_bc = threading.Lock()
    local = threading.local()
    ev_lu, ev_commit = threading.Event(), threading.Event()
    trace = []

    class Atomic:
        def __enter__(s):
            local.prof = getattr(local, "prof", 0) + 1
            if local.prof == 1:
                local.attente, local.verrous = {"bc": None, "factures": []}, []
        def __exit__(s, et, ev, tb):
            local.prof -= 1
            if local.prof == 0:
                if et is None:  # COMMIT
                    if local.attente["bc"] is not None: base["bc"].update(local.attente["bc"])
                    base["factures"].extend(local.attente["factures"])
                    trace.append(threading.current_thread().name + " : commit")
                    if threading.current_thread().name == "creer_facture": ev_commit.set()
                for v in local.verrous: v.release()
            return False

    def en_transaction(): return getattr(local, "prof", 0) > 0

    class BC:  # copie d'une ligne BC lue en base
        def __init__(s):
            s.__dict__.update(base["bc"]); s.pk = 1; s.company = "co"; s.company_id = 1; s.devis = None; s.devis_id = None
            s.client = "cl"; s.has_proof_of_delivery = True
            s.livraisons = types.SimpleNamespace(exists=lambda: False)
        def save(s, *a, **k):
            if en_transaction(): local.attente["bc"] = {"statut": s.statut}
            else: base["bc"]["statut"] = s.statut  # autocommit
            trace.append(threading.current_thread().name + " : bc.save(statut=" + s.statut + ")")

    class QsBC:
        def select_for_update(s): return s
        def get(s, pk):
            if not en_transaction(): raise RuntimeError("select_for_update hors transaction")
            verrou_bc.acquire(); local.verrous.append(verrou_bc)
            trace.append(threading.current_thread().name + " : verrou BC pris")
            return BC()

    class QsF:
        def __init__(s, bc=None): s.bc = bc
        def filter(s, bon_commande=None, **k): return QsF(bon_commande)
        def exclude(s, **k): return s
        def _vivantes(s):
            vues = list(base["factures"]) + (list(local.attente["factures"]) if en_transaction() else [])
            return [f for f in vues if f.statut != FSt.ANNULEE]
        def exists(s): return bool(s._vivantes())
        def first(s):
            r = (s._vivantes() or [None])[0]
            if threading.current_thread().name == "annuler":  # intervalle lecture → écriture de l'annulation
                trace.append("annuler : facture vivante lue = " + repr(r and r.reference)); ev_lu.set()
                ev_commit.wait(1.0)
            return r
        def create(s, **kw):
            f = types.SimpleNamespace(**kw); local.attente["factures"].append(f)
            trace.append(threading.current_thread().name + " : facture créée " + kw["reference"]); return f

    BonCommande = types.SimpleNamespace(Statut=St, objects=QsBC())
    Facture = types.SimpleNamespace(Statut=FSt, objects=QsF())

    class Response:
        def __init__(s, data=None, status=200): s.data, s.status_code = data, status

    def module(nom, **attrs):
        m = types.ModuleType(nom); m.__dict__.update(attrs); m.__path__ = []; return m

    faux = {
        "apps": module("apps"), "apps.ventes": module("apps.ventes"), "apps.ventes.views": module("apps.ventes.views"),
        "apps.ventes.models": module("apps.ventes.models", BonCommande=BonCommande, Facture=Facture),
        "apps.ventes.domain": module("apps.ventes.domain"),
        "apps.ventes.domain.annulation_facture": module("apps.ventes.domain.annulation_facture",
                                                        detacher_factures_annulees_du_bc=lambda bc, u: None,
                                                        retirer_brouillons_de_la_vente=lambda *a, **k: None),
        "apps.ventes.domain.facturation_ops": module("apps.ventes.domain.facturation_ops",
                                                     copier_devis_sur_facture=lambda *a: None, entete_facture_depuis_devis=lambda d: {}),
        "apps.ventes.utils": module("apps.ventes.utils"),
        "apps.ventes.utils.company_settings": module("apps.ventes.utils.company_settings", create_provisoire=lambda fn: fn("BROUILLON-1")),
        "apps.ventes.vente_facturation": module("apps.ventes.vente_facturation", factures_de_la_vente=lambda d: []),
        "core": module("core"), "core.numbering": module("core.numbering", est_reference_provisoire=lambda r: True),
        "apps.facturation": module("apps.facturation"), "apps.facturation.views": module("apps.facturation.views"),
        "apps.facturation.views.facture_gardes": module("apps.facturation.views.facture_gardes", PeutEncaisser=object),
    }
    sel = faux["apps.ventes.selectors_facturation"] = module("apps.ventes.selectors_facturation")
    sel.__dict__.update({"__package__": "apps.ventes", "__builtins__": __builtins__,
                         "exiger_devis_facturable": lambda *a: None, "DevisDejaFacture": Exception})
    exec(compile(ast.Module([porte_ast], []), SEL, "exec"), sel.__dict__)
    sauve = {k: sys.modules.get(k) for k in faux}
    sys.modules.update(faux)
    g = {"__builtins__": __builtins__, "__package__": "apps.ventes.views", "__name__": "apps.ventes.views.bon_commande",
         "transaction": types.SimpleNamespace(atomic=Atomic), "BonCommande": BonCommande, "Facture": Facture,
         "Response": Response, "status": types.SimpleNamespace(HTTP_409_CONFLICT=409, HTTP_201_CREATED=201, HTTP_403_FORBIDDEN=403),
         "BonCommandeSerializer": lambda bc: types.SimpleNamespace(data={"statut": bc.statut}),
         "FactureSerializer": lambda f, context=None: types.SimpleNamespace(data={"reference": f.reference}),
         "_reserver_stock_bc_actif": lambda company: False}
    reponses = {}
    try:
        for n in (annuler_ast, creer_ast):
            exec(compile(ast.Module([n], []), VUE, "exec"), g)

        class Vue:
            def get_object(s): return BC()  # get_object() : copie lue SANS verrou, comme DRF

        def fil_annuler():
            reponses["annuler"] = g["annuler"](Vue(), types.SimpleNamespace(user="responsable_1", data={})).status_code

        def fil_creer():
            ev_lu.wait(2.0)  # « Créer la facture » part pendant que l'annulation est en vol
            reponses["creer_facture"] = g["creer_facture"](Vue(), types.SimpleNamespace(user="responsable_2", data={})).status_code

        fils = [threading.Thread(target=fil_annuler, name="annuler"), threading.Thread(target=fil_creer, name="creer_facture")]
        for f in fils: f.start()
        for f in fils: f.join(10)
    finally:
        for k, v in sauve.items(): sys.modules.pop(k, None) if v is None else sys.modules.__setitem__(k, v)
    vivantes = [f.reference for f in base["factures"] if f.statut != FSt.ANNULEE]
    return {"repro": base["bc"]["statut"] == St.ANNULE and bool(vivantes),
            "reponses": reponses, "bc_statut_final": base["bc"]["statut"], "factures_vivantes_sur_le_bc": vivantes, "trace": trace}


def sonde(ctx=None):
    annuler = _fonction(VUE, "annuler", "BonCommandeViewSet")
    creer = _fonction(VUE, "creer_facture", "BonCommandeViewSet")
    porte = _fonction(SEL, "porte_facture_bc")
    reel = _jouer(annuler, creer, porte)
    controle = _jouer(_avec_verrou_partage(annuler), creer, porte)
    src_annuler, src_creer = ast.unparse(annuler), ast.unparse(creer)
    return {"repro": reel["repro"], "observe": {
        "methode": "rejeu (vrais BonCommandeViewSet.annuler / creer_facture et porte_facture_bc extraits par ast, base factice "
                   "validé/en attente, vrai verrou de ligne tenu jusqu'à la fin d'atomic, deux fils)",
        "scenario": "BC confirmé sans facture ; responsable 1 « Annuler », responsable 2 « Créer la facture » pendant l'annulation",
        "code_reel": reel,
        "controle_verrou_partage": {"repro": controle["repro"], "reponses": controle["reponses"],
                                    "bc_statut_final": controle["bc_statut_final"],
                                    "factures_vivantes_sur_le_bc": controle["factures_vivantes_sur_le_bc"]},
        "annuler_select_for_update": "select_for_update" in src_annuler, "annuler_atomic": "transaction.atomic" in src_annuler,
        "creer_facture_select_for_update": "select_for_update" in src_creer}}


if __name__ == "__main__":
    import json
    print(json.dumps(sonde(), ensure_ascii=False, indent=1, default=str))
