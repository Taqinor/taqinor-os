# flake8: noqa  (sonde HÔTE de contre-visite « vérifie ACNC » — sans Django, sans base, sans Docker)
"""C-ACNC-VER2-201 — ACNC2 partielle à l'écran : `frontend/src/pages/ventes/NoteDebitDialog.jsx` garde la clé d'envoi
(`cleEnvoi`) et la saisie (`motif`, `montant`) tant qu'aucun succès n'est revenu ; le dialogue reste monté
(`FactureList.jsx` le rend toujours) et sa remise à zéro à l'ouverture ou au changement de facture ne touche ni la clé ni la
saisie. Côté serveur, l'espace de clés de `creer-note-debit` est (société, `…FactureViewSet.note_debit`, clé) et l'empreinte
est le CORPS seul (`core/idempotency.py::_fingerprint(request.data)`) : l'id de la facture n'y entre pas.

Scénario : une note de 500 sur la facture A part, la réponse est perdue après validation ; le dialogue est fermé puis ouvert
sur la facture B (même taux de TVA) ; « Créer » renvoie le MÊME corps sous la MÊME clé ⇒ le serveur rejoue la réponse 201 de
la note de A, rien n'est créé pour B, l'écran annonce « Note de débit … créée ».

Partie serveur : on exécute les VRAIS `IdempotentCreateMixin`, `_reserver`, `_liberer`, `_fingerprint`
(core/idempotency.py) et `cle_du_corps`, `rejeu_par_cle` (apps/facturation/views/facture_rectificatifs.py), extraits par ast ;
seul le modèle `IdempotencyRecord` (contrainte unique (company, endpoint, key)) est un faux en mémoire. Partie écran : lecture
du VRAI composant (bloc de remise à zéro à l'ouverture, remise de la clé). Contrôle : la même paire de requêtes avec une clé
neuve pour B crée bien deux notes."""
SONDE = {"constat": "C-ACNC-VER2-201", "sha": "84561dcd3a",
         "attendu": "note de débit de A dont la réponse est perdue, dialogue rouvert sur B : 201 rejoué avec la note de A, aucune note créée pour B"}
import ast, hashlib, json, pathlib, re, sys, types
sys.dont_write_bytecode = True
RACINE = pathlib.Path(__file__).resolve().parents[4]
IDEM = "backend/django_core/core/idempotency.py"
RECT = "backend/django_core/apps/facturation/views/facture_rectificatifs.py"
JSX = "frontend/src/pages/ventes/NoteDebitDialog.jsx"


def _noeuds(chemin, noms):
    arbre = ast.parse((RACINE / chemin).read_text(encoding="utf-8"))
    return [n for n in arbre.body if isinstance(n, (ast.FunctionDef, ast.ClassDef)) and n.name in noms]


def _serveur():
    class IntegrityError(Exception): pass
    class Conflit(Exception): pass
    class EnCours(Exception): pass

    lignes = []

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

    def module(n, **a):
        m = types.ModuleType(n); m.__dict__.update(a); m.__path__ = []; return m

    faux = {"rest_framework": module("rest_framework"),
            "rest_framework.response": module("rest_framework.response", Response=Response),
            "django": module("django"), "django.utils": module("django.utils", timezone=types.SimpleNamespace(now=lambda: 10**9))}
    g = {"__builtins__": __builtins__, "__name__": "core.idempotency", "json": json, "hashlib": hashlib,
         "transaction": types.SimpleNamespace(atomic=Atomic), "IntegrityError": IntegrityError,
         "IdempotencyRecord": types.SimpleNamespace(objects=Objects(), Etat=Etat),
         "IdempotencyConflict": Conflit, "IdempotencyEnCours": EnCours, "RESERVATION_EXPIREE": 0,
         "IDEMPOTENCY_KEY_HEADER": "HTTP_IDEMPOTENCY_KEY", "logger": types.SimpleNamespace(warning=lambda *a, **k: None)}
    for n in _noeuds(IDEM, {"_fingerprint", "IdempotentCreateMixin", "_reserver", "_liberer"}) + _noeuds(RECT, {"cle_du_corps", "rejeu_par_cle"}):
        exec(compile(ast.Module([n], []), IDEM if n.name != "rejeu_par_cle" and n.name != "cle_du_corps" else RECT, "exec"), g)
    return g, faux, Response, lignes


