from django.urls import path, include
from rest_framework.routers import DefaultRouter

from .views import (
    InstallationViewSet, InterventionViewSet, TypeInterventionViewSet,
    ChecklistTemplateViewSet, ChecklistEtapeModeleViewSet, ShotListSlotViewSet,
    SafetyChecklistSlotViewSet,
    JalonProjetViewSet, ModeleProjetViewSet, ReunionChantierViewSet,
    DocumentProjetViewSet, RevisionDocumentViewSet,
)

router = DefaultRouter()
router.register(r'chantiers', InstallationViewSet)
router.register(r'interventions', InterventionViewSet)
router.register(r'types-intervention', TypeInterventionViewSet)
router.register(r'checklist-templates', ChecklistTemplateViewSet)
router.register(r'checklist-etapes', ChecklistEtapeModeleViewSet)
router.register(r'shotlist-slots', ShotListSlotViewSet)
router.register(r'consignes-securite', SafetyChecklistSlotViewSet)
router.register(r'jalons-projet', JalonProjetViewSet)
router.register(r'modeles-projet', ModeleProjetViewSet)
router.register(r'reunions-chantier', ReunionChantierViewSet)
router.register(r'documents-projet', DocumentProjetViewSet)
router.register(r'revisions-document', RevisionDocumentViewSet)

urlpatterns = [
    path('', include(router.urls)),
]
