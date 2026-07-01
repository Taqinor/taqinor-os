"""DC26 (FG5) — UN référentiel calendrier : jours ouvrés + fériés marocains.

Couche de FONDATION partagée, GÉNÉRIQUE et sans état métier : fournit l'unique
source de vérité des jours ouvrés au Maroc et les helpers consommés par les
congés, la relance commerciale, la maintenance, le dispatch terrain et la paie.
``core`` n'importe AUCUNE app métier (contrat import-linter
``core-foundation-is-a-base-layer``) — ces helpers ne dépendent que de la
bibliothèque standard.

Modèle de jours ouvrés
----------------------

* Semaine ouvrée : lundi → vendredi. Samedi et dimanche = week-end (norme du
  secteur public/tertiaire marocain). ``WEEKEND_DAYS`` est ajustable par
  l'appelant si un métier travaille le samedi.
* Jours fériés FIXES (grégoriens) marocains : codés en dur ci-dessous, valables
  chaque année.
* Jours fériés MOBILES (calendrier hégirien : Aïd al-Fitr, Aïd al-Adha, Nouvel
  An hégirien, Aïd al-Mawlid) : NON déductibles d'une règle grégorienne fixe.
  Ils sont fournis par année via ``MOROCCAN_MOVABLE_HOLIDAYS`` (jeu de départ
  vérifiable) et peuvent être enrichis par l'appelant (paramètre ``extra_holidays``
  des helpers) sans modifier ce module — on ne devine JAMAIS une date hégirienne.

API
---

* ``is_weekend(d)`` / ``is_holiday(d, extra_holidays=None)`` /
  ``is_working_day(d, extra_holidays=None)``.
* ``next_working_day(d, extra_holidays=None)`` — premier jour ouvré STRICTEMENT
  après ``d``.
* ``add_working_days(d, n, extra_holidays=None)`` — décale de ``n`` jours ouvrés
  (n<0 = vers le passé).
* ``count_working_days(start, end, extra_holidays=None)`` — nombre de jours
  ouvrés dans l'intervalle INCLUSIF ``[start, end]``.
* ``moroccan_holidays(year, extra_holidays=None)`` — set des fériés d'une année.
"""
from __future__ import annotations

import datetime as _dt

# Samedi (5) et dimanche (6) — week-end par défaut (Python weekday: lundi=0).
WEEKEND_DAYS = frozenset({5, 6})

# Jours fériés FIXES grégoriens marocains : {(mois, jour): libellé}.
MOROCCAN_FIXED_HOLIDAYS = {
    (1, 1): "Nouvel An",
    (1, 11): "Manifeste de l'Indépendance",
    (5, 1): "Fête du Travail",
    (7, 30): "Fête du Trône",
    (8, 14): "Oued Ed-Dahab",
    (8, 20): "Révolution du Roi et du Peuple",
    (8, 21): "Fête de la Jeunesse",
    (11, 6): "Marche Verte",
    (11, 18): "Fête de l'Indépendance",
}

# Jours fériés MOBILES (hégiriens) — date observée au Maroc, fournie par année.
# Jeu de départ ; à enrichir via ``extra_holidays`` plutôt que de deviner une
# date lunaire. (Dates indicatives, à confirmer chaque année auprès du calendrier
# officiel.)
MOROCCAN_MOVABLE_HOLIDAYS = {
    2026: {
        _dt.date(2026, 3, 20): "Aïd al-Fitr",
        _dt.date(2026, 3, 21): "Aïd al-Fitr (2e jour)",
        _dt.date(2026, 5, 27): "Aïd al-Adha",
        _dt.date(2026, 5, 28): "Aïd al-Adha (2e jour)",
        _dt.date(2026, 6, 17): "Nouvel An hégirien",
        _dt.date(2026, 8, 26): "Aïd al-Mawlid",
    },
}


def _as_date(d):
    """Normalise un ``datetime`` en ``date`` (laisse un ``date`` intact)."""
    if isinstance(d, _dt.datetime):
        return d.date()
    if isinstance(d, _dt.date):
        return d
    raise TypeError("Une date (ou datetime) est attendue.")


def moroccan_holidays(year, extra_holidays=None):
    """Set des jours fériés marocains pour une année (fixes + mobiles connus).

    ``extra_holidays`` : itérable optionnel de ``date`` à ajouter (fériés
    mobiles d'une année non encore codée, ou fériés locaux).
    """
    days = {
        _dt.date(year, mois, jour)
        for (mois, jour) in MOROCCAN_FIXED_HOLIDAYS
    }
    days |= set(MOROCCAN_MOVABLE_HOLIDAYS.get(year, {}).keys())
    if extra_holidays:
        days |= {_as_date(d) for d in extra_holidays}
    return days


def is_weekend(d):
    """Vrai si ``d`` tombe un jour de week-end (samedi/dimanche par défaut)."""
    return _as_date(d).weekday() in WEEKEND_DAYS


def is_holiday(d, extra_holidays=None):
    """Vrai si ``d`` est un jour férié marocain (fixe ou mobile connu)."""
    d = _as_date(d)
    return d in moroccan_holidays(d.year, extra_holidays)


def is_working_day(d, extra_holidays=None):
    """Vrai si ``d`` est ouvré (ni week-end, ni férié)."""
    d = _as_date(d)
    return not is_weekend(d) and not is_holiday(d, extra_holidays)


def next_working_day(d, extra_holidays=None):
    """Premier jour ouvré STRICTEMENT après ``d``."""
    d = _as_date(d)
    candidate = d + _dt.timedelta(days=1)
    while not is_working_day(candidate, extra_holidays):
        candidate += _dt.timedelta(days=1)
    return candidate


def previous_working_day(d, extra_holidays=None):
    """Premier jour ouvré STRICTEMENT avant ``d``."""
    d = _as_date(d)
    candidate = d - _dt.timedelta(days=1)
    while not is_working_day(candidate, extra_holidays):
        candidate -= _dt.timedelta(days=1)
    return candidate


def add_working_days(d, n, extra_holidays=None):
    """Décale ``d`` de ``n`` jours ouvrés (n négatif = vers le passé).

    ``n == 0`` renvoie ``d`` tel quel (même si non ouvré) — pas de saut implicite.
    """
    d = _as_date(d)
    if n == 0:
        return d
    step = 1 if n > 0 else -1
    remaining = abs(int(n))
    current = d
    while remaining > 0:
        current += _dt.timedelta(days=step)
        if is_working_day(current, extra_holidays):
            remaining -= 1
    return current


def count_working_days(start, end, extra_holidays=None):
    """Nombre de jours ouvrés dans l'intervalle INCLUSIF ``[start, end]``.

    Si ``end < start``, renvoie 0.
    """
    start = _as_date(start)
    end = _as_date(end)
    if end < start:
        return 0
    count = 0
    current = start
    while current <= end:
        if is_working_day(current, extra_holidays):
            count += 1
        current += _dt.timedelta(days=1)
    return count
