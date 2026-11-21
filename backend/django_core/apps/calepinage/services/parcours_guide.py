"""ACAL392 — l'ÉTAT du parcours guidé de l'atelier, calculé à chaque lecture.

Contrat ``contract_samples/calepinage_parcours_guide.json`` (ACAL386) : cinq
étapes (toit, panneaux, electrique, resultats, documents) et « ce qui manque »
regroupé par (``code``, ``cible``) avec ``nombre`` = lignes fusionnées.

LECTURE PURE : ni statut, ni version, ni écriture. Les ``avertissements`` de
``selectors.resultat_servi`` restent bruts pour leurs autres lecteurs ; ce
module ne fait que les REGROUPER d'après une table de motifs connus. Un motif
inconnu est gardé tel quel (code ``divers``, étape ``resultats``, gravité
``info``) — jamais perdu, jamais inventé.
"""
from __future__ import annotations

import re

__all__ = ['ETAPES', 'MOTIFS', 'etat_du_parcours']

ETAPES = ('toit', 'panneaux', 'electrique', 'resultats', 'documents')

#: Table des motifs connus : (code, regex insensible à la casse, étape,
#: onglet, champ, gravité). Premier motif qui correspond gagne. ``reglages`` =
#: écran /calepinage/reglages (réglage société).
MOTIFS = (
    ('norme_absente', r'aucune norme (?:électrique|electrique)',
     'electrique', 'reglages', 'norme', 'a_regler'),
    ('simulation_perimee', r'simulation périmée',
     'resultats', 'production', '', 'a_regler'),
    ('production_non_simulee', r'production non simulée',
     'resultats', 'production', '', 'a_regler'),
    ('coefficients_non_sources', r'non sourcées?',
     'resultats', 'reglages', '', 'info'),
    ('ratio_dc_ac', r'ratio DC/AC',
     'electrique', 'verdict-electrique', 'ratio_dc_ac', 'a_regler'),
    ('acces_solaire_absent', r'accès solaire',
     'resultats', 'production', '', 'info'),
    ('longueur_chaine', r'longueur de chaîne',
     'electrique', 'verdict-electrique', 'longueur_chaine', 'a_regler'),
)
_COMPILES = tuple((code, re.compile(motif, re.IGNORECASE), etape, onglet,
                   champ, gravite)
                  for code, motif, etape, onglet, champ, gravite in MOTIFS)


def _classer(message):
    for code, motif, etape, onglet, champ, gravite in _COMPILES:
        if motif.search(message):
            return code, etape, onglet, champ, gravite
    return 'divers', 'resultats', 'production', '', 'info'


def _regrouper_manque(avertissements):
    """Les avertissements bruts → ``manque[]`` sans deux lignes de même
    (``code``, ``cible``) ; ``nombre`` = lignes fusionnées. Ordre de première
    apparition ; le message gardé est celui de la première ligne."""
    groupes = {}
    for brut in avertissements or ():
        message = str(brut or '').strip()
        if not message:
            continue
        code, etape, onglet, champ, gravite = _classer(message)
        cle = (code, onglet, champ)
        if cle in groupes:
            groupes[cle]['nombre'] += 1
            continue
        groupes[cle] = {
            'code': code, 'message': message, 'etape': etape,
            'cible': {'onglet': onglet, 'champ': champ},
            'gravite': gravite, 'nombre': 1,
        }
    return list(groupes.values())


def _etapes_du_parcours(*, toit_fait, modules, verdict, simule, perime,
                        devis_lie):
    """Les cinq états, d'après des faits déjà lus (fonction PURE)."""
    panneaux_faits = bool(modules) and modules > 0
    panneaux = 'fait' if (toit_fait and panneaux_faits) else 'a_faire'
    if not panneaux_faits:
        electrique = 'a_faire'
    elif verdict in ('conforme', 'alerte'):
        electrique = 'fait'
    elif verdict == 'bloquant':
        electrique = 'bloque'
    else:
        electrique = 'en_cours'
    if perime:
        resultats = 'en_cours'
    elif simule:
        resultats = 'fait'
    else:
        resultats = 'a_faire'
    if devis_lie:
        documents = 'fait'
    else:
        documents = 'en_cours' if resultats == 'fait' else 'a_faire'
    etats = {'toit': 'fait' if toit_fait else 'a_faire', 'panneaux': panneaux,
             'electrique': electrique, 'resultats': resultats,
             'documents': documents}
    return [{'cle': cle, 'etat': etats[cle]} for cle in ETAPES]


def etat_du_parcours(calepinage):
    """``{etapes, manque}`` — la forme exacte du contrat ACAL386."""
    from ..selectors import resultat_servi
    from .electrique import TemperaturesInvalides, evaluation_electrique
    from .layout import layout_decrit_une_geometrie

    servi = resultat_servi(calepinage)
    pose = servi.get('pose') if isinstance(servi.get('pose'), dict) else {}
    modules = pose.get('total_modules')
    modules = modules if isinstance(modules, (int, float)) else 0
    verdict = 'indetermine'
    if modules > 0:
        try:
            verdict = evaluation_electrique(calepinage).get(
                'verdict', 'indetermine')
        except TemperaturesInvalides:
            verdict = 'indetermine'
    etapes = _etapes_du_parcours(
        toit_fait=layout_decrit_une_geometrie(
            getattr(calepinage, 'roof_layout', None)),
        modules=modules, verdict=verdict, simule=bool(servi.get('simule')),
        perime=bool(servi.get('simulation_perimee')),
        devis_lie=getattr(calepinage, 'devis_id', None) is not None)
    return {'etapes': etapes,
            'manque': _regrouper_manque(servi.get('avertissements'))}
