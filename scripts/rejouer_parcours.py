#!/usr/bin/env python3
"""AMET98 (C-AMET-025) — rejeu d'un PARCOURS sur UN enregistrement de la pile locale.

    python scripts/rejouer_parcours.py PA4 --enregistrement <id devis> [--modele ventes.Devis]
        [--utilisateur demo_admin] [--corps etapes.json] [--dry-run] [--sans-enregistrement]

1. La table est d'abord validée par `parcours_tables.verifier_table` (refus si ÉCHEC) — les mêmes
   fonctions que `check_parcours.py`.
2. Chaque étape est jouée par l'API réelle (`APIClient`, route DRF retrouvée depuis la fonction
   d'entrée ou le déclencheur), DANS le conteneur Django, par le programme de `sonde.py` (AMET93) :
   transaction annulée, mail en mémoire, Celery coupé, HTTP sortant bloqué, comptes avant / après
   — rien n'est gardé ; une base modifiée = ÉCHEC, jamais d'enregistrement. Une étape `manquante`
   est rapportée, jamais jouée. `--corps` : `{id_étape: corps JSON}` pour les actions qui en exigent
   (« {app.Modele.champ} » = champ de l'objet chaîné ; `{"__fichier__": nom, "contenu": …}` = envoi multipart ;
   `"<id>.apercu"` = corps de l'aperçu). Aperçu DÉCLARÉ (déclencheur = vue dry-run distincte de l'action) : joué
   d'abord, son jeton passé à l'action. Route à `<modele>_id` : pk de l'objet de CE modèle. Étape automatique
   dont le déclencheur nomme une tâche (`fichier.py::fonction`) : la tâche est exécutée dans la transaction ;
   sans artefact lié (ou sans tâche nommée) : « hors rejeu » avec la raison, jamais FAIL — sauf tâche levée.
3. Oracles qa-explorer 1-10 au niveau API (1 : ≥ 500 ; 2 : 4xx sur l'action que la table ne DÉCLARE pas
   — `statuts_declares` : « HTTP 4xx » d'une règle aval, 409 d'un `refus_409` ; 5 : liste relue après
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
    """`pk` : une valeur pour tous les paramètres, ou {nom: valeur} (route à `<modele>_id` nommé)."""
    def val(m):
        return str(pk.get(m.group(1) or m.group(2), "") if isinstance(pk, dict) else pk)
    s = re.sub(r"\(\?P<(\w+)>[^)]*\)|<(?:\w+:)?(\w+)>", val, route)
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


def _c_route_de(C, ancre, vue_fonction=True):
    fichier, _, sym = (ancre or "").partition("::")
    morceaux = sym.split(".")
    if len(morceaux) < 2 and not vue_fonction:
        return None
    if len(morceaux) < 2:  # ADVS41 — vue-FONCTION (@api_view, page publique à jeton) nommée par l'ENTRÉE
        mod = fichier.replace("backend/django_core/", "")[:-3].replace("/", ".")
        return next(((r, v, cb.cls) for r, cb in C["routes"] for v in ("get", "post")
                     if sym and getattr(getattr(cb, "cls", None), "__name__", None) == sym
                     and getattr(cb.cls, "__module__", None) == mod and not getattr(cb, "actions", None)
                     and "format" not in r and hasattr(cb.cls, v)), None)
    action = {"perform_create": "create", "perform_update": "partial_update"}.get(morceaux[1], morceaux[1])
    return _c_chercher(C, lambda c: morceaux[0] in {k.__name__ for k in c.__mro__}, action)


def _c_par_appelant(C, e, Mp, notes):
    """Entrée DOMAINE : l'action de vue qui l'APPELLE (ancres de l'hôte, `actions_appelantes`, index AST) ;
    préfère le modèle du checkpoint, puis un objet déjà lié, sinon l'ordre de l'hôte."""
    trouves = []
    for ancre in C["P"]["appelants"].get(e.get("id")) or []:
        fichier, _, nom = ancre.partition("::")
        mod = fichier.replace("backend/django_core/", "")[:-3].replace("/", ".")
        vue_f = lambda c: c.__name__ == nom and c.__module__ == mod  # noqa: E731 — vue-fonction / classe nue
        t = _c_route_de(C, ancre) if "." in nom else _c_chercher(C, vue_f, "create") or _c_chercher(C, vue_f, "post")
        if t:
            trouves.append((ancre, t))
    if not trouves:
        n = len(C["P"]["appelants"].get(e.get("id")) or [])
        notes.append(f"{n} action(s) de vue appelante(s), aucune route DRF" if n else
                     "aucune action de vue n'appelle la fonction d'entrée (index AST)")
        return None
    M = [_c_modele_vue(t[2]) for _, t in trouves]
    i = min(range(len(trouves)), key=lambda k: (M[k] is not Mp or Mp is None,
                                                getattr(getattr(M[k], "_meta", None), "label", "") not in C["objets"]))
    notes.append(f"via {trouves[i][0]} (appelle la fonction d'entrée ; {len(trouves)} candidate(s) : "
                 + ", ".join(a.partition("::")[2] for a, _ in trouves) + ")")
    return trouves[i][1]


def _c_artefact(C, Mp):
    """Étape automatique : un `Mp` lié à N'IMPORTE QUEL objet chaîné à l'enregistrement (toutes les factures
    du devis, pas seulement la dernière, souvent celle que le rejeu vient de créer)."""
    objets = C["objets"]

    def fks(M):
        return [f for f in M._meta.fields if (f.many_to_one or f.one_to_one) and f.related_model is not None]
    for f in fks(Mp):
        R = f.related_model
        ids = {objets[R._meta.label]} if R._meta.label in objets else set()
        for g in [g for g in fks(R) if g.related_model._meta.label in objets]:
            ids |= set(R._default_manager.filter(**{g.name: objets[g.related_model._meta.label]})
                       .values_list("pk", flat=True))
        o = Mp._default_manager.filter(**{f.name + "__in": ids}).order_by("-pk").first() if ids else None
        if o is not None:
            return o.pk
    return None


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


def _c_jeton(C):
    """ADVS41 — jeton d'une route publique : le lien le plus récent (modèle à champ `token`, FK vers un objet
    suivi, non expiré) — celui que l'envoi rejoué vient de frapper dans la même transaction."""
    from django.apps import apps
    from django.utils import timezone
    for M in apps.get_models():
        noms = {f.name for f in M._meta.fields}
        for f in [f for f in M._meta.fields if "token" in noms and f.many_to_one and f.related_model is not None]:
            if f.related_model._meta.label in C["objets"]:
                qs = M._default_manager.filter(**{f.name: C["objets"][f.related_model._meta.label]})
                o = (qs.filter(expires_at__gt=timezone.now()) if "expires_at" in noms else qs).order_by("-pk").first()
                if o is not None:
                    return o.token
    return None


