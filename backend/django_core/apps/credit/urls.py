from django.urls import include, path
from rest_framework.routers import DefaultRouter

from . import views

router = DefaultRouter()
router.register(r'limites', views.LimiteCreditViewSet, basename='limitecredit')
router.register(r'derogations', views.DerogationCreditViewSet,
                basename='derogationcredit')
router.register(r'conditions-segment', views.ConditionPaiementSegmentViewSet,
                basename='conditionpaiementsegment')
router.register(r'segments-client', views.SegmentClientCreditViewSet,
                basename='segmentclientcredit')
router.register(r'polices-assurance', views.PoliceAssuranceCreditViewSet,
                basename='policeassurancecredit')
router.register(r'encours-garantis', views.EncoursGarantiClientViewSet,
                basename='encoursgaranticlient')

urlpatterns = [
    path('ping/', views.ping, name='credit-ping'),
    path('reglage/', views.ReglageCreditView.as_view(), name='credit-reglage'),
    path('clients/<int:client_id>/fiche/', views.fiche_credit_client,
         name='credit-fiche-client'),
    path('clients/<int:client_id>/score/', views.score_credit_client,
         name='credit-score-client'),
    path('exposition/', views.exposition_credit, name='credit-exposition'),
    path('badges/', views.badges_credit_view, name='credit-badges'),
    path('', include(router.urls)),
]
