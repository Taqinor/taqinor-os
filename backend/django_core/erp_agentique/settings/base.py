"""
Django settings for erp_agentique project.
Base settings - shared across all environments.
"""

import os
import sys
import warnings
from pathlib import Path
from datetime import timedelta

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent.parent

# SECURITY WARNING: keep the secret key used in production secret!
_DEBUG_FLAG = os.environ.get('DJANGO_DEBUG', 'True').lower() in ('true', '1', 'yes')
SECRET_KEY = os.environ.get('DJANGO_SECRET_KEY', 'django-insecure-change-me' if _DEBUG_FLAG else '')

if not _DEBUG_FLAG and (not SECRET_KEY or SECRET_KEY == 'django-insecure-change-me'):
    raise RuntimeError(
        "La variable d'environnement DJANGO_SECRET_KEY est obligatoire en production."
    )

if _DEBUG_FLAG and SECRET_KEY == 'django-insecure-change-me':
    warnings.warn(
        "SECRET_KEY par défaut détectée. Générez une vraie clé avec :\n"
        "  python -c \"from django.core.management.utils import "
        "get_random_secret_key; print(get_random_secret_key())\"",
        stacklevel=1,
    )

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = _DEBUG_FLAG

ALLOWED_HOSTS = os.environ.get('DJANGO_ALLOWED_HOSTS', 'localhost,127.0.0.1').split(',')

# Origines de confiance CSRF (obligatoire derrière HTTPS : Django vérifie
# l'Origin des POST). Liste séparée par des virgules, schéma inclus,
# ex. CSRF_TRUSTED_ORIGINS=https://taqinor-os.example.com
CSRF_TRUSTED_ORIGINS = [
    o.strip() for o in os.environ.get('CSRF_TRUSTED_ORIGINS', '').split(',')
    if o.strip()
]

# Application definition
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    # Third-party apps
    'rest_framework',
    'rest_framework_simplejwt',
    'rest_framework_simplejwt.token_blacklist',
    'corsheaders',
    # YAPIC5 — génération de schéma OpenAPI 3 (management command `spectacular`
    # + templates Swagger/ReDoc). Requis par DEFAULT_SCHEMA_CLASS ci-dessous.
    'drf_spectacular',
    # Local apps
    # App de fondation : modèles abstraits, mixins, bus d'événements
    # (core.events), portée des enregistrements (core.scoping) et fondation IA
    # (core.ai — interfaces de fournisseurs IA NO-OP par défaut). Aucun modèle
    # concret → aucune migration. N'importe que vers le bas (import-linter).
    'core',
    'authentication',
    'apps.stock',
    'apps.crm',
    'apps.ventes',
    'apps.reporting',
    'apps.parametres',
    'apps.roles',
    'apps.installations',
    'apps.sav',
    'apps.outillage',
    'apps.ged',
    'apps.records',
    'apps.customfields',
    'apps.documents',
    'apps.audit',
    # N97 — import/export réutilisable. Enregistré pour exposer la commande
    # de gestion `export_company_data` (aucun modèle, donc aucune migration).
    'apps.dataimport',
    # N50/N51/N52 — supervision de la production (monitoring) des systèmes
    # installés. Interface fournisseur swappable (no-op par défaut, squelette
    # FusionSolar) ; tout no-ope tant que rien n'est configuré.
    'apps.monitoring',
    # N75 — moteur de notifications unifié (in-app + canaux existants).
    'apps.notifications',
    # N72 / N73 — moteur d'automatisations sans code (règles + approbations).
    'apps.automation',
    # N89 — API publique REST (clés API, scopes, webhooks signés).
    'apps.publicapi',
    # ODX9/ODX10 — Marketing (Email/SMS Marketing + Automation + Surveys +
    # Events + fidélité). Sorti de compta en préservant les tables physiques
    # (SeparateDatabaseAndState). Chargé AVANT compta : le shim de ré-export
    # de compta.models importe apps.marketing.models.
    'apps.marketing',
    # ODX11 — Appels d'offres (marchés publics/privés, FG222–227). Sorti de
    # compta en préservant les tables physiques (SeparateDatabaseAndState).
    # Chargé AVANT compta : le shim de ré-export de compta.models importe
    # apps.ao.models.
    'apps.ao',
    # ODX12 — Portail self-service client (FG228–233). Sorti de compta en
    # préservant les tables physiques (SeparateDatabaseAndState). Chargé AVANT
    # compta : le shim de ré-export de compta.models importe apps.portail.models.
    'apps.portail',
    # FG107-FG121 — Comptabilité générale (plan CGNC, journaux, écritures en
    # partie double, états de synthèse). Auto-écritures OFF par défaut.
    'apps.compta',
    # FLOTTE1 — Gestion de flotte (véhicules immatriculés + engins roulants).
    # Module interne multi-société, entièrement additif.
    'apps.flotte',
    # AG1 — Catalogue d'actions agentiques (déclarées en code, aucun modèle).
    # Expose ce que l'agent peut proposer au caller, filtré par permission +
    # société. Métadonnées seulement ; l'exécution re-vérifie côté endpoint.
    'apps.agent',
    # Group S — Messagerie interne d'équipe (« Discuss ») : DM + canaux,
    # pièces jointes/voix, mentions, réactions, partage d'enregistrement.
    # Multi-tenant strict ; temps réel par polling (pas de WebSocket en v1).
    'apps.chat',
    # Modules ERP greenfield (fondations) — multi-société, additifs, scopés
    # société côté serveur. RH (dossier employé master DC29), Paie (paramètres
    # CNSS/AMO/IR), Gestion de projet (multi-chantiers), Contrats (CLM), QHSE
    # (NCR/CAPA), Base de connaissances, Réclamations & litiges.
    'apps.rh',
    'apps.paie',
    'apps.gestion_projet',
    'apps.contrats',
    'apps.qhse',
    'apps.kb',
    'apps.litiges',
    # XPOS1 — Vente comptoir (point of sale, accessoires).
    'apps.pos',
    # ARC17 — Répertoire unifié des tiers (res.partner). COUCHE FONDATION :
    # ne dépend d'aucune app de domaine ; les domaines la référenceront
    # (ARC18/19). Contrat import-linter `tiers-is-a-base-layer`.
    'apps.tiers',
    # NTSEC — Fondation Identité & accès (SSO/SCIM/politiques réseau &
    # session). N'importe aucune app métier ; scopée société côté serveur.
    # NTSEC11 y livre l'allowlist IP/CIDR (NetworkPolicy + middleware inerte
    # par défaut).
    'apps.identity',
    # XPLT21 — Softphone VoIP intégré (SIP/WebRTC, gated). Interface
    # fournisseur SWAPPABLE (NoOp par défaut) — additif, company-scopé.
    'apps.voip',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'corsheaders.middleware.CorsMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    # SCA43 / NTPLT16 — mémo de config société PAR REQUÊTE (contextvar). Ouvre un
    # scope de cache autour de chaque requête pour que les accesseurs de config
    # (CompanyProfile/DocumentTemplates/identité/TVA) lisent la config une seule
    # fois quel que soit le nombre de devis sérialisés (dé-N+1 de la liste). Hors
    # requête (Celery/PDF) → aucun scope → comportement historique inchangé.
    'core.request_cache.RequestConfigCacheMiddleware',
    # ODX4 — 404 sur les endpoints d'un module désactivé pour la société.
    # Défaut = actif (aucun 404 nouveau sans toggle). Placé après l'auth Django ;
    # résout lui-même le JWT DRF best-effort (aucun blocage sans jeton valide).
    'core.permissions.DisabledModuleMiddleware',
    # SCA18 — 403 sur les appels API d'un tenant suspendu/en fermeture (défaut
    # actif : aucun blocage sans société non-active). Placé après l'auth Django ;
    # résout le JWT DRF best-effort, superuser + endpoints /auth exemptés.
    # Porte la requête courante pour la capture du Journal d'activité (Feature G).
    'apps.audit.middleware.AuditActorMiddleware',
    # NTPLT1 — pose le GUC Postgres app.current_company par requête (fondation
    # RLS, défense en profondeur multi-tenant). NO-OP TOTAL sans le flag env
    # POSTGRES_RLS_ENABLED=1 (défaut OFF) : aucune requête SQL supplémentaire.
    'core.tenant_context.TenantContextMiddleware',
    # NTSEC11 — allowlist IP/CIDR par société. INERTE par défaut : ne bloque
    # ni ne journalise rien tant qu'une société n'a pas de NetworkPolicy en
    # mode monitor/enforce. Endpoints publics jamais soumis.
    'apps.identity.middleware.NetworkPolicyMiddleware',
    # NTPLT43/44/51 — observabilité par requête (request_id, contexte tenant,
    # durée). Placé en DERNIER : mesure la durée au plus près de la vue. OPT-IN —
    # sans LOG_FORMAT=json / SLOW_REQUEST_MS / scrape /metrics, il ne fait que
    # poser un contextvar + deux lectures d'horloge (coût négligeable) et pose
    # l'en-tête X-Request-ID sur la réponse.
    'core.observability.RequestObservabilityMiddleware',
]