def _c_appeler(C, verbe, chemin, corps=None):
    from django.db import transaction
    api = C["api"]
    fichiers = isinstance(corps, dict) and any(isinstance(v, dict) and "__fichier__" in v for v in corps.values())
    if fichiers:  # {"file": {"__fichier__": "releve.csv", "contenu": "..."}} -> envoi multipart
        from django.core.files.uploadedfile import SimpleUploadedFile
        corps = {k: SimpleUploadedFile(v["__fichier__"], str(v.get("contenu", "")).encode("utf-8"))
                 if isinstance(v, dict) and "__fichier__" in v else v for k, v in corps.items()}
    with transaction.atomic():
        r = (api.get(chemin) if verbe == "get" else
             getattr(api, verbe)(chemin, corps or {}, format="multipart" if fichiers else "json"))
    ctype = r.get("Content-Type", "")
    # ADVS41 — corps ENTIER (une liste de 50 devis dépasse 1,5 Mo : tronquée, elle ne se lisait plus en JSON)
    texte = "" if "pdf" in ctype else r.content.decode("utf-8", "replace")
    try:
        donnees = json.loads(texte) if "json" in ctype else None
    except ValueError:
        donnees = None
    return r.status_code, ctype, texte, donnees


def _c_gabarit(C, v):
    """Corps `--corps` : « {app.Modele.champ} » remplacé par le champ (relu) de l'objet chaîné à l'enregistrement."""
    from django.apps import apps
    if isinstance(v, dict):
        return {k: _c_gabarit(C, x) for k, x in v.items()}
    if isinstance(v, list):
        return [_c_gabarit(C, x) for x in v]

    def champ(m):
        try:
            M = apps.get_model(m.group(1))
        except (LookupError, ValueError):
            return m.group(0)
        pk = _c_lier(C, M)
        o = M._default_manager.filter(pk=pk).first() if pk is not None else None
        return m.group(0) if o is None else str(getattr(o, m.group(2), m.group(0)))
    return re.sub(r"\{(\w+\.\w+)\.(\w+)\}", champ, v) if isinstance(v, str) else v


