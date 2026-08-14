"""NTWMS9/NTWMS10 — connecteurs TRANSPORTEUR (Strategy pattern).

Chaque transporteur réel (Amana, DHL, Chronopost…) est un connecteur qui sait
créer une expédition (numéro de suivi + étiquette PDF) et estimer un tarif. Un
SEUL connecteur est livré par défaut : ``NoOpProvider``, qui produit une
étiquette interne générique SANS aucun appel externe. Les intégrations réelles
sont GATED derrière une clé d'API par société.

RÉUTILISE LA PRIMITIVE PLATEFORME — ne la réimplémente jamais :
  * registre + interface : ``core.integrations`` (``BaseProvider``,
    ``register_provider``, ``get_provider_class``, ``provider_from_config``) ;
  * paramétrage + secret par société : ``core.models.IntegrationConfig``
    (``settings`` JSON non sensible, ``secret_ref`` = NOM de la variable
    d'environnement — jamais la clé en clair).

Sans ``IntegrationConfig`` actif, tout dégrade proprement sur le NoOp : aucun
appel réseau, aucune erreur, comportement identique à aujourd'hui.
"""
from .base import (  # noqa: F401
    TYPE_TRANSPORT,
    NoOpProvider,
    TransportProvider,
    provider_pour_societe,
    providers_configures,
)

__all__ = [
    'TYPE_TRANSPORT',
    'NoOpProvider',
    'TransportProvider',
    'provider_pour_societe',
    'providers_configures',
]
