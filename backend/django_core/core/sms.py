"""FG371 — Passerelle SMS marocaine (fondation, branchable).

Aujourd'hui le canal SMS est un no-op : ce module fournit l'ossature pour
brancher un VRAI fournisseur SMS sans que ``core`` n'importe une app métier
(contrat import-linter ``core-foundation-is-a-base-layer``).

Conception
----------

* ``SmsProvider`` (base) déclare l'interface ``send(to, message)`` et
  ``is_configured()``. Tant qu'aucun credential réel n'est présent, le
  fournisseur reste « non configuré » et NE fait AUCUN appel réseau.
* ``GenericHttpSmsProvider`` est un connecteur HTTP générique paramétrable par
  ``settings`` (``base_url``, ``sender``…) + secret (clé d'API via
  ``IntegrationConfig.secret_ref``). Il est enregistré sous le code
  ``« generic_http »``. Brancher un fournisseur marocain réel (ex. une API
  type Infobip/clickatell locale) = soit le configurer via ``settings`` +
  variable d'environnement, soit ajouter une sous-classe enregistrée.
* ``send_sms(company, to, message)`` résout la config SMS active de la société
  (``IntegrationConfig`` type « sms »), instancie le connecteur et envoie. Si
  rien n'est configuré, renvoie un résultat ``sent=False`` SANS lever (no-op
  propre — comportement identique à l'existant tant qu'aucun compte n'est
  branché).

⚠ AUTH/DEP : l'envoi réel exige un compte fournisseur + une clé d'API que seul
le fondateur peut provisionner (variable d'environnement nommée par
``secret_ref``). Sans elle, le module dégrade proprement.
"""
from __future__ import annotations

from .integrations import (
    TYPE_SMS,
    BaseProvider,
    register_provider,
)


class SmsResult:
    """Résultat normalisé d'un envoi SMS (jamais une exception côté appelant)."""

    def __init__(self, sent: bool, provider: str = '', detail: str = '',
                 message_id: str = ''):
        self.sent = sent
        self.provider = provider
        self.detail = detail
        self.message_id = message_id

    def as_dict(self) -> dict:
        return {
            'sent': self.sent,
            'provider': self.provider,
            'detail': self.detail,
            'message_id': self.message_id,
        }


class SmsProvider(BaseProvider):
    """Base d'un connecteur SMS (fondation)."""

    integration_type = TYPE_SMS

    def send(self, to: str, message: str) -> SmsResult:  # pragma: no cover
        raise NotImplementedError


@register_provider
class GenericHttpSmsProvider(SmsProvider):
    """Connecteur SMS HTTP générique, configurable (FG371).

    ``settings`` attendus : ``base_url`` (endpoint d'envoi), ``sender`` (nom
    d'expéditeur, optionnel). Le secret (clé d'API) vient de
    ``IntegrationConfig.secret_ref`` (variable d'environnement). Non configuré
    (pas d'URL ou pas de secret) → ``is_configured()`` faux et envoi no-op.
    """

    code = 'generic_http'
    label = 'SMS HTTP générique'

    def is_configured(self) -> bool:
        return bool(self.config.get('base_url')) and bool(self.secret)

    def send(self, to: str, message: str) -> SmsResult:
        if not self.is_configured():
            return SmsResult(
                sent=False, provider=self.code,
                detail='Connecteur SMS non configuré (URL/secret manquant).')
        # Appel réseau réel délibérément absent tant qu'aucun compte n'est
        # provisionné : on importe ``requests`` paresseusement pour ne pas
        # imposer la dépendance réseau à la fondation, et on dégrade si absente.
        try:
            import requests  # noqa: F401  (import paresseux, optionnel)
        except Exception:  # noqa: BLE001
            return SmsResult(
                sent=False, provider=self.code,
                detail="Bibliothèque HTTP indisponible.")
        payload = {
            'to': to,
            'message': message,
            'sender': self.config.get('sender', ''),
        }
        try:
            resp = requests.post(
                self.config['base_url'],
                json=payload,
                headers={'Authorization': f'Bearer {self.secret}'},
                timeout=float(self.config.get('timeout', 10)),
            )
            ok = 200 <= resp.status_code < 300
            return SmsResult(
                sent=ok, provider=self.code,
                detail=f'HTTP {resp.status_code}',
                message_id=str(resp.headers.get('X-Message-Id', '')))
        except Exception as exc:  # noqa: BLE001 — réseau/transport.
            return SmsResult(
                sent=False, provider=self.code, detail=f'Erreur réseau : {exc}')


def _active_sms_config(company):
    """Config SMS active de la société, ou ``None`` (import paresseux modèle)."""
    from .models import IntegrationConfig
    return (IntegrationConfig.objects
            .filter(company=company, integration_type=TYPE_SMS, actif=True)
            .order_by('id')
            .first())


def send_sms(company, to: str, message: str) -> SmsResult:
    """Envoie un SMS via le connecteur configuré pour ``company``.

    Aucune config / connecteur inconnu / non configuré → ``SmsResult`` avec
    ``sent=False`` (no-op propre, jamais d'exception). Multi-tenant : la
    société est imposée par l'appelant (jamais lue d'un corps de requête).
    """
    from .integrations import provider_from_config

    cfg = _active_sms_config(company)
    if cfg is None:
        return SmsResult(
            sent=False, detail='Aucune intégration SMS configurée.')
    provider = provider_from_config(cfg)
    if provider is None:
        return SmsResult(
            sent=False, provider=cfg.provider,
            detail=f'Connecteur SMS inconnu : {cfg.provider!r}.')
    return provider.send(to, message)
