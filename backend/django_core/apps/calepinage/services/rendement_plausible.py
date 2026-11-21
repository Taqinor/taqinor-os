"""ACAL704 — le garde-fou de vraisemblance du rendement spécifique.

Il n'avertit QUE contre des bornes SAISIES par la société (kWh/kWc et par
an), avec leur source (règle de ``etapes.reglage``) : aucune borne n'est
écrite en code (D-CALX 7 — l'ancienne constante (600 ; 2 400) n'était citée
par aucune page publiée). Une seule borne saisie ⇒ seule celle-là est testée ;
aucune ⇒ aucun avertissement. La valeur n'est jamais bornée ni corrigée.
"""
from __future__ import annotations

CLE_MIN = 'rendement_specifique_min_kwh_kwc'
CLE_MAX = 'rendement_specifique_max_kwh_kwc'
MOTIF_RENDEMENT_INVRAISEMBLABLE = (
    'Rendement spécifique de {valeur} kWh/kWc par an hors de la plage '
    'vraisemblable [{bas} ; {haut}] : vérifiez la fenêtre météo, la '
    'puissance posée et la série reçue. La valeur est publiée telle quelle.')
BORNE_NON_SAISIE = 'non saisie'

__all__ = ['CLE_MIN', 'CLE_MAX', 'MOTIF_RENDEMENT_INVRAISEMBLABLE',
           'avertissement_de_rendement']


def _borne(contexte, cle):
    from . import etapes
    from .valeurs import nombre

    saisie = etapes.reglage(contexte, cle)
    return nombre(saisie.get('valeur')) if saisie else None


def avertissement_de_rendement(rendement, contexte):
    """Le texte d'avertissement, ou ``''`` (aucune borne franchie / saisie)."""
    if rendement is None:
        return ''
    bas, haut = _borne(contexte, CLE_MIN), _borne(contexte, CLE_MAX)
    hors = ((bas is not None and rendement < bas)
            or (haut is not None and rendement > haut))
    if not hors:
        return ''
    return MOTIF_RENDEMENT_INVRAISEMBLABLE.format(
        valeur=rendement, bas=BORNE_NON_SAISIE if bas is None else f'{bas:g}',
        haut=BORNE_NON_SAISIE if haut is None else f'{haut:g}')
