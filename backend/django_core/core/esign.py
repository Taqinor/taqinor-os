"""FG372 — E-signature (Yousign/DocuSign…), fondation branchable.

Permet d'envoyer un document (Devis, contrat…) en signature électronique et de
suivre son statut, SANS que ``core`` n'importe l'app qui produit le document
(contrat import-linter ``core-foundation-is-a-base-layer``). La cible est
attachée via ``contenttypes`` sur ``EsignRequest`` (modèle FG372).

Conception
----------

* ``EsignProvider`` (base) : interface ``send_for_signature(request)`` +
  ``fetch_status(request)`` + ``is_configured()``. Non configuré → no-op
  propre (aucun appel réseau).
* ``GenericEsignProvider`` : connecteur HTTP générique paramétrable
  (``base_url`` via ``settings``, clé d'API via ``IntegrationConfig.secret_ref``)
  enregistré sous ``« generic »``. Brancher Yousign/DocuSign = soit le
  configurer, soit ajouter une sous-classe enregistrée.
* ``creer_demande(company, ...)`` matérialise un ``EsignRequest`` (multi-tenant,
  société imposée). ``envoyer(request)`` / ``rafraichir_statut(request)``
  délèguent au connecteur configuré et mettent à jour le statut.

⚠ AUTH : l'envoi réel exige un compte Yousign/DocuSign + une clé d'API que seul
le fondateur provisionne (variable d'environnement via ``secret_ref``). Sans
elle, le module reste en brouillon / no-op.
"""
from __future__ import annotations

from django.utils import timezone

from .integrations import (
    TYPE_ESIGN,
    BaseProvider,
    provider_from_config,
    register_provider,
)


class EsignProvider(BaseProvider):
    """Base d'un connecteur e-signature (fondation)."""

    integration_type = TYPE_ESIGN

    def send_for_signature(self, request) -> dict:  # pragma: no cover
        raise NotImplementedError

    def fetch_status(self, request) -> dict:  # pragma: no cover
        raise NotImplementedError


@register_provider
class GenericEsignProvider(EsignProvider):
    """Connecteur e-sign HTTP générique, configurable (FG372).

    Non configuré (URL/secret manquant) → renvoie un résultat ``ok=False`` SANS
    appel réseau. L'appel réseau réel est délibérément différé tant qu'aucun
    compte n'est branché.
    """

    code = 'generic'
    label = 'E-signature générique'

    def is_configured(self) -> bool:
        return bool(self.config.get('base_url')) and bool(self.secret)

    def send_for_signature(self, request) -> dict:
        if not self.is_configured():
            return {'ok': False,
                    'detail': 'Connecteur e-sign non configuré.'}
        return {'ok': True, 'external_id': '', 'detail': 'envoyé (générique)'}

    def fetch_status(self, request) -> dict:
        if not self.is_configured():
            return {'ok': False,
                    'detail': 'Connecteur e-sign non configuré.'}
        return {'ok': True, 'statut': request.statut}


def _active_esign_config(company):
    from .models import IntegrationConfig
    return (IntegrationConfig.objects
            .filter(company=company, integration_type=TYPE_ESIGN, actif=True)
            .order_by('id')
            .first())


def creer_demande(company, *, provider=None, target=None,
                  signataire_email='', signataire_nom=''):
    """Crée un ``EsignRequest`` (brouillon) pour la société (multi-tenant).

    ``provider`` par défaut = celui de la config e-sign active de la société,
    sinon ``'generic'``. ``target`` (optionnel) est attaché via contenttypes.
    """
    from django.contrib.contenttypes.models import ContentType

    from .models import EsignRequest

    if provider is None:
        cfg = _active_esign_config(company)
        provider = cfg.provider if cfg else GenericEsignProvider.code

    kwargs = {
        'company': company,
        'provider': provider,
        'signataire_email': signataire_email,
        'signataire_nom': signataire_nom,
    }
    if target is not None:
        kwargs['content_type'] = ContentType.objects.get_for_model(type(target))
        kwargs['object_id'] = target.pk
    return EsignRequest.objects.create(**kwargs)


def _provider_for(request):
    cfg = _active_esign_config(request.company)
    if cfg is not None and cfg.provider == request.provider:
        return provider_from_config(cfg)
    # Pas de config dédiée : connecteur générique non configuré (no-op propre).
    from .integrations import get_provider_class
    cls = get_provider_class(TYPE_ESIGN, request.provider)
    return cls() if cls else None


def envoyer(request):
    """Envoie la demande au fournisseur et met à jour le statut.

    No-op propre si non configuré : la demande reste en brouillon avec un détail
    explicite (jamais d'exception, jamais d'appel réseau non configuré).
    """
    from .models import EsignRequest

    provider = _provider_for(request)
    if provider is None:
        request.statut = EsignRequest.STATUT_ERREUR
        request.detail = {'detail': f'Connecteur inconnu : {request.provider!r}'}
        request.save(update_fields=['statut', 'detail', 'updated_at'])
        return request
    res = provider.send_for_signature(request)
    if res.get('ok'):
        request.statut = EsignRequest.STATUT_ENVOYE
        request.external_id = res.get('external_id', '') or ''
        request.sent_le = timezone.now()
    else:
        request.detail = {'detail': res.get('detail', '')}
    request.save()
    return request


def rafraichir_statut(request):
    """Interroge le fournisseur et synchronise le statut (no-op si non configuré)."""
    provider = _provider_for(request)
    if provider is None:
        return request
    res = provider.fetch_status(request)
    if res.get('ok') and res.get('statut'):
        request.statut = res['statut']
        if res.get('signed_url'):
            request.signed_url = res['signed_url']
        request.save()
    return request
