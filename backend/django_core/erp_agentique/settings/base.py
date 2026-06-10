"""
Django settings for erp_agentique project.
Base settings - shared across all environments.
"""

import os
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
    },
}

# Simple JWT Configuration
SIMPLE_JWT = {
    'ACCESS_TOKEN_LIFETIME': timedelta(hours=8),
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

# Email — django-anymail avec SendGrid (Phase 2 Sem. 4)
ANYMAIL = {
    'SENDGRID_API_KEY': os.environ.get('SENDGRID_API_KEY', ''),
}
EMAIL_BACKEND = os.environ.get(
    'EMAIL_BACKEND',
    'django.core.mail.backends.console.EmailBackend'  # console en dev, anymail en prod
)
DEFAULT_FROM_EMAIL = os.environ.get('DEFAULT_FROM_EMAIL', 'noreply@erp.local')
CONTACT_EMAIL = os.environ.get('CONTACT_EMAIL', 'reda.kasri@taqinor.ma')

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

# Security headers (safe in all environments)
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = 'DENY'
SECURE_BROWSER_XSS_FILTER = True
