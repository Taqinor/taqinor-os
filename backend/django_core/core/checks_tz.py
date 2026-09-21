"""Contrôles système — L'HEURE LÉGALE MAROCAINE, VÉRIFIÉE AU DÉMARRAGE.

LE FAIT. Le Maroc est repassé DÉFINITIVEMENT à l'heure GMT (UTC+0) dans la
nuit du samedi 19 au dimanche 20 septembre 2026 (02:00 → 01:00) : décret
n° 2.26.530 relatif à l'heure légale (Conseil de gouvernement du 25/06/2026,
Bulletin officiel n° 7521 du 29/06/2026), qui abroge le décret 2.18.855 de
2018 — UTC+1 permanent, avec retour à UTC+0 pendant le Ramadan. Il n'y a plus
AUCUNE bascule saisonnière ni Ramadan.

POURQUOI UN CONTRÔLE, ET PAS UNE CONSTANTE. L'ERP ne code aucun décalage : il
nomme son fuseau (``TIME_ZONE = 'Africa/Casablanca'``, ``CELERY_TIMEZONE``
idem, ``Intl.DateTimeFormat(..., timeZone: 'Africa/Casablanca')`` côté page) et
laisse la base de fuseaux trancher. C'est la bonne façon de faire — mais elle
déplace le risque : une base de fuseaux PÉRIMÉE rend un code parfaitement juste
faux d'une heure pleine, partout et en silence (relances envoyées une heure
trop tôt, jours de regroupement décalés autour de minuit, courbes de production
décalées d'un cran). Rien ne plante, rien n'apparaît dans un journal.

Ce module rend ce silence impossible :

* **ERREUR BLOQUANTE** — la base de fuseaux de PYTHON ne connaît pas le décret.
  Un contrôle système de niveau ``Error`` fait échouer toute commande
  ``manage.py`` : le service ne démarre pas avec une heure fausse. Les images
  posent ``PYTHONTZPATH=""`` (zoneinfo ne lit QUE le paquet pip ``tzdata``,
  épinglé à 2026.4) précisément pour que ce contrôle soit vert par
  construction ; il attrape l'image reconstruite sans le pin, l'hôte de
  développement resté à une vieille ``tzdata``, et la régression future.

* **AVERTISSEMENT** (jamais bloquant, étiqueté ``database``) — la base de
  fuseaux de POSTGRES ne connaît pas le décret. Postgres a la SIENNE, celle de
  son image (``pgvector/pgvector:pg16``, Debian) : les 62 conversions
  ``Trunc*``/``Extract*`` du dépôt lui délèguent le découpage par jour. Une
  tzdata Postgres périmée décale donc les regroupements autour de minuit sans
  que Python n'y puisse rien. Non bloquant à dessein : couper le service pour
  l'image de la BASE de données serait disproportionné, et le message nomme le
  remède exact.

Le contrôle ``database`` ne s'exécute QUE lorsque Django demande les contrôles
de base de données (``manage.py check --database default``, ``migrate``, et le
lanceur de tests) : ailleurs, ``databases`` vaut ``None`` et la fonction rend
``[]`` sans ouvrir la moindre connexion — même convention que
``django.core.checks.database.check_database_backends``.
"""
from __future__ import annotations

import datetime as _dt
from zoneinfo import ZoneInfo

from django.core.checks import Error, Tags, Warning as CheckWarning, register

#: Le fuseau métier — le même nom que ``settings.TIME_ZONE`` et que
#: ``core.dates.FUSEAU_METIER``, mais sans dépendre de leur valeur : ce module
#: vérifie la BASE DE FUSEAUX, pas le réglage.
FUSEAU_MAROC = 'Africa/Casablanca'

#: L'instant TÉMOIN : le lendemain de la bascule, en plein jour, donc très loin
#: de l'heure de transition (02:00 le 20/09). Aucune ambiguïté possible.
INSTANT_TEMOIN = _dt.datetime(2026, 9, 21, 12, 0, tzinfo=_dt.timezone.utc)

#: Le décalage que le décret 2.26.530 impose à cet instant : ZÉRO.
DECALAGE_ATTENDU = _dt.timedelta(0)

#: La même question, posée à Postgres. ``AT TIME ZONE`` rend un timestamp NU
#: (sans fuseau) : à UTC+0, midi UTC reste midi.
SQL_TEMOIN = (
    "SELECT (TIMESTAMPTZ '2026-09-21 12:00+00' AT TIME ZONE 'Africa/Casablanca')"
)

#: Ce que Postgres doit répondre — un ``datetime`` naïf.
REPONSE_POSTGRES_ATTENDUE = _dt.datetime(2026, 9, 21, 12, 0)

ID_PYTHON_PERIMEE = 'core.E_TZ_MAROC_PYTHON_PERIMEE'
ID_PYTHON_ABSENTE = 'core.E_TZ_MAROC_PYTHON_ABSENTE'
ID_POSTGRES_PERIMEE = 'core.W_TZ_MAROC_POSTGRES_PERIMEE'