ROOT_URLCONF = 'erp_agentique.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
    {
        # Moteur Jinja2 pour les templates PDF (WeasyPrint)
        'BACKEND': 'django.template.backends.jinja2.Jinja2',
        'DIRS': [BASE_DIR / 'templates' / 'pdf'],
        'APP_DIRS': False,
        'OPTIONS': {
            'environment': 'erp_agentique.jinja2.environment',
        },
    },
]

WSGI_APPLICATION = 'erp_agentique.wsgi.application'

# Database
# YOPSB7 — CONN_MAX_AGE : sans lui, chaque requête HTTP/Celery ouvre/ferme une
# connexion Postgres. Avec plusieurs workers Django (threads) + workers Celery
# + FastAPI, on peut approcher `max_connections` sous charge. `CONN_MAX_AGE`
# (secondes, 0=désactivé/comportement historique) réutilise les connexions ;
# `CONN_HEALTH_CHECKS` revalide la connexion avant réemploi (évite de servir
# une connexion morte après un redémarrage Postgres). Pilotable par env :
# DB_CONN_MAX_AGE (défaut 60s). Voir docs/CODEMAP.md §7 pour la formule
# (répliques × workers × threads) < max_connections.
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': os.environ.get('DB_NAME', 'erp_db'),
        'USER': os.environ.get('DB_USER', 'erp_user'),
        'PASSWORD': os.environ.get('DB_PASSWORD', 'erp_password'),
        'HOST': os.environ.get('DB_HOST', 'db'),
        'PORT': os.environ.get('DB_PORT', '5432'),
        'CONN_MAX_AGE': int(os.environ.get('DB_CONN_MAX_AGE', '60')),
        'CONN_HEALTH_CHECKS': True,
        # NTPLT18 — statement_timeout par défaut au niveau connexion. Sans lui,
        # une requête ORM folle (jointure oubliée, LIKE non indexé sur des
        # millions de lignes) peut épingler un worker gunicorn indéfiniment.
        # Postgres tue tout statement dépassant ce délai (ms) — le worker se
        # libère au lieu de geler. Pilotable par DB_STATEMENT_TIMEOUT_MS (défaut
        # 30 000 = 30 s) ; 0 = désactivé (comportement historique). Les jobs
        # légitimement longs élargissent explicitement le délai via
        # `core.db_guards.statement_timeout()` (SET LOCAL). Les dumps/restores
        # passent par pg_dump/pg_restore (subprocess) et ne sont donc PAS
        # soumis à cette OPTION — aucun risque de les tronquer.
        'OPTIONS': {
            'options': (
                f"-c statement_timeout="
                f"{int(os.environ.get('DB_STATEMENT_TIMEOUT_MS', '30000'))}"
            ),
        } if int(os.environ.get('DB_STATEMENT_TIMEOUT_MS', '30000')) > 0 else {},
    }
}

# NTPLT3 — Rôle applicatif non-BYPASSRLS pour le RUNTIME quand RLS est actif.
#
# Quand POSTGRES_RLS_ENABLED=1 ET DB_APP_USER est défini, le serveur
# Django/Celery se connecte avec le rôle APPLICATIF (app_rls, sans BYPASSRLS —
# cf. backend/db/rls_roles.sql) : il est alors PHYSIQUEMENT soumis aux policies
# RLS (NTPLT2), et le GUC app.current_company (NTPLT1) décide des lignes
# visibles. Une fuite cross-tenant devient impossible même via SQL brut.
#
# MAIS les chemins OWNER (migrations, seed, dumps, la commande `rls` elle-même,
# les tests) DOIVENT rester sur le rôle OWNER/BYPASSRLS pour voir toutes les
# lignes de tous les tenants — sinon `migrate`/`core.dump_database` échoueraient
# flag ON. On garde donc l'OWNER pour ces commandes de gestion, l'app role
# UNIQUEMENT pour le service runtime. Défaut OFF : sans le flag, la config est
# byte-identique à ci-dessus (l'owner partout, aucun rôle applicatif requis).
_RLS_ENABLED = os.environ.get('POSTGRES_RLS_ENABLED', '0') == '1'
_DB_APP_USER = os.environ.get('DB_APP_USER', '').strip()
# Commandes qui exigent le rôle OWNER (DDL / accès cross-tenant complet).
_OWNER_COMMANDS = frozenset({
    'migrate', 'makemigrations', 'sqlmigrate', 'dbshell', 'flush',
    'loaddata', 'dumpdata', 'test', 'rls', 'dump_database', 'restore_drill',
    'collectstatic', 'createsuperuser', 'shell', 'showmigrations',
})


def _running_owner_command() -> bool:
    """True si l'invocation courante est une commande OWNER (manage.py <cmd>).

    Détection par sys.argv (le seed passe par des commandes `seed_*`, toutes
    couvertes par le préfixe). Hors manage.py (gunicorn/celery) → False, donc
    le service runtime prend bien le rôle applicatif.
    """
    argv = sys.argv
    if len(argv) < 2 or 'manage.py' not in argv[0]:
        # gunicorn/celery/asgi : pas une commande manage.py → runtime app role.
        return False
    cmd = argv[1]
    return cmd in _OWNER_COMMANDS or cmd.startswith('seed')


