"""FG370 — Passerelle de paiement carte en ligne (CMI / Payzone), fondation
branchable.

Permet d'initier le paiement carte en ligne d'un document facturable (Facture,
échéance…) et de suivre le statut de la transaction, SANS que ``core`` n'importe
l'app qui produit le document (contrat import-linter
``core-foundation-is-a-base-layer``). La cible est attachée via ``contenttypes``
sur ``PaymentTransaction`` (modèle FG370).

Conception
----------

* ``PaymentProvider`` (base) : interface ``create_payment(transaction)`` +
  ``fetch_status(transaction)`` + ``is_configured()``. Non configuré → no-op
  propre (aucun appel réseau).
* ``CmiProvider`` / ``PayzoneProvider`` : connecteurs marchands marocains,
  enregistrés sous ``« cmi »`` / ``« payzone »``. Tant qu'aucun compte marchand
  + clé n'est branché, ``is_configured()`` est faux et aucun appel réseau n'a
  lieu (la transaction reste « initiée » avec un détail explicite).
* ``creer_transaction(company, ...)`` matérialise une ``PaymentTransaction``
  (multi-tenant, société imposée). ``initier(transaction)`` délègue au
  connecteur configuré ; ``marquer_paye(transaction)`` capture le paiement et
  émet l'événement ``core.events.payment_captured`` pour que l'app comptable
  rapproche vers ``Paiement`` (core ne crée jamais lui-même un ``Paiement``).

⚠ AUTH : la capture réelle exige un compte marchand CMI/Payzone + une clé
provisionnée par le fondateur (variable d'environnement via ``secret_ref`` de
``IntegrationConfig``). Sans elle, le module reste en no-op.
"""
from __future__ import annotations

from django.utils import timezone

from .integrations import (
    TYPE_PAYMENT,
    BaseProvider,
    provider_from_config,
    register_provider,
)


class PaymentProvider(BaseProvider):
    """Base d'un connecteur de paiement carte en ligne (fondation)."""

    integration_type = TYPE_PAYMENT

    def create_payment(self, transaction) -> dict:  # pragma: no cover
        raise NotImplementedError

    def fetch_status(self, transaction) -> dict:  # pragma: no cover
        raise NotImplementedError


class _HostedPagePaymentProvider(PaymentProvider):
    """Connecteur PSP « page hébergée » paramétrable, base commune CMI/Payzone.

    Non configuré (URL de base ou secret manquant) → renvoie ``ok=False`` SANS
    appel réseau. L'appel réseau réel est délibérément différé tant qu'aucun
    compte marchand n'est branché.
    """

    def is_configured(self) -> bool:
        return bool(self.config.get('base_url')) and bool(self.secret)

    def create_payment(self, transaction) -> dict:
        if not self.is_configured():
            return {'ok': False,
                    'detail': f'Connecteur {self.code} non configuré.'}
        # Branchement réel différé : on renverrait ici l'URL de redirection
        # hébergée du PSP + une référence externe.
        return {'ok': True, 'external_ref': '', 'redirect_url': '',
                'detail': f'paiement initié ({self.code})'}

    def fetch_status(self, transaction) -> dict:
        if not self.is_configured():
            return {'ok': False,
                    'detail': f'Connecteur {self.code} non configuré.'}
        return {'ok': True, 'statut': transaction.statut}


@register_provider
class CmiProvider(_HostedPagePaymentProvider):
    """Connecteur CMI (Centre Monétique Interbancaire) — Maroc."""

    code = 'cmi'
    label = 'CMI (carte bancaire)'


@register_provider
class PayzoneProvider(_HostedPagePaymentProvider):
    """Connecteur Payzone — Maroc."""

    code = 'payzone'
    label = 'Payzone (carte bancaire)'


def _active_payment_config(company, provider=None):
    from .models import IntegrationConfig
    qs = (IntegrationConfig.objects
          .filter(company=company, integration_type=TYPE_PAYMENT, actif=True))
    if provider:
        qs = qs.filter(provider=provider)
    return qs.order_by('id').first()


def creer_transaction(company, *, montant, provider=None, devise='MAD',
                      target=None, payeur_email=''):
    """Crée une ``PaymentTransaction`` (initiée) pour la société (multi-tenant).

    ``provider`` par défaut = celui de la config paiement active de la société,
    sinon ``'cmi'``. ``target`` (optionnel) — la facture — est attaché via
    contenttypes. ``company`` est toujours imposée côté serveur.
    """
    from django.contrib.contenttypes.models import ContentType

    from .models import PaymentTransaction

    if provider is None:
        cfg = _active_payment_config(company)
        provider = cfg.provider if cfg else CmiProvider.code

    kwargs = {
        'company': company,
        'provider': provider,
        'montant': montant,
        'devise': devise,
        'payeur_email': payeur_email,
    }
    if target is not None:
        kwargs['content_type'] = ContentType.objects.get_for_model(type(target))
        kwargs['object_id'] = target.pk
    return PaymentTransaction.objects.create(**kwargs)


def _provider_for(transaction):
    cfg = _active_payment_config(transaction.company, transaction.provider)
    if cfg is not None:
        return provider_from_config(cfg)
    from .integrations import get_provider_class
    cls = get_provider_class(TYPE_PAYMENT, transaction.provider)
    return cls() if cls else None


def initier(transaction):
    """Initie le paiement auprès du PSP et met à jour la transaction.

    No-op propre si non configuré : la transaction reste « initiée » avec un
    détail explicite (jamais d'exception, jamais d'appel réseau non configuré).
    """
    from .models import PaymentTransaction

    provider = _provider_for(transaction)
    if provider is None:
        transaction.statut = PaymentTransaction.STATUT_ECHEC
        transaction.detail = {
            'detail': f'Connecteur inconnu : {transaction.provider!r}'}
        transaction.save(update_fields=['statut', 'detail', 'updated_at'])
        return transaction
    res = provider.create_payment(transaction)
    if res.get('ok'):
        transaction.statut = PaymentTransaction.STATUT_EN_ATTENTE
        transaction.external_ref = res.get('external_ref', '') or ''
        transaction.redirect_url = res.get('redirect_url', '') or ''
    else:
        transaction.detail = {'detail': res.get('detail', '')}
    transaction.save()
    return transaction


def marquer_paye(transaction, *, external_ref=''):
    """Capture le paiement (statut « payé ») et émet ``payment_captured``.

    L'app comptable réagit à l'événement pour matérialiser un ``Paiement`` et
    rapprocher la facture — ``core`` ne crée jamais lui-même un ``Paiement``
    métier (il reste fondation). Idempotent : re-marquer une transaction déjà
    payée ne ré-émet pas l'événement.
    """
    from .models import PaymentTransaction

    if transaction.statut == PaymentTransaction.STATUT_PAYE:
        return transaction
    transaction.statut = PaymentTransaction.STATUT_PAYE
    if external_ref:
        transaction.external_ref = external_ref
    transaction.paye_le = timezone.now()
    transaction.save()

    from .events import payment_captured
    payment_captured.send(sender=PaymentTransaction, transaction=transaction,
                          company=transaction.company)
    return transaction
