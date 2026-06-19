"""
Interface fournisseur de monitoring — SWAPPABLE, calquée sur l'OCR.

Comme l'interface OCR existante, on expose une interface unique
(`MonitoringProvider.fetch_recent`) et un REGISTRE de fournisseurs sélectionnés
par clé. Deux implémentations livrées :

  * NoOpProvider ('noop') — le DÉFAUT. Ne récupère RIEN : la production se
    saisit à la main. C'est le comportement d'aujourd'hui ; aucun coût, aucun
    appel réseau, aucune dépendance.

  * FusionSolarProvider ('fusionsolar') — SQUELETTE de connecteur Huawei
    FusionSolar. Il lit ses identifiants depuis la config PAR SYSTÈME et
    appellerait l'API NorthBound de FusionSolar. Il NO-OPE proprement (renvoie
    []) tant qu'aucun identifiant n'est configuré OU si l'appel échoue. Aucune
    nouvelle dépendance pip : si on branche un jour le réseau, on utilise
    `httpx` (déjà présent) ; en l'absence d'identifiants, rien n'est importé ni
    appelé.

Chaque fournisseur renvoie une liste de dicts de relevés :
    {'date': date, 'energy_kwh': Decimal|float, 'period_days': int,
     'external_id': str}
La couche service convertit ces dicts en ProductionReading (source='auto'),
idempotente via `external_id`.
"""
from __future__ import annotations

import datetime
import logging

logger = logging.getLogger(__name__)


class MonitoringProvider:
    """Interface de base. `key` identifie le fournisseur dans le registre."""

    key = 'base'
    label = 'Fournisseur'

    def fetch_recent(self, system, config):
        """Renvoie une liste de dicts de relevés récents pour `system`.

        `system` = installations.Installation ; `config` = MonitoringConfig.
        L'implémentation par défaut ne renvoie rien (saisie manuelle)."""
        raise NotImplementedError


class NoOpProvider(MonitoringProvider):
    """Fournisseur par défaut : aucune récupération (saisie manuelle)."""

    key = 'noop'
    label = 'Manuel (aucune supervision)'

    def fetch_recent(self, system, config):
        return []


class FusionSolarProvider(MonitoringProvider):
    """Squelette de connecteur Huawei FusionSolar (NorthBound API).

    S'ACTIVE uniquement quand des identifiants sont configurés pour le système
    (`config.credentials` non vide, ex. {username, system_code, station_code}).
    Sans identifiants — ou si l'appel échoue — il NO-OPE (renvoie []), donc le
    système retombe sur la saisie manuelle. Aucun coût ni dépendance par défaut.
    """

    key = 'fusionsolar'
    label = 'Huawei FusionSolar'
    # Base NorthBound par défaut (surchargeable via credentials['base_url']).
    DEFAULT_BASE_URL = 'https://eu5.fusionsolar.huawei.com/thirdData'

    def fetch_recent(self, system, config):
        creds = getattr(config, 'credentials', None) or {}
        # Sans identifiants → no-op (saisie manuelle), comme aujourd'hui.
        if not creds or not config.enabled:
            return []
        try:
            return self._fetch(system, config, creds)
        except Exception:  # noqa: BLE001 — un connecteur ne doit JAMAIS casser l'OS.
            logger.warning(
                'FusionSolar fetch a échoué pour le système %s (no-op).',
                getattr(system, 'id', None), exc_info=True)
            return []

    def _fetch(self, system, config, creds):
        """Récupération réelle — SQUELETTE.

        Branchement futur : authentification (login → XSRF-Token), puis
        getKpiStationDay/getStationRealKpi via `httpx` (déjà dépendance). Tant
        que ce n'est pas câblé, on renvoie [] (aucun appel réseau effectué).
        """
        # base_url = creds.get('base_url', self.DEFAULT_BASE_URL)
        # station = creds.get('station_code')
        # import httpx  # déjà une dépendance — importé seulement si on branche.
        # ... login, getKpiStationDay, mapper en relevés ...
        # Squelette : aucune intégration câblée → no-op sûr.
        return []


# ── Registre des fournisseurs (swappable, comme l'OCR) ───────────────────────
_REGISTRY = {
    NoOpProvider.key: NoOpProvider,
    FusionSolarProvider.key: FusionSolarProvider,
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


def _coerce_reading(raw):
    """Normalise un dict de relevé fournisseur (tolérant)."""
    d = raw.get('date')
    if isinstance(d, str):
        d = datetime.date.fromisoformat(d)
    return {
        'date': d,
        'energy_kwh': raw.get('energy_kwh', 0),
        'period_days': int(raw.get('period_days', 1) or 1),
        'external_id': str(raw.get('external_id', '') or ''),
    }
