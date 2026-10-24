#!/usr/bin/env python3
"""Rejeu d'une table de parcours sur UN enregistrement de la pile locale (AMET98, C-AMET-025, C15/C19).

    python scripts/rejouer_parcours.py PA4 --enregistrement <id du devis> [--utilisateur demo_admin]

1. Charge ``backend/django_core/apps/<pilote>/parcours/<PA>.json`` ; une table que
   ``check_parcours.py`` rejette n'est pas jouée.
2. Envoie au conteneur Django, par ``sonde.py`` (AMET93 : transaction ANNULÉE, mail en mémoire,
   Celery coupé, HTTP sortant bloqué), CE fichier suivi de ``def sonde(ctx)`` : chaque étape est
   jouée par l'API réelle (``APIClient`` authentifié comme un utilisateur de la société de
   l'enregistrement) :
   - clic / manuel / http : la route DRF qui sert la fonction d'entrée, le déclencheur ou un
     appelant Python de la fonction d'entrée (index AST d'``audit_tache.py``, AMET80) est trouvée
     dans le résolveur d'URL de Django et appelée sur l'objet courant de son modèle ; l'objet que
     l'étape crée devient l'objet courant de son modèle de persistance ;
   - événement / beat / signal / tâche : jamais appelée — on OBSERVE si son modèle de
     persistance a été écrit depuis le début du rejeu (beat / tâche non écrits : NA, la
     transaction annulée ne les déclenche pas) ;
   - ``manquante: true`` : rapportée, jamais jouée.
3. Juge chaque étape : oracles qa-explorer 1-10 (3, 4 et 8 relèvent du navigateur : NA) et 3
   oracles de parcours — ``declenchee`` (l'étape a réellement eu lieu), ``checkpoint`` (persisté ;
   si ``modifiable``, un PATCH d'un champ déclaré est relu à l'identique), ``aval`` (``refus_409`` :
   la même action rejouée est refusée ; ``reference`` : l'objet reste dans la société).
4. Écrit ``docs/audits/acceptation/<PA>/<date>-<sha9>.md`` + ``.results.json`` dans le format de
   ``check_acceptation.py`` (AMET88), ``couvre`` = ``taches[]`` des étapes jouées. Un dossier par
   parcours : le nom date + sha9 ferait se recouvrir deux parcours rejoués le même jour dans un
   dossier de groupe. PASS seulement si TOUTES les étapes jouées passent et que la base est
   inchangée (exit 0) ; sinon exit 1. Jamais contre la prod (conteneur local de ``sonde.py``).
"""
from __future__ import annotations

import argparse
import datetime
import json
import re
import subprocess
import sys
from pathlib import Path

# Le programme envoyé au conteneur (ce fichier lui-même) s'exécute sans ``__file__``.
ROOT = Path(globals().get("__file__", ".")).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

MARQUE = "@@PARCOURS "
AUTO = {"evenement", "beat", "signal", "tache"}
PLANIFIES = {"beat", "tache"}
HOOKS = {"perform_create": "create", "perform_update": "partial_update", "perform_destroy": "destroy"}
LIBELLES_ACHAT = re.compile(r"prix d'achat|prix_achat|coût d'achat|\bmarge\b", re.I)


# --- Côté conteneur : Django n'est importé que dans les fonctions (fichier importable sans lui) ---

def _module_et_qual(ref) -> tuple:
    fichier, _, qual = str(ref or "").partition("::")
    return fichier.split("backend/django_core/", 1)[-1][:-3].replace("/", "."), qual


def _modele(ref):
    """Le modèle Django que nomme ``fichier.py::Modele`` (``checkpoint.persistance``), ou None."""
    from django.apps import apps
    module, qual = _module_et_qual(ref)
    return next((m for m in apps.get_models() if m.__name__ == qual and m.__module__ == module), None)


def _modele_vue(cls):
    queryset = getattr(cls, "queryset", None)
    meta = getattr(getattr(cls, "serializer_class", None), "Meta", None)
    return queryset.model if queryset is not None else getattr(meta, "model", None)


