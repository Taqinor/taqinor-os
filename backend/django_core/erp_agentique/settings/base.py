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
    # ODX4 — 404 sur les endpoints d'un module désactivé pour la société.
    # Défaut = actif (aucun 404 nouveau sans toggle). Placé après l'auth Django ;
    # résout lui-même le JWT DRF best-effort (aucun blocage sans jeton valide).
    'core.permissions.DisabledModuleMiddleware',
    # Porte la requête courante pour la capture du Journal d'activité (Feature G).
    'apps.audit.middleware.AuditActorMiddleware',
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
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': os.environ.get('DB_NAME', 'erp_db'),
        'USER': os.environ.get('DB_USER', 'erp_user'),
        'PASSWORD': os.environ.get('DB_PASSWORD', 'erp_password'),
        'HOST': os.environ.get('DB_HOST', 'db'),
        'PORT': os.environ.get('DB_PORT', '5432'),
    }
}

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

# Django REST Framework
REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': (
        'authentication.cookie_auth.CookieJWTAuthentication',
    ),
    'DEFAULT_PERMISSION_CLASSES': (
        'rest_framework.permissions.IsAuthenticated',
    ),
    'DEFAULT_PAGINATION_CLASS': 'rest_framework.pagination.PageNumberPagination',
    'PAGE_SIZE': 100,
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
    },
    # YDATA9 — DRF sérialise déjà les `Decimal` en string par défaut (c'est
    # la valeur par défaut de DRF), mais rien ne le VERROUILLAIT explicitement
    # dans ce repo : un changement accidentel de ce réglage romprait la
    # précision des montants à la frontière API (un float JSON perd des
    # décimales). Posé explicitement pour que ce comportement soit un choix
    # documenté, testé, jamais un défaut implicite qui pourrait dériver.
    'COERCE_DECIMAL_TO_STRING': True,
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
CACHES = {
    "default": {
        "BACKEND": "django_redis.cache.RedisCache",
        "LOCATION": f"redis://{os.environ.get('REDIS_HOST', 'redis')}:{os.environ.get('REDIS_PORT', '6379')}/1",
        "OPTIONS": {
            "CLIENT_CLASS": "django_redis.client.DefaultClient",
        }
    }
}

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
# N109 — auto-generate a VAPID keypair (persisted DB singleton) in production
# when no keys are provided via env, so web push works out of the box. OFF under
# the test runner so the "unconfigured => empty endpoint => no-op" contract holds.
VAPID_AUTOGENERATE = os.environ.get('VAPID_AUTOGENERATE', '0' if TESTING else '1') == '1'

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
