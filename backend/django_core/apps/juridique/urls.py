"""Routes du groupe NTJUR — montées sous ``/api/django/juridique/``.

Le 2ᵉ segment (``juridique``) correspond à la clé ``module_manifest['key']`` :
le gatage 404 des modules désactivés vise donc le bon module sans entrée
``PREFIX_TO_MODULE`` supplémentaire dans ``core/permissions.py``.
"""
from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import DossierJuridiqueViewSet

router = DefaultRouter()
router.register(
    r'dossiers', DossierJuridiqueViewSet, basename='juridique-dossier')

urlpatterns = [
    path('', include(router.urls)),
]
