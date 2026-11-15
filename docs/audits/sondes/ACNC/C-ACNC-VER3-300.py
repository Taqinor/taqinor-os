# flake8: noqa  (sonde HÔTE de contre-visite « vérifie ACNC » — sans Django, sans base, sans Docker)
"""C-ACNC-VER3-300 — ACNC72 appliquée « à l'identique » au jumeau de la fiche facture fournisseur
(`frontend/src/pages/stock/FacturesFournisseur.jsx::FactureDetail`) : la clé du règlement est désormais remise à zéro dès que
`montant`, `datePaiement` ou `mode` change. Or, après une réponse perdue, `ajouter` n'appelle que `onSaved` (le parent
`FacturesFournisseur` relit sa LISTE par `reload()`, jamais `selected`) et la fiche garde sa copie locale
`useState(factureProp)` : le dialogue montre encore l'ancien solde et « Aucun paiement ». Toute retouche de la saisie avant le
second clic (date remplie, mode changé, montant retapé) part avec une clé NEUVE : le serveur crée un second règlement, le plafond
`verrouiller_facture_fournisseur_et_verifier_solde` ne refusant que ce qui dépasse le solde dû.

Avant ACNC72 la même retouche recevait le 409 `IdempotencyConflict` (clé gardée, corps différent) : rien n'était écrit. Le
ledger (`PaiementsFournisseurLedgerPage.jsx`) relit, lui, le registre affiché (hypothèse explicite d'ACNC72) ; la fiche, non.

Partie serveur : on exécute les VRAIS `IdempotentCreateMixin`, `_reserver`, `_liberer`, `_fingerprint`
(core/idempotency.py) et `verrouiller_facture_fournisseur_et_verifier_solde` (apps/stock/services.py), extraits par ast, avec
le suffixe réel `paiements.<pk>` de `FactureFournisseurViewSet.paiements` ; seuls `IdempotencyRecord` (contrainte unique
(company, endpoint, key)) et `FactureFournisseur` (solde dû) sont des faux en mémoire. Partie écran : lecture du VRAI composant
(dépendances de la remise de clé, branche « sans réponse » d'`ajouter`, copie locale de la facture, `onSaved` du parent).
Contrôles : (1) clé gardée (écran d'avant ACNC72) et saisie retouchée ⇒ 409, un règlement ; (2) saisie inchangée ⇒ rejeu,
un règlement."""
SONDE = {"constat": "C-ACNC-VER3-300", "sha": "8fc408bf61",
         "attendu": "règlement de 3 000 sur une facture de 10 000, réponse perdue, date retouchée puis nouveau clic : 2 règlements, solde 4 000 au lieu de 7 000"}
import ast, hashlib, json, pathlib, re, sys, types
from decimal import Decimal
sys.dont_write_bytecode = True
RACINE = pathlib.Path(__file__).resolve().parents[4]
IDEM = "backend/django_core/core/idempotency.py"
SERV = "backend/django_core/apps/stock/services.py"
VUE = "backend/django_core/apps/stock/views/facture_fournisseur.py"
JSX = "frontend/src/pages/stock/FacturesFournisseur.jsx"


def _noeuds(chemin, noms):
    arbre = ast.parse((RACINE / chemin).read_text(encoding="utf-8"))
    return [n for n in arbre.body if isinstance(n, (ast.FunctionDef, ast.ClassDef)) and n.name in noms]


