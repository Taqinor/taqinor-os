#!/usr/bin/env python3
"""AMET98 (C-AMET-025) — rejeu d'un PARCOURS sur UN enregistrement de la pile locale.

    python scripts/rejouer_parcours.py PA4 --enregistrement <id devis> [--modele ventes.Devis]
        [--utilisateur demo_admin] [--corps etapes.json] [--dry-run] [--sans-enregistrement]

1. La table est d'abord validée par `parcours_tables.verifier_table` (refus si ÉCHEC) — les mêmes
   fonctions que `check_acceptation.py --parcours`.
2. Chaque étape est jouée par l'API réelle (`APIClient`, route DRF retrouvée depuis la fonction
   d'entrée ou le déclencheur), DANS le conteneur Django, par le programme de `sonde.py` (AMET93) :
   transaction annulée, mail en mémoire, Celery coupé, HTTP sortant bloqué, comptes avant / après
   — rien n'est gardé ; une base modifiée = ÉCHEC, jamais d'enregistrement. Une étape `manquante`
   est rapportée, jamais jouée. `--corps` : `{id_étape: corps JSON}` pour les actions qui en exigent.
3. Oracles qa-explorer 1-10 au niveau API (1 : ≥ 500 ; 2 : 4xx sur l'action ; 5 : liste relue après
   un 201 ; 6 : PDF `/proposal` ; 7 : `prix_achat` sur une route client ; 9 : `company` d'une autre
   société ; 3, 4, 8 sans navigateur et 10 = commande de l'orchestrateur : NA) + 3 oracles de
   parcours : `auto` (étape automatique : son artefact de checkpoint existe, lié à l'enregistrement),
   `checkpoint` (persisté ; modifiable = PATCH des champs relu identique), `aval` (`refus_409` :
   l'action rejouée est refusée en 4xx ; les autres règles : NA, à observer).
4. Enregistrement `docs/audits/acceptation/<PA>/<date>-<sha9>.md` + `.results.json` écrit par
   L'écrivain partagé `frontend/e2e/acceptation/_enregistrement.js` (AMET90, contrat AMET88) :
   `couvre:` = `taches[]` des étapes jouées (un rejeu de parcours couvre des ids de tout groupe).
   Seules les étapes jouées qui portent des tâches y entrent ; les autres sont rapportées.
"""
from __future__ import annotations

import argparse
import inspect
import json
import re
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import parcours_tables as cp  # noqa: E402 — après sys.path/setup() (D-ENF22)
import sonde  # noqa: E402 — après sys.path/setup() (D-ENF22)

ROOT = cp.ROOT
MARQUE = "@@PARCOURS "
ORACLES = [str(i) for i in range(1, 11)]
MODELES_PAR_DEFAUT = {"PA1": "crm.Lead", "PA3": "ventes.Devis", "PA4": "ventes.Devis"}


# --- Exécuté DANS le conteneur : programme() envoie la source de `_CONTENEUR` en ligne à sonde.py ---
# (rien du module ici : seuls json / re / sys, importés en tête du programme, et le contexte C)

def _c_routes():
    from django.urls import URLResolver, get_resolver
    routes = []

    def marcher(motifs, prefixe):
        for m in motifs:
            if isinstance(m, URLResolver):
                marcher(m.url_patterns, prefixe + str(m.pattern))
            else:
                routes.append((prefixe + str(m.pattern), m.callback))
    marcher(get_resolver().url_patterns, "")
    return routes


def _c_url(route, pk):
    s = re.sub(r"\(\?P<\w+>[^)]*\)|<(?:\w+:)?\w+>", str(pk), route)
    return "/" + s.replace("^", "").replace("$", "").replace("\\", "").lstrip("/")


def _c_modele_vue(cls):
    qs = getattr(cls, "queryset", None)
    meta = getattr(getattr(cls, "serializer_class", None), "Meta", None)
    return qs.model if qs is not None else getattr(meta, "model", None)


def _c_chercher(C, test, action):
    """(route, verbe, vue) de la 1re vue DRF qui satisfait `test` et expose `action`."""
    for route, cb in C["routes"]:
        cls, actions = getattr(cb, "cls", None), getattr(cb, "actions", None) or {}
        if cls is None or "format" in route or not test(cls):
            continue
        for verbe, nom in actions.items() or [(action, action)]:
            if nom == action and (actions or hasattr(cls, action)):
                return route, verbe, cls
    return None


