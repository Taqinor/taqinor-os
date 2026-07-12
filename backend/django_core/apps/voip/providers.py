"""XPLT21 — Interface fournisseur VoIP SWAPPABLE, calquée sur
`apps.monitoring.providers` (elle-même calquée sur l'interface OCR).

  * NoOpProvider ('noop') — le DÉFAUT. N'amorce AUCUN appel réseau : c'est le
    comportement d'aujourd'hui (FG208 click-to-call `tel:` + journal manuel).
    Aucun coût, aucune dépendance.

  * SipGeneriqueProvider ('sip_generique') — SQUELETTE de connecteur SIP/
    WebRTC générique. S'ACTIVE uniquement quand `VoipParametres.est_configure`
    est vrai (société active + fournisseur choisi + serveur SIP renseigné) ;
    NO-OPE proprement (renvoie un statut inchangé) tant qu'aucun serveur SIP
    n'est configuré ou en cas d'erreur — jamais d'exception qui casserait
    l'ERP. Aucune nouvelle dépendance pip : le branchement réseau réel (WebRTC
    côté navigateur, signalisation SIP côté serveur) est un futur ajout ; ce
    squelette pose seulement le contrat.
"""
from __future__ import annotations

import logging

logger = logging.getLogger(__name__)


class VoipProvider:
    """Interface de base. `key` identifie le fournisseur dans le registre."""

    key = 'base'
    label = 'Fournisseur'

    def start_outbound_call(self, numero, parametres):
        """Amorce un appel sortant vers `numero`. Renvoie un dict
        `{'external_call_id': str, 'statut': str}` ou None (no-op)."""
        raise NotImplementedError


class NoOpProvider(VoipProvider):
    """Fournisseur par défaut : aucun appel réseau amorcé."""

    key = 'noop'
    label = 'Aucun (softphone désactivé)'

    def start_outbound_call(self, numero, parametres):
        return None


class SipGeneriqueProvider(VoipProvider):
    """Squelette de connecteur SIP/WebRTC générique, gated par configuration.

    Sans `VoipParametres.est_configure` — no-op sûr (aucun appel réseau, le
    softphone reste inerte). Une fois configuré, le branchement réel (offre/
    réponse WebRTC, signalisation SIP) reste à câbler ; ce squelette pose
    seulement le contrat + le no-op sûr en attendant.
    """

    key = 'sip_generique'
    label = 'SIP/WebRTC générique'

    def start_outbound_call(self, numero, parametres):
        if not getattr(parametres, 'est_configure', False):
            return None
        try:
            return self._start(numero, parametres)
        except Exception:  # noqa: BLE001 — un connecteur ne casse JAMAIS l'OS.
            logger.warning(
                'SipGeneriqueProvider.start_outbound_call a échoué pour %s '
                '(no-op).', getattr(parametres, 'company_id', None),
                exc_info=True)
            return None

    def _start(self, numero, parametres):
        """Amorce réelle — SQUELETTE. Branchement futur : signalisation SIP
        (INVITE) vers `parametres.serveur_sip`. Tant que ce n'est pas câblé,
        on renvoie un statut 'initie' sans appel réseau effectif."""
        return {'external_call_id': '', 'statut': 'initie'}


_REGISTRY = {
    NoOpProvider.key: NoOpProvider(),
    SipGeneriqueProvider.key: SipGeneriqueProvider(),
}


def get_provider(key):
    """Fournisseur par clé — retombe sur NoOp si la clé est inconnue (dégrade
    proprement, jamais de KeyError)."""
    return _REGISTRY.get(key) or _REGISTRY[NoOpProvider.key]