if _RLS_ENABLED and _DB_APP_USER and not _running_owner_command():
    DATABASES['default']['USER'] = _DB_APP_USER
    DATABASES['default']['PASSWORD'] = os.environ.get('DB_APP_PASSWORD', '')

# Password validation
AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

# Custom User Model
AUTH_USER_MODEL = 'authentication.CustomUser'

# Internationalization
LANGUAGE_CODE = 'fr-fr'
TIME_ZONE = 'UTC'
USE_I18N = True
USE_TZ = True

# Static files
STATIC_URL = 'static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'

# Default primary key field type
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# YOPSB14 — limites d'upload applicatives (Django) alignées sur
# `client_max_body_size 15m` déjà posé dans backend/nginx/nginx.conf. Sans
# elles, Django n'a AUCUNE limite propre : un upload énorme accepté par
# nginx pourrait épuiser la mémoire du worker (bufferisation complète avant
# rejet). 15 Mo = 15 * 1024 * 1024 octets, pilotable par env pour un futur
# réglage sans redéploiement de code.
DATA_UPLOAD_MAX_MEMORY_SIZE = int(
    os.environ.get('DATA_UPLOAD_MAX_MEMORY_SIZE', str(15 * 1024 * 1024)))
FILE_UPLOAD_MAX_MEMORY_SIZE = int(
    os.environ.get('FILE_UPLOAD_MAX_MEMORY_SIZE', str(15 * 1024 * 1024)))
DATA_UPLOAD_MAX_NUMBER_FIELDS = int(
    os.environ.get('DATA_UPLOAD_MAX_NUMBER_FIELDS', '2000'))

# Django REST Framework
REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': (
        'authentication.cookie_auth.CookieJWTAuthentication',
    ),
    'DEFAULT_PERMISSION_CLASSES': (
        'rest_framework.permissions.IsAuthenticated',
    ),
    # YAPIC1 — pagination partagée avec plafond dur : page_size=50 par défaut,
    # ``?page_size=`` autorisé, max_page_size=200 (plafond serveur). L'enveloppe
    # count/next/previous/results reste identique à DRF.
    'DEFAULT_PAGINATION_CLASS': 'core.pagination.StandardPagination',
    'PAGE_SIZE': 50,
    # NTPLT42 — throttle applicatif PAR TENANT posé en défaut global : protège
    # l'instance partagée du script fou d'UN client sans toucher les autres. Le
    # budget vient de DEFAULT_THROTTLE_RATES['tenant'] (env TENANT_RATE_LIMIT).
    # Rate None (env '0'/vide, ou sous les tests) = throttle inactif → aucun
    # changement de comportement. Les surfaces anonymes (login/register) gardent
    # leurs throttles dédiés (le throttle tenant se désactive sans société).
    'DEFAULT_THROTTLE_CLASSES': (
        'core.throttling.TenantRateThrottle',
    ),
    # Fix 1 : taux de throttle par scope (appliqués per-view)
    'DEFAULT_THROTTLE_RATES': {
        'login': '5/minute',   # 5 tentatives/min par IP sur /token/
        'register': '3/hour',  # 3 inscriptions/h par IP sur /register/
        # N89 — débit de l'API publique, par CLÉ d'API (pas par IP).
        'publicapi': '120/minute',
        # XGED7 — dépôt public par jeton (GED), par IP + jeton.
        'ged_public_depot': '30/minute',
        # XPLT4 — webhook entrant automatisation, par jeton.
        'automation_webhook': '60/minute',
        # XSAL8 — scan de carte de visite (OCR), par utilisateur authentifié.
        'crm_ocr_scan': '20/hour',
        # QX41 — scopes des throttles publics jusqu'ici codés inline, désormais
        # source de vérité UNIQUE ici (les classes lisent settings en priorité,
        # repli sur leur défaut). ``public_sharelink`` : liens publics
        # devis/facture/proposition (par IP+jeton) ; ``public_livechat`` :
        # ouverture de session chat public (par IP).
        'public_sharelink': '30/minute',
        'public_livechat': '30/minute',
        # NTPLT42 — budget par société (env TENANT_RATE_LIMIT, défaut 1200/min).
        # '0'/vide → None = throttle tenant désactivé (rempli plus bas, après la
        # définition de TESTING, où il est forcé off pour ne pas fausser la suite).
        'tenant': None,
    },
    # YDATA9 — DRF sérialise déjà les `Decimal` en string par défaut (c'est
    # la valeur par défaut de DRF), mais rien ne le VERROUILLAIT explicitement
    # dans ce repo : un changement accidentel de ce réglage romprait la
    # précision des montants à la frontière API (un float JSON perd des
    # décimales). Posé explicitement pour que ce comportement soit un choix
    # documenté, testé, jamais un défaut implicite qui pourrait dériver.
    'COERCE_DECIMAL_TO_STRING': True,
    # YAPIC5 — schéma OpenAPI 3 auto-généré (drf-spectacular) : remplace le
    # AutoSchema DRF par défaut pour que /api/schema/ + Swagger/ReDoc reflètent
    # RÉELLEMENT les viewsets enregistrés (FG105 = page FR écrite à la main,
    # ne bouge pas, reste la doc de référence de l'API PUBLIQUE api/public/).
    'DEFAULT_SCHEMA_CLASS': 'drf_spectacular.openapi.AutoSchema',
    # YAPIC7 — stratégie de versionnement UNIQUE et documentée
    # (docs/api-conventions.md). URLPathVersioning : `request.version` vaut
    # 'v1' sur TOUTE vue, ancienne ('api/django/...') ou nouvelle
    # ('api/v1/...') — AUCUNE route ne capture de segment `<version>` dans
    # l'URL (préfixes littéraux dans erp_agentique/urls.py, délibérément :
    # une capture injecterait un kwarg `version` dans chaque vue), donc
    # `URLPathVersioning.determine_version` retombe systématiquement sur
    # DEFAULT_VERSION. Le comportement de rejet d'une version hors
    # ALLOWED_VERSIONS (propre, via `exceptions.NotFound`, jamais une 404
    # Django brute) est prouvé en isolation par
    # tests/test_api_versioning.py — pas par une route réelle.
    'DEFAULT_VERSIONING_CLASS': 'rest_framework.versioning.URLPathVersioning',
    'DEFAULT_VERSION': 'v1',
    'ALLOWED_VERSIONS': ('v1',),
}

# YAPIC5 — réglages drf-spectacular. COMPONENT_SPLIT_REQUEST distingue les
# schémas Request/Response (champs read_only exclus du corps de requête dans
# le schéma généré). SERVE_PERMISSIONS gate /api/schema/, /api/docs/ et
# /api/redoc/ derrière IsAuthenticated (pas d'exposition anonyme du contrat
# d'API complet). SORT_OPERATIONS désactivé pour préserver l'ordre naturel de
# `erp_agentique/urls.py` (plus lisible par app).
SPECTACULAR_SETTINGS = {
    'TITLE': 'TAQINOR OS — API',
    'DESCRIPTION': (
        "Schéma OpenAPI 3 auto-généré des ViewSets DRF de l'ERP interne "
        "(api/django/...). L'API publique par clé (api/public/...) garde sa "
        "propre page de référence FR écrite à la main (apps/publicapi/docs.py)."
    ),
    'VERSION': '1.0.0',
    'SERVE_INCLUDE_SCHEMA': False,
    'COMPONENT_SPLIT_REQUEST': True,
    'SERVE_PERMISSIONS': ['rest_framework.permissions.IsAuthenticated'],
}