def _c_route_de(C, ancre):
    morceaux = (ancre or "").partition("::")[2].split(".")
    if len(morceaux) < 2:
        return None
    action = {"perform_create": "create", "perform_update": "partial_update"}.get(morceaux[1], morceaux[1])
    return _c_chercher(C, lambda c: morceaux[0] in {k.__name__ for k in c.__mro__}, action)


def _c_modele_de(ancre):
    from django.apps import apps
    fichier, _, sym = (ancre or "").partition("::")
    mod, nom = fichier.replace("backend/django_core/", "")[:-3].replace("/", "."), sym.split(".")[0]
    tous = [m for m in apps.get_models() if m.__name__ == nom]
    return next((m for m in tous if m.__module__ == mod), tous[0] if tous else None)


def _c_lier(C, M):
    """pk de l'objet de modèle `M` chaîné (FK / OneToOne, dans un sens ou l'autre) à l'enregistrement."""
    from django.apps import apps
    objets = C["objets"]
    if M is None or M._meta.label in objets:
        return None if M is None else objets[M._meta.label]
    liens = [f for f in M._meta.fields if (f.many_to_one or f.one_to_one) and f.related_model is not None]
    for f in liens:
        if f.related_model._meta.label in objets:
            o = M._default_manager.filter(**{f.name: objets[f.related_model._meta.label]}).order_by("-pk").first()
            if o is not None:
                objets[M._meta.label] = o.pk
                return o.pk
    for label, pk in list(objets.items()):
        src = apps.get_model(label)._default_manager.filter(pk=pk).first()
        for f in src._meta.fields if src is not None else []:
            if (f.many_to_one or f.one_to_one) and f.related_model is M and getattr(src, f.attname):
                objets[M._meta.label] = getattr(src, f.attname)
                return objets[M._meta.label]
    return None


def _c_appeler(C, verbe, chemin, corps=None):
    from django.db import transaction
    api = C["api"]
    with transaction.atomic():
        r = api.get(chemin) if verbe == "get" else getattr(api, verbe)(chemin, corps or {}, format="json")
    ctype = r.get("Content-Type", "")
    texte = "" if "pdf" in ctype else r.content[:500000].decode("utf-8", "replace")
    try:
        donnees = json.loads(texte) if "json" in ctype else None
    except ValueError:
        donnees = None
    return r.status_code, ctype, texte, donnees


def _c_oracles_api(C, res, appel, cls, types):
    """Oracles qa-explorer 1, 2, 5, 6, 7, 9 d'une action jouée + oracle de parcours `aval` (refus_409)."""
    verbe, chemin, corps, (st, ctype, texte, donnees) = appel
    O, R, co = res["oracles"], res["parcours"], C["co"]
    O["1"], O["2"] = ("FAIL" if st >= 500 else "PASS"), ("FAIL" if 400 <= st < 500 else "PASS")
    if "proposal" in chemin:
        O["6"] = "PASS" if st == 200 and "pdf" in ctype else "FAIL"
    if any(k in chemin for k in ("public", "proposal", "portail")):
        O["7"] = "FAIL" if "prix_achat" in texte else "PASS"
    if isinstance(donnees, dict) and "company" in donnees and co:
        O["9"] = "PASS" if str(donnees["company"]) == str(co) else "FAIL"
    liste = _c_chercher(C, lambda c: c is cls, "list") if st == 201 else None
    if liste:
        d2 = _c_appeler(C, "get", _c_url(liste[0], ""))[3]
        O["5"] = "PASS" if (d2.get("results") if isinstance(d2, dict) else d2) else "FAIL"
    if "refus_409" in types and st < 300 and verbe == "post":
        st3 = _c_appeler(C, verbe, chemin, corps)[0]
        R["aval"] = "PASS" if 400 <= st3 < 500 else "FAIL"
        res["notes"].append(f"refus_409 : action rejouée -> {st3}")


