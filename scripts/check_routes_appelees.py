#!/usr/bin/env python3
"""ACRM49 - garde « route servie sans appelant » de l'app crm.

Classe visee : un ecran est retire (commit 348a7c7b0 : kpi-adherence, mes-stats)
mais sa route ET son calcul restent servis, a la charge du serveur, sans que
personne ne les appelle. ``check_api_contract.py`` verifie le sens
front -> route (aucun appel vers une route inexistante) ; cette garde verifie le
sens inverse pour le routeur crm : chaque route DRF a au moins un appelant.

Une route crm est VALIDE si l'une de ces conditions tient :
1. un appel de ``frontend/src`` (clients ``api/*.js`` ou composants, resolus par
   l'extracteur de ``check_api_contract.py``) la joint ;
2. un test e2e de ``frontend/e2e`` la joint par un chemin litteral ;
3. elle est « sans ecran par construction » : prefixe ``public/`` ou
   ``webhooks/`` (appeles par le site public, Meta, un cron - jamais par l'ERP)
   ou portail a jeton ``apporteur-portail/`` ;
4. elle figure dans ``A_CORRIGER`` ci-dessous, une ligne MOTIVEE par route.

Un detail de routeur ``<pk>`` est couvert des qu'un appelant joint la liste ou
une action de la meme ressource (le client CRUD l'atteint par le meme prefixe).

``A_CORRIGER`` est de la dette reelle : routes servies sans aucun appelant,
dont le sort est a trancher par le proprietaire crm (decision fondateur ACRM2 :
retirer, parquer derriere un reglage, ou construire l'ecran). Cette garde ne les
corrige jamais ; elle FAIT DESCENDRE la liste : une entree qui a desormais un
appelant (ou dont la route a disparu) est un echec « entree perimee » - on la
retire. Aucune entree ne s'ajoute pour faire passer la garde (ENF14).

Lecture statique pure (aucun import Django). Usage : ``python
scripts/check_routes_appelees.py``.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import check_api_contract as cac  # noqa: E402

MONTAGE = ("api", "django", "crm")
E2E_DIR = ROOT / "frontend" / "e2e"

#: Premiers segments (apres ``api/django/crm``) servis a des appelants non-ERP.
SANS_ECRAN_PAR_CONSTRUCTION = {
    "public": "route publique tokenisee, appelee par le site public (apps/web)",
    "webhooks": "rappel entrant (site public, Meta, YanBow), jamais appele par un ecran ERP",
    "apporteur-portail": "portail public a jeton de l'apporteur d'affaires",
}

_ACRM2_I = ("A CORRIGER (ACRM2 i, proprietaire crm) : ecran retire le 30/09 (348a7c7b0), "
            "la route et son calcul 'en retard' restent servis sans appelant")
_ACRM2_II = ("A CORRIGER (ACRM2 ii, proprietaire crm) : salle de vente - aucune salle ne "
             "se cree depuis l'ERP, route servie sans ecran (parquer ou construire)")
_ACRM2_III = ("A CORRIGER (ACRM2 iii, proprietaire crm) : apporteurs / deals enregistres - "
              "commission calculee a chaque devis accepte, aucun ecran (parquer ou construire)")
_ACRM2_IV = ("A CORRIGER (ACRM2 iv, proprietaire crm) : aucun appelant front "
             "(retrait recommande)")
_SANS_ECRAN = ("A CORRIGER (proprietaire crm) : route servie sans aucun appelant "
               "front ni e2e - retirer, ou construire l'ecran")

#: ``crm/<route>`` (``<>`` = parametre, ``<pk>`` = detail de routeur) -> raison.
A_CORRIGER: dict[str, str] = {
    "crm/salles-vente": _ACRM2_II,
    "crm/salles-vente/<pk>": _ACRM2_II,
    "crm/salles-vente/<>/analytics": _ACRM2_II,
    "crm/salles-vente/<>/items": _ACRM2_II,
    "crm/salles-vente/<>/items/<>": _ACRM2_II,
    "crm/apporteurs": _ACRM2_III,
    "crm/apporteurs/<pk>": _ACRM2_III,
    "crm/deals-enregistres": _ACRM2_III,
    "crm/deals-enregistres/<pk>": _ACRM2_III,
    "crm/deals-enregistres/<>/approuver": _ACRM2_III,
    "crm/deals-enregistres/<>/rejeter": _ACRM2_III,
    "crm/deals-enregistres/a-payer": _ACRM2_III,
    "crm/defis/<>/export-xlsx": _ACRM2_IV,
    "crm/points-contact/attribution": _ACRM2_IV,
    "crm/clients/<>/dupliquer": _SANS_ECRAN,
    "crm/clients/<>/engagement": _SANS_ECRAN,
    "crm/forecast/historique": _SANS_ECRAN,
    "crm/objectifs": _SANS_ECRAN,
    "crm/partenaires": _SANS_ECRAN,
    "crm/partenaires/<pk>": _SANS_ECRAN,
    "crm/partenaires/<>/provisionner-acces": _SANS_ECRAN,
    "crm/plans-compte/<>/chatter/historique": _SANS_ECRAN,
    "crm/plans-compte/<>/chatter/noter": _SANS_ECRAN,
}

_E2E_CHEMIN = re.compile(r"/api/django/crm/[^'\"`\s?#)\\]*")
_TROU = re.compile(r"\$\{[^{}]*\}")


def routes_crm(routes) -> list[tuple]:
    """Routes du routeur crm (tuples de segments), triees."""
    return sorted(r for r in routes if tuple(r[:3]) == MONTAGE)


def appels_e2e(dossier: Path = E2E_DIR) -> set[tuple]:
    """Chemins crm litteraux des specs e2e, ``${...}`` -> joker."""
    out: set[tuple] = set()
    if not dossier.is_dir():
        return out
    for p in sorted(dossier.rglob("*.js")):
        try:
            texte = p.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        for m in _E2E_CHEMIN.finditer(texte):
            brut = _TROU.sub(cac.ANY, m.group(0))
            segs = tuple(s for s in brut.strip("/").split("/") if s)
            out.add(segs)
    return out


def _cle(route: tuple) -> str:
    return "/".join(route[2:])


def routes_sans_appelant(routes, appels) -> list[tuple]:
    """Routes crm sans appelant, hors « sans ecran par construction ».

    ``routes`` : tuples de segments (``api, django, crm, ...``) ; ``appels`` :
    tuples normalises (front + e2e). Les exemptions ``A_CORRIGER`` NE sont PAS
    retirees ici (voir ``verifier``).
    """
    crm = routes_crm(routes)
    appels = list(appels)
    directs = {r: any(cac.compatible(a, r) for a in appels) for r in crm}
    manquantes = []
    for r in crm:
        if len(r) > 3 and r[3] in SANS_ECRAN_PAR_CONSTRUCTION:
            continue
        if directs[r]:
            continue
        if r[-1] == cac.PK:
            prefixe = r[:-1]
            if any(ok for autre, ok in directs.items()
                   if autre[:len(prefixe)] == prefixe and ok):
                continue
        manquantes.append(r)
    return manquantes


def verifier(routes, appels, a_corriger=None):
    """-> (violations, perimees) : routes nouvelles sans appelant ni raison ;
    entrees A_CORRIGER devenues inutiles."""
    a_corriger = A_CORRIGER if a_corriger is None else a_corriger
    sans = routes_sans_appelant(routes, appels)
    cles = {_cle(r): r for r in sans}
    violations = [r for k, r in cles.items() if k not in a_corriger]
    perimees = sorted(k for k in a_corriger if k not in cles)
    return violations, perimees


def mesurer():
    backend = cac.BackendRoutes()
    backend.build()
    extracteur = cac.FrontendCalls(cac.frontend_files())
    extracteur.collect()
    appels = set()
    for _rel, _line, raw, mount in extracteur.calls:
        n = cac.normalise_call(raw, mount)
        if n:
            appels.add(tuple(n))
    appels |= appels_e2e()
    return backend.routes, appels


def main(argv=None) -> int:
    routes, appels = mesurer()
    violations, perimees = verifier(routes, appels)
    crm = routes_crm(routes)
    if not crm:
        print("check_routes_appelees : AUCUNE route crm resolue - extracteur casse.")
        return 1
    code = 0
    if violations:
        code = 1
        print(f"check_routes_appelees : {len(violations)} route(s) crm SANS appelant "
              "(ni frontend/src, ni e2e, ni exemption motivee) :")
        for r in violations:
            print(f"  /{'/'.join(r)}")
        print("\nCorriger : brancher un appelant (frontend/src/api/*.js), ou retirer "
              "la route et son calcul. A_CORRIGER n'est pas un moyen de passer.")
    if perimees:
        code = 1
        print(f"check_routes_appelees : {len(perimees)} entree(s) A_CORRIGER perimee(s) "
              "(la route a un appelant ou n'existe plus) - les retirer :")
        for k in perimees:
            print(f"  {k}")
    if code == 0:
        print(f"check_routes_appelees : OK - {len(crm)} routes crm, "
              f"{len(A_CORRIGER)} dette(s) A_CORRIGER motivee(s).")
    return code


if __name__ == "__main__":
    sys.exit(main())
