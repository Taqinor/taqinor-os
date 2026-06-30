"""FG375 — Géocodage & cartes (fondation branchable).

Géocode une adresse (lead/client) en coordonnées GPS afin d'alimenter la carte,
SANS que ``core`` n'importe l'app crm/clients (contrat import-linter
``core-foundation-is-a-base-layer``). L'appelant passe une CHAÎNE d'adresse ;
``core`` renvoie ``GeoPoint(lat, lng)`` ; l'app métier stocke le résultat
elle-même sur son propre modèle.

Conception
----------

* ``GeocodingProvider`` (base) : ``geocode(address) -> GeoPoint | None`` +
  ``is_configured()``.
* ``NominatimGeocodingProvider`` : connecteur OpenStreetMap/Nominatim GRATUIT
  (pas de clé d'API requise — usage raisonnable + User-Agent). Enregistré sous
  ``« nominatim »`` et utilisé par défaut.
* ``GenericKeyedGeocodingProvider`` : connecteur HTTP générique paramétrable
  qui exige une clé d'API (``IntegrationConfig.secret_ref``), pour brancher un
  service payant plus précis (DEP:geocoding-api).
* ``geocode(address, company=None)`` choisit le connecteur configuré pour la
  société (sinon Nominatim) et renvoie un ``GeoPoint`` ou ``None`` (no-op propre,
  jamais d'exception).
"""
from __future__ import annotations

from .integrations import (
    TYPE_GEOCODING,
    BaseProvider,
    provider_from_config,
    register_provider,
)


class GeoPoint:
    """Point géographique simple (lat/lng + libellé résolu)."""

    def __init__(self, lat: float, lng: float, label: str = ''):
        self.lat = lat
        self.lng = lng
        self.label = label

    def as_dict(self) -> dict:
        return {'lat': self.lat, 'lng': self.lng, 'label': self.label}

    def __eq__(self, other):
        return (isinstance(other, GeoPoint)
                and self.lat == other.lat and self.lng == other.lng)


class GeocodingProvider(BaseProvider):
    """Base d'un connecteur de géocodage (fondation)."""

    integration_type = TYPE_GEOCODING

    def geocode(self, address: str):
        raise NotImplementedError  # pragma: no cover


@register_provider
class NominatimGeocodingProvider(GeocodingProvider):
    """Géocodage OpenStreetMap/Nominatim — GRATUIT, sans clé d'API (FG375).

    Toujours « configuré » (pas de secret requis) mais dégrade en ``None`` si
    la lib HTTP est absente ou le service injoignable (jamais d'exception).
    """

    code = 'nominatim'
    label = 'OpenStreetMap (Nominatim)'

    def is_configured(self) -> bool:
        return True  # gratuit, sans clé.

    def geocode(self, address: str):
        if not address:
            return None
        try:
            import requests
        except Exception:  # noqa: BLE001
            return None
        try:
            resp = requests.get(
                'https://nominatim.openstreetmap.org/search',
                params={'q': address, 'format': 'json', 'limit': 1},
                headers={'User-Agent': 'TaqinorOS/1.0 (geocoding)'},
                timeout=float(self.config.get('timeout', 10)),
            )
            if not (200 <= resp.status_code < 300):
                return None
            data = resp.json()
            if not data:
                return None
            first = data[0]
            return GeoPoint(
                lat=float(first['lat']), lng=float(first['lon']),
                label=first.get('display_name', ''))
        except Exception:  # noqa: BLE001 — réseau/format : dégrade en None.
            return None


@register_provider
class GenericKeyedGeocodingProvider(GeocodingProvider):
    """Connecteur géocodage payant générique (clé d'API requise) (FG375).

    Non configuré (URL/secret manquant) → ``None`` (no-op propre). À utiliser
    pour un service plus précis quand le fondateur provisionne une clé d'API
    (DEP:geocoding-api).
    """

    code = 'generic_keyed'
    label = 'Géocodage payant (clé requise)'

    def is_configured(self) -> bool:
        return bool(self.config.get('base_url')) and bool(self.secret)

    def geocode(self, address: str):
        if not self.is_configured() or not address:
            return None
        try:
            import requests
        except Exception:  # noqa: BLE001
            return None
        try:
            resp = requests.get(
                self.config['base_url'],
                params={'q': address, 'key': self.secret},
                timeout=float(self.config.get('timeout', 10)),
            )
            if not (200 <= resp.status_code < 300):
                return None
            data = resp.json()
            results = data.get('results') or []
            if not results:
                return None
            loc = results[0].get('geometry', {}).get('location', {})
            if 'lat' not in loc or 'lng' not in loc:
                return None
            return GeoPoint(lat=float(loc['lat']), lng=float(loc['lng']),
                            label=results[0].get('formatted', ''))
        except Exception:  # noqa: BLE001
            return None


def _active_geocoding_config(company):
    if company is None:
        return None
    from .models import IntegrationConfig
    return (IntegrationConfig.objects
            .filter(company=company, integration_type=TYPE_GEOCODING,
                    actif=True)
            .order_by('id')
            .first())


def geocode(address: str, company=None):
    """Géocode une adresse en ``GeoPoint`` (ou ``None``).

    Choisit le connecteur configuré pour ``company`` (s'il y en a un), sinon
    Nominatim (gratuit) par défaut. No-op propre : jamais d'exception. L'app
    métier stocke elle-même le résultat (pas d'import descendant).
    """
    cfg = _active_geocoding_config(company)
    if cfg is not None:
        provider = provider_from_config(cfg)
        if provider is not None:
            return provider.geocode(address)
    return NominatimGeocodingProvider().geocode(address)
