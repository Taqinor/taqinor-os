"""
Production-specific settings.
"""
import os

from .base import *  # noqa: F401, F403

DEBUG = False

# En production, SECRET_KEY et ALLOWED_HOSTS DOIVENT être fournis via variables d'env

# Headers de sécurité
SECURE_BROWSER_XSS_FILTER = True
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = 'DENY'
SECURE_HSTS_SECONDS = 31536000
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
# HSTS preload (ERR22) : éligibilité à la liste de préchargement HSTS des
# navigateurs (n'a d'effet qu'avec SECONDS + INCLUDE_SUBDOMAINS, déjà posés).
SECURE_HSTS_PRELOAD = True

# Cookies & transport (ERR22) — durcissement production. L'app est servie
# DERRIÈRE un proxy TLS (Caddy → api.taqinor.ma) : on déclare l'en-tête de
# confiance pour que ``request.is_secure()`` évalue correctement, puis on force
# le HTTPS et le flag Secure sur les cookies de session/CSRF afin qu'ils ne
# voyagent jamais en clair. Strictement réservé à prod (dev/test inchangés :
# ces réglages vivent ici, pas dans base.py).
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
SECURE_SSL_REDIRECT = True
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True

# CORS restrictif en production
CORS_ALLOW_ALL_ORIGINS = False
# Origines autorisées surchargées depuis l'environnement (ERR22). En prod, on
# ne réutilise PAS la liste localhost de base : on lit ``CORS_ALLOWED_ORIGINS``
# (csv) et, à défaut, on retombe sur les domaines publics canoniques. Idem pour
# CSRF_TRUSTED_ORIGINS, requis par Django dès qu'on poste depuis un autre
# domaine HTTPS.
_cors_env = os.environ.get('CORS_ALLOWED_ORIGINS', '').strip()
if _cors_env:
    CORS_ALLOWED_ORIGINS = [
        o.strip() for o in _cors_env.split(',') if o.strip()
    ]
else:
    CORS_ALLOWED_ORIGINS = [
        'https://taqinor.ma',
        'https://www.taqinor.ma',
    ]
CSRF_TRUSTED_ORIGINS = list(CORS_ALLOWED_ORIGINS)

# ─────────────────────────────────────────────────────────────────────────────
# QJR423 / DR8 — UN INCIDENT DE PRODUCTION EST LISIBLE SANS DEBUG.
#
# CE QUI MANQUAIT. ``prod.py`` ne configurait AUCUN ``LOGGING`` : seul le mode
# ``LOG_FORMAT=json`` de ``base.py`` en posait un, et à défaut la production
# retombait sur la configuration par défaut de Django — où les exceptions
# ``django.request`` ne partent nulle part hors DEBUG. Diagnostiquer un
# incident revenait donc à rallumer DEBUG, ce que le contrôle système
# ``core/checks.py`` interdit désormais.
#
# LA RÈGLE. Si ``base.py`` a déjà posé une configuration (``LOG_FORMAT=json``,
# logs structurés NTPLT43), elle est RESPECTÉE telle quelle. Sinon, on pose une
# configuration console minimale et horodatée : les erreurs de requête et les
# messages applicatifs deviennent lisibles dans ``docker logs``, sans DEBUG et
# sans dépendance nouvelle. Strictement réservé à prod — dev/test inchangés.
if not globals().get('LOGGING'):
    LOGGING = {
        'version': 1,
        'disable_existing_loggers': False,
        'formatters': {
            'prod': {
                'format': (
                    '%(asctime)s %(levelname)s %(name)s %(message)s'),
            },
        },
        'handlers': {
            'console': {
                'class': 'logging.StreamHandler',
                'formatter': 'prod',
            },
        },
        'root': {
            'handlers': ['console'],
            'level': os.environ.get('LOG_LEVEL', 'INFO').upper(),
        },
        'loggers': {
            # Les exceptions non rattrapées d'une vue : la ligne qui manquait.
            'django.request': {
                'handlers': ['console'],
                'level': 'ERROR',
                'propagate': False,
            },
            'django': {
                'handlers': ['console'],
                'level': 'INFO',
                'propagate': False,
            },
            # Le code métier du dépôt (apps.*, core.*) reste en INFO.
            'apps': {
                'handlers': ['console'],
                'level': 'INFO',
                'propagate': False,
            },
            'core': {
                'handlers': ['console'],
                'level': 'INFO',
                'propagate': False,
            },
        },
    }
