from django.urls import path, include
from rest_framework.routers import DefaultRouter

from .views import (
    CustomFieldDefinitionViewSet, HiddenStandardFieldViewSet,
    module_schema, restore_defaults,
)

router = DefaultRouter()
router.register(r'definitions', CustomFieldDefinitionViewSet)
router.register(r'hidden-fields', HiddenStandardFieldViewSet)

urlpatterns = [
    # Schéma d'un module (définitions actives + standard masqués) pour les
    # formulaires / listes.
    path('schema/<str:module>/', module_schema, name='customfields-schema'),
    # Réinitialiser un module par défaut (admin).
    path('restore/<str:module>/', restore_defaults, name='customfields-restore'),
    path('', include(router.urls)),
]