def _rejouer(cles):
    g, faux, Response, lignes = _serveur()
    sauve = {k: sys.modules.get(k) for k in faux}
    sys.modules.update(faux)
    try:
        Vue = type("FactureViewSet", (g["IdempotentCreateMixin"],), {"__module__": "apps.facturation.views.facture"})
        notes = []

        def creer_note_debit(pk, corps):  # le geste réel crée une note numérotée sur la facture pk
            notes.append({"id": len(notes) + 1, "reference": f"ND-2026-{len(notes) + 1:04d}", "facture": pk,
                          "montant": corps["montant"]})
            return Response(notes[-1], status=201)

        reponses = []
        for pk, cle in zip(("A", "B"), cles):
            corps = {"motif": "Pénalité de retard", "montant": "500", "taux_tva": "20", "idempotency_key": cle}
            req = types.SimpleNamespace(data=corps, META={}, headers={}, user=types.SimpleNamespace(company="societe-1"))
            r = g["rejeu_par_cle"](Vue(), req, "note_debit", lambda pk=pk, corps=corps: creer_note_debit(pk, corps))
            reponses.append({"facture_visee": pk, "status": r.status_code, "note_rendue": r.data})
            # la réponse de A est « perdue » côté écran : rien ne remet la clé à zéro (seul un succès reçu le fait)
        return {"reponses": reponses, "notes_creees": notes}
    finally:
        for k, v in sauve.items(): sys.modules.pop(k, None) if v is None else sys.modules.__setitem__(k, v)


def _ecran():
    src = (RACINE / JSX).read_text(encoding="utf-8")
    bloc = re.search(r"if \(open !== wasOpen \|\| factureId !== vuFactureId\) \{(.*?)\n  \}", src, re.S)
    remises_cle = re.findall(r"cleEnvoi\.current = null", src)
    return {"bloc_ouverture_trouve": bool(bloc),
            "ouverture_remet_la_cle": bool(bloc) and "cleEnvoi" in bloc.group(1),
            "ouverture_vide_motif_montant": bool(bloc) and ("setMotif" in bloc.group(1) or "setMontant" in bloc.group(1)),
            "remises_de_cle_dans_le_composant": len(remises_cle),
            "cle_creee_au_premier_envoi": "cleEnvoi.current ??=" in src}


def sonde(ctx=None):
    reel = _rejouer(("cle-K", "cle-K"))   # écran actuel : même clé pour B
    controle = _rejouer(("cle-K", "cle-L"))  # clé renouvelée à l'ouverture sur B
    ecran = _ecran()
    b = reel["reponses"][1]
    repro = (ecran["bloc_ouverture_trouve"] and not ecran["ouverture_remet_la_cle"] and b["status"] == 201
             and b["note_rendue"]["facture"] == "A" and not any(n["facture"] == "B" for n in reel["notes_creees"]))
    return {"repro": repro, "observe": {
        "methode": "rejeu (vrais IdempotentCreateMixin/_reserver/_fingerprint et rejeu_par_cle/cle_du_corps extraits par ast, "
                   "IdempotencyRecord en mémoire sous contrainte unique) + lecture du vrai NoteDebitDialog.jsx",
        "scenario": "note de 500 sur A, réponse perdue ; dialogue fermé puis rouvert sur B (même taux) ; « Créer » avec la saisie restée",
        "ecran": ecran, "serveur_meme_cle": reel, "controle_cle_neuve_pour_B": controle}}


if __name__ == "__main__":
    import os
    print(json.dumps(sonde(), ensure_ascii=False, indent=1, default=str)); sys.stdout.flush()
    os._exit(0)