# Simple JWT Configuration
SIMPLE_JWT = {
    # ERR87 — durée de vie courte du jeton d'accès (30 min). Le logout met le
    # refresh en liste noire mais ne peut pas révoquer un access déjà émis : on
    # borne donc sa fenêtre de validité. Le rafraîchissement transparent
    # (CookieTokenRefreshView + ROTATE_REFRESH_TOKENS) renouvelle l'access depuis
    # le cookie refresh, donc la session utilisateur reste fluide.
    'ACCESS_TOKEN_LIFETIME': timedelta(minutes=30),
    'REFRESH_TOKEN_LIFETIME': timedelta(days=7),
    'ROTATE_REFRESH_TOKENS': True,
    'BLACKLIST_AFTER_ROTATION': True,
    'UPDATE_LAST_LOGIN': True,
    'ALGORITHM': 'HS256',
    'SIGNING_KEY': SECRET_KEY,
    'VERIFYING_KEY': None,
    'AUDIENCE': None,
    'ISSUER': None,
    'JWK_URL': None,
    'LEEWAY': 0,
    'AUTH_HEADER_TYPES': ('Bearer',),
    'AUTH_HEADER_NAME': 'HTTP_AUTHORIZATION',
    'USER_ID_FIELD': 'id',
    'USER_ID_CLAIM': 'user_id',
    'USER_AUTHENTICATION_RULE': 'rest_framework_simplejwt.authentication.default_user_authentication_rule',
    'AUTH_TOKEN_CLASSES': ('rest_framework_simplejwt.tokens.AccessToken',),
    'TOKEN_TYPE_CLAIM': 'token_type',
    'TOKEN_USER_CLASS': 'rest_framework_simplejwt.models.TokenUser',
    'JTI_CLAIM': 'jti',
    'SLIDING_TOKEN_REFRESH_EXP_CLAIM': 'refresh_exp',
    'SLIDING_TOKEN_LIFETIME': timedelta(minutes=5),
    'SLIDING_TOKEN_REFRESH_LIFETIME': timedelta(days=1),
}

# Redis Cache Configuration
# SCA10 — le cache Django cible désormais une instance Redis DÉDIÉE
# (`redis_cache`, docker-compose.yml), séparée du broker Celery (`redis`,
# db0) qui garde `noeviction` + persistance AOF. REDIS_CACHE_HOST/
# REDIS_CACHE_PORT (env) retombent sur REDIS_HOST/REDIS_PORT si absents —
# RÉTRO-COMPATIBLE : sans ces nouvelles variables posées, CACHES pointe
# EXACTEMENT vers l'ancienne cible (même hôte que le broker, db1),
# comportement byte-identique à avant SCA10.
CACHES = {
    "default": {
        "BACKEND": "django_redis.cache.RedisCache",
        "LOCATION": (
            f"redis://{os.environ.get('REDIS_CACHE_HOST', os.environ.get('REDIS_HOST', 'redis'))}"
            f":{os.environ.get('REDIS_CACHE_PORT', os.environ.get('REDIS_PORT', '6379'))}/1"
        ),
        "OPTIONS": {
            "CLIENT_CLASS": "django_redis.client.DefaultClient",
            # NTPLT24 — résilience Redis : une panne du cache dégrade en
            # cache-miss (get→None, set→no-op) AU LIEU de propager une
            # ConnectionError qui renverrait 500 sur TOUT l'ERP (chaque vue qui
            # lit/écrit le cache). django-redis journalise l'exception ignorée
            # via le logger 'django_redis' (LOGGING ci-dessous) pour ne pas
            # masquer une panne réelle. Argument SLA : une brique de cache qui
            # tombe ne couche pas le produit.
            "IGNORE_EXCEPTIONS": True,
        }
    }
}
# NTPLT24 — journaliser (WARNING) les exceptions Redis ignorées par django-redis
# au lieu de les avaler en silence. Fusionné avec toute config LOGGING existante.
DJANGO_REDIS_LOG_IGNORED_EXCEPTIONS = True
DJANGO_REDIS_LOGGER = 'django_redis'

# CORS Configuration
CORS_ALLOWED_ORIGINS = [
    "http://localhost:3000",
    "http://localhost",
]
CORS_ALLOW_CREDENTIALS = True

# Celery Configuration
CELERY_BROKER_URL = f"redis://{os.environ.get('REDIS_HOST', 'redis')}:{os.environ.get('REDIS_PORT', '6379')}/0"
CELERY_RESULT_BACKEND = CELERY_BROKER_URL
# G9 — Celery Beat raisonne en Africa/Casablanca (cf. erp_agentique/celery.py).
# Le planning (beat_schedule) est défini dans celery.py ; on fige ici le fuseau
# côté CELERY pour cohérence si Beat est lancé via les settings.
CELERY_TIMEZONE = 'Africa/Casablanca'
CELERY_ENABLE_UTC = False

# YOPSB8 — réglages de production durcis. Sans limite de temps ni garde de
# perte de worker, une tâche bloquée (ex. rendu PDF WeasyPrint qui hangs)
# épingle un worker indéfiniment. Le rendu PDF mesuré est ~3-4,5s : marge
# large avec 120s/180s.
#   * CELERY_TASK_SOFT_TIME_LIMIT — lève SoftTimeLimitExceeded dans la tâche
#     (peut être attrapée pour un nettoyage propre) après 120s ;
#   * CELERY_TASK_TIME_LIMIT — tue le worker process après 180s (dur) ;
#   * CELERY_TASK_ACKS_LATE — ack APRÈS exécution (pas avant) : une tâche
#     interrompue par un crash worker est re-livrée, jamais perdue ;
#   * CELERY_TASK_REJECT_ON_WORKER_LOST — si le worker meurt EN COURS
#     d'exécution, la tâche est explicitement REJETÉE (donc re-livrée via
#     acks_late) plutôt que silencieusement perdue ;
#   * CELERY_WORKER_PREFETCH_MULTIPLIER=1 — équité : un worker ne pré-charge
#     qu'UNE tâche à la fois (pas de accaparement de la queue par un worker
#     lent pendant qu'un autre est inactif).
#
# IMPORTANT (documenté aussi dans docs/CODEMAP.md) : `acks_late` +
# `reject_on_worker_lost` signifient qu'UNE tâche à effet de bord PEUT être
# relancée après un crash worker — toute tâche Celery DOIT donc rester
# idempotente (les tâches ventes existantes le sont déjà via
# `_idempotent_cached_key`).
CELERY_TASK_SOFT_TIME_LIMIT = 120
CELERY_TASK_TIME_LIMIT = 180
CELERY_TASK_ACKS_LATE = True
CELERY_TASK_REJECT_ON_WORKER_LOST = True
CELERY_WORKER_PREFETCH_MULTIPLIER = 1

