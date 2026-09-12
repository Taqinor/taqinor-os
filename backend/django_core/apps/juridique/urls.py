"""Routes du groupe NTJUR — montées sous ``/api/django/juridique/``.

Le 2ᵉ segment (``juridique``) correspond à la clé ``module_manifest['key']`` :
le gatage 404 des modules désactivés vise donc le bon module sans entrée
``PREFIX_TO_MODULE`` supplémentaire dans ``core/permissions.py``.
"""
from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import (
    AudienceViewSet, CabinetAvocatViewSet, DelaiPrescriptionViewSet,
    DossierJuridiqueViewSet, MandatAvocatViewSet, NoteHonorairesViewSet,
    RegleApprobationJuridiqueViewSet,
)

router = DefaultRouter()
router.register(
    r'dossiers', DossierJuridiqueViewSet, basename='juridique-dossier')
router.register(
    r'cabinets-avocats', CabinetAvocatViewSet, basename='juridique-cabinet')
router.register(
    r'mandats', MandatAvocatViewSet, basename='juridique-mandat')
router.register(
    r'regles-approbation', RegleApprobationJuridiqueViewSet,
    basename='juridique-regle-approbation')
router.register(
    r'audiences', AudienceViewSet, basename='juridique-audience')
router.register(
    r'delais-prescription', DelaiPrescriptionViewSet,
    basename='juridique-delai-prescription')
router.register(
    r'notes-honoraires', NoteHonorairesViewSet,
    basename='juridique-note-honoraires')

urlpatterns = [
    path('', include(router.urls)),
]
