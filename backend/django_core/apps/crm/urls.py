from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    AppointmentViewSet, ClientViewSet, ConcurrentPerteViewSet, LeadViewSet,
    assignable_users, equipes_statistiques, rapport_attribution,
    LeadTagViewSet, MotifPerteViewSet, CanalViewSet, ParrainageViewSet,
    MessageTemplateViewSet, ObjectifCommercialViewSet, PlanActiviteViewSet,
    PointContactViewSet, SavedViewViewSet, SiteProfileViewSet,
    EquipeCommercialeViewSet, WebsiteLeadPayloadViewSet,
)
from .webhooks import website_lead_webhook, meta_lead_ads_webhook
from .roof_views import lead_roof_footprint
from .public_chat_views import (
    open_chat_session, post_chat_message, get_chat_session,
)
from .public_booking_views import public_booking_status, public_booking_reserve
# ODX13 — mêmes ViewSets que ``apps.compta.urls`` (basenames explicitement
# préfixés ``crm-…`` pour NE PAS entrer en collision avec les noms d'URL du
# routeur compta, qui reverse ``partenaire-list`` etc.).
from .views import (
    CommissionPartenaireViewSet, PartenaireViewSet,
    SoumissionLeadPartenaireViewSet,
)
# NTCRM4/5/6/10/12 — forecast, plan de compte, playbooks.
from .views import (
    ForecastEntryViewSet, PlanCompteViewSet, PlaybookEtapeViewSet,
    PlaybookTacheViewSet, PlaybookViewSet, RevueCompteViewSet,
    forecast_historique_view, forecast_rollup_view, lead_playbook_view,
)

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
router.register(r'plans-activite', PlanActiviteViewSet)  # ZSAL2
router.register(r'equipes', EquipeCommercialeViewSet)  # ZSAL3 (admin CRUD)
router.register(r'website-lead-payloads', WebsiteLeadPayloadViewSet)  # QX16
router.register(r'vues-enregistrees', SavedViewViewSet)  # LB48
# ODX13 — nouvelles routes /api/django/crm/… (anciennes /api/django/compta/…
# conservées à l'identique, voir apps/compta/urls.py).
router.register(r'partenaires', PartenaireViewSet, basename='crm-partenaire')
router.register(r'soumissions-lead-partenaire', SoumissionLeadPartenaireViewSet,
                basename='crm-soumission-lead-partenaire')
router.register(r'commissions-partenaire', CommissionPartenaireViewSet,
                basename='crm-commission-partenaire')
# WIR81 — ``crm.TerritoireCommercial`` (FG236, legacy) N'EST plus monté ici :
# le double montage ODX13 (/crm/ + /compta/) est consolidé sur l'UNIQUE préfixe
# historique ``/api/django/compta/territoires-commerciaux/`` (le ViewSet vit
# dans ``apps.compta.views``, ODX22 relogera son corps vers crm plus tard).
# NB : ce modèle n'est PAS le moteur d'assignation des leads — celui-ci est
# ``apps.territoires.Territoire`` (NTCRM1/2), consulté par
# ``crm.services.default_responsable_for`` ; TerritoireCommercial reste
# conservé pour la FK à venir NTDST11.
# NTCRM4 — Catégories de forecast (commit/best-case/pipeline/omis).
router.register(r'forecast-entries', ForecastEntryViewSet)
# NTCRM10 — Plan de compte (Account Planning).
router.register(r'plans-compte', PlanCompteViewSet)
router.register(r'revues-compte', RevueCompteViewSet)
# NTCRM12 — Playbooks de vente par étape STAGES.py.
router.register(r'playbooks', PlaybookViewSet)
router.register(r'playbook-etapes', PlaybookEtapeViewSet)
router.register(r'playbook-taches', PlaybookTacheViewSet)

urlpatterns = [
    # Récepteur des leads du site public (secret statique, voir webhooks.py)
    path('webhooks/website-leads/', website_lead_webhook, name='website-lead-webhook'),
    # XMKT32 — Sync Meta Lead Ads (gated, no-op sans jeton — voir webhooks.py)
    path('webhooks/meta-lead-ads/', meta_lead_ads_webhook, name='meta-lead-ads-webhook'),
    # Employés assignables (sélecteur de responsable) — ouvert à la Commerciale.
    path('assignable-users/', assignable_users, name='assignable-users'),
    # ZSAL3 — Tableau de bord « Mes équipes ». Doit précéder include(router.urls)
    # : sinon le routeur (equipes/<pk>/) intercepterait 'statistiques' comme pk.
    path('equipes/statistiques/', equipes_statistiques, name='equipes-statistiques'),
    # ZSAL6 — Rapport d'attribution des leads (par commercial + par source).
    path('rapports/attribution/', rapport_attribution, name='rapport-attribution'),
    # QJ25 — Contour OSM du bâtiment épinglé (free, sans clé API)
    path('leads/<int:lead_id>/roof-footprint/', lead_roof_footprint, name='lead-roof-footprint'),
    # XMKT37 — Livechat public tokenisé (voir public_chat_views.py)
    path('public/chat/sessions/', open_chat_session, name='public-chat-open'),
    path('public/chat/sessions/<str:token>/messages/', post_chat_message,
         name='public-chat-post'),
    path('public/chat/sessions/<str:token>/', get_chat_session,
         name='public-chat-get'),
    # XSAL17 — Réservation de visite publique tokenisée (voir
    # public_booking_views.py) : {lien_rdv} des templates/messages pointe ici.
    path('public/booking/<str:token>/', public_booking_status,
         name='public-booking-status'),
    path('public/booking/<str:token>/reserve/', public_booking_reserve,
         name='public-booking-reserve'),
    # NTCRM5 — Roll-up hiérarchique du forecast. Doit précéder le routeur :
    # sinon 'forecast-entries/<pk>/' du routeur intercepterait 'rollup'.
    path('forecast/rollup/', forecast_rollup_view, name='forecast-rollup'),
    # NTCRM6 — Historique des snapshots hebdomadaires du forecast.
    path('forecast/historique/', forecast_historique_view, name='forecast-historique'),
    # NTCRM12 — Progression playbook d'un lead (lecture + coche tâche).
    path('leads/<int:lead_id>/playbook/', lead_playbook_view, name='lead-playbook'),
    path('', include(router.urls)),
]
