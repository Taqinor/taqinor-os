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

QX3 (2026-07-10) — SÉCURITÉ FAIL-CLOSED : le webhook public de paiement est
monté sans authentification (``/api/django/public/pay/<token>/webhook/``).
Auparavant ``NoOpProvider.verify_webhook`` renvoyait ``paid: True`` pour
N'IMPORTE quel payload — un simple ``POST {}`` fabriquait un ``Paiement`` et
faisait passer la facture à PAYEE. Le défaut NoOp REFUSE désormais toute
confirmation (``paid: False``), exactement comme la branche « sans identifiants »
de ``HostedGatewayProvider`` : sans passerelle réelle vérifiant une signature,
aucun paiement n'est jamais confirmé. Un encaissement manuel passe par le
chemin ERP authentifié, jamais par ce webhook public.
"""
from __future__ import annotations

import logging

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

    # ── XCTR22 — Tokenisation carte / mandat + débit récurrent ──
    # Extension de l'interface, SEULEMENT pour les fournisseurs qui la
    # supportent. AUCUN PAN n'est jamais stocké côté ERP : seul un token
    # opaque du fournisseur (+ 4 derniers chiffres/expiration pour
    # l'affichage) est persisté sur `ventes.MandatPaiement`.
    def tokenize(self, *, client, return_url=None):
        """Ouvre une session hébergée où le CLIENT enregistre sa carte.

        Renvoie {'tokenize_url': str, 'provider_ref': str} — l'appelant
        redirige le client vers `tokenize_url` ; le fournisseur notifie
        ensuite (webhook séparé, hors périmètre ici) avec le token final."""
        raise NotImplementedError

    def charge(self, *, token, montant):
        """Débite un montant sur un token de carte déjà enregistré.

        Renvoie {'ok': bool, 'provider_ref': str, 'motif_echec': str}."""
        raise NotImplementedError


class NoOpProvider(PaymentProvider):
    """Fournisseur par défaut : page de paiement INTERNE, aucun coût/dépendance.

    La page publique « Payer en ligne » (servie par l'ERP) joue le rôle de page
    de paiement. QX3 — SÉCURITÉ : le webhook NoOp ne confirme JAMAIS un paiement
    (``paid: False``). Sans passerelle réelle qui vérifie une signature, un POST
    non authentifié ne peut pas fabriquer d'encaissement. Aucune passerelle live
    n'est câblée ici."""

    key = 'noop'
    label = 'Paiement manuel (aucune passerelle)'

    def create_session(self, link):
        # URL relative de la page publique interne — pas d'hôte externe.
        return {
            'pay_url': f'/api/django/public/pay/{link.token}/',
            'provider_ref': '',
        }

    def verify_webhook(self, link, payload):
        # QX3 — FAIL-CLOSED : ce webhook public n'est pas authentifié. Sans
        # vérification de signature d'une vraie passerelle, on ne confirme
        # JAMAIS un paiement. Le montant ne provient jamais du payload : il est
        # toujours figé côté serveur (``link.montant``) en aval. Miroir exact de
        # la branche « sans identifiants » de ``HostedGatewayProvider``.
        return {'paid': False, 'provider_ref': '', 'montant': None}

    def tokenize(self, *, client, return_url=None):
        # Aucune tokenisation réelle : jamais de PAN ni de token opaque
        # produit — le mandat reste indisponible tant qu'aucun fournisseur
        # réel n'est configuré.
        return {'tokenize_url': '', 'provider_ref': ''}

    def charge(self, *, token, montant):
        return {
            'ok': False, 'provider_ref': '',
            'motif_echec': 'Tokenisation non configurée (fournisseur noop).',
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

    def tokenize(self, *, client, return_url=None):
        creds = self._credentials(None)
        if not creds:
            return {'tokenize_url': '', 'provider_ref': ''}
        try:
            # ... créer une session de tokenisation hébergée (CMI) ...
            return {'tokenize_url': '', 'provider_ref': ''}
        except Exception:  # noqa: BLE001
            logger.warning('HostedGateway tokenize a échoué (no-op).',
                           exc_info=True)
            return {'tokenize_url': '', 'provider_ref': ''}

    def charge(self, *, token, montant):
        creds = self._credentials(None)
        if not creds or not token:
            return {
                'ok': False, 'provider_ref': '',
                'motif_echec': 'Tokenisation CMI non configurée.',
            }
        try:
            # ... débiter le token via l'API CMI ...
            return {'ok': False, 'provider_ref': '', 'motif_echec': ''}
        except Exception:  # noqa: BLE001
            logger.warning('HostedGateway charge a échoué (no-op).',
                           exc_info=True)
            return {
                'ok': False, 'provider_ref': '',
                'motif_echec': 'Erreur fournisseur.',
            }


class MockTokenizedProvider(PaymentProvider):
    """Fournisseur de TEST (tokenisation + débit simulés, aucun réseau).

    Sert à prouver le câblage bout en bout (mandat → débit → dunning)
    sans dépendre d'une plateforme réelle qui n'existe pas encore côté
    tokenisation CMI. Jamais enregistré comme défaut."""

    key = 'mock_tokenized'
    label = 'Fournisseur de test (tokenisation simulée)'

    def tokenize(self, *, client, return_url=None):
        import uuid
        return {
            'tokenize_url': '/mock-tokenize/',
            'provider_ref': f'MOCK-TOK-{uuid.uuid4().hex[:10]}',
        }

    def charge(self, *, token, montant):
        import uuid
        if not token:
            return {
                'ok': False, 'provider_ref': '',
                'motif_echec': 'Token manquant.',
            }
        if token == 'FAIL':
            return {
                'ok': False, 'provider_ref': '',
                'motif_echec': 'Carte refusée (test).',
            }
        return {
            'ok': True,
            'provider_ref': f'MOCK-CHG-{uuid.uuid4().hex[:10]}',
            'motif_echec': '',
        }


# ── Registre des fournisseurs (swappable, comme le monitoring) ───────────────
_REGISTRY = {
    NoOpProvider.key: NoOpProvider,
    HostedGatewayProvider.key: HostedGatewayProvider,
    MockTokenizedProvider.key: MockTokenizedProvider,
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
