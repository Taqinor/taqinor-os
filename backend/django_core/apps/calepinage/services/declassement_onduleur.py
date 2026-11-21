"""ACAL664 — la puissance AC de l'onduleur à la température d'AIR maximale du site.

La température utile est la T2m MAXIMALE du TMY (``temperatures_tmy``, clé
``temperature_max_c``) — jamais ``TemperaturesSite.chaud_c``, qui est une
température de CELLULE. Des températures SAISIES à la main sont des valeurs de
dimensionnement, pas l'air : la ligne se tait alors (« non connue »). La
réduction (début, pente) vient de la fiche ; absente, rien n'est supposé.
"""
from __future__ import annotations

from core.electrique.onduleurs import puissance_a_temperature
from core.electrique.types import STATUT_NON_VERIFIABLE, STATUT_OK, fr

__all__ = ['CODE_DECLASSEMENT_THERMIQUE', 'motifs_du_declassement']

CODE_DECLASSEMENT_THERMIQUE = 'DECLASSEMENT_THERMIQUE'
_SOURCE_FICHE = "fiche technique de l'onduleur"


def _air_maximale(calepinage, donnees):
    """T2m maximale servie par le fournisseur TMY, ou ``None`` (saisie, pas de TMY)."""
    from . import electrique

    fournisseur = electrique._fournisseur_temperatures()
    if fournisseur is None:
        return None
    vues = []

    def _capter(lat, lon):
        reponse = fournisseur(lat, lon)
        vues.append(reponse)
        return reponse

    try:
        electrique.temperatures_pour_calepinage(calepinage, saisie=donnees, fournisseur=_capter)
    except electrique.TemperaturesInvalides:
        return None
    reponse = vues[-1] if vues and isinstance(vues[-1], dict) else {}
    return electrique._nombre(reponse.get('temperature_max_c'))


def motifs_du_declassement(calepinage, donnees, materiel):
    """Zéro ou un motif de publication sur la puissance AC à chaud."""
    from .electrique import _motif_publication, _nombre

    onduleur = (materiel or {}).get('onduleur')
    if not onduleur:
        return []   # matériel non désigné : déjà dit par FICHE_INCOMPLETE
    ac_kw = _nombre(onduleur.get('ac_kw'))
    debut = _nombre(onduleur.get('pnom_reduite_debut_c'))
    pente = _nombre(onduleur.get('pnom_pente_pct_c'))
    if ac_kw is None or debut is None or pente is None:
        return [_motif_publication(
            CODE_DECLASSEMENT_THERMIQUE, STATUT_NON_VERIFIABLE,
            'déclassement thermique non modélisé : la fiche ne publie ni début ni pente de réduction')]
    air = _air_maximale(calepinage, donnees)
    if air is None:
        return [_motif_publication(
            CODE_DECLASSEMENT_THERMIQUE, STATUT_NON_VERIFIABLE, "température d'air non connue")]
    kw = puissance_a_temperature(ac_kw, debut, pente, air)
    part = kw / ac_kw * 100.0 if ac_kw else 0.0
    return [_motif_publication(
        CODE_DECLASSEMENT_THERMIQUE, STATUT_OK,
        'Puissance AC à %s °C : %s kW (%s %% de la nominale, d\'après la fiche)'
        % (fr(air, 0), fr(kw, 1), fr(part, 0)), _SOURCE_FICHE)]
