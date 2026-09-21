"""Routes du module ``datarooms`` — montées sous ``/api/django/datarooms/``.

Le 2ᵉ segment (``datarooms``) correspond à la clé ``module_manifest['key']`` :
le gatage 404 des modules désactivés vise donc le bon module sans entrée
``PREFIX_TO_MODULE`` supplémentaire dans ``core/permissions.py``.
"""
from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import (
    AccesSalleDonneesViewSet, SalleDeDonneesDocumentViewSet,
    SalleDeDonneesViewSet, public_salle, public_salle_document,
)

router = DefaultRouter()
router.register(r'salles', SalleDeDonneesViewSet, basename='dataroom-salle')
router.register(r'salle-documents', SalleDeDonneesDocumentViewSet,
                basename='dataroom-salle-document')
router.register(r'acces', AccesSalleDonneesViewSet, basename='dataroom-acces')

urlpatterns = [
    # NTDOC12 — accès PUBLIC (sans login) à une salle par jeton VIEWER.
    # Déclaré AVANT le routeur pour ne jamais être capté par une route
    # authentifiée (même précaution que `ged.urls` `public/<token>/`).
    # AllowAny est posé sur la vue elle-même.
    # headless: salle ouverte par un lien viewer tokenisé, hors ERP
    # NTDOC13 — document servi au viewer, filigrané à SON nom. Déclaré AVANT
    # la route sommaire (plus spécifique).
    # headless: document d'une salle servi par lien viewer, hors ERP
    path('public/<str:token>/documents/<int:document_id>/',
         public_salle_document, name='dataroom-public-document'),
    path('public/<str:token>/', public_salle, name='dataroom-public-salle'),
    path('', include(router.urls)),
]
