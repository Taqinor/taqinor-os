from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import OfflineOperationViewSet, OfflineSyncBatchView

router = DefaultRouter()
router.register(r'operations', OfflineOperationViewSet,
                basename='offlinesync-operation')

urlpatterns = [
    # NTMOB1 — déclaré AVANT le routeur : sans cela « batch » serait lu comme
    # l'identifiant d'une opération du journal.
    path('operations/batch/', OfflineSyncBatchView.as_view(),
         name='offlinesync-batch'),
    path('', include(router.urls)),
]
