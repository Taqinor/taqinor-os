"""
Development-specific settings.
"""
import logging

from .base import *  # noqa: F401, F403

DEBUG = True

# YOPSB12 — détecteur de requêtes N+1 en développement UNIQUEMENT. Import
# GARDÉ : le paquet ``nplusone`` n'est installé QUE via requirements-dev.txt
# (jamais requirements.txt) — sans lui, ce bloc est un no-op total (aucune
# exception, comportement identique à avant). ``NPLUSONE_RAISE = False`` :
# journalise plutôt que de lever une exception — un N+1 détecté en dev ne
# doit jamais planter le serveur de développement, seulement apparaître
# dans les logs pour inciter à ajouter select_related/prefetch_related
# (convention documentée dans docs/CODEMAP.md §7). Jamais chargé en
# prod/CI-tests (settings.prod ne l'importe jamais, et le paquet n'est de
# toute façon pas dans requirements.txt).
try:
    import nplusone.ext.django  # noqa: F401

    INSTALLED_APPS = list(INSTALLED_APPS) + ['nplusone.ext.django']  # noqa: F405
    MIDDLEWARE = list(MIDDLEWARE) + [  # noqa: F405
        'nplusone.ext.django.NPlusOneMiddleware',
    ]
    NPLUSONE_RAISE = False
    NPLUSONE_LOGGER = logging.getLogger('nplusone')
    NPLUSONE_LOG_LEVEL = logging.WARNING
except ImportError:
    # nplusone non installé (pip install -r requirements-dev.txt pour
    # l'activer localement) — comportement inchangé, aucune erreur.
    pass

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
