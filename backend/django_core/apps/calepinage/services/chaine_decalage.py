"""ACAL723 — les trois aides du DÉCALAGE HORAIRE de la chaîne de pertes.

Extraites de ``chaine_pertes.py`` (fichier-mur : il ne grossit pas) : lire
l'horodatage d'un point, la part saisonnière du décalage d'un fuseau et
ré-étiqueter un point. Aucune valeur mesurée n'est jamais touchée.
"""
from __future__ import annotations

import datetime
import logging

from apps.calepinage.services import etapes as _etapes


def moment_du_point(point):
    """L'horodatage d'un point, ou ``None`` s'il n'en porte pas de lisible."""
    if not isinstance(point, dict):
        return None
    try:
        return datetime.datetime(
            int(point['annee']), int(point['mois']), int(point['jour']),
            int(point['heure']), tzinfo=datetime.timezone.utc)
    except (KeyError, TypeError, ValueError):
        return None


def part_saisonniere_minutes(fuseau, moment):
    """La part SAISONNIÈRE du décalage, lue dans ``zoneinfo`` à cette date.

    C'est ``utcoffset - standard``, c'est-à-dire exactement ce que la base de
    fuseaux appelle ``dst()`` : au Maroc, ``0`` hors Ramadan et ``-60`` min
    pendant (la base modélise le retour à UTC+0 comme un décalage saisonnier
    NÉGATIF). Aucune valeur n'est écrite ici : tout vient de la base.
    """
    if not fuseau or moment is None:
        return None
    try:
        from zoneinfo import ZoneInfo

        saison = moment.replace(tzinfo=ZoneInfo(fuseau)).dst()
    except Exception:       # pragma: no cover - dépend de la base installée
        logging.getLogger(__name__).warning(
            'chaine_decalage.part_saisonniere_minutes : ignorée',
            exc_info=True)
        return None
    if saison is None:
        return None
    return int(saison.total_seconds() // 60)


def point_decale(point, moment, minutes, decalage_utc=None):
    """Une COPIE du point ré-étiquetée — aucune valeur mesurée n'est touchée.

    Ré-indexer, c'est CHANGER L'ÉTIQUETTE d'une heure, jamais sa mesure :
    l'irradiance, la température et le vent du point restent exactement ceux
    que PVGIS a servis. ACAL131 — ``decalage_utc`` (minutes) est posé sur le
    point (``etapes.CLE_DECALAGE_POINT``) : l'heure LÉGALE ré-étiquetée moins
    ce décalage est son instant UTC.
    """
    copie = dict(point)
    if decalage_utc is not None:
        copie[_etapes.CLE_DECALAGE_POINT] = decalage_utc
    if not minutes:
        return copie
    cible = moment + datetime.timedelta(minutes=minutes)
    copie['annee'] = cible.year
    copie['mois'] = cible.month
    copie['jour'] = cible.day
    copie['heure'] = cible.hour
    return copie
