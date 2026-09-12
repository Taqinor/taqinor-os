"""Routes du module ``datarooms`` — montées sous ``/api/django/datarooms/``.

Le 2ᵉ segment (``datarooms``) correspond à la clé ``module_manifest['key']`` :
le gatage 404 des modules désactivés vise donc le bon module sans entrée
``PREFIX_TO_MODULE`` supplémentaire dans ``core/permissions.py``.
"""
from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import SalleDeDonneesDocumentViewSet, SalleDeDonneesViewSet

router = DefaultRouter()
router.register(r'salles', SalleDeDonneesViewSet, basename='dataroom-salle')
router.register(r'salle-documents', SalleDeDonneesDocumentViewSet,
                basename='dataroom-salle-document')

urlpatterns = [
    path('', include(router.urls)),
]