def _c_jouer_api(C, e, res, trouve, types):
    """Joue l'étape par sa route DRF ; False si aucun objet lié n'existe pour une route de détail."""
    route, verbe, cls = trouve
    detail = bool(re.search(r"\(\?P<|<\w", route))
    pk = _c_lier(C, _c_modele_vue(cls)) if detail else ""
    if detail and pk is None:
        nom = getattr(_c_modele_vue(cls), "__name__", "?")
        res["notes"].append(f"aucun {nom} lié à l'enregistrement : non jouée")
        return False
    chemin, corps = _c_url(route, pk), C["P"]["corps"].get(e.get("id"), {})
    reponse = _c_appeler(C, verbe, chemin, corps)
    res["joue"], res["appel"] = True, f"{verbe.upper()} {chemin} -> {reponse[0]}"
    _c_oracles_api(C, res, (verbe, chemin, corps, reponse), cls, types)
    return True


def _c_checkpoint(C, res, point, Mp, auto):
    """Oracles de parcours `auto` (artefact lié) et `checkpoint` (persisté ; modifiable = PATCH relu identique)."""
    R, notes = res["parcours"], res["notes"]
    pk_p = _c_lier(C, Mp)
    if auto:
        R["auto"] = "PASS" if pk_p else "FAIL"
    if Mp is not None:
        R["checkpoint"] = "PASS" if pk_p else "FAIL"
    cles = [c.split(".")[-1] for c in point.get("champs") or []]
    cles = [c for c in cles if Mp is not None and c in {f.name for f in Mp._meta.fields if f.editable}]
    modifiable = pk_p and point.get("modifiable")
    maj = _c_chercher(C, lambda c: _c_modele_vue(c) is Mp, "partial_update") if modifiable else None
    if maj and cles:
        u = _c_url(maj[0], pk_p)
        avant = _c_appeler(C, "get", u)[3]
        if isinstance(avant, dict) and all(c in avant for c in cles):
            st4 = _c_appeler(C, "patch", u, {c: avant[c] for c in cles})[0]
            apres = _c_appeler(C, "get", u)[3] or {}
            ok = st4 < 300 and all(apres.get(c) == avant[c] for c in cles)
            R["checkpoint"] = "PASS" if ok else "FAIL"
            notes.append(f"checkpoint {cles} : PATCH -> {st4}, relu {'identique' if ok else 'différent'}")


def _c_etape(C, e):
    """Résultat d'UNE étape : jouée par l'API, constatée (automatique) ou rapportée (manquante / sans route)."""
    res = {"id": e.get("id"), "joue": False, "appel": "", "notes": [],
           "oracles": {o: "NA" for o in C["P"]["oracles"]},
           "parcours": {"auto": "NA", "checkpoint": "NA", "aval": "NA"}}
    if e.get("manquante") is True:
        res["notes"].append("étape manquante déclarée : non jouée")
        return res
    decl, point = e.get("declencheur") or {}, e.get("checkpoint") or {}
    auto, Mp = decl.get("type") in C["P"]["auto"], _c_modele_de(point.get("persistance"))
    regles = e.get("regle_aval", e.get("regles_aval")) or []
    types = {r if isinstance(r, str) else r.get("type") for r in regles}
    entree = e.get("fonction_entree")
    trouve = _c_route_de(C, entree if isinstance(entree, str) else "") or _c_route_de(C, decl.get("source"))
    if trouve:
        if not _c_jouer_api(C, e, res, trouve, types):
            return res
    elif auto:
        res["joue"], res["appel"] = True, f"auto ({decl.get('type')}) : artefact {getattr(Mp, '__name__', '?')}"
    else:
        res["notes"].append("aucune route API pour la fonction d'entrée ni le déclencheur : non jouée")
        return res
    _c_checkpoint(C, res, point, Mp, auto)
    autres = [x if isinstance(x, str) else (x.get("type") or x.get("regle")) for x in regles]
    autres = [str(x) for x in autres if x != "refus_409"]
    if autres:
        res["notes"].append("règles aval à observer : " + " ; ".join(autres))
    return res