# YOPSB9 — isolation des queues Celery par classe de travail. Sans ceci,
# toutes les tâches (rendu PDF interactif déclenché par un commercial, digests
# planifiés, sweeps de rétention, webhooks) partagent la queue `default` : un
# batch de nuit peut affamer un rendu PDF synchrone. Trois queues :
#   * `interactive` — rendus PDF déclenchés par une action utilisateur
#     synchrone (ventes.generate_*_pdf) + transcription vocale (chat.transcribe_*) ;
#   * `scheduled` — tout job planifié via Celery Beat (voir beat_schedule
#     dans erp_agentique/celery.py — TOUTES les tâches qui y apparaissent
#     sont, par construction, des jobs planifiés) ;
#   * `default` — le reste (webhooks entrants, tâches déclenchées par un
#     signal/événement synchrone non listé ci-dessus).
#
# AUCUN changement de comportement par défaut : une seule commande worker
# (`celery -A erp_agentique worker`) consomme TOUJOURS les 3 queues sans
# argument `-Q` (Celery route selon `task_routes` mais un worker sans `-Q`
# explicite écoute la/les queue(s) par défaut UNIQUEMENT — voir
# docs/CODEMAP.md pour la commande `-Q default,interactive,scheduled` à
# utiliser pour que le worker unique consomme bien les 3).
CELERY_TASK_ROUTES = {
    'ventes.generate_devis_pdf': {'queue': 'interactive'},
    'ventes.generate_facture_pdf': {'queue': 'interactive'},
    # SCA41 — export xlsx volumineux déclenché par une action utilisateur → même
    # queue `interactive` que les rendus PDF (pilote de NTPLT29/30).
    'ventes.build_async_export': {'queue': 'interactive'},
    'chat.transcribe_voice_attachment': {'queue': 'interactive'},
    # Toutes les tâches planifiées (beat_schedule) → `scheduled`.
    'ventes.check_overdue_factures': {'queue': 'scheduled'},
    'ventes.expire_stale_devis': {'queue': 'scheduled'},
    'ventes.relance_reminders': {'queue': 'scheduled'},
    'ventes.devis_followup_nudges': {'queue': 'scheduled'},
    'ventes.releve_mensuel_reminders': {'queue': 'scheduled'},
    'crm.appointment_reminders': {'queue': 'scheduled'},
    'crm.recycler_leads_non_travailles': {'queue': 'scheduled'},
    'notifications.daily_digest': {'queue': 'scheduled'},
    'notifications.weekly_digest': {'queue': 'scheduled'},
    'notifications.sweep_daily': {'queue': 'scheduled'},
    'notifications.reveiller_snoozes': {'queue': 'scheduled'},
    'automation.time_triggers_daily': {'queue': 'scheduled'},
    'reporting.email_saved_reports': {'queue': 'scheduled'},
    'reporting.evaluate_kpi_alertes': {'queue': 'scheduled'},
    'reporting.controle_integrite': {'queue': 'scheduled'},
    # NTPLT6 — snapshot d'usage tenant (beat 01:45) → queue planifiée.
    'core.snapshot_tenant_usage': {'queue': 'scheduled'},
    'core.dispatch_outbox': {'queue': 'scheduled'},
    'core.ensure_partitions': {'queue': 'scheduled'},
    'core.scan_live_isolation': {'queue': 'scheduled'},
    'ged.purge_corbeille_echue': {'queue': 'scheduled'},
    'ged.signature_relances_expiration': {'queue': 'scheduled'},
    'ged.verifier_integrite_archives': {'queue': 'scheduled'},
    'ged.notifier_emetteurs_expiration_signature': {'queue': 'scheduled'},
    'contrats.generer_factures_recurrentes_dues': {'queue': 'scheduled'},
    'contrats.reconductions_et_alertes_daily': {'queue': 'scheduled'},
    'chat.send_scheduled_messages': {'queue': 'scheduled'},
    'chat.send_due_reminders': {'queue': 'scheduled'},
    'chat.retention_sweep': {'queue': 'scheduled'},
    'installations.rappel_rdv_j1': {'queue': 'scheduled'},
    'installations.meteo_planning_j3': {'queue': 'scheduled'},
    'rh.alertes_expiration': {'queue': 'scheduled'},
    'rh.alertes_cdd': {'queue': 'scheduled'},
    'sav.generer_visites_dues_quotidien': {'queue': 'scheduled'},
    'stock.recompute_reordering': {'queue': 'scheduled'},
    'core.dump_database': {'queue': 'scheduled'},
    'core.restore_drill': {'queue': 'scheduled'},
    'core.purge_backups': {'queue': 'scheduled'},
    'core.run_retention': {'queue': 'scheduled'},
    'core.beat_heartbeat': {'queue': 'scheduled'},
    'monitoring.balayage_quotidien': {'queue': 'scheduled'},
    'stock.expiration_alerts': {'queue': 'scheduled'},
    'stock.relancer_bcf_en_retard': {'queue': 'scheduled'},
    'crm.escalader_rappels_demandes': {'queue': 'scheduled'},
    # QX11/QX36 — rappels d'échéance + relevés côté ventes.
    'ventes.pre_echeance_reminders': {'queue': 'scheduled'},
    'ventes.devis_a_facturer_reminder': {'queue': 'scheduled'},
    # QX — moteur de relance d'engagement + relève des boîtes entrantes.
    'ventes.engagement_followup_engine': {'queue': 'scheduled'},
    'ventes.poll_inbound_mailboxes': {'queue': 'scheduled'},
    'ged.poll_mail_intake': {'queue': 'scheduled'},
    # Marketing/compta — séquences, campagnes, communications, dormants, A/B.
    'compta.executer_sequences_relance': {'queue': 'scheduled'},
    'compta.envoyer_campagnes_planifiees': {'queue': 'scheduled'},
    'compta.envoyer_communications_evenement': {'queue': 'scheduled'},
    'compta.recalculer_dormants_marketing': {'queue': 'scheduled'},
    'compta.traiter_posts_sociaux': {'queue': 'scheduled'},
    'compta.decider_gagnants_ab': {'queue': 'scheduled'},
    # KB — balayages lectures obligatoires / articles périmés.
    'kb.sweep_lectures_obligatoires': {'queue': 'scheduled'},
    'kb.sweep_articles_perimes': {'queue': 'scheduled'},
    # QHSE — escalade des check-ins en retard.
    'qhse.escalader_checkins_en_retard': {'queue': 'scheduled'},
    # Notifications — balayage des leads chauds.
    'notifications.sweep_hot_leads': {'queue': 'scheduled'},
    # NTPLT27 — 4e queue `bulk` pour le travail de masse (imports dataimport,
    # exports planifiés volumineux, backfills, seed à l'échelle). Un import de
    # 100 000 lignes ne doit plus retarder un digest planifié ni un rendu PDF
    # interactif : il part sur `bulk`, consommée à part. Routage par CONVENTION
    # de nommage (fnmatch — Celery matche les clés glob de task_routes) pour
    # couvrir les tâches de masse présentes ET futures sans les énumérer une à
    # une : tout nom `*.import_*`, `*.export_bulk_*`, `*.backfill_*`,
    # `*.seed_*`. Aucune tâche existante ne matche ces motifs aujourd'hui —
    # ajout purement additif, zéro changement de routage pour l'existant.
    '*.import_*': {'queue': 'bulk'},
    '*.backfill_*': {'queue': 'bulk'},
    '*.seed_*': {'queue': 'bulk'},
    '*.export_bulk_*': {'queue': 'bulk'},
}
# Le worker par défaut (sans -Q) écoute la queue nommée dans
# task_default_queue — on la garde `default` pour ne rien casser ; en
# production, lancer le worker avec `-Q default,interactive,scheduled,bulk`
# (NTPLT27 ajoute `bulk`) pour qu'un worker UNIQUE consomme bien les 4
# (comportement mono-worker inchangé tant que ce -Q n'est pas explicitement
# restreint — voir docs/deploy-prod / docker-compose.prod.yml).
CELERY_TASK_DEFAULT_QUEUE = 'default'

