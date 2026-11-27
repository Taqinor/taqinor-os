"""ACAL612 — le ``titre`` et la ``phrase`` de la publication, composés ICI.

L'écran ne compose aucun texte : il lit ``titre`` (« Prêt », « À compléter :
N points », « Bloquant : N ») et ``phrase``, faits de l'``etat`` et des
``points`` déjà posés par ACAL934 (``etat_dossier_electrique``) — jamais
recalculés — et des libellés RÉELS des motifs, recopiés tels quels.
``publiable``, ``etat`` et ``motifs`` gardent leur valeur exacte ; ``points`` aussi, sauf
ACAL1937 : « à compléter » sert le compte du rail quand l'appelant le fournit.
"""
from __future__ import annotations

__all__ = ['synthese_de_publication']

#: Combien de libellés réels la phrase cite (les suivants sont résumés par « … »).
_LIBELLES_CITES = 2


def _points(n):
    return '%d point' % n if n == 1 else '%d points' % n


def _cites(motifs, statuts):
    libelles = [m.get('libelle') for m in motifs if m.get('statut') in statuts]
    texte = ' ; '.join(libelles[:_LIBELLES_CITES])
    return texte + ('…' if len(libelles) > _LIBELLES_CITES else '')


def synthese_de_publication(publication, points_du_rail=None):
    """La ``publication`` servie, gagnant ``titre`` et ``phrase`` (``None`` ⇒ ``None``).

    ACAL1937 — « À compléter : N points » dit le nombre du RAIL (``nombre_a_regler`` +
    ``nombre_bloquants`` de « Prêt à envoyer ? », étape Électrique) quand l'appelant le
    fournit : un seul compte pour le rail, la pastille et le Verdict. Sans lui, le compte
    des motifs de la publication (``points``) reste servi tel quel."""
    if publication is None:
        return None
    from core.electrique.types import STATUT_BLOQUANT, STATUT_NON_VERIFIABLE

    from .electrique import STATUT_MOTIF_OMIS, STATUT_MOTIF_SANS_SOURCE

    etat, points = publication.get('etat'), publication.get('points') or 0
    motifs = publication.get('motifs') or []
    if etat == 'bloquant':
        titre = 'Bloquant : %d' % points
        phrase = 'Publication impossible : %s' % _cites(motifs, (STATUT_BLOQUANT,))
    elif etat == 'a_completer':
        if points_du_rail:
            points = points_du_rail
        titre = 'À compléter : %s' % _points(points)
        reste = 'restent' if points > 1 else 'reste'
        phrase = 'Aucun motif bloquant ; %s %s à compléter : %s' % (
            _points(points), reste, _cites(motifs, (
                STATUT_NON_VERIFIABLE, STATUT_MOTIF_OMIS, STATUT_MOTIF_SANS_SOURCE)))
    else:
        titre, phrase = 'Prêt', 'Aucun motif bloquant, aucun point à compléter.'
    servie = {**publication, 'titre': titre, 'phrase': phrase}
    if etat == 'a_completer' and points_du_rail:
        servie['points'] = points_du_rail  # un seul nombre : celui du titre, du rail, de la pastille
    return servie
