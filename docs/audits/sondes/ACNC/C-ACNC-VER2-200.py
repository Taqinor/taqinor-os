# flake8: noqa  (sonde HÔTE de contre-visite « vérifie ACNC » — sans Django, sans base, sans Docker)
"""C-ACNC-VER2-200 — jumeau resté ouvert d'ACNC62 : « Annuler » un BC (`BonCommandeViewSet.annuler`) relit désormais le BC
sous `select_for_update`, mais « Facturer la vente » nature complète (`facturer_vente` → `_creer_brouillon_complet`,
apps/ventes/domain/facturation_vente.py) ne verrouille que le DEVIS et lit le BC du devis SANS verrou : il juge « BC non annulé,
sans facture » puis insère la facture complète avec `bon_commande=bc`. Les deux transactions ne partagent aucun verrou : la
facture n'est pas encore validée quand l'annulation relit les factures vivantes, l'annulation écrit `annule`, les deux valident.
État final : BC `annule` portant une facture vivante — l'état qu'AUD118 et ACNC62 interdisent.

On extrait par ast les VRAIS corps de `annuler` (views/bon_commande.py) et de `_creer_brouillon_complet`, `_inserer_facture`
(domain/facturation_vente.py) ; la base est un faux à deux couches (lignes validées / écritures en attente de la transaction du
fil) avec un vrai verrou de ligne BC (threading.Lock) tenu jusqu'à la fin de l'`atomic` le plus externe. Le fil « facturer »
joue `_creer_brouillon_complet` dans une transaction (celle de `facturer_vente`, dont le verrou du devis n'est jamais pris par
l'annulation et n'est donc pas modélisé) ; le seul point d'ordonnancement est « facture insérée, non validée → attente bornée
du commit de l'annulation ». Contrôle : le même `_creer_brouillon_complet`, réécrit par ast pour lire le BC par
`select_for_update()`, doit rendre repro False (le verrou serait alors partagé avec `annuler`)."""
SONDE = {"constat": "C-ACNC-VER2-200", "sha": "84561dcd3a",
         "attendu": "BC confirmé ; « Facturer la vente » complète et « Annuler » le BC croisés : 200 à l'annulation, BC `annule` en base portant la facture complète vivante"}
import ast, pathlib, sys, threading, types
sys.dont_write_bytecode = True
RACINE = pathlib.Path(__file__).resolve().parents[4]
VUE = "backend/django_core/apps/ventes/views/bon_commande.py"
VENTE = "backend/django_core/apps/ventes/domain/facturation_vente.py"


def _fonction(chemin, nom, classe=None):
    arbre = ast.parse((RACINE / chemin).read_text(encoding="utf-8"))
    noeuds = arbre.body
    if classe:
        noeuds = next(n for n in arbre.body if isinstance(n, ast.ClassDef) and n.name == classe).body
    n = next(n for n in noeuds if isinstance(n, ast.FunctionDef) and n.name == nom)
    n.decorator_list = []
    return n


def _bc_sous_verrou(fn):
    """Contrôle : la lecture du BC du devis passe par `select_for_update()` (correctif minimal côté facturation)."""
    src = ast.unparse(fn)
    cible = "BonCommande.objects.filter("
    assert cible in src, "lecture du BC introuvable dans _creer_brouillon_complet"
    return ast.parse(src.replace(cible, "BonCommande.objects.select_for_update().filter(", 1)).body[0]


