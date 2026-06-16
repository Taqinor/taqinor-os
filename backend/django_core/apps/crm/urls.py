from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    ClientViewSet, LeadViewSet, assignable_users,
    LeadTagViewSet, MotifPerteViewSet,
    global_search_view, notifications_view,
)
from .webhooks import website_lead_webhook

router = DefaultRouter()
router.register(r'clients', ClientViewSet)
router.register(r'leads', LeadViewSet)
router.register(r'tags', LeadTagViewSet)
router.register(r'motifs-perte', MotifPerteViewSet)

urlpatterns = [
    # Récepteur des leads du site public (secret statique, voir webhooks.py)
    path('webhooks/website-leads/', website_lead_webhook, name='website-lead-webhook'),
    # Employés assignables (sélecteur de responsable) — ouvert à la Commerciale.
    path('assignable-users/', assignable_users, name='assignable-users'),
    # Recherche globale + notifications in-app (calculées à la volée).
    path('search/', global_search_view, name='crm-global-search'),
    path('notifications/', notifications_view, name='crm-notifications'),
    path('', include(router.urls)),
]
