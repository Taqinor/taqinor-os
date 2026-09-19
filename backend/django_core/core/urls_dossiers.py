"""NTWFL17 — routes du dossier transverse (``core.Dossier``).

  GET/POST          dossiers/                → liste / création
  GET/PUT/DELETE    dossiers/{id}/           → détail
  POST              dossiers/{id}/lier/      → rattache un objet métier
  POST              dossiers/{id}/delier/    → détache cet objet
  GET/POST          dossiers/{id}/checklist/ → lit / ajoute / coche une étape

WIRING : ces routes vivent dans leur propre URLConf pour ne pas toucher
``core/urls.py`` (édité par une autre lane). Pour les monter, ajouter UNE ligne
à ``core/urls.py`` :

    urlpatterns += [path('', include('core.urls_dossiers'))]
"""
from rest_framework.routers import DefaultRouter

from .views_dossiers import DossierViewSet

router = DefaultRouter()
router.register(r'dossiers', DossierViewSet, basename='core-dossier')

urlpatterns = router.urls
