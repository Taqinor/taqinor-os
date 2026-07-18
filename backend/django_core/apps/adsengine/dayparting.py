"""ADSDEEP36 — Dayparting : horaire natif Meta OU planification INTERNE.

Meta n'accepte le champ natif ``adset_schedule`` que sur un ad set en BUDGET
LIFETIME (dossier write-surface §1/§7 — un budget quotidien ne le supporte
pas) : pour ces ad sets, on route vers ``meta_client.set_adset_schedule``.
Pour un ad set à budget QUOTIDIEN, aucun natif n'existe : le chemin INTERNE
évalue la grille nous-mêmes et ne fait JAMAIS un adrule Meta auto-exécuté
(dossier §6 — les seules règles Meta natives tolérées sont des
``NOTIFICATION``, jamais un ``PAUSE``/``UNPAUSE`` côté Meta).

INVARIANT PERMANENT (règle #3, vérifié ailleurs par test) : ``meta_client``
n'expose AUCUNE méthode de réactivation — le chemin interne ne peut donc JAMAIS
proposer de « ré-allumer » un ad set, seulement de le mettre en PAUSE (kind
``pause`` existant, ENGFIX5) quand la grille dit « hors fenêtre ». Remettre en
ligne à l'entrée d'une fenêtre reste un geste humain permanent.

Les DEUX chemins partagent la même représentation INTERNE : une grille
heure×jour, 7 entrées (``DAYS``, lundi-first) de 24 valeurs 0/1 (1 = diffusion
autorisée à cette heure). Une entrée par heure ⇒ toute borne est, PAR
CONSTRUCTION, toujours à l'heure pleine (jamais de minutes fractionnaires).
"""
from __future__ import annotations

DAYS = ('mon', 'tue', 'wed', 'thu', 'fri', 'sat', 'sun')
HOURS_PER_DAY = 24

# Index des jours Meta pour ``adset_schedule`` (0=dimanche..6=samedi, dossier
# Marketing API) — DIFFÉRENT de l'ordre interne ``DAYS`` (lundi-first).
_META_DAY_INDEX = {
    'mon': 1, 'tue': 2, 'wed': 3, 'thu': 4, 'fri': 5, 'sat': 6, 'sun': 0,
}


class DaypartingError(ValueError):
    """Grille invalide (jour manquant, ligne de mauvaise longueur…)."""


def empty_grid(*, allowed=True):
    """Grille neuve : toutes les heures ALLOUÉES (``allowed=True``, le défaut —
    partir d'une diffusion ouverte 24/7 et RESTREINDRE) ou toutes BLOQUÉES."""
    value = 1 if allowed else 0
    return {day: [value] * HOURS_PER_DAY for day in DAYS}


def validate_grid(grid):
    """Une grille valide = un dict portant EXACTEMENT les 7 clés ``DAYS``,
    chacune une liste/tuple de 24 valeurs. Lève ``DaypartingError`` sinon —
    jamais un ``IndexError``/``KeyError`` opaque plus loin."""
    if not isinstance(grid, dict):
        raise DaypartingError("La grille doit être un dict {jour: [24 valeurs]}.")
    for day in DAYS:
        row = grid.get(day)
        if not isinstance(row, (list, tuple)) or len(row) != HOURS_PER_DAY:
            raise DaypartingError(
                f"Jour « {day} » : {HOURS_PER_DAY} valeurs (une par heure) "
                "attendues.")
    return True


def to_native_adset_schedule(grid):
    """ADSDEEP36 — Convertit la grille en ``adset_schedule`` natif Meta : fusionne
    les heures ALLOUÉES consécutives d'un même jour en UN seul bloc (moins de
    blocs, payload plus petit). Chaque bloc est BORNÉ À L'HEURE PLEINE
    (``start_minute``/``end_minute`` multiples de 60 — garanti par construction,
    une grille n'ayant qu'une entrée PAR HEURE)."""
    validate_grid(grid)
    blocks = []
    for day in DAYS:
        row = list(grid[day])
        h = 0
        while h < HOURS_PER_DAY:
            if row[h]:
                start = h
                while h < HOURS_PER_DAY and row[h]:
                    h += 1
                blocks.append({
                    'days': [_META_DAY_INDEX[day]],
                    'start_minute': start * 60,
                    'end_minute': h * 60,
                    'timezone_type': 'USER',
                })
            else:
                h += 1
    return blocks


def internal_pause_needed(grid, *, now, is_currently_paused):
    """ADSDEEP36 — Chemin INTERNE (ad set à budget QUOTIDIEN) : vrai si ``now``
    tombe HORS de la fenêtre allouée de la grille ET que l'ad set n'est pas
    DÉJÀ en pause (jamais proposer une pause redondante). Ne dit RIEN sur la
    ré-activation à l'entrée d'une fenêtre — aucune méthode ne l'exécute
    (invariant permanent règle #3), remettre en ligne reste un geste humain."""
    validate_grid(grid)
    if is_currently_paused:
        return False
    day = DAYS[now.weekday()]
    allowed = bool(grid[day][now.hour])
    return not allowed
