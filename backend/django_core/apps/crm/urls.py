from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import ClientViewSet, LeadViewSet
from .webhooks import website_lead_webhook

router = DefaultRouter()
router.register(r'clients', ClientViewSet)
router.register(r'leads', LeadViewSet)

urlpatterns = [
    # Récepteur des leads du site public (secret statique, voir webhooks.py)
    path('webhooks/website-leads/', website_lead_webhook, name='website-lead-webhook'),
    path('', include(router.urls)),
]