def _routes() -> list:
    """[(nom inversable, classe, actions, détail)] de chaque route DRF de ViewSet."""
    from django.urls import URLPattern, URLResolver, get_resolver
    sortie = []

    def parcourir(motifs, ns):
        for m in motifs:
            if isinstance(m, URLResolver):
                parcourir(m.url_patterns, ns + ([m.namespace] if m.namespace else []))
            elif isinstance(m, URLPattern) and m.name and getattr(m.callback, "actions", None):
                cls = m.callback.cls
                cle = getattr(cls, "lookup_url_kwarg", None) or getattr(cls, "lookup_field", "pk")
                sortie.append((":".join(ns + [m.name]), cls, m.callback.actions, cle in m.pattern.regex.groupindex))
    parcourir(get_resolver().url_patterns, [])
    return sortie


def _routes_de(ref, routes) -> list:
    """Routes [(nom, verbe, classe, détail)] servies par ``fichier::Classe.methode`` (``::Classe`` = create)."""
    module, qual = _module_et_qual(ref)
    methode = qual.rpartition(".")[2] if "." in qual else "create"
    action = HOOKS.get(methode, methode)
    trouvees = []
    for nom, cls, actions, detail in routes:
        cible = getattr(cls, methode, None) if "." in qual else cls
        if getattr(cible, "__qualname__", "") == qual and getattr(cible, "__module__", "") == module:
            trouvees += [(nom, verbe, cls, detail) for verbe, a in actions.items() if a == action]
    return trouvees


def _choisir(candidats, routes, ctx):
    for ref in candidats:
        for nom, verbe, cls, detail in _routes_de(ref, routes):
            modele = _modele_vue(cls)
            if not detail or (modele is not None and modele._meta.label in ctx):
                return {"nom": nom, "verbe": verbe, "cls": cls, "detail": detail, "modele": modele}
    return None


def _url(route, ctx) -> str:
    from django.urls import reverse
    if not route["detail"]:
        return reverse(route["nom"])
    cls, modele = route["cls"], route["modele"]
    objet = modele._default_manager.get(pk=ctx[modele._meta.label])
    cle = getattr(cls, "lookup_url_kwarg", None) or cls.lookup_field
    return reverse(route["nom"], kwargs={cle: getattr(objet, cls.lookup_field)})


def _etrangers(donnees, societe) -> int:
    """Objets d'une AUTRE société dans une réponse (oracle 9)."""
    if isinstance(donnees, list):
        return sum(_etrangers(v, societe) for v in donnees)
    if not isinstance(donnees, dict) or societe is None:
        return 0
    propres = sum(1 for k in ("company", "company_id") if type(donnees.get(k)) is int and donnees[k] != societe)
    return propres + sum(_etrangers(v, societe) for v in donnees.values())


def _appeler(client, verbe, url, corps, societe, o, attendu_refus=False):
    reponse = client.get(url) if verbe == "get" else getattr(client, verbe)(url, corps or {}, format="json")
    try:
        donnees = reponse.json()
    except Exception:  # réponse non JSON (PDF, vide)
        donnees = None
    o["appels"].append({"verbe": verbe.upper(), "url": url, "statut": reponse.status_code,
                        "etrangers": _etrangers(donnees, societe), "attendu_refus": attendu_refus})
    return reponse.status_code, donnees


def _etat(modele, pk):
    if modele is None:
        return None
    gestion = modele._default_manager
    objet = gestion.filter(pk=pk).first() if pk is not None else None
    champs = {f.attname: str(getattr(objet, f.attname)) for f in modele._meta.concrete_fields} if objet else {}
    return {"n": gestion.count(), "max": gestion.order_by("-pk").values_list("pk", flat=True).first(), "obj": champs}


def _ecrit(avant, apres) -> dict:
    if not avant or not apres:
        return {}
    return {"crees": apres["n"] - avant["n"],
            "modifies": sorted(k for k, v in apres["obj"].items() if avant["obj"] and avant["obj"].get(k) != v)}


def _route_modele(routes, modele, detail, verbe, action):
    return next(({"nom": r[0], "cls": r[1], "detail": detail, "modele": modele} for r in routes
                 if r[3] == detail and r[2].get(verbe) == action and _modele_vue(r[1]) is modele), None)


