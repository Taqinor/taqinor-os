"""FG53 — Interface fournisseur de paiement (SWAPPABLE, calquée sur l'OCR /
monitoring).

Comme l'interface de monitoring (`apps/monitoring/providers.py`), on expose une
interface unique et un REGISTRE de fournisseurs sélectionnés par clé. DEUX
implémentations livrées :

  * NoOpProvider ('noop') — le DÉFAUT. N'INITIE aucun paiement réel : il fabrique
    une URL de page de paiement INTERNE (la page publique « Payer en ligne »
    servie par l'ERP). Aucune dépendance pip, aucun appel réseau, aucun coût,
    aucune clé. C'est le scaffold proposé maintenant — la passerelle live est
    GATÉE (DEP:<SDK> + COST + AUTH).

  * HostedGatewayProvider ('hosted') — SQUELETTE d'une passerelle hébergée
    générique (CMI/Stripe/PayPal…). Il lit ses identifiants depuis la config
    société et créerait une session de paiement hébergée. Il NO-OPE proprement
    (retombe sur la page interne) tant qu'aucun identifiant n'est configuré OU si
    l'appel échoue. Aucune nouvelle dépendance pip n'est importée par défaut.

Chaque fournisseur expose :
    create_session(link) -> {'pay_url': str, 'provider_ref': str}
        URL où le client paie + référence du fournisseur (idempotence webhook).
    verify_webhook(link, payload) -> {'paid': bool, 'provider_ref': str,
                                      'montant': Decimal|None}
        Valide une notification entrante et dit si le paiement est confirmé.

Le DÉFAUT NoOp confirme le paiement sur simple appel webhook (mode manuel /
hors-ligne) — utile pour le scaffold et les tests ; une passerelle réelle
remplacerait verify_webhook par une vérification de signature.
"""
from __future__ import annotations

import logging
from decimal import Decimal

logger = logging.getLogger(__name__)


class PaymentProvider:
    """Interface de base. `key` identifie le fournisseur dans le registre."""

    key = 'base'
    label = 'Fournisseur'

    def create_session(self, link):
        """Renvoie {'pay_url', 'provider_ref'} pour un PaymentLink donné."""
        raise NotImplementedError

    def verify_webhook(self, link, payload):
        """Valide une notification ; renvoie {'paid', 'provider_ref', 'montant'}."""
        raise NotImplementedError


class NoOpProvider(PaymentProvider):
    """Fournisseur par défaut : page de paiement INTERNE, aucun coût/dépendance.

    La page publique « Payer en ligne » (servie par l'ERP) joue le rôle de page
    de paiement. Le webhook NoOp confirme le paiement sur appel (mode manuel) —
    une passerelle réelle remplacera ``verify_webhook`` par une vérification de
    signature. Aucune passerelle live n'est câblée ici."""

    key = 'noop'
    label = 'Paiement manuel (aucune passerelle)'

    def create_session(self, link):
        # URL relative de la page publique interne — pas d'hôte externe.
        return {
            'pay_url': f'/api/django/public/pay/{link.token}/',
            'provider_ref': '',
        }

    def verify_webhook(self, link, payload):
        payload = payload or {}
        # Mode manuel : un webhook reçu vaut confirmation. Le montant par défaut
        # est le montant figé du lien ; un payload peut le surcharger.
        montant = payload.get('montant')
        if montant is not None:
            try:
                montant = Decimal(str(montant))
            except Exception:  # noqa: BLE001
                montant = None
        return {
            'paid': True,
            'provider_ref': str(payload.get('provider_ref') or '') or '',
            'montant': montant,
        }


class HostedGatewayProvider(PaymentProvider):
    """Squelette d'une passerelle de paiement hébergée (CMI/Stripe/PayPal…).

    S'ACTIVE uniquement quand des identifiants sont configurés. Sans identifiants
    — ou si l'appel échoue — il NO-OPE (retombe sur la page interne / refuse la
    confirmation), donc aucun coût ni dépendance par défaut. Branchement futur :
    `httpx` (déjà présent) pour créer la session hébergée + vérifier la signature
    du webhook. Tant que ce n'est pas câblé, il se comporte comme NoOp en
    lecture seule SANS confirmer un paiement non vérifié."""

    key = 'hosted'
    label = 'Passerelle hébergée (gatée)'

    def _credentials(self, link):
        # Branchement futur : lire depuis CompanyProfile / config société.
        # Aucune source câblée → vide → no-op sûr.
        return {}

    def create_session(self, link):
        creds = self._credentials(link)
        if not creds:
            # Sans identifiants → retombe sur la page interne (no-op sûr).
            return NoOpProvider().create_session(link)
        try:
            # import httpx  # déjà une dépendance — importé seulement si câblé.
            # ... créer une session hébergée et renvoyer son URL + ref ...
            return NoOpProvider().create_session(link)  # squelette inerte
        except Exception:  # noqa: BLE001 — un connecteur ne casse jamais l'OS.
            logger.warning('HostedGateway create_session a échoué (no-op).',
                           exc_info=True)
            return NoOpProvider().create_session(link)

    def verify_webhook(self, link, payload):
        creds = self._credentials(link)
        if not creds:
            # Sans identifiants, on ne confirme JAMAIS un paiement non vérifié.
            return {'paid': False, 'provider_ref': '', 'montant': None}
        try:
            # ... vérifier la signature de la notification, lire le montant ...
            return {'paid': False, 'provider_ref': '', 'montant': None}
        except Exception:  # noqa: BLE001
            logger.warning('HostedGateway verify_webhook a échoué (no-op).',
                           exc_info=True)
            return {'paid': False, 'provider_ref': '', 'montant': None}


# ── Registre des fournisseurs (swappable, comme le monitoring) ───────────────
_REGISTRY = {
    NoOpProvider.key: NoOpProvider,
    HostedGatewayProvider.key: HostedGatewayProvider,
}


def register_provider(cls):
    """Enregistre un fournisseur supplémentaire (clé = `cls.key`)."""
    _REGISTRY[cls.key] = cls
    return cls


def available_providers():
    """Liste [(clé, libellé)] des fournisseurs pour l'UI/les choix."""
    return [(cls.key, cls.label) for cls in _REGISTRY.values()]


def get_provider(key):
    """Instancie le fournisseur de la clé donnée ; NoOp si inconnu (sûr)."""
    cls = _REGISTRY.get(key or 'noop', NoOpProvider)
    return cls()
