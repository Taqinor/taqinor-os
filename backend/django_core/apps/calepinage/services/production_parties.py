"""ACAL843 — ``production.parties`` : l'EXISTANT et l'AJOUTÉ côte à côte.

Publié seulement quand un pan du document est ``existant`` ; sans pan
existant la clé est ABSENTE (le résultat est octet pour octet celui d'avant).
Ce bloc REGROUPE ``production.par_pan`` : il n'est la source d'aucun chiffre
(``production.total`` reste celui de la chaîne, pans existants comptés neufs).

``p50_kwh_avec_age`` d'un pan = son P50 × f(âge + 1) ÷ f(1) : le facteur est
celui du vieillissement (ACAL842) — la ligne 1 de ``tableau_pluriannuel`` d'UN
pan, jamais un second calcul de dégradation. Un pan neuf vaut son P50 ; un pan
existant sans année de mise en service, ou sans fiche de dégradation, n'a pas
de valeur (``None``) et la mention le dit — aucune dégradation supposée.
"""
from __future__ import annotations

import datetime

from .etapes.vieillissement import tableau_pluriannuel

MENTION = ("Les pans existants sont comptés neufs dans le total de la chaîne ; "
           "« avec âge » applique la dégradation de la fiche du module à "
           "l'année de mise en service saisie de chaque pan existant.")
MENTION_SANS_AGE = (" Valeur « avec âge » absente : année de mise en service "
                    "ou fiche de dégradation non renseignée.")


def _somme(valeurs):
    """La somme arrondie, ``None`` si une valeur manque (jamais un 0)."""
    if any(not isinstance(v, (int, float)) for v in valeurs):
        return None
    return round(sum(valeurs), 3)


def _avec_age(p50, age, contexte):
    """P50 × f(âge + 1) ÷ f(1) : neuf = P50 ; âge ou fiche absents = ``None``."""
    if not isinstance(p50, (int, float)):
        return None
    if age == 0:
        return round(p50, 3)
    if age is None:
        return None
    bloc = tableau_pluriannuel(p50, contexte,
                               parts=[{'p50_kwh': p50, 'age_ans': age}])
    return None if bloc['motif_omission'] else bloc['annees'][0]['p50_kwh']


def _partie(lignes, ages, contexte):
    avec_age = [_avec_age(ligne.get('p50_kwh'), age, contexte)
                for ligne, age in zip(lignes, ages)]
    return {'pans': [ligne.get('pan') for ligne in lignes],
            'kwc': _somme([ligne.get('kwc') for ligne in lignes]),
            'p50_kwh_neuf': _somme([ligne.get('p50_kwh') for ligne in lignes]),
            'p50_kwh_avec_age': _somme(avec_age)}


def parties_de_la_production(document, par_pan, contexte, maintenant=None):
    """``{existant, ajoute, total, mention}`` ou ``None`` sans pan existant."""
    annee = (maintenant or datetime.datetime.now(datetime.timezone.utc)).year
    existants = {}
    for zone in (document or {}).get('zones') or []:
        if isinstance(zone, dict) and zone.get('existant'):
            mise = zone.get('anneeMiseEnService')
            age = (annee - mise if isinstance(mise, int)
                   and not isinstance(mise, bool) else None)
            for repere in (zone.get('label'), zone.get('id')):
                if repere:
                    existants[str(repere)] = age
    lignes = [ligne for ligne in par_pan or () if isinstance(ligne, dict)]
    ceux_la = [ligne for ligne in lignes if str(ligne.get('pan')) in existants]
    if not ceux_la:
        return None
    ajoutes = [ligne for ligne in lignes if str(ligne.get('pan')) not in existants]
    existant = _partie(ceux_la, [existants[str(ligne['pan'])]
                                 for ligne in ceux_la], contexte)
    ajoute = _partie(ajoutes, [0] * len(ajoutes), contexte)
    total = {cle: _somme([existant[cle], ajoute[cle]])
             for cle in ('kwc', 'p50_kwh_neuf', 'p50_kwh_avec_age')}
    manque = existant['p50_kwh_avec_age'] is None
    return {'existant': existant, 'ajoute': ajoute, 'total': total,
            'mention': MENTION + (MENTION_SANS_AGE if manque else '')}
