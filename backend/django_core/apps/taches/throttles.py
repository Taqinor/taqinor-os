"""Débits des routes à jeton (reference/api.md §0 ; donnees.md §5) : capture 60/h et 200/j, flux 60/h,
tuile 120/h ; au-delà, 429.

Patron `CalendrierIcsThrottle` (`apps/reporting/calendar.py`) : taux écrit ici (`get_rate` surchargé,
aucune ligne dans les réglages). Le seau est celui du JETON (l'id du `JetonAcces` authentifié, jamais
le clair) : changer de réseau ne remet pas le compteur à zéro. Sans jeton authentifié (le refus
neutre a déjà répondu), rien n'est compté.
"""
from rest_framework.throttling import SimpleRateThrottle

from apps.taches.models.presence import JetonAcces


class _ThrottleJeton(SimpleRateThrottle):
    rate = None

    def get_rate(self):
        return self.rate

    def get_cache_key(self, request, view):
        jeton = getattr(request, 'auth', None)
        if not isinstance(jeton, JetonAcces):
            return None
        return self.cache_format % {'scope': self.scope, 'ident': jeton.pk}


class ThrottleCapture(_ThrottleJeton):
    scope = 'taches_capture'
    rate = '60/hour'


class ThrottleCaptureJour(_ThrottleJeton):
    scope = 'taches_capture_jour'
    rate = '200/day'


class ThrottleFlux(_ThrottleJeton):
    scope = 'taches_flux'
    rate = '60/hour'


class ThrottleTuile(_ThrottleJeton):
    scope = 'taches_tuile'
    rate = '120/hour'
