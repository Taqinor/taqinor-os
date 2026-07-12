import os
from django.contrib import admin
from django.urls import path, include
from rest_framework_simplejwt.views import TokenRefreshView, TokenVerifyView
from authentication.views import CustomTokenObtainPairView

_ADMIN_URL = os.environ.get('DJANGO_ADMIN_URL', 'api/django/admin/')

urlpatterns = [
    path(_ADMIN_URL, admin.site.urls),
    # JWT Auth endpoints
    path(
        'api/django/token/',
        CustomTokenObtainPairView.as_view(),
        name='token_obtain_pair',
    ),
    path(
        'api/django/token/refresh/',
        TokenRefreshView.as_view(),
        name='token_refresh',
    ),
    path(
        'api/django/token/verify/',
        TokenVerifyView.as_view(),
        name='token_verify',
    ),
    # App URLs
    path('api/django/', include('authentication.urls')),
    path('api/django/stock/', include('apps.stock.urls')),
    path('api/django/crm/', include('apps.crm.urls')),
    path('api/django/ventes/', include('apps.ventes.urls')),
    path('api/django/parametres/', include('apps.parametres.urls')),
    path('api/django/roles/', include('apps.roles.urls')),
    path('api/django/reporting/', include('apps.reporting.urls')),
    path('api/django/contact/', include('apps.contact.urls')),
    path('api/django/installations/', include('apps.installations.urls')),
    path('api/django/sav/', include('apps.sav.urls')),
    path('api/django/outillage/', include('apps.outillage.urls')),
    path('api/django/ged/', include('apps.ged.urls')),
    path('api/django/core/', include('core.urls')),  # FG368 — jobs Celery Beat
    path('api/django/records/', include('apps.records.urls')),
    path('api/django/imports/', include('apps.dataimport.urls')),
    path('api/django/custom-fields/', include('apps.customfields.urls')),
    path('api/django/documents/', include('apps.documents.urls')),
    path('api/django/audit/', include('apps.audit.urls')),
    path('api/django/monitoring/', include('apps.monitoring.urls')),
    path('api/django/notifications/', include('apps.notifications.urls')),
    path('api/django/automation/', include('apps.automation.urls')),
    # Liens publics tokenisés (PDF client via WhatsApp) — sans login.
    path('api/django/public/', include('apps.ventes.public_urls')),
    # FG86 — Suivi client ticket SAV — sans login.
    path('api/django/public/sav/', include('apps.sav.public_urls')),
    # XPLT4 — Webhook entrant générique (token dans l'URL) — sans login.
    path('api/django/public/', include('apps.automation.public_urls')),
    # N89 — API publique REST par clé d'API (données read-only).
    path('api/public/', include('apps.publicapi.public_urls')),
    # N89 — gestion des clés API & webhooks (session admin, Paramètres).
    path('api/django/publicapi/', include('apps.publicapi.urls')),
    # FG107-FG121 — Comptabilité générale (interne, admin/responsable).
    path('api/django/compta/', include('apps.compta.urls')),
    # ODX10 — Marketing (Email/SMS, séquences, enquêtes/NPS, événements,
    # fidélité). Nouveau préfixe ; les anciennes routes /compta/… restent
    # servies à l'identique (mêmes ViewSets) pour ne casser aucun client.
    path('api/django/marketing/', include('apps.marketing.urls')),
    # ODX11 — Appels d'offres (marchés publics/privés). Nouveau préfixe ; les
    # anciennes routes /compta/… restent servies à l'identique (mêmes ViewSets).
    path('api/django/ao/', include('apps.ao.urls')),
    # ODX12 — Portail self-service client. Nouveau préfixe ; les anciennes
    # routes /compta/… restent servies à l'identique (mêmes ViewSets/vues).
    path('api/django/portail/', include('apps.portail.urls')),
    # FLOTTE1 — Gestion de flotte (véhicules + engins roulants, interne).
    path('api/django/flotte/', include('apps.flotte.urls')),
    # AG1 — Catalogue d'actions agentiques (métadonnées, filtré par caller).
    path('api/django/agent/', include('apps.agent.urls')),
    # Group S — Messagerie interne d'équipe (« Discuss »).
    path('api/django/chat/', include('apps.chat.urls')),
    # Modules ERP greenfield (fondations) — internes, admin/responsable.
    path('api/django/rh/', include('apps.rh.urls')),
    path('api/django/paie/', include('apps.paie.urls')),
    path('api/django/gestion-projet/', include('apps.gestion_projet.urls')),
    path('api/django/contrats/', include('apps.contrats.urls')),
    path('api/django/qhse/', include('apps.qhse.urls')),
    path('api/django/kb/', include('apps.kb.urls')),
    path('api/django/litiges/', include('apps.litiges.urls')),
    # ARC17 — Répertoire des tiers (res.partner), couche fondation.
    path('api/django/tiers/', include('apps.tiers.urls')),
    # XPLT21 — Softphone VoIP intégré (SIP/WebRTC, gated).
    path('api/django/voip/', include('apps.voip.urls')),
    # XPOS1 — Vente comptoir (point of sale).
    path('api/django/pos/', include('apps.pos.urls')),
    # XPOS3 — Lien public tokenisé vers le PDF du ticket de caisse.
    path('api/django/public/pos/', include('apps.pos.public_urls')),
    # XCTR14 — Portail client : « Mes contrats & abonnements » — sans login.
    path('api/django/public/contrats/', include('apps.contrats.public_urls')),
    # XPUR21 — Réponse fournisseur en ligne à une RFQ — sans login.
    path('api/django/public/installations/',
         include('apps.installations.public_urls')),
    # XPUR22 — Portail fournisseur en lecture seule (sans login).
    path('api/django/public/stock/', include('apps.stock.public_urls')),
    # NTSEC — Fondation Identité & accès (NTSEC11 : allowlist IP/CIDR).
    path('api/django/identity/', include('apps.identity.urls')),
]

# En production (DEBUG off + gunicorn), les statiques (admin Django) sont
# servis par Django lui-même derrière nginx — volume faible (UI interne),
# pas de dépendance supplémentaire. Activé explicitement par l'env.
if os.environ.get('DJANGO_SERVE_STATIC') == '1':
    from django.conf import settings
    from django.urls import re_path
    from django.views.static import serve as _static_serve

    urlpatterns += [
        re_path(r'^static/(?P<path>.*)$', _static_serve,
                {'document_root': settings.STATIC_ROOT}),
    ]
