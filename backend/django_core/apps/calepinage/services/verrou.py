"""CAL207 / ACAL42 — le verrou du calepinage = le prédicat VENTES, rien de plus.

UNE SEULE RÈGLE, CELLE DE VENTES (ACAL42, C-ACAL-096)
-----------------------------------------------------
Le calepinage est en lecture seule EXACTEMENT quand son devis lié refuse le
geste ``CALEPINAGE`` : ``apps.ventes.selectors.devis_modifiabilite(devis,
geste='CALEPINAGE')['modifiable']`` est faux (table ``GESTES`` de
``ventes/domain/modifiabilite.py`` — brouillon et envoyé se corrigent,
D-QJR5-5 ; accepté, refusé, expiré ou remplacé se RÉVISENT). Aucune règle
recopiée ici, aucun déverrouillage : l'ancien « Déverrouiller /
Reverrouiller » (CALX27) et le récepteur ``devis_sent`` sont SUPPRIMÉS — le
seul geste qui rouvre une conception figée est « Réviser (v2) » côté devis.

Un calepinage SANS devis lié n'est jamais verrouillé. Le statut du devis
n'est jamais écrit (règle #4).

LA RESTAURATION DE VERSION (CAL20) HÉRITE DU MÊME REFUS
-------------------------------------------------------
``services.versions.restaurer_version`` appelle ``services.layout.
enregistrer_layout`` — LE chemin d'écriture unique du document de
conception. Le refus posé ICI protège donc les DEUX gestes.
"""
from __future__ import annotations

from rest_framework.exceptions import APIException

__all__ = [
    'VerrouilleRefuse', 'GESTE_CALEPINAGE', 'verdict_verrou',
    'est_verrouille', 'verifier_ecriture_autorisee',
]

#: Le geste ventes que le calepinage interroge (``GESTES`` de ventes).
GESTE_CALEPINAGE = 'CALEPINAGE'


class VerrouilleRefuse(APIException):
    """409 — le calepinage est en lecture seule (devis lié figé).

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


def verdict_verrou(calepinage):
    """Le verdict ventes du geste ``CALEPINAGE`` sur le devis lié, ou
    ``None`` sans devis lié (jamais verrouillé)."""
    devis = _devis_lie(calepinage)
    if devis is None:
        return None
    from apps.ventes.selectors import devis_modifiabilite

    return devis_modifiabilite(devis, geste=GESTE_CALEPINAGE)


def est_verrouille(calepinage):
    """``True`` si le calepinage est en lecture seule : devis lié présent ET
    ``not devis_modifiabilite(devis, geste='CALEPINAGE')['modifiable']``."""
    verdict = verdict_verrou(calepinage)
    return verdict is not None and not verdict.get('modifiable', True)


def verifier_ecriture_autorisee(calepinage):
    """Refuse (409, clé ``roof_layout``) toute écriture de conception quand le
    calepinage est verrouillé, avec le MOTIF de ventes mot pour mot (ex.
    « Devis accepté : révisez-le ») — no-op sinon."""
    verdict = verdict_verrou(calepinage)
    if verdict is not None and not verdict.get('modifiable', True):
        raise VerrouilleRefuse(
            verdict.get('raison_non_modifiable')
            or 'Devis lié figé : révisez-le (nouvelle version).',
            champ='roof_layout')
