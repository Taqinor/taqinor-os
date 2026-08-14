"""Routes du groupe NTMIG — montées sous ``/api/django/migration/``."""
from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import (
    DeploiementPartenaireViewSet, LotMigrationViewSet,
    PlaybookInstanceViewSet, ProjetMigrationViewSet,
    ScoreCertificationView)

router = DefaultRouter()
router.register(
    r'projets-migration', ProjetMigrationViewSet,
    basename='migration-projet')
router.register(
    r'lots-migration', LotMigrationViewSet, basename='migration-lot')
router.register(
    r'playbook-instances', PlaybookInstanceViewSet,
    basename='migration-playbook-instance')
router.register(
    r'deploiements-partenaire', DeploiementPartenaireViewSet,
    basename='migration-deploiement-partenaire')

urlpatterns = [
    # NTMIG27 — score PROPOSÉ de certification d'un partenaire (lecture seule ;
    # l'attribution du niveau reste un PATCH admin sur la fiche partenaire).
    path('certification/<int:partenaire_id>/score/',
         ScoreCertificationView.as_view(),
         name='migration-certification-score'),
    path('', include(router.urls)),
]