# Email — django-anymail (N87). Compte d'envoi configurable : Brevo (ex-
# Sendinblue) via BREVO_API_KEY, ou SendGrid (héritage), ou SMTP. SANS clé,
# EMAIL_BACKEND reste le backend console → l'envoi est un NO-OP qui préserve le
# comportement actuel (aucun appel réseau, aucune exception). Pour activer
# Brevo en prod : EMAIL_BACKEND=anymail.backends.sendinblue.EmailBackend +
# BREVO_API_KEY=<clé> + DEFAULT_FROM_EMAIL=<expéditeur vérifié Brevo>.
ANYMAIL = {
    'SENDGRID_API_KEY': os.environ.get('SENDGRID_API_KEY', ''),
    # Clé API Brevo (anymail nomme ce backend « sendinblue »). Vide = NO-OP.
    'SENDINBLUE_API_KEY': os.environ.get('BREVO_API_KEY', ''),
}
EMAIL_BACKEND = os.environ.get(
    'EMAIL_BACKEND',
    'django.core.mail.backends.console.EmailBackend'  # console en dev, anymail en prod
)
DEFAULT_FROM_EMAIL = os.environ.get('DEFAULT_FROM_EMAIL', 'noreply@erp.local')
CONTACT_EMAIL = os.environ.get('CONTACT_EMAIL', 'reda.kasri@taqinor.ma')

# N88 — Capture des emails entrants. Sans secret/host configuré, la capture est
# un NO-OP réseau (aucune connexion ouverte). BREVO_INBOUND_SECRET sécurise un
# futur webhook inbound Brevo ; INBOUND_EMAIL_HOST un futur relevé IMAP.
BREVO_INBOUND_SECRET = os.environ.get('BREVO_INBOUND_SECRET', '')
INBOUND_EMAIL_HOST = os.environ.get('INBOUND_EMAIL_HOST', '')

# Public contact form — PARKED by default. When off, the /api/django/contact/
# endpoint returns 404 and sends no email. Flip to '1' to re-enable (see CLAUDE.md).
CONTACT_FORM_ENABLED = os.environ.get('CONTACT_FORM_ENABLED', '0') == '1'

# XRH33 — public careers/recruitment page, PARKED (OFF) by default (same
# pattern as CONTACT_FORM_ENABLED). When off, both public rh careers
# endpoints (list + apply) return 404. Founder decision to expose (or not)
# recruitment publicly. Flip to '1' to re-enable.
CAREERS_ENABLED = os.environ.get('CAREERS_ENABLED', '0') == '1'

# Récepteur des leads du site public taqinor.ma (apps/crm/webhooks.py).
# Sans secret configuré, le endpoint répond 401 à tout — fermé par défaut.
WEBSITE_LEAD_WEBHOOK_SECRET = os.environ.get('WEBSITE_LEAD_WEBHOOK_SECRET', '')
# Tenant cible des leads web (id de Company) ; à défaut, la première Company.
WEBSITE_LEADS_COMPANY_ID = os.environ.get('WEBSITE_LEADS_COMPANY_ID') or None

# URL publique par DÉFAUT de la plateforme (page proposition/suivi client). Un
# tenant white-label pointe ses liens sur SON propre site (CompanyProfile.site_web,
# cf. quote_engine.builder) ; SITE_URL n'est que le repli plateforme/fondateur,
# configurable par déploiement (SCA29 — pas de marque en dur dans le code app).
SITE_URL = os.environ.get('SITE_URL', 'https://taqinor.ma')

# XMKT32 — Sync Meta Lead Ads → leads CRM (gated, API officielle, jamais de
# scraping). Sans META_LEAD_ADS_VERIFY_TOKEN, le webhook de vérification
# (GET hub.challenge) répond 404 ; sans META_LEAD_ADS_ACCESS_TOKEN, le POST
# de notification est un no-op silencieux (rien n'est créé). Voir
# apps/crm/webhooks.py::meta_lead_ads_webhook.
META_LEAD_ADS_VERIFY_TOKEN = os.environ.get('META_LEAD_ADS_VERIFY_TOKEN', '')
META_LEAD_ADS_ACCESS_TOKEN = os.environ.get('META_LEAD_ADS_ACCESS_TOKEN', '')
# Tenant cible des leads Meta Lead Ads (id de Company) ; à défaut, la
# première Company (même repli que WEBSITE_LEADS_COMPANY_ID).
META_LEAD_ADS_COMPANY_ID = os.environ.get('META_LEAD_ADS_COMPANY_ID') or None

# Stockage fichiers — MinIO / S3 (Phase 2 Sem. 4)
MINIO_ENDPOINT = os.environ.get('MINIO_ENDPOINT', 'minio:9000')
MINIO_ACCESS_KEY = os.environ.get('MINIO_ROOT_USER', 'erp_admin')
MINIO_SECRET_KEY = os.environ.get('MINIO_ROOT_PASSWORD', 'erp_minio_password')
MINIO_BUCKET_PDF = os.environ.get('MINIO_BUCKET_PDF', 'erp-pdf')
MINIO_BUCKET_UPLOADS = os.environ.get('MINIO_BUCKET_UPLOADS', 'erp-uploads')

# Branding entreprise (champs remplis via le dashboard Sem. 7)
ENTREPRISE_NOM = os.environ.get('ENTREPRISE_NOM', 'Mon Entreprise')
ENTREPRISE_ADRESSE = os.environ.get('ENTREPRISE_ADRESSE', '')
ENTREPRISE_EMAIL = os.environ.get('ENTREPRISE_EMAIL', '')
ENTREPRISE_TELEPHONE = os.environ.get('ENTREPRISE_TELEPHONE', '')
ENTREPRISE_COULEUR = os.environ.get('ENTREPRISE_COULEUR', '#2563EB')