def _c_parametres(C, route, cls):
    """({nom: valeur} des paramètres de la route, nom introuvable | None) : `token` = jeton du lien, `<modele>_id`
    = pk de l'objet de CE modèle chaîné à l'enregistrement (jamais le pk du modèle de la vue), sinon pk de la vue."""
    from django.apps import apps
    valeurs = {}
    for a, b in re.findall(r"\(\?P<(\w+)>|<(?:\w+:)?(\w+)>", route):
        nom = a or b
        if nom == "token":
            valeurs[nom] = _c_jeton(C)
        elif nom.endswith("_id"):
            cible = nom[:-3].replace("_", "")
            tous = [M for M in apps.get_models() if M.__name__.lower() == cible]
            M = next((M for M in tous if M._meta.label in C["objets"]), tous[0] if tous else None)
            valeurs[nom] = _c_lier(C, M)
        else:
            valeurs[nom] = _c_lier(C, _c_modele_vue(cls))
        if valeurs[nom] is None:
            return valeurs, nom
    return valeurs, None


def _c_apercu(C, e, trouve, res):
    """Aperçu DÉCLARÉ (déclencheur = vue dry-run / aperçu distincte de l'action) : le joue d'abord et rend
    {jeton, ok} ; corps de l'aperçu = `--corps {"<id>.apercu": ...}`. None : l'étape n'en déclare pas."""
    source = (e.get("declencheur") or {}).get("source") or ""
    ap = _c_route_de(C, source)
    if not ap or ap[0] == trouve[0] or not re.search(r"dry.?run|apercu|preview", ap[0] + source, re.I):
        return None
    chemin = _c_url(ap[0], "")
    st, _, texte, d = _c_appeler(C, ap[1], chemin, _c_gabarit(C, C["P"]["corps"].get(e.get("id") + ".apercu", {})))
    jeton = (d.get("token") or d.get("jeton")) if isinstance(d, dict) else None
    res["notes"].append(f"aperçu déclaré {ap[1].upper()} {chemin} -> {st}"
                        + (" (jeton passé à l'action)" if jeton else f", sans jeton ({texte[:160]})"))
    return {"jeton": jeton, "ok": st < 400 and bool(jeton)}


def _c_tache(C, ancre, res):
    """Étape automatique : la tâche planifiée NOMMÉE par le déclencheur (`fichier.py::fonction`, sans argument)
    exécutée dans la transaction du rejeu. True / False (levée) / None (aucune tâche exécutable nommée)."""
    import importlib
    from django.db import transaction
    fichier, _, sym = (ancre or "").partition("::")
    if not fichier.startswith("backend/django_core/") or not fichier.endswith(".py") or not sym or "." in sym:
        return None
    try:
        f = getattr(importlib.import_module(fichier[len("backend/django_core/"):-3].replace("/", ".")), sym, None)
    except ImportError:
        return None
    if not callable(f):
        return None
    try:
        with transaction.atomic():
            retour = f()
    except Exception as exc:  # noqa: BLE001 — rapportée, l'étape tombe
        res["notes"].append(f"tâche {sym}() levée : {type(exc).__name__}: {exc}"[:300])
        return False
    res["notes"].append(f"tâche {sym}() exécutée dans la transaction -> {retour!r}"[:200])
    return True