def _jouer(envois):
    """`envois` = [(clé, corps)] envoyés à POST /stock/factures-fournisseur/<pk>/paiements/ ; rend les codes et l'état."""
    class IntegrityError(Exception): pass
    class Conflit(Exception): pass
    class EnCours(Exception): pass

    lignes, paiements = [], []
    facture = types.SimpleNamespace(pk=41, montant_ttc=Decimal("10000"), solde_du=Decimal("10000"))

    class Etat:
        EN_COURS, TERMINE = "en_cours", "termine"

    class Ligne(types.SimpleNamespace):
        def save(s, update_fields=None): pass

    class Qs:
        def __init__(s, crit): s.crit = crit
        def _match(s): return [l for l in lignes if all(getattr(l, k) == v for k, v in s.crit.items())]
        def first(s): return (s._match() or [None])[0]
        def delete(s):
            for l in s._match(): lignes.remove(l)

    class Objects:
        def create(s, **kw):
            if any(l.company == kw["company"] and l.endpoint == kw["endpoint"] and l.key == kw["key"] for l in lignes):
                raise IntegrityError("core_idempotencyrecord_unique")
            l = Ligne(created_at=0, **kw); lignes.append(l); return l
        def filter(s, **kw): return Qs(kw)

    class Atomic:
        def __enter__(s): return s
        def __exit__(s, *a): return False

    class Response:
        def __init__(s, data=None, status=200): s.data, s.status_code = data, status

    class FFObjects:
        def select_for_update(s): return s
        def get(s, pk): return types.SimpleNamespace(pk=pk, solde_du=facture.solde_du)

    def module(n, **a):
        m = types.ModuleType(n); m.__dict__.update(a); m.__path__ = []; return m

    faux = {"rest_framework": module("rest_framework"),
            "rest_framework.response": module("rest_framework.response", Response=Response),
            "django": module("django"), "django.utils": module("django.utils", timezone=types.SimpleNamespace(now=lambda: 10**9)),
            "apps": module("apps"), "apps.stock": module("apps.stock"),
            "apps.stock.models": module("apps.stock.models", FactureFournisseur=types.SimpleNamespace(objects=FFObjects()))}
    g = {"__builtins__": __builtins__, "__name__": "core.idempotency", "json": json, "hashlib": hashlib,
         "transaction": types.SimpleNamespace(atomic=Atomic), "IntegrityError": IntegrityError,
         "IdempotencyRecord": types.SimpleNamespace(objects=Objects(), Etat=Etat),
         "IdempotencyConflict": Conflit, "IdempotencyEnCours": EnCours, "RESERVATION_EXPIREE": 0,
         "IDEMPOTENCY_KEY_HEADER": "HTTP_IDEMPOTENCY_KEY", "logger": types.SimpleNamespace(warning=lambda *a, **k: None)}
    gs = {"__builtins__": __builtins__, "__name__": "apps.stock.services", "__package__": "apps.stock"}
    sauve = {k: sys.modules.get(k) for k in faux}
    sys.modules.update(faux)
    try:
        for n in _noeuds(IDEM, {"_fingerprint", "IdempotentCreateMixin", "_reserver", "_liberer"}):
            exec(compile(ast.Module([n], []), IDEM, "exec"), g)
        for n in _noeuds(SERV, {"verrouiller_facture_fournisseur_et_verifier_solde"}):
            exec(compile(ast.Module([n], []), SERV, "exec"), gs)
        Vue = type("FactureFournisseurViewSet", (g["IdempotentCreateMixin"],), {"__module__": "apps.stock.views.facture_fournisseur"})

        def ajouter(corps):  # le geste réel : plafond relu sous verrou, puis règlement enregistré
            montant = Decimal(str(corps["montant"]))
            try:
                gs["verrouiller_facture_fournisseur_et_verifier_solde"](facture, montant)
            except ValueError as exc:
                return Response({"detail": str(exc)}, status=409)
            paiements.append({"id": len(paiements) + 1, "montant": str(montant), "date_paiement": corps["date_paiement"]})
            facture.solde_du -= montant
            return Response({"id": facture.pk, "solde_du": str(facture.solde_du)}, status=201)

        codes = []
        for cle, corps in envois:
            req = types.SimpleNamespace(data=corps, META={"HTTP_IDEMPOTENCY_KEY": cle}, headers={},
                                        user=types.SimpleNamespace(company="societe-1"))
            try:
                r = Vue()._avec_idempotence(req, lambda corps=corps: ajouter(corps), suffixe=f"paiements.{facture.pk}")
                codes.append(r.status_code)
            except Conflit:
                codes.append("409 IdempotencyConflict")
        return {"codes": codes, "reglements": paiements, "solde_du": str(facture.solde_du)}
    finally:
        for k, v in sauve.items(): sys.modules.pop(k, None) if v is None else sys.modules.__setitem__(k, v)


def _ecran():
    src = (RACINE / JSX).read_text(encoding="utf-8")
    debut = src.index("export function FactureDetail(")
    fiche = src[debut:src.index("\nexport ", debut + 10) if "\nexport " in src[debut + 10:] else len(src)]
    remise = re.search(r"useEffect\(\(\) => \{ cleReglement\.current = null \}, \[([^\]]*)\]\)", fiche)
    ajouter = re.search(r"const ajouter = async \(\) => \{(.*?)\n  \}\n", fiche, re.S)
    branche = re.search(r"catch \(err\) \{(.*?)\}\s*finally", ajouter.group(1), re.S).group(1) if ajouter else ""
    parent = re.search(r"const onSaved = \(msg\) => \{([^}]*)\}", src)
    vue = (RACINE / VUE).read_text(encoding="utf-8")
    return {"remise_de_cle_sur": remise.group(1) if remise else None,
            "copie_locale_jamais_resynchronisee": "useState(factureProp)" in fiche and fiche.count("factureProp") == 2,
            "sans_reponse_relit_la_fiche": bool(re.search(r"setFacture|getFactureFournisseur|stockApi\.get", branche)),
            "sans_reponse_appelle": re.sub(r"\s+", " ", branche.strip())[:160],
            "onSaved_du_parent": re.sub(r"\s+", " ", parent.group(1).strip()) if parent else None,
            "suffixe_serveur_lie_a_la_facture": "suffixe=f'paiements.{pk}'" in vue}


def sonde(ctx=None):
    corps1 = {"montant": 3000, "date_paiement": None, "mode": "virement"}
    corps2 = {"montant": 3000, "date_paiement": "2026-11-15", "mode": "virement"}  # date remplie avant le second clic
    reel = _jouer([("cle-K1", corps1), ("cle-K2", corps2)])          # écran actuel : clé neuve après la retouche
    avant_acnc72 = _jouer([("cle-K1", corps1), ("cle-K1", corps2)])  # clé gardée : 409, rien d'écrit
    reclic_inchange = _jouer([("cle-K1", corps1), ("cle-K1", corps1)])
    ecran = _ecran()
    remet = ecran["remise_de_cle_sur"] or ""
    repro = ("datePaiement" in remet and ecran["copie_locale_jamais_resynchronisee"] and not ecran["sans_reponse_relit_la_fiche"]
             and len(reel["reglements"]) == 2)
    return {"repro": repro, "observe": {
        "methode": "rejeu (vrais IdempotentCreateMixin/_reserver/_fingerprint et verrouiller_facture_fournisseur_et_verifier_solde "
                   "extraits par ast, suffixe paiements.<pk>, IdempotencyRecord et solde en mémoire) + lecture du vrai FactureDetail",
        "scenario": "fiche d'une facture fournisseur de 10 000 ; règlement de 3 000, réponse perdue après passage au serveur ; "
                    "la fiche montre encore « Aucun paiement » ; le Directeur remplit la date puis reclique",
        "ecran": ecran, "code_reel": reel, "controle_cle_gardee_avant_acnc72": avant_acnc72,
        "controle_saisie_inchangee": reclic_inchange}}


if __name__ == "__main__":
    import os
    print(json.dumps(sonde(), ensure_ascii=False, indent=1, default=str)); sys.stdout.flush()
    os._exit(0)
