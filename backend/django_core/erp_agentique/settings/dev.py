"""
Development-specific settings.
"""
from .base import *  # noqa: F401, F403

DEBUG = True

# En dev, accepter toutes les origines CORS
CORS_ALLOW_ALL_ORIGINS = True

# Logging SQL en dev
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'handlers': {
        'console': {'class': 'logging.StreamHandler'},
    },
    'loggers': {
        'django.db.backends': {
            'handlers': ['console'],
            'level': 'DEBUG',
        },
    },
}