def _liste_contient(modele, pk, routes, client, societe, o):
    """Oracle 5 : l'objet créé figure dans la 1re page de la liste de son modèle (None : pas de liste)."""
    route = _route_modele(routes, modele, False, "get", "list")
    if route is None:
        return None
    _, donnees = _appeler(client, "get", _url(route, {}), None, societe, o)
    lignes = donnees.get("results", []) if isinstance(donnees, dict) else donnees or []
    return any(isinstance(x, dict) and x.get("id") == pk for x in lignes)


def _muter(valeur):
    if isinstance(valeur, bool):
        return not valeur
    try:
        return float(valeur) + 1
    except (TypeError, ValueError):
        return f"{valeur} (rejeu)" if isinstance(valeur, str) else None


def _egal(a, b) -> bool:
    try:
        return float(a) == float(b)
    except (TypeError, ValueError):
        return str(a) == str(b)


def _modifiable(etape, modele, ctx, routes, client, societe, o):
    """Checkpoint ``modifiable`` : PATCH d'un champ déclaré puis relecture ; None si non adressable."""
    chk = etape.get("checkpoint") or {}
    if not chk.get("modifiable") or modele is None or modele._meta.label not in ctx:
        return None
    noms = {f.name for f in modele._meta.concrete_fields
            if f.editable and not f.is_relation and not f.primary_key and not f.choices}
    champ = next((c.rsplit(".", 1)[-1] for c in chk.get("champs") or [] if c.rsplit(".", 1)[-1] in noms), None)
    route = _route_modele(routes, modele, True, "patch", "partial_update")
    if champ is None or route is None:
        return None
    url = _url(route, ctx)
    _, avant = _appeler(client, "get", url, None, societe, o)
    valeur = _muter((avant or {}).get(champ))
    if valeur is None:
        return None
    statut, _ = _appeler(client, "patch", url, {champ: valeur}, societe, o)
    _, relu = _appeler(client, "get", url, None, societe, o)
    return statut < 400 and _egal((relu or {}).get(champ), valeur)


def _jouer_appel(etape, o, modele, params, routes, client, ctx, societe):
    route = _choisir(params["candidats"].get(o["id"]) or [], routes, ctx)
    if route is None:
        o.update(statut="non_rejouable", motif="aucune route DRF (fonction d'entrée, déclencheur, appelants) "
                                               "sur un objet du parcours")
        return
    label = modele._meta.label if modele is not None else None
    avant, url = _etat(modele, ctx.get(label)), _url(route, ctx)
    corps = (etape.get("rejeu") or {}).get("corps")
    statut, _ = _appeler(client, route["verbe"], url, corps, societe, o)
    o.update(statut="joue", verbe=route["verbe"], ecrit=_ecrit(avant, _etat(modele, ctx.get(label))),
             modele_route=route["modele"]._meta.label if route["modele"] is not None else None)
    types = {r.get("type") for r in etape.get("regle_aval") or [] if isinstance(r, dict)}
    if "refus_409" in types and statut < 400:
        second, _ = _appeler(client, route["verbe"], url, corps, societe, o, attendu_refus=True)
        o["regles"]["refus_409"] = 400 <= second < 500


def _jouer_etape(etape, modele, debut, params, routes, client, ctx, societe) -> dict:
    """Observation d'UNE étape (jouée, observée ou rapportée) ; une exception n'arrête pas le rejeu."""
    o = {"id": etape.get("id"), "taches": list(etape.get("taches") or []), "appels": [], "regles": {}}
    if etape.get("manquante"):
        return dict(o, statut="manquante")
    from django.db import transaction
    label = modele._meta.label if modele is not None else None
    try:
        with transaction.atomic():
            type_ = (etape.get("declencheur") or {}).get("type")
            if type_ in AUTO:
                o.update(statut="auto", planifiee=type_ in PLANIFIES,
                         ecrit=_ecrit(debut, _etat(modele, ctx.get(label))))
            else:
                _jouer_appel(etape, o, modele, params, routes, client, ctx, societe)
            if (o.get("ecrit") or {}).get("crees"):
                ctx[label] = _etat(modele, None)["max"]
                o["liste"] = _liste_contient(modele, ctx[label], routes, client, societe, o)
            if label in ctx:
                o["objet"] = [label, ctx[label]]
                if "reference" in {r.get("type") for r in etape.get("regle_aval") or [] if isinstance(r, dict)}:
                    objet = modele._default_manager.filter(pk=ctx[label]).first()
                    o["regles"]["reference"] = getattr(objet, "company_id", societe) == societe
            o["modifiable"] = _modifiable(etape, modele, ctx, routes, client, societe, o)
    except Exception as exc:
        o.update(statut="erreur", motif=f"{type(exc).__name__} : {exc}"[:300])
    return o


