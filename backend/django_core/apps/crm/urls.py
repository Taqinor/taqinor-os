from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import ClientViewSet, LeadViewSet, assignable_users
from .webhooks import website_lead_webhook

router = DefaultRouter()
router.register(r'clients', ClientViewSet)
router.register(r'leads', LeadViewSet)

urlpatterns = [
    # Récepteur des leads du site public (secret statique, voir webhooks.py)
    path('webhooks/website-leads/', website_lead_webhook, name='website-lead-webhook'),
    # Employés assignables (sélecteur de responsable) — ouvert à la Commerciale.
    path('assignable-users/', assignable_users, name='assignable-users'),
    path('', include(router.urls)),
]