# Quote PDF engine. When True (default), client quote PDFs are rendered by the
# vendored premium engine (apps.ventes.quote_engine). Set to '0' to fall back to
# the legacy ventes WeasyPrint quote PDF. Only affects QUOTES, never invoices.
USE_PREMIUM_QUOTE_ENGINE = os.environ.get('USE_PREMIUM_QUOTE_ENGINE', '1') != '0'

# ARC21 — DÉCISION founder-gated : Tiers comme source d'écriture de l'identité.
# OFF par défaut → comportement byte-identique à aujourd'hui (les modèles
# historiques restent maîtres, Tiers n'est qu'un miroir one-way ARC18/19/56).
# ON (transition) → double-écriture via apps.tiers.services (Tiers source,
# historique miroir lecture). Réversible ; à n'activer qu'après le dossier
# docs/decisions/ARC21-tiers-source-ecriture.md (vidage des doublons ARC20 +
# non-régression PDF/exports). NE PAS activer sans décision fondateur.
TIERS_SOURCE_ECRITURE = os.environ.get('TIERS_SOURCE_ECRITURE', '0') == '1'

# XFSM12 — trace d'étalonnage de l'instrument sur la fiche de recette IEC
# 62446-1 (CommissioningRecord.instrument_id). Paramétrable warn/block (défaut
# warn) : quand True, enregistrer une fiche référençant un instrument dont
# l'étalonnage FG80 est expiré est REFUSÉ (400) ; par défaut ce n'est qu'un
# avertissement non-bloquant côté client (le payload API le signale quand
# même via `instrument_etalonnage_expire`).
INSTRUMENT_ETALONNAGE_BLOQUANT = (
    os.environ.get('INSTRUMENT_ETALONNAGE_BLOQUANT', '0') == '1')

# GED12 — recherche sémantique documentaire (pgvector). KEY-GATED : OFF par
# défaut, donc l'indexation d'embeddings est un no-op (aucun appel/coût) et la
# recherche sémantique retombe sur le plein-texte GED11. Le founder l'active en
# posant GED_EMBEDDING_ENABLED=1 + la clé du provider d'embeddings.
GED_EMBEDDING_ENABLED = os.environ.get('GED_EMBEDDING_ENABLED', '0') == '1'

# GED25 — purge automatique de la corbeille (GED26 soft-delete). DRY-RUN PAR
# DÉFAUT : la tâche planifiée `ged.purge_corbeille_echue` ne SUPPRIME RIEN tant
# que GED_PURGE_AUTO_APPLY n'est pas explicitement à 1 (elle se contente de
# compter/logger). `GED_PURGE_GRACE_DAYS` est le délai de grâce (jours) qu'un
# document doit passer EN CORBEILLE avant de devenir éligible (défaut 30). Les
# gardes légales GED23 (write-once) / GED24 (legal hold) restent toujours
# respectées — un document protégé n'est jamais purgé.
GED_PURGE_AUTO_APPLY = os.environ.get('GED_PURGE_AUTO_APPLY', '0') == '1'
GED_PURGE_GRACE_DAYS = int(os.environ.get('GED_PURGE_GRACE_DAYS', '30'))

# YOPSB3 — purge GFS automatique des dumps Postgres (core.BackupRun
# kind=db_dump). DRY-RUN PAR DÉFAUT (même convention que GED_PURGE_AUTO_APPLY
# ci-dessus) : la tâche planifiée `core.purge_backups` ne supprime rien tant
# que BACKUP_PURGE_AUTO_APPLY n'est pas explicitement à 1. Schéma configurable
# (défauts codés) : BACKUP_RETENTION_DAILY=7, WEEKLY=4, MONTHLY=12 sont lus
# directement depuis l'environnement dans `core.backup._retention_settings`.
BACKUP_PURGE_AUTO_APPLY = os.environ.get('BACKUP_PURGE_AUTO_APPLY', '0') == '1'

# YOPSB10 — registre de rétention partagé (core.retention). DRY-RUN PAR
# DÉFAUT (même convention que GED_PURGE_AUTO_APPLY/BACKUP_PURGE_AUTO_APPLY
# ci-dessus) : la tâche planifiée `core.run_retention` transmet
# `apply_=False` à CHAQUE politique enregistrée tant que
# RETENTION_AUTO_APPLY n'est pas explicitement à 1 — aucune politique ne
# doit alors supprimer quoi que ce soit (contrat imposé à chaque politique).
RETENTION_AUTO_APPLY = os.environ.get('RETENTION_AUTO_APPLY', '0') == '1'

# GED33/GED34 — OCR de pièces + classification automatique. KEY-GATED : OFF par
# défaut → tout est un no-op déterministe (aucun appel réseau, aucun coût, aucune
# dépendance nouvelle). Le founder branchera un provider réel (Zhipu/…) en posant
# le flag + la clé. Tant que c'est OFF, l'extraction OCR et la classification IA
# se contentent de signaler « non disponible » sans rien inventer.
GED_OCR_ENABLED = os.environ.get('GED_OCR_ENABLED', '0') == '1'
GED_CLASSIFICATION_ENABLED = (
    os.environ.get('GED_CLASSIFICATION_ENABLED', '0') == '1')

# QK6 — OCR de la photo de facture/compteur captée par le site (webhook CRM).
# KEY-GATED : OFF par défaut → la photo est simplement jointe au lead (aucun
# appel réseau, aucun coût). Le founder l'active en posant le flag une fois la
# clé Zhipu configurée côté service FastAPI IA.
CRM_CAPTURE_OCR_ENABLED = (
    os.environ.get('CRM_CAPTURE_OCR_ENABLED', '0') == '1')

# GED36 — quota de stockage par société (octets). 0 = illimité (défaut). Sert de
# valeur PAR DÉFAUT quand une société n'a pas de quota explicite (`QuotaStockage`).
GED_QUOTA_DEFAUT_OCTETS = int(os.environ.get('GED_QUOTA_DEFAUT_OCTETS', '0'))

# XGED9 — Ingestion par email → GED (alias par cabinet/dossier). KEY-GATED :
# OFF par défaut → no-op (aucune connexion IMAP tentée par ce chemin). Réutilise
# la même config IMAP que FG373 (`core.email_intake`, IntegrationConfig
# `email_in`) — ce flag n'active QUE le routage des pièces jointes vers la GED
# (le founder l'active une fois les réglages IMAP posés).
GED_MAIL_INTAKE_ENABLED = os.environ.get('GED_MAIL_INTAKE_ENABLED', '0') == '1'

# XGED5 — Horodatage qualifié RFC 3161 (TSA) du scellement PAdES des PDF
# signés. KEY-GATED : vide par défaut → no-op (le sceau PAdES, s'il est posé
# via pyHanko, l'est SANS horodatage TSA). Le founder configurera l'URL d'une
# TSA (ex. un service conforme loi 43-20) pour activer ce volet.
GED_TSA_URL = os.environ.get('GED_TSA_URL', '')

# Security headers (safe in all environments)
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = 'DENY'
SECURE_BROWSER_XSS_FILTER = True