def _pdf(ctx, routes, client):
    """Oracles 6 et 7 sur le ``/proposal`` du devis du parcours (lecture seule, règle #4)."""
    from django.apps import apps
    devis = apps.get_model("ventes", "Devis")
    route = _route_modele(routes, devis, True, "get", "proposal")
    if route is None or "ventes.Devis" not in ctx:
        return None
    reponse = client.get(_url(route, ctx))
    contenu = b"".join(reponse.streaming_content) if getattr(reponse, "streaming", False) else reponse.content
    try:
        import fitz
        texte = "".join(page.get_text() for page in fitz.open(stream=contenu, filetype="pdf"))
    except Exception:  # PyMuPDF absent ou PDF illisible : oracle 7 non jugé
        texte = None
    return {"statut": reponse.status_code, "type": reponse.get("Content-Type", ""), "taille": len(contenu),
            "tete": contenu[:5].decode("latin-1"),
            "prix_achat": None if texte is None else bool(LIBELLES_ACHAT.search(texte))}


def _coherence(societe):
    """Oracle 10 : violations d'``audit_coherence --no-persist`` de la société (None si indisponible)."""
    import io
    from django.core.management import call_command
    from authentication.models import Company
    tampon = io.StringIO()
    try:
        slug = Company.objects.filter(pk=societe).values_list("slug", flat=True).first()
        call_command("audit_coherence", company=slug, json=True, no_persist=True, stdout=tampon)
        return json.loads(tampon.getvalue()).get("violations", [])
    except Exception:  # commande absente ou en échec : oracle 10 ignoré (qa-explorer)
        return None


def _finaliser(observations, ctx, routes, client, societe):
    pdf, violations = _pdf(ctx, routes, client), _coherence(societe)
    for o in observations:
        if o.get("statut") not in ("joue", "auto"):
            continue
        label, pk = o.get("objet") or (None, None)
        if pdf is not None and "ventes.Devis" in (label, o.get("modele_route")):
            o["pdf"] = pdf
        if violations is not None:
            nom = (label or "").rsplit(".", 1)[-1].lower()
            o["coherence"] = [v.get("rule") for v in violations
                              if str(v.get("object_type", "")).rsplit(".", 1)[-1].lower() == nom
                              and str(v.get("object_id")) == str(pk)]


def _utilisateur(nom, societe):
    from django.contrib.auth import get_user_model
    actifs = get_user_model()._default_manager.filter(is_active=True)
    if nom:
        return actifs.get(username=nom)
    societaires = actifs.filter(company_id=societe) if societe is not None else actifs
    return societaires.order_by("-is_superuser", "pk").first()


def _depart(params, routes):
    """Modèle de l'enregistrement : ``--modele``, sinon celui de la 1re route de détail de la table."""
    from django.apps import apps
    if params.get("modele"):
        return apps.get_model(params["modele"])
    for refs in params["candidats"].values():
        for ref in refs:
            for _nom, _verbe, cls, detail in _routes_de(ref, routes):
                if detail and _modele_vue(cls) is not None:
                    return _modele_vue(cls)
    raise LookupError("modèle de l'enregistrement introuvable : passer --modele app.Modele")


