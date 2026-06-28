"""FG5 — Utilitaires de calendrier ouvré, par société.

Trois helpers publics :
  - is_jour_ouvre(date, company)         → bool
  - prochain_jour_ouvre(date, company)   → date (premier jour ouvré ≥ date)
  - ajouter_jours_ouvres(date, n, company) → date après n jours ouvrés

Un « jour ouvré » = un jour de la semaine marqué comme ouvré dans la
`WorkingHoursConfig` de la société ET non présent dans sa table `Holiday`
(qu'il soit récurrent annuel ou une date exacte pour l'année courante).

ADDITIF : sans `WorkingHoursConfig` pour la société, on tombe sur le défaut
Lundi–Vendredi (bits 0–4, valeur 31). Sans aucune `Holiday`, aucun jour n'est
bloqué par les fériés.

PERFORMANCE : les deux ensembles (config + fériés de l'année) sont chargés
une seule fois par appel de haut niveau et propagés. Un appel isolé à
`is_jour_ouvre` charge toujours les données fraîches (usage direct simple).
"""
from __future__ import annotations

import datetime
import logging

logger = logging.getLogger(__name__)

# Bitmask défaut : Lundi–Vendredi (bits 0–4).
_DEFAULT_WORKING_DAYS = 0b00011111  # 31

# Garde-fou contre une boucle infinie (ex. société avec 0 jours ouvrés).
_MAX_ITERATIONS = 1000


# ---------------------------------------------------------------------------
# Chargement des données (lazy, par appel)
# ---------------------------------------------------------------------------

def _load_working_days(company) -> int:
    """Charge le bitmask de jours ouvrés de la société. Défaut : Lun–Ven."""
    try:
        from .models import WorkingHoursConfig
        cfg = WorkingHoursConfig.objects.filter(company=company).first()
        if cfg is not None:
            return cfg.working_days
    except Exception as exc:  # pragma: no cover - défensif
        logger.warning('calendar_utils: chargement WorkingHoursConfig échoué : %s', exc)
    return _DEFAULT_WORKING_DAYS


def _load_holidays_for_year(company, year: int) -> set[tuple[int, int]]:
    """Retourne l'ensemble des (mois, jour) fériés pour la société et l'année.

    Pour les jours récurrents annuels, on compare (mois, jour).
    Pour les jours non récurrents, on compare (mois, jour) uniquement si
    l'année stockée correspond à `year`.
    """
    try:
        from .models import Holiday
        qs = Holiday.objects.filter(company=company)
        result: set[tuple[int, int]] = set()
        for h in qs:
            if h.recurrent_annuel:
                result.add((h.date.month, h.date.day))
            elif h.date.year == year:
                result.add((h.date.month, h.date.day))
        return result
    except Exception as exc:  # pragma: no cover - défensif
        logger.warning('calendar_utils: chargement Holiday échoué : %s', exc)
        return set()


# ---------------------------------------------------------------------------
# Helpers internes
# ---------------------------------------------------------------------------

def _is_holiday(d: datetime.date, holidays: set[tuple[int, int]]) -> bool:
    return (d.month, d.day) in holidays


def _is_working_day_raw(
        d: datetime.date,
        working_days: int,
        holidays: set[tuple[int, int]]) -> bool:
    """Vrai si `d` est ouvré selon le bitmask ET non férié."""
    weekday = d.weekday()  # 0=Lun … 6=Dim
    if not (working_days & (1 << weekday)):
        return False
    return not _is_holiday(d, holidays)


# ---------------------------------------------------------------------------
# API publique
# ---------------------------------------------------------------------------

def is_jour_ouvre(d: datetime.date, company) -> bool:
    """Renvoie True si `d` est un jour ouvré pour `company`.

    Tient compte du bitmask de jours de travail ET des jours fériés (fixes +
    annuels) de la société. Sans configuration : Lun–Ven, aucun férié.
    """
    working_days = _load_working_days(company)
    holidays = _load_holidays_for_year(company, d.year)
    return _is_working_day_raw(d, working_days, holidays)


def prochain_jour_ouvre(d: datetime.date, company) -> datetime.date:
    """Renvoie le premier jour ouvré >= `d` pour `company`.

    Si `d` est déjà ouvré, le renvoie tel quel. Sinon avance d'un jour à la
    fois. Sécurisé contre une configuration sans aucun jour ouvré (retourne
    `d` + _MAX_ITERATIONS au pire).
    """
    working_days = _load_working_days(company)
    # Charge les fériés pour l'année de départ + l'année suivante (si on
    # franchit le 31/12).
    holidays: set[tuple[int, int]] = set()
    holidays |= _load_holidays_for_year(company, d.year)
    holidays |= _load_holidays_for_year(company, d.year + 1)

    current = d
    for _ in range(_MAX_ITERATIONS):
        if _is_working_day_raw(current, working_days, holidays):
            return current
        current += datetime.timedelta(days=1)
    # Garde-fou : ne devrait jamais se produire avec une config valide.
    logger.warning(
        'prochain_jour_ouvre: aucun jour ouvré trouvé pour %s après %d itérations.',
        company, _MAX_ITERATIONS)
    return current


def ajouter_jours_ouvres(d: datetime.date, n: int, company) -> datetime.date:
    """Renvoie la date après avoir avancé de `n` jours ouvrés depuis `d`.

    `d` lui-même N'est PAS compté (on part du lendemain si n > 0). Si n = 0,
    renvoie `d` (comportement identique à prochain_jour_ouvre).
    Si n < 0, renvoie `d` sans modifier (cas non supporté, comportement sûr).
    Sécurisé contre l'absence de jours ouvrés (_MAX_ITERATIONS).
    """
    if n < 0:
        logger.warning('ajouter_jours_ouvres: n < 0 (%d) ignoré.', n)
        return d
    if n == 0:
        return prochain_jour_ouvre(d, company)

    working_days = _load_working_days(company)
    # Pré-charge les fériés pour une plage raisonnable (année de `d` + 2 ans).
    holidays: set[tuple[int, int]] = set()
    for yr in range(d.year, d.year + 3):
        holidays |= _load_holidays_for_year(company, yr)

    current = d
    remaining = n
    iterations = 0
    while remaining > 0 and iterations < _MAX_ITERATIONS:
        current += datetime.timedelta(days=1)
        iterations += 1
        if _is_working_day_raw(current, working_days, holidays):
            remaining -= 1

    if remaining > 0:
        logger.warning(
            'ajouter_jours_ouvres: %d jours restants après %d itérations.',
            remaining, _MAX_ITERATIONS)

    return current