def _jouer(annuler_ast, complet_ast, inserer_ast):
    St = types.SimpleNamespace(EN_ATTENTE="en_attente", CONFIRME="confirme", LIVRE="livre", ANNULE="annule")
    FSt = types.SimpleNamespace(BROUILLON="brouillon", ANNULEE="annulee")
    TF = types.SimpleNamespace(COMPLETE="complete")
    base = {"bc": {"statut": St.CONFIRME}, "factures": []}  # lignes VALIDÉES
    verrou_bc = threading.Lock()
    local = threading.local()
    ev_insere, ev_commit_annuler = threading.Event(), threading.Event()
    trace = []

    def nom(): return threading.current_thread().name

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
                    trace.append(nom() + " : commit")
                    if nom() == "annuler": ev_commit_annuler.set()
                for v in local.verrous: v.release()
            return False

    def en_transaction(): return getattr(local, "prof", 0) > 0

    class BC:  # copie d'une ligne BC lue en base
        def __init__(s):
            s.__dict__.update(base["bc"]); s.pk = 1; s.company = "co"; s.company_id = 1; s.devis_id = 7
            s.livraisons = types.SimpleNamespace(exists=lambda: False)
        def save(s, *a, **k):
            if en_transaction(): local.attente["bc"] = {"statut": s.statut}
            else: base["bc"]["statut"] = s.statut
            trace.append(nom() + " : bc.save(statut=" + s.statut + ")")

    class QsBC:
        def __init__(s, verrou=False): s.verrou = verrou
        def select_for_update(s): return QsBC(True)
        def _prendre(s):
            if s.verrou:
                if not en_transaction(): raise RuntimeError("select_for_update hors transaction")
                verrou_bc.acquire(); local.verrous.append(verrou_bc)
                trace.append(nom() + " : verrou BC pris")
        def get(s, pk):
            s._prendre(); return BC()
        def filter(s, **k): return s
        def first(s):
            s._prendre(); bc = BC()
            trace.append(nom() + " : BC lu (statut=" + bc.statut + ", verrou=" + str(s.verrou) + ")")
            return bc

    class QsF:
        def __init__(s, bc=None): s.bc = bc
        def filter(s, bon_commande=None, **k): return QsF(bon_commande)
        def exclude(s, **k): return s
        def _vivantes(s):
            vues = list(base["factures"]) + (list(local.attente["factures"]) if en_transaction() else [])
            return [f for f in vues if f.statut != FSt.ANNULEE]
        def exists(s):
            r = bool(s._vivantes()); trace.append(nom() + " : facture sur le BC ? " + str(r)); return r
        def first(s):
            r = (s._vivantes() or [None])[0]
            trace.append(nom() + " : facture vivante lue = " + repr(r and r.reference)); return r
        def create(s, **kw):
            f = types.SimpleNamespace(**kw); local.attente["factures"].append(f)
            trace.append(nom() + " : facture créée " + kw["reference"] + " (bon_commande=" + repr(kw["bon_commande"] and kw["bon_commande"].pk) + ")")
            return f

    BonCommande = types.SimpleNamespace(Statut=St, objects=QsBC())
    Facture = types.SimpleNamespace(Statut=FSt, TypeFacture=TF, objects=QsF())

    class Response:
        def __init__(s, data=None, status=200): s.data, s.status_code = data, status

    def module(n, **attrs):
        m = types.ModuleType(n); m.__dict__.update(attrs); m.__path__ = []; return m

    def copier(facture, devis):  # copier_devis_sur_facture : point d'ordonnancement (facture insérée, non validée)
        ev_insere.set(); ev_commit_annuler.wait(1.0); return facture

    faux = {
        "apps": module("apps"), "apps.ventes": module("apps.ventes"),
        "apps.ventes.models": module("apps.ventes.models", BonCommande=BonCommande, Facture=Facture),
        "apps.ventes.domain": module("apps.ventes.domain"),
        "apps.ventes.domain.facturation_ops": module("apps.ventes.domain.facturation_ops",
                                                     copier_devis_sur_facture=copier, entete_facture_depuis_devis=lambda d: {}),
        "apps.ventes.utils": module("apps.ventes.utils"),
        "apps.ventes.utils.company_settings": module("apps.ventes.utils.company_settings", create_provisoire=lambda fn: fn("BROUILLON-9")),
    }
    sauve = {k: sys.modules.get(k) for k in faux}
    sys.modules.update(faux)
    gv = {"__builtins__": __builtins__, "__package__": "apps.ventes.domain", "__name__": "apps.ventes.domain.facturation_vente",
          "_revue_initiale": lambda devis, user: {}}
    g = {"__builtins__": __builtins__, "__package__": "apps.ventes.views", "__name__": "apps.ventes.views.bon_commande",
         "transaction": types.SimpleNamespace(atomic=Atomic), "BonCommande": BonCommande, "Facture": Facture,
         "Response": Response, "status": types.SimpleNamespace(HTTP_409_CONFLICT=409),
         "BonCommandeSerializer": lambda bc: types.SimpleNamespace(data={"statut": bc.statut}),
         "_reserver_stock_bc_actif": lambda company: False}
    reponses = {}
    try:
        for n in (inserer_ast, complet_ast):
            exec(compile(ast.Module([n], []), VENTE, "exec"), gv)
        exec(compile(ast.Module([annuler_ast], []), VUE, "exec"), g)
        devis = types.SimpleNamespace(pk=7, company_id=1, company="co", client="cl")

        class Vue:
            def get_object(s): return BC()

        def fil_facturer():
            with Atomic():  # la transaction de facturer_vente (verrou du devis : jamais pris par « Annuler »)
                f = gv["_creer_brouillon_complet"](devis, "responsable_2", None)
            reponses["facturer_vente"] = {"facture": f.reference, "bon_commande": f.bon_commande and f.bon_commande.pk}

        def fil_annuler():
            ev_insere.wait(2.0)  # « Annuler » part pendant que « Facturer la vente » est en vol
            reponses["annuler"] = g["annuler"](Vue(), types.SimpleNamespace(user="responsable_1", data={})).status_code

        fils = [threading.Thread(target=fil_facturer, name="facturer", daemon=True),
                threading.Thread(target=fil_annuler, name="annuler", daemon=True)]
        for f in fils: f.start()
        for f in fils: f.join(10)
    finally:
        for k, v in sauve.items(): sys.modules.pop(k, None) if v is None else sys.modules.__setitem__(k, v)
    vivantes = [f.reference for f in base["factures"] if f.statut != FSt.ANNULEE and f.bon_commande is not None]
    return {"repro": base["bc"]["statut"] == St.ANNULE and bool(vivantes),
            "reponses": reponses, "bc_statut_final": base["bc"]["statut"], "factures_vivantes_sur_le_bc": vivantes, "trace": trace}


