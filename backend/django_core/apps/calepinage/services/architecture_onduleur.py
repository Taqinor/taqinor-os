"""ACAL671 — « plutôt onduleur de chaîne, micro-onduleurs ou optimiseurs ».

Deux lectures de la conception, aucune perte d'énergie (la perte d'ombrage
vient de la simulation, D4) : le NOMBRE D'ORIENTATIONS des pans posés
(``chaines.concevoir_par_pan``) et le plus grand ``ecart_interne`` d'accès
solaire à l'intérieur d'une chaîne (``ombrage_chaines.ombrage_des_chaines``,
géométrie lue du document). Les SEUILS sont deux réglages société
(``electrique_societe``, valeur + source), vides par défaut : sans eux, la
ligne nomme les seuils manquants et ne rend AUCUN verdict. Jamais bloquant.
"""
from __future__ import annotations

from core.electrique.types import STATUT_NON_VERIFIABLE, STATUT_OK, fr

__all__ = ['CODE_ARCHITECTURE_ONDULEUR', 'CLE_SEUIL_ORIENTATIONS',
           'CLE_SEUIL_ECART', 'motifs_de_l_architecture']

CODE_ARCHITECTURE_ONDULEUR = 'ARCHITECTURE_ONDULEUR'
CLE_SEUIL_ORIENTATIONS = 'seuil_orientations_micro'
CLE_SEUIL_ECART = 'seuil_ecart_acces_optimiseur'


def _orientations(conception):
    """Orientations distinctes des pans posés ; un pan d'orientation inconnue
    compte pour une orientation à lui seul (jamais fusionné, comme CAL124)."""
    vues = set()
    for pan in getattr(conception, 'pans', ()) or ():
        if not pan.modules:
            continue
        connue = pan.azimut_deg is not None and pan.inclinaison_deg is not None
        vues.add((pan.azimut_deg, pan.inclinaison_deg) if connue else ('pan', pan.cle_stable))
    return len(vues)


def _ecart_max(conception, document, donnees):
    """Le plus grand écart interne d'accès solaire (0 à 1), ou ``None`` non mesuré."""
    from .chaines import (
        AffectationInvalide, affectation, normaliser_affectation_imposee,
    )
    from .ombrage_chaines import ombrage_des_chaines

    try:
        imposee = normaliser_affectation_imposee(donnees.get('affectation_manuelle'))
    except AffectationInvalide:
        imposee = ()
    lecture = ombrage_des_chaines(document, affectation(conception, imposee=imposee))
    ecarts = [c['ecart_interne'] for c in lecture['chaines'] if c.get('ecart_interne') is not None]
    return max(ecarts) if lecture['mesure'] and ecarts else None


def motifs_de_l_architecture(conception, document, donnees, reglages):
    """Zéro ou un motif de publication (``ok`` ou ``non_verifiable``)."""
    from .electrique import _motif_publication
    from .raccordement import _reglage
    from .parametres_cles import SECTION_ELECTRIQUE_SOCIETE, registre

    seuils = {cle: _reglage(reglages, cle) for cle in (CLE_SEUIL_ORIENTATIONS, CLE_SEUIL_ECART)}
    manquants = [cle for cle, (valeur, _source) in seuils.items() if valeur is None]
    if manquants:
        return [_motif_publication(CODE_ARCHITECTURE_ONDULEUR, STATUT_NON_VERIFIABLE,
                                   'réglages non saisis : %s' % ' ; '.join(
                                       registre(SECTION_ELECTRIQUE_SOCIETE)[cle][0] for cle in manquants))]
    if getattr(conception, 'manquantes', ()) or not getattr(conception, 'chaines', ()):
        return []   # matériel ou chaînes absents : déjà dit par FICHE_INCOMPLETE
    ecart = _ecart_max(conception, document, donnees or {})
    if ecart is None:
        return [_motif_publication(CODE_ARCHITECTURE_ONDULEUR, STATUT_NON_VERIFIABLE,
                                   'accès solaire non mesuré')]
    orientations = _orientations(conception)
    micro = orientations >= seuils[CLE_SEUIL_ORIENTATIONS][0]
    optimiseur = ecart >= seuils[CLE_SEUIL_ECART][0]
    conseil = (' ou '.join(nom for nom, oui in (('micro-onduleurs', micro), ('optimiseurs', optimiseur)) if oui)
               + ' à étudier') if micro or optimiseur else 'onduleur de chaîne'
    sources = ' ; '.join(dict.fromkeys(source for _valeur, source in seuils.values()))
    return [_motif_publication(
        CODE_ARCHITECTURE_ONDULEUR, STATUT_OK,
        "%d orientation%s et un écart d'accès solaire de %s %% dans une chaîne : %s"
        % (orientations, 's' if orientations > 1 else '', fr(ecart * 100, 0), conseil), sources)]