def _c_oracles_api(C, res, appel, cls, types):
    """Oracles qa-explorer 1, 2, 5, 6, 7, 9 d'une action jouée + oracle de parcours `aval` (refus_409)."""
    verbe, chemin, corps, (st, ctype, texte, donnees) = appel
    O, R, co = res["oracles"], res["parcours"], C["co"]
    declare = 400 <= st < 500 and st in set(C["P"]["declares"].get(res["id"]) or [])
    O["1"], O["2"] = ("FAIL" if st >= 500 else "PASS"), ("FAIL" if 400 <= st < 500 and not declare else "PASS")
    if declare:  # 4xx que la table DÉCLARE (regle_aval « HTTP nnn » / refus_409) : la réponse attendue
        res["notes"].append(f"{st} déclaré par la table : réponse attendue de l'étape")
    if "proposal" in chemin and chemin.rstrip("/").endswith(("proposal", "pdf")):  # rendu PDF, pas la data JSON
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
    params, manque = _c_parametres(C, route, cls)
    if manque:
        nom = "lien à jeton valide" if manque == "token" else (
            manque if manque.endswith("_id") else getattr(_c_modele_vue(cls), "__name__", "?"))
        res["notes"].append(f"aucun {nom} lié à l'enregistrement : non jouée")
        return False
    chemin, corps = _c_url(route, params), _c_gabarit(C, C["P"]["corps"].get(e.get("id"), {}))
    ap = _c_apercu(C, e, trouve, res)
    if ap and ap["jeton"] and isinstance(corps, dict) and "token" not in corps:
        corps = dict(corps, token=ap["jeton"])
    reponse = _c_appeler(C, verbe, chemin, corps)
    res["joue"], res["appel"] = True, f"{verbe.upper()} {chemin} -> {reponse[0]}"
    declare = reponse[0] in set(C["P"]["declares"].get(e.get("id")) or [])
    if 400 <= reponse[0] < 500 and not corps and verbe != "get" and not declare:
        res["notes"].append(f"corps vide envoyé ({reponse[2][:160]}) : fournir --corps {{\"{e.get('id')}\": {{...}}}}")
    _c_oracles_api(C, res, (verbe, chemin, corps, reponse), cls, types)
    if ap and not ap["ok"]:  # aperçu déclaré en échec : un refus « jeton absent » n'est JAMAIS une réponse attendue
        res["oracles"]["2"] = "FAIL"
        res["notes"].append("aperçu déclaré en échec : enchaînement aperçu -> action impossible")
    return True


def _c_checkpoint(C, res, point, Mp, auto):
    """Oracles de parcours `auto` (artefact lié) et `checkpoint` (persisté ; modifiable = PATCH relu identique)."""
    R, notes = res["parcours"], res["notes"]
    pk_p = _c_lier(C, Mp)
    if auto:
        pk_p = pk_p or (_c_artefact(C, Mp) if Mp is not None else None)
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
    trouve = _c_route_de(C, entree if isinstance(entree, str) else "") or _c_route_de(C, decl.get("source"), False)
    if not trouve and not auto:
        trouve = _c_par_appelant(C, e, Mp, res["notes"])
    tache = None
    if trouve:
        if not _c_jouer_api(C, e, res, trouve, types):
            return res
    elif auto:
        tache = _c_tache(C, decl.get("source"), res)
        res["joue"], res["appel"] = True, f"auto ({decl.get('type')}) : artefact {getattr(Mp, '__name__', '?')}"
    else:
        res["notes"].append("aucune route API pour la fonction d'entrée, ses appelants ni le déclencheur : non jouée")
        return res
    _c_checkpoint(C, res, point, Mp, auto)
    if auto and tache is not False and res["parcours"]["auto"] == "FAIL":  # jamais quand la tâche a levé
        res["hors_rejeu"] = ("tâche planifiée exécutée dans la transaction, aucun artefact lié : sa condition "
                             "(échéance, date) n'est pas atteinte par un enregistrement créé le jour du rejeu"
                             if tache else "le déclencheur ne nomme aucune tâche exécutable et aucun artefact lié")
        res["parcours"].update(auto="NA", checkpoint="NA")
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