def rejouer_dans_django(params) -> dict:
    """Point d'entrée DANS le conteneur : joue la table et imprime ``@@PARCOURS <json>`` sur le vrai
    stdout (la sortie d'une sonde est tronquée à 6 000 caractères)."""
    from rest_framework.test import APIClient
    routes = _routes()
    depart = _depart(params, routes)
    objet = depart._default_manager.get(pk=params["enregistrement"])
    societe = getattr(objet, "company_id", None)
    client = APIClient()
    client.raise_request_exception = False
    client.force_authenticate(_utilisateur(params.get("utilisateur"), societe))
    ctx = {depart._meta.label: objet.pk}
    etapes = params["table"]["etapes"]
    modeles = {e.get("id"): _modele((e.get("checkpoint") or {}).get("persistance")) for e in etapes}
    debut = {i: _etat(m, ctx.get(m._meta.label)) for i, m in modeles.items() if m is not None}
    observations = [_jouer_etape(e, modeles[e.get("id")], debut.get(e.get("id")), params, routes, client, ctx,
                                 societe) for e in etapes]
    _finaliser(observations, ctx, routes, client, societe)
    print(MARQUE + json.dumps(observations, default=str, ensure_ascii=True), file=sys.__stdout__, flush=True)
    return {"repro": True, "etapes": len(observations)}


# --- Côté hôte : jugement, enregistrement d'acceptation, CLI ---

def _pf(ok) -> str:
    return "PASS" if ok else "FAIL"


def oracles_parcours(o: dict) -> dict:
    """Les 3 oracles de parcours d'une étape observée. Une étape planifiée (beat, tâche) que rien n'a
    écrite reste NA : la transaction annulée ne la déclenche pas (son test nommé la prouve)."""
    statut, ecrit = o.get("statut"), o.get("ecrit") or {}
    ecrite = bool(ecrit.get("crees") or ecrit.get("modifies"))
    principaux = [a for a in o.get("appels") or [] if not a.get("attendu_refus")]
    observable = statut == "joue" or (statut == "auto" and bool(ecrit) and (ecrite or not o.get("planifiee")))
    sortie = {"declenchee": "NA", "checkpoint": "NA", "aval": "NA"}
    if statut == "auto" and observable:
        sortie["declenchee"] = _pf(ecrite)
    elif statut == "joue":
        sortie["declenchee"] = _pf(principaux and principaux[0]["statut"] < 400)
    lecture = o.get("verbe") == "get"
    if observable and ecrit and (not lecture or o.get("modifiable") is not None):
        sortie["checkpoint"] = _pf((ecrite or lecture) and o.get("modifiable") is not False)
    regles = [v for v in (o.get("regles") or {}).values() if v is not None]
    if regles:
        sortie["aval"] = _pf(all(regles))
    return sortie


def evaluer(o: dict) -> dict:
    """Verdict, oracles qa-explorer 1-10, oracles de parcours et trace d'une étape observée."""
    appels = o.get("appels") or []
    q = {str(n): "NA" for n in range(1, 11)}
    if appels:
        q["1"] = _pf(all(a["statut"] < 500 for a in appels))
        q["2"] = _pf(all(a["statut"] < 400 for a in appels if not a.get("attendu_refus")))
        q["9"] = _pf(not any(a.get("etrangers") for a in appels))
    if o.get("liste") is not None:
        q["5"] = _pf(o["liste"])
    pdf = o.get("pdf")
    if pdf:
        q["6"] = _pf(pdf["statut"] == 200 and "pdf" in pdf["type"] and pdf["tete"] == "%PDF-"
                     and pdf["taille"] >= 10000)
        if pdf.get("prix_achat") is not None:
            q["7"] = _pf(not pdf["prix_achat"])
    if o.get("coherence") is not None:
        q["10"] = _pf(not o["coherence"])
    p = oracles_parcours(o)
    echec = "FAIL" in q.values() or "FAIL" in p.values() or o.get("statut") in ("erreur", "non_rejouable")
    notes = (o.get("motif"), f"écrit {o.get('ecrit')}" if o.get("statut") == "auto" else "")
    trace = " ; ".join([f"{a['verbe']} {a['url']} → {a['statut']}" for a in appels] + [x for x in notes if x])
    return {"verdict": "FAIL" if echec else "PASS", "oracles": q, "oracles_parcours": p,
            "trace": trace or str(o.get("statut"))}


