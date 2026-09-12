"""Routes du groupe NTMIG — montées sous ``/api/django/migration/``."""
from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import (
    AnnuairePartenairesCertifiesView, DeploiementPartenaireViewSet,
    GabaritKitView, LotMigrationViewSet, ParcoursCertificationPartenaireViewSet,
    PlaybookInstanceViewSet, ProjetMigrationViewSet, ScoreCertificationView)

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
router.register(
    r'parcours-certification-partenaire',
    ParcoursCertificationPartenaireViewSet,
    basename='migration-parcours-certification-partenaire')

urlpatterns = [
    # NTMIG20 — gabarit (CSV vide + exemple) attendu par un kit source×entité.
    path('kits/<str:source>/<str:entite>/gabarit/',
         GabaritKitView.as_view(), name='migration-kit-gabarit'),
    # NTMIG27 — score PROPOSÉ de certification d'un partenaire (lecture seule ;
    # l'attribution du niveau reste un PATCH admin sur la fiche partenaire).
    path('certification/<int:partenaire_id>/score/',
         ScoreCertificationView.as_view(),
         name='migration-certification-score'),
    # NTMIG29 — annuaire interne des partenaires certifiés (lecture seule).
    path('annuaire-partenaires-certifies/',
         AnnuairePartenairesCertifiesView.as_view(),
         name='migration-annuaire-partenaires-certifies'),
    path('', include(router.urls)),
]
