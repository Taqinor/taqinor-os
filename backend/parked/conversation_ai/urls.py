"""Routes du module « conversation_ai » — montées sous
``/api/django/conversation_ai/``.

Le 2ᵉ segment d'URL est IDENTIQUE à la clé de manifeste (``conversation_ai``) :
le gatage 404 des modules désactivés vise donc le bon module sans entrée
``PREFIX_TO_MODULE``.
"""
from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .viewsets import AppelCommercialViewSet

router = DefaultRouter()
# NTAI21 — enregistrements d'appels commerciaux (upload + transcription).
router.register(r'appels', AppelCommercialViewSet, basename='appel-commercial')

urlpatterns = [
    path('', include(router.urls)),
]
