"""
Production-specific settings.
"""
from .base import *  # noqa: F401, F403

DEBUG = False

# En production, SECRET_KEY et ALLOWED_HOSTS DOIVENT être fournis via variables d'env

# Headers de sécurité
SECURE_BROWSER_XSS_FILTER = True
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = 'DENY'
SECURE_HSTS_SECONDS = 31536000
SECURE_HSTS_INCLUDE_SUBDOMAINS = True

# CORS restrictif en production
CORS_ALLOW_ALL_ORIGINS = False