_CONTENEUR = (_c_routes, _c_url, _c_modele_vue, _c_chercher, _c_route_de, _c_par_appelant, _c_artefact,
              _c_modele_de, _c_lier, _c_jeton, _c_appeler, _c_gabarit, _c_parametres, _c_apercu, _c_tache,
              _c_oracles_api, _c_jouer_api, _c_checkpoint, _c_etape, _jouer)
EN_TETE_CONTENEUR = "import json\nimport re\nimport sys\n\n\n"


def statuts_declares(etape: dict) -> list:
    """Codes 4xx que l'étape DÉCLARE comme réponse attendue : « HTTP nnn » d'une règle aval, 409 pour `refus_409`.
    Un 4xx hors de cette liste reste un FAIL (oracle 2) ; un 5xx l'est toujours."""
    codes = set()
    for r in etape.get("regle_aval", etape.get("regles_aval")) or []:
        texte = r if isinstance(r, str) else " ".join(str(r.get(k) or "") for k in ("type", "detail", "regle"))
        codes |= {int(c) for c in re.findall(r"HTTP\s+(4\d\d)\b", texte)}
        if (r if isinstance(r, str) else r.get("type")) == "refus_409":
            codes.add(409)
    return sorted(codes)


def programme(table: dict, params: dict, timeout: int) -> str:
    """Programme AUTONOME (sonde.py) : transaction annulée, comptes avant / après."""
    P = dict(params, etapes=table.get("etapes") or [], oracles=ORACLES, marque=MARQUE,
             auto=sorted(cp.TYPES_AUTO), corps=params.get("corps") or {}, appelants=params.get("appelants") or {},
             declares={e.get("id"): statuts_declares(e) for e in table.get("etapes") or []})
    source = (EN_TETE_CONTENEUR + "\n\n".join(inspect.getsource(f) for f in _CONTENEUR)
              + f"\n\nP = __import__('json').loads({json.dumps(P, ensure_ascii=True)!r})\n"
              "\n\ndef sonde(ctx):\n    return _jouer(P)\n")
    portes = table.get("portes")  # AARG45 : `modeles` = tables du parcours (clés de `portes` + modèle suivi)
    entete = {"constat": "C-AMET-025", "sha": "rejeu", "attendu": f"rejeu {cp.identifiant(table)}",
              "modeles": sorted(set(portes if isinstance(portes, dict) else ()) | {params.get("modele")} - {None})}
    return sonde.programme(source, entete, timeout)


def ligne_erreur(*textes) -> str:
    """AARG45 — l'exception (type + message) : fin du bloc `ERREUR : ` de sonde.py, sinon 1re après `Traceback`."""
    for texte in filter(None, textes):
        for marque, rang in (("ERREUR : ", -1), ("Traceback (most recent call last):", 0)):
            lignes = [x for x in texte.rsplit(marque, 1)[-1].splitlines() if x.strip() and not x[0].isspace()]
            if marque in texte and lignes:
                return lignes[rang]
    return ""


def _notes(res: dict) -> str:
    notes = res.get("notes") or []
    return "; ".join(notes) if isinstance(notes, list) else str(notes)


