"""ACAL722 — les trois aides de la RÉSOLUTION publiée par la chaîne de pertes.

Extraites de ``chaine_pertes.py`` (fichier-mur : il ne grossit pas) : elles
disent le pas réglé par la société, le pas propre de la courbe de charge et la
phrase qui explique ce qui se passe entre les deux. Aucun calcul d'énergie.
"""
from __future__ import annotations

from apps.calepinage.services import etapes as _etapes

from .valeurs import nombre as _flottant

#: La clé sous laquelle l'appelant (CALX5) POSE la courbe de charge du site,
#: à SON pas : ``{pas_minutes, points}``. La chaîne ne la transforme jamais —
#: elle publie seulement les deux pas, côte à côte.
CLE_CHARGE = 'charge'


def resolution_reglee(contexte):
    """Le pas de simulation RÉGLÉ par la société, ou ``None``."""
    saisi = _etapes.reglage(contexte, 'resolution_minutes')
    if saisi is None:
        return None
    valeur = _flottant(saisi.get('valeur'))
    return None if valeur is None else int(valeur)


def pas_de_la_charge(contexte):
    """Le pas PROPRE de la courbe de charge, publié à côté — jamais fondu."""
    charge = contexte.get(CLE_CHARGE)
    if not isinstance(charge, dict):
        return None
    valeur = _flottant(charge.get('pas_minutes'))
    return None if valeur is None else int(valeur)


def note_de_resolution(mesure, pas_charge):
    """La phrase française qui DIT ce qui se passe entre les deux pas."""
    if mesure is None:
        return ('Le pas de la série météo n\'a pas pu être mesuré : aucune '
                'résolution n\'est annoncée, et aucune interpolation n\'est '
                'faite.')
    note = (f'La météo est au pas de {mesure} min (PVGIS sert une ligne par '
            'heure) et aucune interpolation infra-horaire n\'est faite : '
            'entre deux heures, l\'irradiance n\'est jamais lissée.')
    if pas_charge is None or pas_charge >= mesure:
        return note
    return note + (
        f' La courbe de charge, elle, garde SON pas de {pas_charge} min : '
        'elle n\'est pas ramenée à l\'heure, et la météo y est maintenue en '
        f'ESCALIER — la même valeur pour les {mesure // pas_charge} pas '
        'd\'une même heure.')