def _jouer(P):
    """Point d'entrée dans le conteneur : authentifie, joue chaque étape, imprime les résultats marqués."""
    from django.apps import apps
    from django.contrib.auth import get_user_model
    from rest_framework.test import APIClient
    M = apps.get_model(P["modele"])
    rec = M._default_manager.get(pk=P["enregistrement"])
    co = getattr(rec, "company_id", None)
    U = get_user_model()
    user = (U.objects.get(username=P["utilisateur"]) if P.get("utilisateur") else
            U.objects.filter(is_active=True, company_id=co).order_by("-is_superuser", "pk").first())
    api = APIClient(raise_request_exception=False, HTTP_HOST="localhost")
    api.force_authenticate(user)
    C = {"P": P, "routes": _c_routes(), "objets": {M._meta.label: rec.pk}, "api": api, "co": co}
    resultats = [_c_etape(C, e) for e in P["etapes"]]
    sys.__stdout__.write(P["marque"] + json.dumps(resultats, ensure_ascii=True, default=str) + "\n")
    return {"repro": True, "etapes": len(resultats)}


_CONTENEUR = (_c_routes, _c_url, _c_modele_vue, _c_chercher, _c_route_de, _c_modele_de, _c_lier, _c_appeler,
              _c_oracles_api, _c_jouer_api, _c_checkpoint, _c_etape, _jouer)
EN_TETE_CONTENEUR = "import json\nimport re\nimport sys\n\n\n"


def programme(table: dict, params: dict, timeout: int) -> str:
    """Programme AUTONOME (sonde.py) : transaction annulée, comptes avant / après."""
    P = dict(params, etapes=table.get("etapes") or [], oracles=ORACLES, marque=MARQUE,
             auto=sorted(cp.TYPES_AUTO), corps=params.get("corps") or {})
    source = (EN_TETE_CONTENEUR + "\n\n".join(inspect.getsource(f) for f in _CONTENEUR)
              + f"\n\nP = __import__('json').loads({json.dumps(P, ensure_ascii=True)!r})\n"
              "\n\ndef sonde(ctx):\n    return _jouer(P)\n")
    entete = {"constat": "C-AMET-025", "sha": "rejeu", "attendu": f"rejeu {cp.identifiant(table)}"}
    return sonde.programme(source, entete, timeout)


def _notes(res: dict) -> str:
    notes = res.get("notes") or []
    return "; ".join(notes) if isinstance(notes, list) else str(notes)


def etapes_enregistrement(table: dict, resultats: list) -> tuple:
    """(étapes au format results.json AMET88, lignes « non enregistrées » à rapporter)."""
    par_id = {r.get("id"): r for r in resultats}
    etapes, ignorees = [], []
    for e in cp.parcours.etapes(table):
        ident, res = e.get("id"), par_id.get(e.get("id")) or {}
        if cp.est_manquante(e):
            ignorees.append(f"{ident} : manquante déclarée, jamais jouée")
        elif not res.get("joue"):
            ignorees.append(f"{ident} : non jouée ({_notes(res) or 'sans résultat'})")
        elif not e.get("taches"):
            ignorees.append(f"{ident} : jouée, sans tâche à couvrir ({res.get('appel')})")
        else:
            verdicts = list(res["oracles"].values()) + list(res["parcours"].values())
            etapes.append({
                "id": ident, "taches": list(e["taches"]), "verdict": "FAIL" if "FAIL" in verdicts else "PASS",
                "base_verdict": None, "trace": f"{res.get('appel')} (rejouer_parcours.py, transaction annulée)",
                "oracles": {o: res["oracles"].get(o, "NA") for o in ORACLES},
                "oracles_parcours": res["parcours"],
                "notes": "; ".join(filter(None, [_notes(res), "parcours " + json.dumps(res["parcours"])])),
            })
    return etapes, ignorees


def ecrire_enregistrement(groupe: str, charge: dict) -> int:
    """Écrivain PARTAGÉ (AMET90) : `node e2e/acceptation/_enregistrement.js <G> --etapes-supplementaires`."""
    with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False, encoding="utf-8") as f:
        json.dump(charge, f, ensure_ascii=False)
    p = subprocess.run(["node", "e2e/acceptation/_enregistrement.js", groupe, "--etapes-supplementaires", f.name],
                       cwd=ROOT / "frontend", capture_output=True, text=True, encoding="utf-8", errors="replace")
    print((p.stdout + p.stderr).strip())
    Path(f.name).unlink(missing_ok=True)
    return p.returncode