# ─────────────────────────────────────────────────────────────────────────────
# N92 — Web push (PWA). Clés VAPID lues depuis l'environnement. Par défaut VIDES
# → le push est un NO-OP TOTAL : `notify()` n'envoie aucune notification push et
# l'endpoint de clé publique renvoie une chaîne vide. Pour activer, générer une
# paire VAPID (ex. `vapid --gen` / web-push) et renseigner ces variables :
#   VAPID_PUBLIC_KEY   — clé publique (base64url), exposée au navigateur ;
#   VAPID_PRIVATE_KEY  — clé privée (base64url), serveur uniquement ;
#   VAPID_ADMIN_EMAIL  — contact mailto: requis par la spec Web Push (claim VAPID).
# Tant que la clé privée est vide, AUCUN envoi push n'a lieu (comportement actuel
# préservé). Aucune dépendance n'est chargée tant que rien n'est configuré.
VAPID_PUBLIC_KEY = os.environ.get('VAPID_PUBLIC_KEY', '')
VAPID_PRIVATE_KEY = os.environ.get('VAPID_PRIVATE_KEY', '')
VAPID_ADMIN_EMAIL = os.environ.get('VAPID_ADMIN_EMAIL', '')

TESTING = ('test' in sys.argv) or bool(os.environ.get('PYTEST_CURRENT_TEST'))
# WOW2 — sous le test runner UNIQUEMENT, hacher les mots de passe en MD5 (rapide)
# au lieu du PBKDF2 par défaut (des milliers d'itérations). Chaque test qui crée
# un utilisateur / s'authentifie (quasi tous, la portée multi-société crée des
# users partout) paie sinon le coût PBKDF2 → 2-5× de gain sur toute la suite.
# JAMAIS actif en prod (TESTING n'y est jamais vrai). Patron documenté par Django.
if TESTING:
    PASSWORD_HASHERS = ['django.contrib.auth.hashers.MD5PasswordHasher']
    # WOW1 — sous les tests, cache LOCAL par process (pas le Redis partagé) : en
    # `--parallel`, les N workers partagent le MÊME Redis, donc un `cache.clear()`
    # d'un test efface l'état des AUTRES workers en plein milieu (idempotence
    # cache-based cassée — ex. test_qj27 already_sent). LocMemCache est isolé par
    # process = par worker, donc chaque test voit uniquement son propre cache.
    CACHES = {
        'default': {
            'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
        }
    }
# N109 — auto-generate a VAPID keypair (persisted DB singleton) in production
# when no keys are provided via env, so web push works out of the box. OFF under
# the test runner so the "unconfigured => empty endpoint => no-op" contract holds.
VAPID_AUTOGENERATE = os.environ.get('VAPID_AUTOGENERATE', '0' if TESTING else '1') == '1'

# NTPLT42 — résolution du budget throttle PAR TENANT (après TESTING). Env
# TENANT_RATE_LIMIT (défaut '1200/min'). '0' ou vide → None (throttle désactivé).
# Sous le test runner, DÉSACTIVÉ par défaut : une suite qui boucle des centaines
# de requêtes pour la même société ne doit jamais échouer sur un 429 parasite
# (un test ciblant explicitement le throttle pose TENANT_RATE_LIMIT lui-même).
_tenant_rate = os.environ.get(
    'TENANT_RATE_LIMIT', '0' if TESTING else '1200/min').strip()
REST_FRAMEWORK['DEFAULT_THROTTLE_RATES']['tenant'] = (
    _tenant_rate if _tenant_rate and _tenant_rate != '0' else None)

# ─────────────────────────────────────────────────────────────────────────────
# Fondation IA (core.ai) — sélection des fournisseurs par capacité.
# Dict {capacité: clé_fournisseur}. Le DÉFAUT de chaque capacité est 'noop' :
# sans configuration explicite, AUCUN appel externe n'a lieu, aucune dépendance
# n'est chargée et rien n'est facturé (la fonctionnalité « ne fait rien » plutôt
# que de casser). Pour activer une capacité, enregistrer un vrai fournisseur
# (core.ai.register_provider) et le sélectionner ici, ex. :
#   AI_PROVIDERS = {'ocr': 'zhipu', 'stt': 'whisper', 'llm': 'groq'}
# Un fournisseur sélectionné mais non configuré (clé absente) retombe lui-même
# sur le NO-OP — garantie « aucun appel sans config ». Capacités : 'ocr', 'stt',
# 'vision_qa', 'llm'. Lue depuis AI_PROVIDERS_JSON (JSON) si présente.
import json as _json  # noqa: E402
try:
    AI_PROVIDERS = _json.loads(os.environ.get('AI_PROVIDERS_JSON', '') or '{}')
    if not isinstance(AI_PROVIDERS, dict):
        AI_PROVIDERS = {}
except (ValueError, TypeError):
    AI_PROVIDERS = {}

# ─────────────────────────────────────────────────────────────────────────────
# YHARD6 — endpoint /metrics (Prometheus). JAMAIS public par défaut : la vue
# (core/views.py::metrics_view) exige soit un utilisateur authentifié admin
# (IsAdminRole), soit — pour un scrape Prometheus sans session — une IP dans
# cet allowlist (ex. l'IP du serveur de monitoring interne). Vide par défaut =
# accès admin-only uniquement (aucune IP autorisée). ``django-prometheus`` est
# une dépendance OSS OPTIONNELLE (cf. requirements.txt) pour les métriques
# HTTP/DB standard ; l'endpoint fonctionne même sans elle (collecteurs custom
# YHARD6 en pur stdlib, cf. core/metrics.py).
METRICS_ALLOWED_IPS = [
    ip.strip() for ip in os.environ.get('METRICS_ALLOWED_IPS', '').split(',')
    if ip.strip()
]

# ─────────────────────────────────────────────────────────────────────────────
# NTPLT43 — logs JSON structurés taggés tenant (request_id/company/user/path/
# status/duration_ms). ACTIVABLE par LOG_FORMAT=json ; par défaut, AUCUNE config
# LOGGING n'est posée ici → le format actuel (défaut Django, ou celui de dev.py)
# reste strictement inchangé. En mode json, chaque ligne de log est un objet JSON
# ingérable tel quel par Loki/CloudWatch (doc: docs/observability.md).
LOG_FORMAT = os.environ.get('LOG_FORMAT', '').strip().lower()
if LOG_FORMAT == 'json':
    from core.logging_ext import build_logging_config  # noqa: E402
    LOGGING = build_logging_config(
        level=os.environ.get('LOG_LEVEL', 'INFO').upper())

# NTPLT43 — access log structuré par requête (une ligne INFO 'core.request' par
# requête). OFF par défaut ; automatiquement activé quand LOG_FORMAT=json.
REQUEST_ACCESS_LOG = (
    os.environ.get('REQUEST_ACCESS_LOG', '1' if LOG_FORMAT == 'json' else '0')
    == '1')

# NTPLT51 — trace des requêtes HTTP lentes. 0 (défaut) = désactivée. Au-delà du
# seuil (ms), une ligne WARNING 'core.slow_request' est émise (durée/path/tenant),
# et en DEBUG le compte SQL + les 3 requêtes les plus longues (CaptureQueries).
SLOW_REQUEST_MS = int(os.environ.get('SLOW_REQUEST_MS', '0') or '0')
