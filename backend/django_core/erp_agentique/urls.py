import os
from django.contrib import admin
from django.urls import path, re_path, include
from rest_framework_simplejwt.views import TokenRefreshView, TokenVerifyView
from authentication.views import CustomTokenObtainPairView
from drf_spectacular.views import (
    SpectacularAPIView, SpectacularSwaggerView, SpectacularRedocView,
)
from apps.publicapi.openapi import PublicOpenApiSchemaView

_ADMIN_URL = os.environ.get('DJANGO_ADMIN_URL', 'api/django/admin/')

# YAPIC7 — routes internes de l'ERP (authentifiées), une entrée par app.
# Cette liste est montée DEUX FOIS ci-dessous : sous le préfixe historique
# 'api/django/' (inchangé, zéro rupture) ET sous le nouveau préfixe littéral
# 'api/v1/' (ex. /api/v1/stock/...) — mêmes vues, mêmes ViewSets, aucune
# logique dupliquée. Voir docs/api-conventions.md.
# Les routes PUBLIQUES tokenisées/par clé d'API (api/django/public/*,
# api/public/*) restent volontairement HORS de cette liste : elles ont leur
# propre modèle d'auth (token dans l'URL / clé d'API) et ne font pas partie
# de ce contrat de version interne.
_APP_URLS = [
    path('', include('authentication.urls')),
    path('stock/', include('apps.stock.urls')),
    path('crm/', include('apps.crm.urls')),
    path('ventes/', include('apps.ventes.urls')),
    path('parametres/', include('apps.parametres.urls')),
    path('roles/', include('apps.roles.urls')),
    path('reporting/', include('apps.reporting.urls')),
    path('contact/', include('apps.contact.urls')),
    path('installations/', include('apps.installations.urls')),
    path('sav/', include('apps.sav.urls')),
    path('outillage/', include('apps.outillage.urls')),
    path('ged/', include('apps.ged.urls')),
    path('core/', include('core.urls')),  # FG368 — jobs Celery Beat
    path('records/', include('apps.records.urls')),
    path('imports/', include('apps.dataimport.urls')),
    path('custom-fields/', include('apps.customfields.urls')),
    # NTEXT13 — catalogue des packages d'extension (marketplace interne).
    path('extensions/', include('apps.extensions.urls')),
    path('documents/', include('apps.documents.urls')),
    path('audit/', include('apps.audit.urls')),
    path('monitoring/', include('apps.monitoring.urls')),
    path('notifications/', include('apps.notifications.urls')),
    path('automation/', include('apps.automation.urls')),
    # N89 — gestion des clés API & webhooks (session admin, Paramètres) ;
    # distinct de l'API publique par clé (api/public/, hors de cette liste).
    path('publicapi/', include('apps.publicapi.urls')),
    # FG107-FG121 — Comptabilité générale (interne, admin/responsable).
    path('compta/', include('apps.compta.urls')),
    # ODX10 — Marketing (Email/SMS, séquences, enquêtes/NPS, événements,
    # fidélité). Nouveau préfixe ; les anciennes routes /compta/… restent
    # servies à l'identique (mêmes ViewSets) pour ne casser aucun client.
    path('marketing/', include('apps.marketing.urls')),
    # ODX11 — Appels d'offres (marchés publics/privés). Nouveau préfixe ; les
    # anciennes routes /compta/… restent servies à l'identique (mêmes ViewSets).
    path('ao/', include('apps.ao.urls')),
    # ODX12 — Portail self-service client. Nouveau préfixe ; les anciennes
    # routes /compta/… restent servies à l'identique (mêmes ViewSets/vues).
    path('portail/', include('apps.portail.urls')),
    # ODX18 — Facturation (Invoicing, séparé de Sales). Nouveau préfixe ; les
    # anciennes routes /ventes/factures|paiements|avoirs|relances|balance-agee|
    # niveaux-relance/… restent servies à l'identique (mêmes ViewSets/vues).
    path('facturation/', include('apps.facturation.urls')),
    # ODX20 — Achats (Purchase). Nouveau préfixe ; les anciennes routes
    # /stock/bons-commande-fournisseur|receptions-fournisseur|
    # factures-fournisseur|retours-fournisseur|prix-fournisseurs/… restent
    # servies à l'identique (mêmes ViewSets). Mouvements stock via stock.services.
    path('achats/', include('apps.achats.urls')),
    # FLOTTE1 — Gestion de flotte (véhicules + engins roulants, interne).
    path('flotte/', include('apps.flotte.urls')),
    # AG1 — Catalogue d'actions agentiques (métadonnées, filtré par caller).
    path('agent/', include('apps.agent.urls')),
    # Group S — Messagerie interne d'équipe (« Discuss »).
    path('chat/', include('apps.chat.urls')),
    # Modules ERP greenfield (fondations) — internes, admin/responsable.
    path('rh/', include('apps.rh.urls')),
    path('paie/', include('apps.paie.urls')),
    path('gestion-projet/', include('apps.gestion_projet.urls')),
    path('contrats/', include('apps.contrats.urls')),
    path('qhse/', include('apps.qhse.urls')),
    path('kb/', include('apps.kb.urls')),
    path('litiges/', include('apps.litiges.urls')),
    # ARC17 — Répertoire des tiers (res.partner), couche fondation.
    path('tiers/', include('apps.tiers.urls')),
    # XPLT21 — Softphone VoIP intégré (SIP/WebRTC, gated).
    path('voip/', include('apps.voip.urls')),
    # XPOS1 — Vente comptoir (point of sale).
    path('pos/', include('apps.pos.urls')),
    # NTSEC — Fondation Identité & accès (NTSEC11 : allowlist IP/CIDR).
    path('identity/', include('apps.identity.urls')),
    # Groupe ENG — Moteur publicitaire Meta Ads dans l'ERP.
    path('adsengine/', include('apps.adsengine.urls')),
    # NTSAN1 — Santé (cabinet/clinique).
    path('sante/', include('apps.sante.urls')),
    # Groupe NTIDE — Boîte à idées interne, campagnes d'innovation, feedback.
    path('innovation/', include('apps.innovation.urls')),
    # NTUX1 — Vues sauvegardées serveur (personnelles/partagées).
    path('uxviews/', include('apps.uxviews.urls')),
]

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
    # YAPIC5 — schéma OpenAPI 3 (JSON) + docs interactives, derrière
    # IsAuthenticated (SPECTACULAR_SETTINGS['SERVE_PERMISSIONS']).
    path('api/schema/', SpectacularAPIView.as_view(), name='schema'),
    path(
        'api/docs/',
        SpectacularSwaggerView.as_view(url_name='schema'),
        name='swagger-ui',
    ),
    path(
        'api/redoc/',
        SpectacularRedocView.as_view(url_name='schema'),
        name='redoc',
    ),
    # App URLs — préfixe historique, inchangé (zéro rupture).
    path('api/django/', include(_APP_URLS)),
    # Liens publics tokenisés (PDF client via WhatsApp) — sans login.
    path('api/django/public/', include('apps.ventes.public_urls')),
    # FG86 — Suivi client ticket SAV — sans login.
    path('api/django/public/sav/', include('apps.sav.public_urls')),
    # XPLT4 — Webhook entrant générique (token dans l'URL) — sans login.
    path('api/django/public/', include('apps.automation.public_urls')),
    # N89 — API publique REST par clé d'API (données read-only).
    path('api/public/', include('apps.publicapi.public_urls')),
    # NTAPI20 — document OpenAPI 3.1 (aucune auth requise, document de
    # découverte). Chemin littéral MINIMAL sous le futur préfixe versionné
    # (NTAPI1, pas encore construit) : n'anticipe PAS l'alias/dépréciation
    # complet, juste le chemin dont NTAPI20 a besoin.
    path('api/public/v1/openapi.json', PublicOpenApiSchemaView.as_view(),
         name='public-openapi-v1'),
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
    # NTSEC19/20 — Gouvernance des accès (revue d'accès + SoD).
    path('api/django/accessreview/', include('apps.accessreview.urls')),
    # YAPIC7 — namespace de version explicite (URLPathVersioning,
    # DEFAULT_VERSION='v1', ALLOWED_VERSIONS=('v1',) dans REST_FRAMEWORK).
    # Mêmes vues que 'api/django/' ci-dessus (même liste _APP_URLS), sous
    # 'api/v1/...' (ex. /api/v1/stock/produits/). Préfixe LITTÉRAL (pas de
    # segment `<version>` capturé) : une capture aurait injecté un kwarg
    # `version` dans CHAQUE vue/@action de tout le repo — beaucoup n'ont pas
    # de `**kwargs` dans leur signature (`def action(self, request, pk=None)`)
    # et auraient levé un TypeError. `request.version` reste 'v1' partout via
    # le seul DEFAULT_VERSION (aucune route, ancienne ou nouvelle, ne capture
    # de kwarg `version` — cf. `rest_framework.versioning.URLPathVersioning.
    # determine_version`, testé en isolation dans test_api_versioning.py).
    # Placé en DERNIER : les routes publiques ci-dessus gardent la priorité
    # de résolution (fallthrough Django si un préfixe plus spécifique existe).
    # Namespace d'instance ``v1`` : sans lui, ce second montage (défini en
    # DERNIER) remporterait ``reverse('<nom>')`` et renverrait ``/api/v1/…``
    # au lieu du chemin interne canonique ``/api/django/…`` (cf.
    # core.tests.test_db_stats.test_url_registered). Le namespace isole les
    # noms v1 (``reverse('v1:<nom>')``) ; ``/api/v1/…`` reste résoluble à
    # l'identique pour les clients, mais ``reverse('<nom>')`` sans préfixe
    # rend toujours le chemin historique ``api/django``.
    path('api/v1/', include((_APP_URLS, 'v1'), namespace='v1')),
]

# En production (DEBUG off + gunicorn), les statiques (admin Django) sont
# servis par Django lui-même derrière nginx — volume faible (UI interne),
# pas de dépendance supplémentaire. Activé explicitement par l'env.
if os.environ.get('DJANGO_SERVE_STATIC') == '1':
    from django.conf import settings
    from django.views.static import serve as _static_serve

    urlpatterns += [
        re_path(r'^static/(?P<path>.*)$', _static_serve,
                {'document_root': settings.STATIC_ROOT}),
    ]