def enregistrement(pa: str, sha: str, date: str, observations: list) -> dict:
    """results.json (format AMET88) : étapes à tâches dans ``etapes``, les autres à part."""
    jouees, sans_tache, manquantes = [], [], []
    for o in observations:
        if o.get("statut") == "manquante":
            manquantes.append(o.get("id"))
            continue
        etape = {"id": o.get("id"), "taches": list(o.get("taches") or []), "base_verdict": None, **evaluer(o)}
        (jouees if etape["taches"] else sans_tache).append(etape)
    toutes = jouees + sans_tache
    return {"sha": sha, "date": date, "groupe": pa, "parcours": pa,
            "verdict": "PASS" if toutes and all(e["verdict"] == "PASS" for e in toutes) else "FAIL",
            "couvre": sorted({t for e in jouees for t in e["taches"]}), "couvre_avec_ecart": [],
            "etapes": jouees, "etapes_sans_tache": sans_tache, "etapes_manquantes": manquantes}


def ecrire(res: dict, racine) -> Path:
    """Écrit le couple .md / .results.json ; renvoie le chemin du .md."""
    dossier = Path(racine) / "docs" / "audits" / "acceptation" / res["groupe"]
    dossier.mkdir(parents=True, exist_ok=True)
    md = dossier / f"{res['date']}-{res['sha'][:9]}.md"
    md.with_name(md.stem + ".results.json").write_text(
        json.dumps(res, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
    lignes = ["---", f"sha: {res['sha']}", f"date: {res['date']}", f"groupe: {res['groupe']}",
              f"couvre: [{', '.join(res['couvre'])}]", "couvre_avec_ecart: []", f"verdict: {res['verdict']}", "etapes:"]
    for e in res["etapes"]:
        lignes += [f"  - id: {e['id']}", f"    tache: [{', '.join(e['taches'])}]", f"    verdict: {e['verdict']}"]
    lignes += ["---", "", f"# Rejeu du parcours {res['parcours']} (scripts/rejouer_parcours.py, AMET98)", "",
               "| Étape | Tâches | Verdict | Oracles de parcours | Trace |", "|---|---|---|---|---|"]
    for e in res["etapes"] + res["etapes_sans_tache"]:
        parcours = ", ".join(f"{k} {v}" for k, v in e["oracles_parcours"].items())
        lignes.append(f"| {e['id']} | {', '.join(e['taches']) or '—'} | {e['verdict']} | {parcours} | "
                      f"{e['trace'].replace('|', '/')} |")
    lignes += [""] + [f"- Étape manquante rapportée, jamais jouée : {i}" for i in res["etapes_manquantes"]]
    md.write_text("\n".join(lignes) + "\n", encoding="utf-8", newline="\n")
    return md


def candidats(etape: dict, appelants=None) -> list:
    """Références de vues à essayer : fonction d'entrée, déclencheur, puis les appelants Python d'une
    fonction d'entrée de module (``audit_tache.appelants``, index AST AMET80)."""
    entree = etape.get("fonction_entree")
    refs = [r for r in (entree, (etape.get("declencheur") or {}).get("source")) if isinstance(r, str) and ".py::" in r]
    if isinstance(entree, str) and ".py::" in entree and "." not in entree.split("::", 1)[1]:
        try:
            if appelants is None:
                import audit_tache
                appelants = audit_tache.appelants
            refs += [x["symbole"] for x in appelants(entree).get("python", []) if not x.get("test")]
        except BaseException as exc:  # audit_tache sort par SystemExit sur une cible introuvable
            print(f"Avis : appelants de {entree} non calculés ({exc})")
    return list(dict.fromkeys(refs))


def _ligne_marquee(sortie: str, marque: str):
    ligne = next((x for x in sortie.splitlines() if x.startswith(marque)), None)
    return None if ligne is None else json.loads(ligne[len(marque):])


def _parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(description="Rejeu d'une table de parcours sur UN enregistrement (AMET98).")
    ap.add_argument("parcours", help="ex. PA4")
    ap.add_argument("--enregistrement", required=True, help="pk de l'objet de départ (ex. le devis de PA4)")
    ap.add_argument("--utilisateur", help="username de l'acteur (défaut : 1er actif de la société, admin d'abord)")
    ap.add_argument("--modele", help="app.Modele de l'enregistrement (défaut : déduit de la 1re étape)")
    ap.add_argument("--conteneur", help="conteneur Django local (défaut : celui de sonde.py)")
    ap.add_argument("--timeout", type=int, default=900)
    ap.add_argument("--dry-run", action="store_true", help="imprime le programme envoyé, sans docker")
    ap.add_argument("--racine", default=str(ROOT))
    return ap


def main(argv=None, executer=None, appelants=None, sha=None, date=None) -> int:
    import check_acceptation
    import check_parcours
    import sonde
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    a = _parser().parse_args(argv)
    chemins = [c for c in check_parcours.tables(Path(a.racine)) if c.stem == a.parcours]
    if len(chemins) != 1:
        print(f"ÉCHEC — table {a.parcours} introuvable (ou en double) sous {a.racine}")
        return 1
    table = json.loads(chemins[0].read_text(encoding="utf-8"))
    refus = check_parcours.problemes(table)
    if refus:
        print(f"ÉCHEC — {a.parcours} refusée par check_parcours.py :\n  - " + "\n  - ".join(refus))
        return 1
    sha = sha or subprocess.run(["git", "rev-parse", "HEAD"], cwd=a.racine, capture_output=True,
                                text=True).stdout.strip()
    params = {"table": table, "enregistrement": a.enregistrement, "utilisateur": a.utilisateur, "modele": a.modele,
              "candidats": {e.get("id"): candidats(e, appelants) for e in table["etapes"]
                            if not e.get("manquante") and (e.get("declencheur") or {}).get("type") not in AUTO}}
    source = (Path(__file__).read_text(encoding="utf-8") + f"\n\nPARAMS = json.loads({ascii(json.dumps(params))})\n"
              "\n\ndef sonde(ctx):\n    return rejouer_dans_django(PARAMS)\n")
    entete = {"constat": "C-AMET-025", "sha": sha, "attendu": f"{a.parcours} rejoué sur {a.enregistrement}"}
    programme = sonde.programme(source, entete, a.timeout)
    if a.dry_run:
        print(programme)
        return 0
    commande = ["docker", "exec", "-i", a.conteneur or sonde.CONTENEUR, "python", "-u", "manage.py", "shell"]
    code, sortie, erreur = (executer or sonde.executer_docker)(commande, programme, a.timeout)
    observations, bilan = _ligne_marquee(sortie, MARQUE), _ligne_marquee(sortie, sonde.MARQUE) or {}
    if observations is None:
        print(f"ÉCHEC — aucun résultat du conteneur (code {code}) : {(erreur or sortie).strip()[-600:]}")
        return 1
    res = enregistrement(a.parcours, sha, date or datetime.date.today().isoformat(), observations)
    for e in res["etapes"] + res["etapes_sans_tache"]:
        print(f"{e['id']} : {e['verdict']} — {e['trace']}")
    for ident in res["etapes_manquantes"]:
        print(f"{ident} : manquante — rapportée, jamais jouée")
    inchangee = bilan.get("base_inchangee") is True
    print(f"base inchangée : {'oui' if inchangee else 'NON'} ; verdict {a.parcours} : {res['verdict']}")
    if not res["etapes"]:
        print("Aucune étape à tâche : pas d'enregistrement d'acceptation (rapport seul).")
        return 0 if res["verdict"] == "PASS" and inchangee else 1
    md, erreurs = ecrire(res, a.racine), []
    check_acceptation.lire_enregistrement(md, erreurs)
    print(f"Enregistrement : {md} (couvre {', '.join(res['couvre'])})" + "".join(f"\n  - {x}" for x in erreurs))
    return 0 if res["verdict"] == "PASS" and inchangee and not erreurs else 1


if __name__ == "__main__":
    sys.exit(main())
