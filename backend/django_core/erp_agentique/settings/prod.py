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
