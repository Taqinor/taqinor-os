"""NTAPI3 — mixin de réponse COMMUN à toute vue de l'API publique (/api/public/).

Appliqué aux deux bases de vue existantes (``PublicReadOnlyViewSet`` en
lecture, ``PublicWriteAPIView`` en écriture) — jamais dupliqué par vue :
``get_exception_handler()`` dédié (enveloppe d'erreur Stripe-like, voir
``errors.py``), au lieu du handler global YAPIC3
(``core.exceptions.taqinor_exception_handler``, qui reste inchangé pour
``/api/django/``, ``/api/v1/``…).
"""
from .errors import public_api_exception_handler


class PublicApiResponseMixin:
    """À placer EN PREMIER dans le MRO (avant la base DRF) sur toute vue
    montée sous ``/api/public/``."""

    def get_exception_handler(self):
        return public_api_exception_handler