def sonde(ctx=None):
    annuler = _fonction(VUE, "annuler", "BonCommandeViewSet")
    complet = _fonction(VENTE, "_creer_brouillon_complet")
    inserer = _fonction(VENTE, "_inserer_facture")
    reel = _jouer(annuler, complet, inserer)
    controle = _jouer(annuler, _bc_sous_verrou(complet), inserer)
    src_annuler, src_complet = ast.unparse(annuler), ast.unparse(complet)
    return {"repro": reel["repro"], "observe": {
        "methode": "rejeu (vrais BonCommandeViewSet.annuler, _creer_brouillon_complet et _inserer_facture extraits par ast, base "
                   "factice validé/en attente, vrai verrou de ligne BC tenu jusqu'à la fin d'atomic, deux fils)",
        "scenario": "BC confirmé du devis, sans facture ; responsable 2 « Facturer la vente » (complète) depuis la fiche du devis, "
                    "responsable 1 « Annuler » le BC depuis la liste pendant la facturation",
        "code_reel": reel,
        "controle_bc_lu_sous_verrou": {k: controle[k] for k in ("repro", "reponses", "bc_statut_final", "factures_vivantes_sur_le_bc")},
        "annuler_select_for_update": "select_for_update" in src_annuler,
        "creer_brouillon_complet_select_for_update": "select_for_update" in src_complet}}


if __name__ == "__main__":
    import json, os
    print(json.dumps(sonde(), ensure_ascii=False, indent=1, default=str)); sys.stdout.flush()
    os._exit(0)
