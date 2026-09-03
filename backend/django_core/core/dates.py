"""CRX26 — LA date « aujourd'hui » du métier : Africa/Casablanca.

POURQUOI CE MODULE EXISTE
-------------------------
``settings.TIME_ZONE`` vaut ``'UTC'`` (et ``USE_TZ = True``). Or
``django.utils.timezone.localdate()`` rend la date dans le fuseau ACTIF, donc
**la date UTC** — pas la date marocaine. Africa/Casablanca est à UTC+1 la
majeure partie de l'année : entre 23 h 00 et minuit UTC, il est DÉJÀ demain à
Casablanca.

Toute la journée d'un commercial marocain se joue sur cette date : une relance
« due aujourd'hui », un rappel « en retard », un signal d'intérêt « déjà noté
aujourd'hui », le point de départ d'une cadence de relance. Une heure par jour,
ces réponses étaient FAUSSES d'un jour entier — une relance créée à 23 h 30 le
lundi soir partait avec une échéance calculée depuis dimanche.

Ce module est le point de passage UNIQUE. ``core`` reste une couche de
FONDATION : il n'importe aucune app métier (contrat import-linter
``core-foundation-is-a-base-layer``).

API
---
* ``maintenant_local(maintenant=None)`` — l'instant courant converti en heure
  locale marocaine (datetime AWARE).
* ``aujourd_hui_local(maintenant=None)`` — la date du jour à Casablanca.

Les deux acceptent un ``maintenant`` explicite (datetime aware) : c'est ainsi
qu'un test fige l'instant, sans jamais monkeypatcher l'horloge.
"""
from __future__ import annotations

import datetime as _dt
from zoneinfo import ZoneInfo

from django.utils import timezone

#: Fuseau MÉTIER de TAQINOR — celui du terrain, jamais celui du serveur.
FUSEAU_METIER = 'Africa/Casablanca'

#: Instance réutilisable (``ZoneInfo`` est mis en cache par la stdlib, mais un
#: nom unique évite qu'un appelant réinvente la chaîne).
TZ_METIER = ZoneInfo(FUSEAU_METIER)


def maintenant_local(maintenant: _dt.datetime | None = None) -> _dt.datetime:
    """Instant courant EN HEURE LOCALE marocaine (datetime aware).

    ``maintenant`` (optionnel) permet de fournir un instant explicite — un
    datetime NAÏF est interprété dans le fuseau actif de Django avant
    conversion, jamais laissé naïf.
    """
    if maintenant is None:
        maintenant = timezone.now()
    elif timezone.is_naive(maintenant):
        maintenant = timezone.make_aware(maintenant)
    return maintenant.astimezone(TZ_METIER)


def aujourd_hui_local(maintenant: _dt.datetime | None = None) -> _dt.date:
    """Date du jour À CASABLANCA — le « aujourd'hui » du métier.

    Remplace ``timezone.localdate()`` / ``timezone.now().date()`` partout où la
    date sert une décision MÉTIER (échéance, retard, fenêtre du jour, départ
    d'une cadence). Un horodatage technique (journal, audit) garde ``now()``.
    """
    return maintenant_local(maintenant).date()
