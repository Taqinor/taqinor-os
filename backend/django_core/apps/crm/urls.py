from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    AppointmentViewSet, ClientViewSet,
    ConcurrentPerteViewSet, LeadViewSet,
    assignable_users, equipes_statistiques, rapport_attribution,
    LeadTagViewSet, MotifPerteViewSet, CanalViewSet, ParrainageViewSet,
    ObjectifCommercialViewSet,
    PlanActiviteViewSet,
    PointContactViewSet, SavedViewViewSet,
    SiteProfileViewSet,
    EquipeCommercialeViewSet, WebsiteLeadPayloadViewSet,
)
# SPL74 — cadence de relance (cockpit des relances + modèles de message).
from .cadence_views import MessageTemplateViewSet, RelanceEtapeViewSet
from .webhooks import website_lead_webhook, meta_lead_ads_webhook
from .webhooks import demande_rdv_webhook
from .roof_views import lead_roof_footprint
from .public_chat_views import (
    open_chat_session, post_chat_message, get_chat_session,
)
from .public_booking_views import public_booking_status, public_booking_reserve
from .public_questionnaire_views import public_questionnaire
from .public_visite_views import public_visite
from .public_views import public_salle_vente, public_apporteur_mes_deals
from .public_lead_ref_views import lead_ref_lookup
from .public_affiner_views import lead_affiner_pro
# VT12 — la SEULE surface visite restée côté CRM : la texture de toit du lead.
from .views_visite import lead_photo_toit
# NTCRM4/5/6/10/12 — forecast, plan de compte, playbooks.
from .views import (
    ForecastEntryViewSet, PlanCompteViewSet, PlaybookEtapeViewSet,
    PlaybookTacheViewSet, PlaybookViewSet, RevueCompteViewSet,
    forecast_historique_view, forecast_rollup_view, lead_playbook_view,
)
# SPL76 — sous-parcours clients : salle de vente, partenaires, apporteurs,
# deals, défis, T-TRACE.
from .clients_views import (
    AppareilEquipeViewSet, ApporteurViewSet, DealEnregistreViewSet,
    DefiViewSet, PartenaireViewSet, SalleVenteViewSet, VisiteExterneViewSet,
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
# RELANCE FOUNDATION — file « Relances du jour » (multi-touches) + Fait/Sauter.
router.register(r'relance-etapes', RelanceEtapeViewSet, basename='relance-etape')
router.register(r'equipes', EquipeCommercialeViewSet)  # ZSAL3 (admin CRUD)
router.register(r'website-lead-payloads', WebsiteLeadPayloadViewSet)  # QX16
router.register(r'vues-enregistrees', SavedViewViewSet)  # LB48
# SOLMVP10 avait retiré /api/django/crm/partenaires/ (shim ODX13 adossé à
# compta) au profit de l'ancien préfixe /api/django/compta/partenaires/ —
# mais SOLMVP30b a depuis coquillé compta (AUCUNE url, contrat de coquille
# core.parked) : cette route native reprend donc sa place ici, seule maison
# qu'elle ait jamais eue. ``crm.Partenaire`` n'a jamais quitté cette app ;
# aucune donnée perdue.
router.register(r'partenaires', PartenaireViewSet)
# ``SoumissionLeadPartenaire``/``CommissionPartenaire`` restent en base mais
# n'ont PAS de route ici — hors périmètre du correctif CI courant (compta
# était leur seule maison ; aucun test actif ne les requiert).
# WIR81 — ``crm.TerritoireCommercial`` (FG236, legacy) N'EST pas monté ici
# non plus, pour la même raison ; reste conservé pour la FK à venir NTDST11.
# NTCRM4 — Catégories de forecast (commit/best-case/pipeline/omis).
router.register(r'forecast-entries', ForecastEntryViewSet)
# NTCRM10 — Plan de compte (Account Planning).
router.register(r'plans-compte', PlanCompteViewSet)
router.register(r'revues-compte', RevueCompteViewSet)
# NTCRM12 — Playbooks de vente par étape STAGES.py.
router.register(r'playbooks', PlaybookViewSet)
router.register(r'playbook-etapes', PlaybookEtapeViewSet)
router.register(r'playbook-taches', PlaybookTacheViewSet)
# NTCRM17 — Salle de vente digitale (CRUD interne). Le préfixe
# ``salles-vente/`` (interne, authentifié) est distinct de la route publique
# ``salle-vente/<token>/`` déclarée ci-dessous (singulier, tokenisée).
router.register(r'salles-vente', SalleVenteViewSet, basename='salle-vente')
# NTCRM20 — Registre des apporteurs d'affaires (Deal Registration).
router.register(r'apporteurs', ApporteurViewSet, basename='crm-apporteur')
router.register(r'deals-enregistres', DealEnregistreViewSet, basename='deal-enregistre')
# NTCRM23 — Défis et leaderboards d'équipe.
router.register(r'defis', DefiViewSet, basename='crm-defi')
# ALEA15 — l'alias PWA déprécié `/api/django/crm/visites/` (VTA3) est RETIRÉ :
# il servait le viewset visites sous le préfixe crm, hors de la garde du module
# Visites (module désactivé ⇒ l'alias répondait encore). La fenêtre de bascule
# PWA est close ; l'API visites vit sous `/api/django/visites/` uniquement.
# QJ-EQUIPE-2 — écran de revue T-TRACE (lecture seule) + registre des
# appareils équipe (exclusion permanente et rétroactive du traçage).
router.register(r'visites-externes', VisiteExterneViewSet,
                basename='crm-visite-externe')
router.register(r'appareils-equipe', AppareilEquipeViewSet,
                basename='crm-appareil-equipe')

urlpatterns = [
    # Récepteur des leads du site public (secret statique, voir webhooks.py)
    # headless: appele par le site public (apps/web), jamais par un ecran ERP
    path('webhooks/website-leads/', website_lead_webhook, name='website-lead-webhook'),
    # XMKT32 — Sync Meta Lead Ads (gated, no-op sans jeton — voir webhooks.py)
    # headless: rappel entrant de Meta, appele par leur serveur
    path('webhooks/meta-lead-ads/', meta_lead_ads_webhook, name='meta-lead-ads-webhook'),
    # YBW51 — demandes de rendez-vous du site YanBow (société tirée de la clé)
    # headless: appele par le Worker du site apps/yanbow-web, jamais par un ecran ERP
    path('webhooks/demande-rdv/', demande_rdv_webhook, name='demande-rdv-webhook'),
    # WREF2-L3 — relève publique de la référence serveur « NOM-N » pour
    # l'écran de succès du site (voir public_lead_ref_views.py) : le transfert
    # du lead reste fire-and-forget, donc l'écran interroge CET endpoint
    # après coup avec l'idempotencyKey déjà envoyée.
    # headless: appele par le site public (apps/web), jamais par un ecran ERP
    path('public/lead-ref/<str:idempotency_key>/', lead_ref_lookup,
         name='public-lead-ref-lookup'),
    # CIQ413 — relève « Affiner » : jeton du questionnaire PRO du lead créé
    # par CETTE soumission (voir public_affiner_views.py, 404 opaque).
    # headless: appele par le site public (apps/web), jamais par un ecran ERP
    path('public/lead-affiner/<str:idempotency_key>/', lead_affiner_pro,
         name='public-lead-affiner'),
    # Employés assignables (sélecteur de responsable) — ouvert à la Commerciale.
    path('assignable-users/', assignable_users, name='assignable-users'),
    # ZSAL3 — Tableau de bord « Mes équipes ». Doit précéder include(router.urls)
    # : sinon le routeur (equipes/<pk>/) intercepterait 'statistiques' comme pk.
    path('equipes/statistiques/', equipes_statistiques, name='equipes-statistiques'),
    # ZSAL6 — Rapport d'attribution des leads (par commercial + par source).
    path('rapports/attribution/', rapport_attribution, name='rapport-attribution'),
    # QJ25 — Contour OSM du bâtiment épinglé (free, sans clé API)
    path('leads/<int:lead_id>/roof-footprint/', lead_roof_footprint, name='lead-roof-footprint'),
    # VT12 — texture du toit CALÉE du lead (dernière visite validée), lue par
    # l'atelier 3D et la carte de la fiche lead sans connaître le module visite.
    path('leads/<int:lead_id>/photo-toit/', lead_photo_toit,
         name='lead-photo-toit'),
    # XMKT37 — Livechat public tokenisé (voir public_chat_views.py)
    # headless: livechat du site public (apps/web), aucun ecran ERP en face
    path('public/chat/sessions/', open_chat_session, name='public-chat-open'),
    # headless: livechat du site public (apps/web), aucun ecran ERP en face
    path('public/chat/sessions/<str:token>/messages/', post_chat_message,
         name='public-chat-post'),
    # headless: livechat du site public (apps/web), aucun ecran ERP en face
    path('public/chat/sessions/<str:token>/', get_chat_session,
         name='public-chat-get'),
    # XSAL17 — Réservation de visite publique tokenisée (voir
    # public_booking_views.py) : {lien_rdv} des templates/messages pointe ici.
    path('public/booking/<str:token>/', public_booking_status,
         name='public-booking-status'),
    path('public/booking/<str:token>/reserve/', public_booking_reserve,
         name='public-booking-reserve'),
    # T-TRACE — beacon PUBLIC des visites du site (finalité anti-fraude, voir
    # public_visite_views.py + contract_samples/visite_externe.json).
    # MÊME authentification que le webhook lead ci-dessus (X-Webhook-Secret).
    # headless: appele par le site public (apps/web), jamais par un ecran ERP
    path('public/visite/', public_visite, name='public-visite'),
    # L-QUEST — Questionnaire client public tokenisé (voir
    # public_questionnaire_views.py). MÊME URL pour lire et répondre : GET
    # affiche les questions + le pré-remplissage, POST enregistre UNE section.
    path('public/questionnaire/<str:token>/', public_questionnaire,
         name='public-questionnaire'),
    # NTCRM17/18 — Salle de vente digitale publique tokenisée (voir
    # public_views.py). Singulier, distinct de ``salles-vente/`` (CRUD interne).
    path('salle-vente/<str:token>/', public_salle_vente,
         name='public-salle-vente'),
    # NTCRM21 — portail apporteur en lecture seule, tokenisé (jamais un id
    # d'URL devinable, jamais une session CustomUser).
    path('apporteur-portail/<str:token>/mes-deals/', public_apporteur_mes_deals,
         name='public-apporteur-mes-deals'),
    # NTCRM5 — Roll-up hiérarchique du forecast. Doit précéder le routeur :
    # sinon 'forecast-entries/<pk>/' du routeur intercepterait 'rollup'.
    path('forecast/rollup/', forecast_rollup_view, name='forecast-rollup'),
    # NTCRM6 — Historique des snapshots hebdomadaires du forecast.
    path('forecast/historique/', forecast_historique_view, name='forecast-historique'),
    # NTCRM12 — Progression playbook d'un lead (lecture + coche tâche).
    path('leads/<int:lead_id>/playbook/', lead_playbook_view, name='lead-playbook'),
    path('', include(router.urls)),
]
