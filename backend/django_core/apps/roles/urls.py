from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import RoleViewSet
from .views_organisation import (
    DepartementViewSet, EquipeOrgViewSet, PosteViewSet)

router = DefaultRouter()
# Organigramme (27/10/2026) — enregistrés AVANT le préfixe vide de
# ``RoleViewSet``, sinon « departements/ » serait lu comme un détail de rôle.
router.register(r'departements', DepartementViewSet, basename='roles-departements')
router.register(r'postes', PosteViewSet, basename='roles-postes')
router.register(r'equipes', EquipeOrgViewSet, basename='roles-equipes')
router.register(r'', RoleViewSet, basename='roles')

urlpatterns = [
    path('', include(router.urls)),
]
