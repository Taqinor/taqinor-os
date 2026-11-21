"""CALX16 — la chaîne la plus faible en ombrage, désignée par comparaison.

Extrait tel quel de ``services/electrique.py`` (ACAL646 : le fichier dépasse
4 000 lignes et ne grossit pas) ; ``electrique`` ré-importe ces noms, ses
lecteurs et ses tests continuent de les lire par lui.
"""
from __future__ import annotations

#: Comment la chaîne est désignée. Une COMPARAISON, pas un seuil : le plus mal
#: exposé des modules mesurés du toit, rien de plus.
METHODE_CHAINE_FAIBLE = (
    'Chaîne qui porte le module le plus mal exposé du toit, désignée par '
    "COMPARAISON des accès solaires du document (aucun seuil) — c'est un "
    "signal de CÂBLAGE : aucun kWh n'en est dérivé.")

#: La référence citée, et elle reste une citation — jamais un chiffre repris.
REFERENCE_CHAINE_FAIBLE = (
    'PV*SOL — ombrage module par module publié comme un signal de '
    'configuration '
    '(https://help.valentin-software.com/pvsol/en/pages/pv-modules/shading/)')

MOTIF_CHAINE_FAIBLE_ABSENTE = (
    "Aucune chaîne n'a d'accès solaire mesuré : la chaîne la plus faible en "
    'ombrage n\'est pas désignée. Un module sans accès calculé n\'est pas un '
    'module non ombré.')


def _chaine_la_plus_faible(layout, table_affectation):
    """``(bloc, motif)`` — la chaîne à regarder, ou l'absence MOTIVÉE.

    Args:
        layout: le document ``roof_layout`` v2, qui porte (ou non)
            ``zones[].geometry.solarAccess.values``.
        table_affectation: la table CAL125 réellement dimensionnée.

    Returns:
        ``(bloc, '')`` quand une chaîne est désignée, ``(None, motif)``
        sinon. Le bloc porte la chaîne, son pan, le module fautif, son accès
        solaire (fraction de 0 à 1, telle que le document la publie), l'écart
        contre le module le mieux exposé, la méthode et la référence citée.
    """
    from .ombrage_chaines import ombrage_des_chaines

    lecture = ombrage_des_chaines(layout, table_affectation)
    if not lecture['mesure']:
        return None, lecture['motif']
    if not lecture['signalements']:
        return None, MOTIF_CHAINE_FAIBLE_ABSENTE
    pire = lecture['signalements'][0]
    return {
        'chaine': pire['chaine'],
        'pan': pire['pan'],
        'module': pire['module'],
        'acces_solaire': pire['acces'],
        'ecart': pire['ecart'],
        'methode': METHODE_CHAINE_FAIBLE,
        'reference': REFERENCE_CHAINE_FAIBLE,
        'raison': pire['raison'],
    }, ''
