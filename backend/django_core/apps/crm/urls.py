from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    AppointmentViewSet, ClientViewSet, ConcurrentPerteViewSet, LeadViewSet,
    assignable_users,
    LeadTagViewSet, MotifPerteViewSet, CanalViewSet, ParrainageViewSet,
    MessageTemplateViewSet, ObjectifCommercialViewSet, PointContactViewSet,
    SiteProfileViewSet,
)
from .webhooks import website_lead_webhook
from .roof_views import lead_roof_footprint

router = DefaultRouter()
router.register(r'clients', ClientViewSet)
router.register(r'leads', LeadViewSet)
router.register(r'tags', LeadTagViewSet)
router.register(r'motifs-perte', MotifPerteViewSet)
router.register(r'canaux', CanalViewSet)
router.register(r'parrainages', ParrainageViewSet)
router.register(r'message-templates', MessageTemplateViewSet)  # FG36
router.register(r'appointments', AppointmentViewSet)  # QJ20
router.register(r'objectifs', ObjectifCommercialViewSet)  # FG39
router.register(r'concurrents-perte', ConcurrentPerteViewSet)  # FG242
router.register(r'points-contact', PointContactViewSet)  # FG204
router.register(r'site-profiles', SiteProfileViewSet)  # DC12

urlpatterns = [
    # Récepteur des leads du site public (secret statique, voir webhooks.py)
    path('webhooks/website-leads/', website_lead_webhook, name='website-lead-webhook'),
    # Employés assignables (sélecteur de responsable) — ouvert à la Commerciale.
    path('assignable-users/', assignable_users, name='assignable-users'),
    # QJ25 — Contour OSM du bâtiment épinglé (free, sans clé API)
    path('leads/<int:lead_id>/roof-footprint/', lead_roof_footprint, name='lead-roof-footprint'),
    path('', include(router.urls)),
]
