"""FG378 — Connecteur Odoo Compta (JSON-2, 2-way), fondation branchable.

Pousse factures/paiements vers Odoo et récupère le statut de paiement — UNIQUEMENT
via l'API JSON-2 d'Odoo (règle non-négociable #1 : JAMAIS de SQL direct vers la
base Odoo, en aucune circonstance). ``core`` reste une couche de FONDATION : il
n'importe aucune app métier (contrat import-linter
``core-foundation-is-a-base-layer``) — l'app comptable passe de simples dicts.

RÈGLE #1 (gravée) : ce module ne fait QUE des appels HTTP JSON-2 (``/json/2/…``).
Il n'ouvre AUCUNE connexion base de données vers Odoo, n'émet AUCUN SQL. Toute
écriture passe par l'API JSON-2.

⚠ AUTH : l'accès réel exige une URL d'instance + une clé d'API Odoo que seul le
fondateur provisionne. Sans elles → ``is_configured()`` faux et toutes les
opérations sont des no-op propres (aucun appel réseau, jamais d'exception).
"""
from __future__ import annotations

from .integrations import (
    BaseProvider,
    provider_from_config,
    register_provider,
)

# Type d'intégration dédié Odoo (sous-famille « accounting »).
TYPE_ODOO = 'odoo'


class OdooJson2Client(BaseProvider):
    """Client Odoo Compta via API JSON-2 STRICTEMENT (règle #1).

    ``config`` attendu : ``base_url`` (instance Odoo), ``db`` (base), ``login``.
    Le secret (clé d'API / mot de passe) vient de ``secret_ref`` (variable
    d'environnement). Aucune écriture SQL n'est jamais émise.
    """

    integration_type = TYPE_ODOO
    code = 'odoo_json2'
    label = 'Odoo Compta (JSON-2)'

    def is_configured(self) -> bool:
        return (bool(self.config.get('base_url'))
                and bool(self.config.get('db'))
                and bool(self.config.get('login'))
                and bool(self.secret))

    def _endpoint(self, path: str) -> str:
        base = (self.config.get('base_url') or '').rstrip('/')
        # API JSON-2 : tout passe par le préfixe /json/2 (jamais de SQL).
        return f'{base}/json/2/{path.lstrip("/")}'

    def _call(self, path: str, payload: dict):
        """Appel JSON-2 générique (no-op propre si non configuré / lib absente)."""
        if not self.is_configured():
            return {'ok': False, 'detail': 'Connecteur Odoo non configuré.'}
        try:
            import requests
        except Exception:  # noqa: BLE001
            return {'ok': False, 'detail': 'Bibliothèque HTTP indisponible.'}
        body = {
            'db': self.config['db'],
            'login': self.config['login'],
            'api_key': self.secret,
            'params': payload,
        }
        try:
            resp = requests.post(self._endpoint(path), json=body, timeout=15)
            ok = 200 <= resp.status_code < 300
            data = resp.json() if ok else {}
            return {'ok': ok, 'status': resp.status_code, 'data': data}
        except Exception as exc:  # noqa: BLE001 — réseau/transport.
            return {'ok': False, 'detail': f'Erreur réseau : {exc}'}

    def push_invoice(self, invoice: dict):
        """Pousse une facture (dict pur) vers Odoo via JSON-2.

        ``invoice`` : ex. ``{"ref", "partner", "lines": [...], "total"}``. La
        forme exacte dépend du mapping Odoo, hors périmètre fondation : on relaie
        le dict tel quel à l'API JSON-2.
        """
        return self._call('account.move/create', invoice)

    def push_payment(self, payment: dict):
        """Pousse un paiement (dict pur) vers Odoo via JSON-2."""
        return self._call('account.payment/create', payment)

    def fetch_payment_status(self, external_ref: str):
        """Récupère le statut de paiement d'une pièce depuis Odoo (JSON-2)."""
        return self._call('account.move/payment_state',
                          {'ref': external_ref})


register_provider(OdooJson2Client)


def _active_odoo_config(company):
    from .models import IntegrationConfig
    return (IntegrationConfig.objects
            .filter(company=company, integration_type=TYPE_ODOO, actif=True)
            .order_by('id')
            .first())


def get_client(company):
    """Instancie le client Odoo configuré pour la société, ou ``None``.

    Multi-tenant : société imposée par l'appelant.
    """
    cfg = _active_odoo_config(company)
    if cfg is None:
        return None
    return provider_from_config(cfg)


def push_invoice(company, invoice: dict):
    """Pousse une facture vers Odoo (no-op propre si non configuré)."""
    client = get_client(company)
    if client is None:
        return {'ok': False, 'detail': 'Aucune intégration Odoo configurée.'}
    return client.push_invoice(invoice)


def push_payment(company, payment: dict):
    """Pousse un paiement vers Odoo (no-op propre si non configuré)."""
    client = get_client(company)
    if client is None:
        return {'ok': False, 'detail': 'Aucune intégration Odoo configurée.'}
    return client.push_payment(payment)


def fetch_payment_status(company, external_ref: str):
    """Récupère le statut de paiement d'une pièce (no-op si non configuré)."""
    client = get_client(company)
    if client is None:
        return {'ok': False, 'detail': 'Aucune intégration Odoo configurée.'}
    return client.fetch_payment_status(external_ref)
