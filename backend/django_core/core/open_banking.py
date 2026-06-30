"""FG379 — Open banking (flux bancaire automatique), fondation branchable.

Tire les transactions d'un agrégateur bancaire (open banking / PSD2) pour
alimenter le rapprochement — SANS que ``core`` n'importe l'app comptable
(contrat import-linter ``core-foundation-is-a-base-layer``). ``core`` se limite
à RÉCUPÉRER et NORMALISER le flux ; le rapprochement (matching avec les
factures/paiements) reste côté compta, qui consomme ces transactions.

Conception
----------

* ``BankAggregatorProvider`` (base) : ``fetch_transactions(since=None) ->
  list[BankTransaction]`` + ``is_configured()``.
* ``GenericOpenBankingProvider`` : connecteur HTTP générique paramétrable
  (``base_url`` + identifiant de compte via ``settings``, jeton d'accès via
  ``IntegrationConfig.secret_ref``). Non configuré → liste vide (no-op propre).
* ``fetch_transactions(company, since=None)`` choisit le connecteur configuré
  pour la société et renvoie une liste de ``BankTransaction`` normalisées
  (jamais d'exception).

⚠ AUTH : l'accès réel exige un compte agrégateur + un jeton OAuth/PSD2 que seul
le fondateur provisionne (variable d'environnement via ``secret_ref``). Sans
lui → no-op propre.
"""
from __future__ import annotations

from .integrations import (
    TYPE_BANKING,
    BaseProvider,
    provider_from_config,
    register_provider,
)


class BankTransaction:
    """Transaction bancaire normalisée (objet pur, agnostique du fournisseur)."""

    def __init__(self, *, external_id='', date='', amount=0.0, currency='MAD',
                 label='', counterparty='', raw=None):
        self.external_id = external_id
        self.date = date
        self.amount = amount
        self.currency = currency
        self.label = label
        self.counterparty = counterparty
        self.raw = dict(raw or {})

    def as_dict(self) -> dict:
        return {
            'external_id': self.external_id,
            'date': self.date,
            'amount': self.amount,
            'currency': self.currency,
            'label': self.label,
            'counterparty': self.counterparty,
        }


class BankAggregatorProvider(BaseProvider):
    """Base d'un connecteur d'agrégateur bancaire (fondation)."""

    integration_type = TYPE_BANKING

    def fetch_transactions(self, since=None):
        raise NotImplementedError  # pragma: no cover


@register_provider
class GenericOpenBankingProvider(BankAggregatorProvider):
    """Connecteur open banking HTTP générique, configurable (FG379).

    Non configuré (URL/secret manquant) → liste vide SANS appel réseau. À
    spécialiser pour un agrégateur réel (sous-classe enregistrée) une fois le
    jeton PSD2 provisionné.
    """

    code = 'generic'
    label = 'Open banking générique'

    def is_configured(self) -> bool:
        return bool(self.config.get('base_url')) and bool(self.secret)

    def fetch_transactions(self, since=None):
        if not self.is_configured():
            return []
        try:
            import requests
        except Exception:  # noqa: BLE001
            return []
        params = {'account': self.config.get('account', '')}
        if since:
            params['since'] = str(since)
        try:
            resp = requests.get(
                self.config['base_url'],
                params=params,
                headers={'Authorization': f'Bearer {self.secret}'},
                timeout=20,
            )
            if not (200 <= resp.status_code < 300):
                return []
            rows = resp.json().get('transactions', [])
        except Exception:  # noqa: BLE001 — réseau/format : dégrade en vide.
            return []
        out = []
        for r in rows:
            try:
                out.append(BankTransaction(
                    external_id=str(r.get('id', '')),
                    date=r.get('date', ''),
                    amount=float(r.get('amount', 0) or 0),
                    currency=r.get('currency', 'MAD'),
                    label=r.get('label', ''),
                    counterparty=r.get('counterparty', ''),
                    raw=r,
                ))
            except (TypeError, ValueError):
                continue
        return out


def _active_banking_config(company):
    from .models import IntegrationConfig
    return (IntegrationConfig.objects
            .filter(company=company, integration_type=TYPE_BANKING, actif=True)
            .order_by('id')
            .first())


def fetch_transactions(company, since=None):
    """Récupère les transactions bancaires de la société (no-op si non configuré).

    Multi-tenant : société imposée par l'appelant. Renvoie une liste de
    ``BankTransaction`` (vide si aucune intégration / non configuré). Le
    rapprochement reste côté compta (core ne fait que normaliser le flux).
    """
    cfg = _active_banking_config(company)
    if cfg is None:
        return []
    provider = provider_from_config(cfg)
    if provider is None:
        return []
    return provider.fetch_transactions(since=since)
