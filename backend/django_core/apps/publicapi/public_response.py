"""Mixin de réponse COMMUN à toute vue de l'API publique (/api/public/).

Appliqué aux deux bases de vue existantes (``PublicReadOnlyViewSet`` en
lecture, ``PublicWriteAPIView`` en écriture) — jamais dupliqué par vue :

* NTAPI3 — ``get_exception_handler()`` dédié (enveloppe d'erreur Stripe-like,
  voir ``errors.py``), au lieu du handler global YAPIC3
  (``core.exceptions.taqinor_exception_handler``, qui reste inchangé pour
  ``/api/django/``, ``/api/v1/``…).
* NTAPI5 — pose TOUJOURS l'en-tête ``X-Taqinor-Api-Version`` (épinglé par
  clé, ``ApiKey.api_version``, défaut ``'v1'``) sur TOUTE réponse (succès ou
  erreur), même via un chemin non-versionné (NTAPI1, pas encore construit) —
  la version SERVIE dépend de la clé, jamais du path appelé.
"""
from .errors import public_api_exception_handler

# NTAPI5 — en-tête de version épinglée par clé.
API_VERSION_HEADER = 'X-Taqinor-Api-Version'
# Version servie par défaut si la clé n'a pas encore de `api_version` posé
# (ne devrait pas arriver après la migration NTAPI5) ou si `request.auth`
# n'est pas encore résolu (ex. 401 avant authentification).
DEFAULT_API_VERSION = 'v1'


class PublicApiResponseMixin:
    """À placer EN PREMIER dans le MRO (avant la base DRF) sur toute vue
    montée sous ``/api/public/``."""

    def get_exception_handler(self):
        return public_api_exception_handler

    def finalize_response(self, request, response, *args, **kwargs):
        response = super().finalize_response(request, response, *args, **kwargs)
        api_key = getattr(request, 'auth', None)
        version = getattr(api_key, 'api_version', None) or DEFAULT_API_VERSION
        response[API_VERSION_HEADER] = version
        return response