#: Répété dans les deux messages : un exploitant qui lit l'un ou l'autre doit
#: pouvoir remonter au texte sans rien chercher.
_SOURCE = ("décret n° 2.26.530 relatif à l'heure légale, Bulletin officiel "
           "n° 7521 du 29/06/2026 — le Maroc est à UTC+0 depuis le "
           '20/09/2026')

_INDICE_PYTHON = (
    "tzdata==2026.4 est épinglé dans backend/django_core/requirements.txt et "
    'backend/fastapi_ia/requirements.txt, et les Dockerfiles posent '
    'PYTHONTZPATH="" pour que zoneinfo ne lise QUE ce paquet-là (la tzdata de '
    "Debian peut être en retard sur IANA). Reconstruisez l'image : "
    'docker compose up -d --build. En développement sans docker : '
    'pip install -U "tzdata==2026.4".')


def decalage_maroc(instant=None):
    """Décalage UTC effectif d'``Africa/Casablanca`` à ``instant``.

    Renvoie un ``timedelta``, ou ``None`` si la base de fuseaux ne connaît pas
    le fuseau (paquet ``tzdata`` absent alors que ``PYTHONTZPATH`` est vide).
    Fonction PURE, sans I/O ni réglage Django : c'est elle que les tests
    interrogent.
    """
    if instant is None:
        instant = INSTANT_TEMOIN
    try:
        fuseau = ZoneInfo(FUSEAU_MAROC)
    except Exception:       # pragma: no cover - dépend de la base installée
        return None
    return instant.astimezone(fuseau).utcoffset()


@register()
def verifier_heure_legale_marocaine(app_configs=None, **kwargs):
    """La base de fuseaux de Python connaît-elle le décret 2.26.530 ?"""
    decalage = decalage_maroc()
    if decalage == DECALAGE_ATTENDU:
        return []

    if decalage is None:
        return [Error(
            "La base de fuseaux horaires ne connaît pas « Africa/Casablanca » "
            ": aucune date ne peut être convertie en heure marocaine. Les "
            'images posent PYTHONTZPATH="" — zoneinfo ne lit donc QUE le '
            "paquet pip tzdata, et il est absent de cet environnement.",
            hint=_INDICE_PYTHON,
            id=ID_PYTHON_ABSENTE)]

    heures = decalage.total_seconds() / 3600.0
    return [Error(
        f"La base de fuseaux horaires de Python est PÉRIMÉE : elle place "
        f"« Africa/Casablanca » à UTC{heures:+.0f} le 21/09/2026, alors que "
        f"l'heure légale y est UTC+0 ({_SOURCE}). Tout l'ERP nomme son fuseau "
        f"au lieu de coder un décalage : avec cette base, les relances, les "
        f"regroupements par jour et les courbes de production seraient tous "
        f"faux d'une heure, en silence.",
        hint=_INDICE_PYTHON,
        id=ID_PYTHON_PERIMEE)]


@register(Tags.database)
def verifier_heure_legale_postgres(app_configs=None, databases=None, **kwargs):
    """La base de fuseaux de POSTGRES connaît-elle le décret 2.26.530 ?

    Rend ``[]`` sans toucher à la base tant que ``databases`` est vide : c'est
    la convention Django des contrôles étiquetés ``database`` (ils ne tournent
    qu'avec ``check --database …``, ``migrate`` ou le lanceur de tests).
    """
    if not databases:
        return []

    from django.db import connections

    avertissements = []
    for alias in databases:
        connexion = connections[alias]
        if connexion.vendor != 'postgresql':
            continue
        try:
            with connexion.cursor() as curseur:
                curseur.execute(SQL_TEMOIN)
                ligne = curseur.fetchone()
        except Exception:   # pragma: no cover - base injoignable : pas notre sujet
            continue
        observe = ligne[0] if ligne else None
        if isinstance(observe, _dt.datetime):
            observe = observe.replace(tzinfo=None)
        if observe == REPONSE_POSTGRES_ATTENDUE:
            continue
        lisible = (observe.isoformat(' ') if isinstance(observe, _dt.datetime)
                   else repr(observe))
        avertissements.append(CheckWarning(
            f"La base de fuseaux de Postgres (« {alias} ») est PÉRIMÉE : "
            f"« 2026-09-21 12:00+00 AT TIME ZONE 'Africa/Casablanca' » rend "
            f"{lisible} au lieu de "
            f"{REPONSE_POSTGRES_ATTENDUE.isoformat(' ')} ({_SOURCE}). Les "
            f"regroupements par jour décalent d'une heure : toutes les "
            f"conversions Trunc*/Extract* du dépôt délèguent le découpage à "
            f"Postgres, pas à Python.",
            hint='Mettez à jour l\'image de la base de données : '
                 '`docker compose pull db && docker compose up -d db` '
                 "(ou reconstruisez l'image de la base). Python, lui, est "
                 'déjà couvert par le pin tzdata des requirements.',
            id=ID_POSTGRES_PERIMEE))
    return avertissements
