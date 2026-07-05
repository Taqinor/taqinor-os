"""Fondation générique des INTÉGRATIONS externes (FG371+).

``core`` est la couche de FONDATION : ce module fournit l'ossature commune que
TOUTES les intégrations sortantes/entrantes réutilisent (SMS, e-signature,
IMAP, calendrier, géocodage, Sage/CEGID, Odoo, open banking…) SANS jamais
importer la moindre app métier (contrat import-linter
``core-foundation-is-a-base-layer``). On y trouve :

  * un REGISTRE de fournisseurs (``register_provider`` / ``get_provider`` /
    ``list_providers``) indexé par ``(integration_type, code)`` — purement en
    mémoire, alimenté par les apps qui montent un connecteur concret ;
  * une base abstraite ``BaseProvider`` (interface minimale + indicateur
    ``is_configured``) dont héritent les connecteurs ;
  * un utilitaire ``provider_from_config`` qui instancie le fournisseur déclaré
    par une ligne ``IntegrationConfig`` (modèle multi-tenant, cf. ``models``).

Aucune dépendance réseau ici : un fournisseur qui n'a pas de compte/credentials
réels reste « non configuré » et NE déclenche AUCUN appel externe — il dégrade
proprement. Les credentials vivent dans ``IntegrationConfig.settings`` (JSON,
par société) ; le secret réel (clé d'API…) est référencé par
``IntegrationConfig.secret_ref`` (nom de variable d'environnement / settings),
jamais stocké en clair dans le code.
"""
from __future__ import annotations

import os

# Registre en mémoire : { integration_type: { code: provider_class } }.
_REGISTRY: dict[str, dict[str, type]] = {}


# Types d'intégration connus (libellés stables). Une app peut en enregistrer
# d'autres librement — cette liste est indicative, pas restrictive.
TYPE_SMS = 'sms'
TYPE_ESIGN = 'esign'
TYPE_EMAIL_IN = 'email_in'
TYPE_CALENDAR = 'calendar'
TYPE_GEOCODING = 'geocoding'
TYPE_ACCOUNTING = 'accounting'
TYPE_BANKING = 'banking'
TYPE_PAYMENT = 'payment'
TYPE_AUTOMATION = 'automation'


class BaseProvider:
    """Interface minimale d'un connecteur d'intégration (fondation).

    Un connecteur concret hérite de cette classe, déclare ``integration_type``
    + ``code`` + ``label``, et implémente ``is_configured()`` (vrai uniquement
    si les credentials nécessaires sont présents). Tant qu'il n'est pas
    configuré, il NE doit JAMAIS effectuer d'appel réseau.

    ``config`` est le dict ``IntegrationConfig.settings`` (peut être vide).
    """

    integration_type: str = ''
    code: str = ''
    label: str = ''

    def __init__(self, config: dict | None = None, secret: str | None = None):
        self.config = dict(config or {})
        self.secret = secret

    def is_configured(self) -> bool:
        """Vrai si le connecteur dispose de tout pour fonctionner.

        Implémentation par défaut prudente : non configuré (aucun secret). Les
        connecteurs concrets surchargent selon leurs besoins réels.
        """
        return bool(self.secret)


def register_provider(provider_cls: type) -> type:
    """Enregistre un connecteur concret dans le registre (idempotent).

    Utilisable comme décorateur. Indexé par ``(integration_type, code)``.
    """
    itype = getattr(provider_cls, 'integration_type', '') or ''
    code = getattr(provider_cls, 'code', '') or ''
    if not itype or not code:
        raise ValueError(
            "Un connecteur doit déclarer integration_type et code non vides.")
    _REGISTRY.setdefault(itype, {})[code] = provider_cls
    return provider_cls


def get_provider_class(integration_type: str, code: str):
    """Classe de connecteur enregistrée, ou ``None`` si inconnue."""
    return _REGISTRY.get(integration_type, {}).get(code)


def list_providers(integration_type: str | None = None) -> list[dict]:
    """Liste normalisée des connecteurs enregistrés (catalogue lisible).

    Forme : ``{"integration_type", "code", "label"}`` triée pour un rendu
    stable. Filtrable par ``integration_type``.
    """
    out = []
    for itype, by_code in _REGISTRY.items():
        if integration_type and itype != integration_type:
            continue
        for code, cls in by_code.items():
            out.append({
                'integration_type': itype,
                'code': code,
                'label': getattr(cls, 'label', '') or code,
            })
    out.sort(key=lambda d: (d['integration_type'], d['code']))
    return out


def resolve_secret(secret_ref: str | None) -> str | None:
    """Résout un secret référencé par nom (variable d'environnement).

    On ne stocke jamais le secret en clair : ``IntegrationConfig.secret_ref``
    nomme une variable d'environnement (ex. ``'SMS_API_KEY'``). Absent → None.
    """
    if not secret_ref:
        return None
    return os.environ.get(secret_ref)


def provider_from_config(config_obj) -> BaseProvider | None:
    """Instancie le connecteur déclaré par une ligne ``IntegrationConfig``.

    Renvoie ``None`` si le type/code n'est pas enregistré. Le secret est résolu
    depuis l'environnement via ``secret_ref`` (jamais lu d'un champ en clair).
    """
    cls = get_provider_class(config_obj.integration_type, config_obj.provider)
    if cls is None:
        return None
    secret = resolve_secret(getattr(config_obj, 'secret_ref', '') or None)
    return cls(config=config_obj.settings or {}, secret=secret)


# ---------------------------------------------------------------------------
# YHARD5 — gouvernance des secrets & suivi de rotation.
#
# Aucune valeur de secret n'est jamais lue ni exposée ici — seulement les
# métadonnées de suivi portées par ``IntegrationConfig`` (nom de variable
# d'environnement, fournisseur, échéance). Pure lecture, company-scopée par le
# caller (queryset déjà filtré).
# ---------------------------------------------------------------------------


def secrets_due_for_rotation(company):
    """Intégrations de ``company`` dont le secret est échu ou sans suivi.

    Échu = ``secret_last_rotated_at + rotation_period_days < maintenant``.
    Une intégration SANS ``rotation_period_days`` n'est pas suivie (exclue) ;
    une intégration avec période mais JAMAIS rotée (``secret_last_rotated_at``
    absent) est considérée échue dès qu'elle a une période définie. Renvoie
    une liste de dicts sans jamais la valeur du secret.
    """
    from django.utils import timezone
    from .models import IntegrationConfig

    now = timezone.now()
    qs = (
        IntegrationConfig.objects
        .filter(company=company)
        .exclude(rotation_period_days__isnull=True)
    )
    due = []
    for cfg in qs:
        if cfg.secret_last_rotated_at is None:
            is_due = True
            due_since = None
        else:
            deadline = cfg.secret_last_rotated_at + timezone.timedelta(
                days=cfg.rotation_period_days)
            is_due = deadline < now
            due_since = deadline if is_due else None
        if not is_due:
            continue
        due.append({
            'id': cfg.id,
            'integration_type': cfg.integration_type,
            'provider': cfg.provider,
            'label': cfg.label,
            'secret_ref': cfg.secret_ref,
            'secret_owner': cfg.secret_owner,
            'rotation_period_days': cfg.rotation_period_days,
            'secret_last_rotated_at': cfg.secret_last_rotated_at,
            'due_since': due_since,
        })
    due.sort(key=lambda d: (d['integration_type'], d['provider']))
    return due
