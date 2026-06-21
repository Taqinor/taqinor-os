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
    # AG1 — Catalogue d'actions agentiques (déclarées en code, aucun modèle).
    # Expose ce que l'agent peut proposer au caller, filtré par permission +
    # société. Métadonnées seulement ; l'exécution re-vérifie côté endpoint.
    'apps.agent',
    # Group S — Messagerie interne d'équipe (« Discuss ») : DM + canaux,
    # pièces jointes/voix, mentions, réactions, partage d'enregistrement.
    # Multi-tenant strict ; temps réel par polling (pas de WebSocket en v1).
    'apps.chat',
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
    },
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

# Récepteur des leads du site public taqinor.ma (apps/crm/webhooks.py).
# Sans secret configuré, le endpoint répond 401 à tout — fermé par défaut.
WEBSITE_LEAD_WEBHOOK_SECRET = os.environ.get('WEBSITE_LEAD_WEBHOOK_SECRET', '')
# Tenant cible des leads web (id de Company) ; à défaut, la première Company.
WEBSITE_LEADS_COMPANY_ID = os.environ.get('WEBSITE_LEADS_COMPANY_ID') or None

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
