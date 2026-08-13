"""NTMOB21 — Météo terrain pour « Ma journée ».

Expose en LECTURE la prévision du jour au point GPS demandé, pour afficher une
alerte simple (« Pluie prévue cet après-midi ») sur l'écran terrain et aider un
technicien à replanifier une pose de panneaux. Purement informatif, JAMAIS
bloquant : toute panne réseau/API renvoie ``disponible: false`` et un message
de repli — jamais une erreur 5xx.

Source : Open-Meteo (https://open-meteo.com), gratuite et SANS clé — DÉJÀ
intégrée dans ce dépôt (``apps.installations.weather``, XFSM21/PUB79) : aucune
nouvelle dépendance externe n'est introduite ici, on ajoute seulement le cache
serveur d'une heure par (latitude, longitude, jour) demandé par NTMOB21.
"""
from datetime import date

from django.core.cache import cache
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response

from authentication.permissions import IsAnyRole

from . import weather

# Une heure, comme demandé : la météo du jour ne bouge pas assez vite pour
# justifier un appel externe par ouverture d'écran (et le service est gratuit
# mais poli — on ne le martèle pas).
CACHE_TTL_S = 3600
# Arrondi des coordonnées pour la clé de cache : ~1 km, largement suffisant
# pour une alerte « pluie sur le chantier » et évite une clé par mètre parcouru.
COORD_PRECISION = 2


def _cle_cache(lat, lon, jour):
    return (f"ntmob21:meteo:{round(lat, COORD_PRECISION)}:"
            f"{round(lon, COORD_PRECISION)}:{jour.isoformat()}")


def _message(forecast):
    """Phrase courte en français, ou None si rien à signaler."""
    if not forecast:
        return None
    pluie = forecast.get('precipitation_mm')
    vent = forecast.get('windgusts_kmh')
    if pluie is not None and pluie >= weather.SEUIL_PLUIE_MM:
        return f"Pluie prévue aujourd'hui ({pluie:g} mm) — pose à replanifier ?"
    if vent is not None and vent >= weather.SEUIL_VENT_KMH:
        return f"Vent fort prévu aujourd'hui (rafales {vent:g} km/h)."
    return None


@api_view(['GET'])
@permission_classes([IsAnyRole])
def meteo_terrain(request):
    """``GET installations/meteo/?lat=&lon=`` — prévision du jour au point.

    Réponse : ``{disponible, message, precipitation_mm, windgusts_kmh}``.
    ``disponible: false`` (+ ``message`` de repli) si les coordonnées sont
    absentes/invalides ou si l'API externe ne répond pas."""
    try:
        lat = float(request.query_params.get('lat'))
        lon = float(request.query_params.get('lon'))
    except (TypeError, ValueError):
        return Response({
            'disponible': False,
            'message': 'Météo indisponible (position inconnue).',
        })

    jour = date.today()
    cle = _cle_cache(lat, lon, jour)
    charge = cache.get(cle)
    if charge is None:
        forecast = weather.fetch_forecast(lat, lon, jour)
        charge = {
            'disponible': bool(forecast),
            'message': _message(forecast) if forecast
            else 'Météo indisponible pour le moment.',
            'precipitation_mm': (forecast or {}).get('precipitation_mm'),
            'windgusts_kmh': (forecast or {}).get('windgusts_kmh'),
        }
        # On met AUSSI en cache l'indisponibilité, mais brièvement : inutile de
        # retenter l'API à chaque rendu d'écran quand elle est en panne.
        cache.set(cle, charge, CACHE_TTL_S if charge['disponible'] else 300)
    return Response(charge)
