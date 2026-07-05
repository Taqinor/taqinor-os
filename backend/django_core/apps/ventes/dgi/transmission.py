"""XFAC29 — Couche de transmission DGI SORTANTE (signature + Simpl-TVA),
key-gated OFF par défaut, calquée sur l'interface `payments/providers.py`.

Gate G14 (2026-06-18) re-documenté (2026-07) : le mandat de facturation
électronique marocain est désormais VIVANT (grandes entreprises janv. 2026,
moyennes juil. 2026, vague <500 kDH janv. 2027 — tax.gov.ma, confirmé par le
fondateur) mais aucune spec technique publique (schéma Simpl-TVA, format de
signature, liste des plateformes agréées) n'est encore documentée à cette
date. Cette couche pose donc l'INTERFACE et le SQUELETTE de transmission
(signature + envoi) derrière un fournisseur swappable, strictement NoOp tant
qu'aucun certificat/⁣config n'est fourni — pour être prête à brancher la
vraie plateforme dès que sa spec sera publiée, sans revoir l'architecture.

Interface (un fournisseur expose) :
    sign_and_transmit(facture, xml_str) -> {
        'ok': bool, 'reference': str, 'motif_rejet': str,
    }
        Signe électroniquement le XML UBL (certificat classe 3, jamais
        commité — fourni par le fondateur via la config société) et le
        transmet à la plateforme agréée. `ok=False` avec `motif_rejet` sur
        échec/rejet ; jamais d'exception qui remonterait jusqu'au client HTTP.

NoOpDgiTransmissionProvider (défaut, clé 'noop') : n'émet AUCUN appel réseau,
ne signe rien, renvoie toujours un échec explicite « transmission non
configurée » — pour ne jamais laisser croire qu'une facture est partie alors
que rien n'a été envoyé. C'est le comportement strict tant que
`is_dgi_transmission_enabled` est False (le cas par défaut).

MockDgiTransmissionProvider (clé 'mock', tests uniquement) : simule une
signature + transmission réussie sans réseau, pour prouver le câblage bout en
bout (statut/référence/motif/retransmission/idempotence) sans dépendre d'une
plateforme réelle absente à ce jour.
"""
from __future__ import annotations

import logging
import uuid

logger = logging.getLogger(__name__)


class DgiTransmissionProvider:
    """Interface de base. `key` identifie le fournisseur dans le registre."""

    key = 'base'
    label = 'Fournisseur de transmission DGI'

    def sign_and_transmit(self, facture, xml_str):
        raise NotImplementedError


class NoOpDgiTransmissionProvider(DgiTransmissionProvider):
    """Défaut : aucun appel réseau, aucune signature, échec explicite."""

    key = 'noop'
    label = 'Transmission DGI non configurée (no-op)'

    def sign_and_transmit(self, facture, xml_str):
        return {
            'ok': False,
            'reference': '',
            'motif_rejet': (
                'Transmission DGI non configurée (aucune plateforme agréée '
                'ni certificat renseignés).'
            ),
        }


class MockDgiTransmissionProvider(DgiTransmissionProvider):
    """Fournisseur de test : simule une signature + transmission réussies."""

    key = 'mock'
    label = 'Fournisseur de test (mock)'

    def sign_and_transmit(self, facture, xml_str):
        return {
            'ok': True,
            'reference': f'DGI-MOCK-{uuid.uuid4().hex[:12].upper()}',
            'motif_rejet': '',
        }


_REGISTRY = {
    NoOpDgiTransmissionProvider.key: NoOpDgiTransmissionProvider,
    MockDgiTransmissionProvider.key: MockDgiTransmissionProvider,
}


def register_provider(cls):
    """Enregistre un fournisseur de transmission supplémentaire."""
    _REGISTRY[cls.key] = cls
    return cls


def get_transmission_provider(key):
    """Instancie le fournisseur de la clé donnée ; NoOp si inconnu (sûr)."""
    cls = _REGISTRY.get(key or 'noop', NoOpDgiTransmissionProvider)
    return cls()


def is_dgi_transmission_enabled(company):
    """État de l'interrupteur maître de TRANSMISSION (distinct de l'export
    local N105 `is_dgi_enabled`). Défaut OFF, jamais d'exception."""
    if company is None:
        return False
    try:
        from apps.parametres.models import CompanyProfile
        profile = (CompanyProfile.objects
                   .filter(company=company)
                   .only('dgi_transmission_actif', 'dgi_transmission_provider')
                   .first())
        return bool(profile and profile.dgi_transmission_actif)
    except Exception:  # pragma: no cover - lecture best-effort, OFF si échec
        return False


def _provider_key_for(company):
    try:
        from apps.parametres.models import CompanyProfile
        profile = (CompanyProfile.objects
                   .filter(company=company)
                   .only('dgi_transmission_provider')
                   .first())
        return (profile and profile.dgi_transmission_provider) or 'noop'
    except Exception:  # pragma: no cover
        return 'noop'


def transmettre_facture(facture):
    """Transmet (ou retransmet) une facture au provider DGI configuré.

    Renvoie le dict `Facture` mis à jour (dgi_statut/dgi_reference/
    dgi_motif_rejet) SANS jamais lever. Garde l'unicité : n'autorise jamais
    deux transmissions ACCEPTÉES pour la même facture (idempotent) — un rejet
    peut être rejoué (nouvelle tentative), une facture déjà acceptée renvoie
    son état sans re-transmettre.
    """
    from ..models import Facture

    if facture.dgi_statut == Facture.DgiStatut.ACCEPTEE:
        # Déjà acceptée : jamais deux transmissions pour la même facture.
        return facture

    if not is_dgi_transmission_enabled(facture.company):
        # Sans configuration = comportement actuel byte-identique : on ne
        # touche à aucun champ de statut.
        return facture

    from .dgi_export import build_ubl_xml
    xml_str = build_ubl_xml(facture)

    provider = get_transmission_provider(_provider_key_for(facture.company))
    result = provider.sign_and_transmit(facture, xml_str)

    facture.dgi_statut = (
        Facture.DgiStatut.ACCEPTEE if result.get('ok')
        else Facture.DgiStatut.REJETEE
    )
    facture.dgi_reference = result.get('reference') or ''
    facture.dgi_motif_rejet = result.get('motif_rejet') or ''
    facture.save(update_fields=['dgi_statut', 'dgi_reference', 'dgi_motif_rejet'])
    return facture
