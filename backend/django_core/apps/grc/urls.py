"""Routes du module GRC & Conformité (NTGRC).

Monté par ``erp_agentique/urls.py`` sous ``api/django/grc/`` (et donc aussi
sous ``api/v1/grc/``). Le 2ᵉ segment correspond à la clé
``module_manifest['key']`` (``grc``) pour que le gatage 404 des modules
désactivés vise le bon module.
"""
from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .public_views import deposer_demande_droit, suivre_demande_droit
from .views import (
    JournalDestructionViewSet, PolitiqueRetentionObjetViewSet,
    ViolationDonneesViewSet,
)

router = DefaultRouter()
# NTGRC4 — durées de conservation par type d'objet (pilote les balayages
# `core.retention` enregistrés par crm/ventes/sav/audit).
router.register(r'politiques-retention-objet', PolitiqueRetentionObjetViewSet,
                basename='grc-politique-retention-objet')
# NTGRC5 — journal APPEND-ONLY des destructions/anonymisations réelles.
router.register(r'journal-destruction', JournalDestructionViewSet,
                basename='grc-journal-destruction')
# NTGRC6 — registre des violations de données + délai légal de 72 h.
router.register(r'violations-donnees', ViolationDonneesViewSet,
                basename='grc-violation-donnees')

urlpatterns = [
    # NTGRC2 — portail PUBLIC de dépôt/suivi d'une demande de droit
    # (loi 09-08). AllowAny + throttle ; déclarés AVANT le routeur pour que
    # « public » ne puisse jamais être capté par un préfixe de viewset.
    path('public/demande-droit/', deposer_demande_droit,
         name='grc-demande-droit-depot'),
    path('public/demande-droit/<str:token>/', suivre_demande_droit,
         name='grc-demande-droit-suivi'),
    path('', include(router.urls)),
]