def etapes_enregistrement(table: dict, resultats: list, couvre=None) -> tuple:
    """(étapes au format results.json AMET88, lignes « non enregistrées » à rapporter). `couvre` (--couvre) :
    chaque étape jouée couvre CES tâches (rejeu preuve d'une tâche de table), id suffixé `.rejeu_<tâche>`."""
    par_id = {r.get("id"): r for r in resultats}
    etapes, ignorees = [], []
    suffixe = ".rejeu_" + "_".join(couvre).lower() if couvre else ""
    for e in cp.parcours.etapes(table):
        ident, res = e.get("id"), par_id.get(e.get("id")) or {}
        if cp.est_manquante(e):
            ignorees.append(f"{ident} : manquante déclarée, jamais jouée")
        elif not res.get("joue"):
            ignorees.append(f"{ident} : non jouée ({_notes(res) or 'sans résultat'})")
        elif res.get("hors_rejeu"):
            ignorees.append(f"{ident} : hors rejeu ({res['hors_rejeu']})")
        elif not (couvre or e.get("taches")):
            ignorees.append(f"{ident} : jouée, sans tâche à couvrir ({res.get('appel')})")
        else:
            verdicts = list(res["oracles"].values()) + list(res["parcours"].values())
            etapes.append({
                "id": ident + suffixe, "taches": list(couvre or e["taches"]),
                "verdict": "FAIL" if "FAIL" in verdicts else "PASS",
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


def appelants_des_etapes(table: dict, racine, appelants=cp.actions_appelantes) -> dict:
    """{id: [ancres d'actions de vue]} des étapes dont la fonction d'entrée n'est pas une action de vue."""
    return {e["id"]: a for e in cp.parcours.etapes(table) if isinstance(e.get("fonction_entree"), str)
            and not cp.est_manquante(e) and (a := appelants(e["fonction_entree"], racine))}


def main(argv=None, executer=sonde.executer_docker, ecrire=ecrire_enregistrement,
         appelants=cp.actions_appelantes) -> int:
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
    a.add_argument("--couvre", help="tâches (virgules) que CHAQUE étape jouée couvre (preuve d'une tâche de table)")
    a.add_argument("--groupe", help="groupe d'acceptation de l'enregistrement (défaut : le parcours)")
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
        motif = "table invalide (check_parcours.py)" if echecs else f"--modele requis pour {pa}"
        print(f"ÉCHEC : {motif}")
        return 1
    corps = json.loads(Path(a.corps).read_text(encoding="utf-8")) if a.corps else {}
    prog = programme(table, {"modele": modele, "enregistrement": a.enregistrement,
                             "utilisateur": a.utilisateur, "corps": corps,
                             "appelants": appelants_des_etapes(table, racine, appelants)}, a.timeout)
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
        print(f"ÉCHEC : rejeu incomplet ou base modifiée (code {rc}) "
              f"{ligne_erreur(bilan.get('observe'), erreur, sortie) or (erreur or sortie).strip()[-600:]}")
        return 1
    resultats = json.loads(brut)
    for r in resultats:
        hors = f" ; HORS REJEU : {r['hors_rejeu']}" if r.get("hors_rejeu") else ""
        print(f"{r['id']} : {r.get('appel') or 'non jouée'} ; parcours {r['parcours']} ; {_notes(r)}{hors}")
    couvre_taches = [t.strip() for t in (a.couvre or "").split(",") if t.strip()]
    etapes, ignorees = etapes_enregistrement(table, resultats, couvre_taches)
    for ligne in ignorees:
        print(f"Hors enregistrement : {ligne}")
    print(f"Base inchangée (transaction annulée) : {bilan.get('comptes_avant')} lignes avant et après.")
    ok = all(e["verdict"] == "PASS" for e in etapes)
    if a.sans_enregistrement or not etapes:
        print("Aucun enregistrement écrit" + (" (aucune étape jouée ne porte de tâche)." if not etapes else "."))
        return 0 if ok else 1
    couvre = sorted({t for e in etapes for t in e["taches"]})
    return 0 if ecrire((a.groupe or pa).upper(), {"couvre": couvre, "etapes": etapes}) == 0 and ok else 1


if __name__ == "__main__":
    sys.exit(main())
