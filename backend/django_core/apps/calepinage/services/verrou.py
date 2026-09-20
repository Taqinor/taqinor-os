"""CAL207 — verrouiller le calepinage après envoi du devis lié.

MIROIR DE LA RÈGLE VENTES, RIEN DE PLUS
-------------------------------------------
``sync-layout`` (``apps/ventes/views/devis.py``) renvoie déjà 409 quand le
devis lié est verrouillé (r1-ventes3d §3.2) : un devis « envoyé » (ou au-delà)
gèle sa conception. Le module Calepinage AUTONOME n'avait aucune règle
équivalente — cette pièce la pose, ICI, pour le pivot du module, sans jamais
écrire le statut du devis (règle #4).

QUAND EST-CE VERROUILLÉ
--------------------------
Dès que le devis lié n'est plus ``brouillon`` — SAUF déverrouillage EXPLICITE
tracé au chatter (``services.journal.journaliser_verrou``), lu par
``dernier_etat_verrou``. Un calepinage SANS devis lié n'est jamais verrouillé
par ce mécanisme.

LE DÉVERROUILLAGE EST TRAÇÉ, PAS PERSISTANT PAR CHAMP
----------------------------------------------------------
Aucun nouveau champ, aucune migration : l'état « ouvert »/« fermé » est LU
dans le chatter (dernière bascule). Le récepteur ``devis_sent``
(``receivers.py``) RE-FERME automatiquement à chaque nouvel envoi — un
déverrouillage ne survit donc jamais à un cycle brouillon → renvoyé.

LA RESTAURATION DE VERSION (CAL20) HÉRITE DU MÊME REFUS (CAL203, fondue ici)
--------------------------------------------------------------------------------
``services.versions.restaurer_version`` appelle ``services.layout.
enregistrer_layout`` — LE chemin d'écriture unique du document de
conception. Le refus posé ICI, dans ce chemin unique, protège donc les DEUX
gestes sans code dupliqué.
"""
from __future__ import annotations

from rest_framework.exceptions import APIException

__all__ = [
    'VerrouilleRefuse', 'est_verrouille', 'verifier_ecriture_autorisee',
    'deverrouiller', 'reverrouiller',
]


class VerrouilleRefuse(APIException):
    """409 — le calepinage est en lecture seule (devis lié envoyé).

    ``APIException`` (et pas un simple ``ValueError``) : l'enveloppe d'erreur
    globale (``core.exceptions``) et le handler DRF natif respectent
    ``status_code`` de N'IMPORTE quelle sous-classe — 409 sort donc SANS
    toucher un seul ``except`` de vue.
    """

    status_code = 409
    default_code = 'calepinage_verrouille'

    def __init__(self, message, *, champ='calepinage'):
        super().__init__({champ: [message]})


def _devis_lie(calepinage):
    return getattr(calepinage, 'devis', None)


def _devis_envoye(calepinage):
    devis = _devis_lie(calepinage)
    if devis is None:
        return False
    statut = getattr(devis, 'statut', None)
    return bool(statut) and statut != 'brouillon'


def est_verrouille(calepinage):
    """``True`` si le calepinage est en lecture seule.

    Devis lié absent, ou encore ``brouillon`` ⇒ jamais verrouillé. Devis
    envoyé (ou au-delà) ⇒ verrouillé, SAUF si la dernière bascule tracée au
    chatter est un déverrouillage explicite.
    """
    if not _devis_envoye(calepinage):
        return False
    from .journal import VERROU_OUVERT, dernier_etat_verrou

    return dernier_etat_verrou(calepinage) != VERROU_OUVERT


def verifier_ecriture_autorisee(calepinage):
    """Refuse (409, champ nommé) toute écriture de conception quand le
    calepinage est verrouillé — no-op sinon."""
    if est_verrouille(calepinage):
        raise VerrouilleRefuse(
            'Ce calepinage est verrouillé : son devis lié a été envoyé. '
            'Déverrouillez-le avant de modifier la conception.',
            champ='roof_layout')


def deverrouiller(calepinage, *, user=None):
    """Déverrouille EXPLICITEMENT — tracé au journal avec l'auteur.

    No-op (renvoie ``False``) si le calepinage n'est pas verrouillé : on ne
    trace pas un déverrouillage qui ne change rien.
    """
    if calepinage is None or not getattr(calepinage, 'pk', None):
        raise VerrouilleRefuse('Calepinage introuvable.', champ='calepinage')
    if not est_verrouille(calepinage):
        return False
    from .journal import journaliser_verrou

    journaliser_verrou(calepinage, ouvert=True, user=user)
    return True


def reverrouiller(calepinage, *, user=None):
    """Reverrouille EXPLICITEMENT — appelée par le récepteur ``devis_sent``
    (chaque nouvel envoi invalide un déverrouillage précédent). Best-effort :
    ne lève jamais (appelée depuis un récepteur d'événement)."""
    if calepinage is None or not getattr(calepinage, 'pk', None):
        return
    from .journal import journaliser_verrou

    journaliser_verrou(calepinage, ouvert=False, user=user)
