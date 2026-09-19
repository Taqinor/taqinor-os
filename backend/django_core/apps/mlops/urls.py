"""Routes du module « mlops » — montées sous ``/api/django/mlops/``.

Le 2ᵉ segment d'URL est IDENTIQUE à la clé de manifeste (``mlops``) : le
gatage 404 des modules désactivés vise donc le bon module sans entrée
``PREFIX_TO_MODULE``.
"""
from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .viewsets import ModeleMLViewSet

router = DefaultRouter()
# NTAI27 — versions de paramètres de scorer (CRUD + activer/).
router.register(r'modeles', ModeleMLViewSet, basename='mlops-modele')

urlpatterns = [
    path('', include(router.urls)),
]