def main(argv=None, executer=sonde.executer_docker, ecrire=ecrire_enregistrement) -> int:
    a = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    a.add_argument("parcours", help="PA1..PA7")
    a.add_argument("--enregistrement", required=True, help="pk de l'enregistrement suivi")
    a.add_argument("--modele", help="app.Modele de l'enregistrement (défaut : %s)" % MODELES_PAR_DEFAUT)
    a.add_argument("--utilisateur", help="username (défaut : 1er actif de la société de l'enregistrement)")
    a.add_argument("--corps", help="JSON {id_étape: corps} pour les actions qui exigent un corps")
    a.add_argument("--conteneur", default=sonde.CONTENEUR)
    a.add_argument("--timeout", type=int, default=300)
    a.add_argument("--racine", default=str(ROOT))
    a.add_argument("--pile", action="store_true", help="monte / met à jour d'abord la pile (pile_locale.ps1)")
    a.add_argument("--dry-run", action="store_true", help="imprime le programme, sans docker")
    a.add_argument("--sans-enregistrement", action="store_true", help="joue et rapporte, n'écrit rien")
    a = a.parse_args(argv)
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    pa, racine = a.parcours.upper(), Path(a.racine)
    rel, table = cp.table_par_id(pa, racine)
    echecs, _ = cp.verifier_table(rel, table, racine)
    for e in echecs:
        print(f"ÉCHEC {e}")
    modele = a.modele or MODELES_PAR_DEFAUT.get(pa)
    if echecs or not modele:
        motif = "table invalide (check_acceptation.py --parcours)" if echecs else f"--modele requis pour {pa}"
        print(f"ÉCHEC : {motif}")
        return 1
    corps = json.loads(Path(a.corps).read_text(encoding="utf-8")) if a.corps else {}
    prog = programme(table, {"modele": modele, "enregistrement": a.enregistrement,
                             "utilisateur": a.utilisateur, "corps": corps}, a.timeout)
    if a.dry_run:
        print(prog)
        return 0
    pile = ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(ROOT / "scripts/pile_locale.ps1")]
    if a.pile and subprocess.run(pile).returncode != 0:
        print("ÉCHEC : pile locale (scripts/pile_locale.ps1, voir ci-dessus)")
        return 1
    cmd = ["docker", "exec", "-i", a.conteneur, "python", "-u", "manage.py", "shell"]
    rc, sortie, erreur = executer(cmd, prog, a.timeout)
    lignes = sortie.splitlines()
    brut = next((x[len(MARQUE):] for x in lignes if x.startswith(MARQUE)), None)
    bilan = next((json.loads(x[len(sonde.MARQUE):]) for x in lignes if x.startswith(sonde.MARQUE)), {})
    if brut is None or bilan.get("verdict") != "REPRO" or bilan.get("base_inchangee") is not True:
        print(f"ÉCHEC : rejeu incomplet ou base modifiée (code {rc}) {bilan.get('observe', '')} "
              f"{(erreur or sortie).strip()[-600:]}")
        return 1
    resultats = json.loads(brut)
    for r in resultats:
        print(f"{r['id']} : {r.get('appel') or 'non jouée'} ; parcours {r['parcours']} ; {_notes(r)}")
    etapes, ignorees = etapes_enregistrement(table, resultats)
    for ligne in ignorees:
        print(f"Hors enregistrement : {ligne}")
    print(f"Base inchangée (transaction annulée) : {bilan.get('comptes_avant')} lignes avant et après.")
    ok = all(e["verdict"] == "PASS" for e in etapes)
    if a.sans_enregistrement or not etapes:
        print("Aucun enregistrement écrit" + (" (aucune étape jouée ne porte de tâche)." if not etapes else "."))
        return 0 if ok else 1
    couvre = sorted({t for e in etapes for t in e["taches"]})
    return 0 if ecrire(pa, {"couvre": couvre, "etapes": etapes}) == 0 and ok else 1


if __name__ == "__main__":
    sys.exit(main())
