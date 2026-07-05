"""Selectors de lecture cross-app pour ``apps.notifications`` (XMKT7).

Point d'entrée unique pour les autres apps qui ont besoin de savoir si un
moment donné tombe dans une « fenêtre de silence » d'envoi marketing — jamais
d'import direct de ``notifications.models`` (WorkingHoursConfig/Holiday)
ailleurs. Réutilise ``calendar_utils.is_jour_ouvre`` (jours fériés + jours
ouvrés de la société) et ajoute une fenêtre horaire nocturne fixe (08h–20h)
puisque ``WorkingHoursConfig`` ne porte pas d'heures de coupure configurables
aujourd'hui — ADDITIF, sans configuration le comportement par défaut n'exclut
QUE la nuit stricte + les jours fériés/non-ouvrés.
"""
from __future__ import annotations

import datetime

from . import calendar_utils

# Fenêtre "jour" par défaut (heure locale serveur) : 08h00-20h00 inclus.
_HEURE_DEBUT_JOUR = 8
_HEURE_FIN_JOUR = 20


def est_hors_fenetre_silence(moment, company) -> bool:
    """Renvoie True si ``moment`` (datetime) tombe DANS la fenêtre de silence
    (nuit ou jour férié/non-ouvré) — c-à-d qu'un SMS/WhatsApp ne DOIT PAS
    partir à ce moment pour ``company``.

    ``moment`` naïf ou aware, seule l'heure locale (``moment.hour``) et la
    date (``moment.date()``) comptent.
    """
    if moment is None:
        return False
    d = moment.date() if isinstance(moment, datetime.datetime) else moment
    if not calendar_utils.is_jour_ouvre(d, company):
        return True
    if isinstance(moment, datetime.datetime):
        heure = moment.hour
        if heure < _HEURE_DEBUT_JOUR or heure >= _HEURE_FIN_JOUR:
            return True
    return False
