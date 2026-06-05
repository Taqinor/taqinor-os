"""
Development-specific settings.
"""
from .base import *  # noqa: F401, F403

DEBUG = True

# Origines autorisees en developpement local uniquement
CORS_ALLOWED_ORIGINS = [
    'http://localhost',
    'http://localhost:3000',
    'http://localhost:5173',
    'http://127.0.0.1',
    'http://127.0.0.1:3000',
]

# SQL logging desactive — trop verbeux et logue les donnees utilisateur
# Activer ponctuellement si besoin : django.db.backends level=DEBUG
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'handlers': {
        'console': {'class': 'logging.StreamHandler'},
    },
    'loggers': {
        'django': {
            'handlers': ['console'],
            'level': 'WARNING',
        },
    },
}
