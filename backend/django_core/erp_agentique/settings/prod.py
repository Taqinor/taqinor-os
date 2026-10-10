"""
Production-specific settings.
"""
import os

from .base import *  # noqa: F401, F403

DEBUG = False

# En production, SECRET_KEY et ALLOWED_HOSTS DOIVENT être fournis via variables d'env
# Procédure de bascule, variables et retour arrière : docs/production.md (ASEC48).


def _liste_env(variable):
    """Liste csv d'une variable d'environnement, entrées nettoyées, vides ôtées."""
    return [v.strip() for v in os.environ.get(variable, '').split(',') if v.strip()]


# ASEC48 — les hôtes servis viennent de l'environnement, SANS le défaut local
# de base.py (`localhost,127.0.0.1`) : variable absente ⇒ liste vide ⇒ Django
# refuse toute requête et le contrôle QJR423 (core/checks.py) bloque les
# commandes manage.py en nommant DJANGO_ALLOWED_HOSTS. Espaces tolérés.
ALLOWED_HOSTS = _liste_env('DJANGO_ALLOWED_HOSTS')

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
# ASEC48 — PAS DE BOUCLE. Chaîne réelle : Caddy (TLS public, redirige lui-même
# le HTTP vers HTTPS, pose `X-Forwarded-Proto {scheme}`) → nginx (relaie cet
# en-tête depuis un pair de confiance seulement, ASEC52) → Django. Une requête
# venue par Caddy est donc vue `is_secure()` et jamais redirigée ; seule une
# requête HTTP qui contourne Caddy l'est. Les SONDES DE SANTÉ ne sont jamais
# redirigées : une sonde interne en HTTP doit lire 200/503, pas un 301 (motif
# sans la barre initiale, comme le compare SecurityMiddleware).
SECURE_REDIRECT_EXEMPT = [r'^api/django/core/health/(?:live|ready)/$']
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True

# CORS restrictif en production
CORS_ALLOW_ALL_ORIGINS = False
# Origines autorisées surchargées depuis l'environnement (ERR22). En prod, on
# ne réutilise PAS la liste localhost de base : on lit ``CORS_ALLOWED_ORIGINS``
# (csv) et, à défaut, on retombe sur les domaines publics canoniques. Idem pour
# CSRF_TRUSTED_ORIGINS, requis par Django dès qu'on poste depuis un autre
# domaine HTTPS.
CORS_ALLOWED_ORIGINS = _liste_env('CORS_ALLOWED_ORIGINS') or [
    'https://taqinor.ma',
    'https://www.taqinor.ma',
]
# ASEC48 — la liste CSRF_TRUSTED_ORIGINS de l'environnement (lue par base.py :
# les deux hôtes de l'ERP sur le serveur) est CONSERVÉE puis complétée des
# origines CORS ; avant, cette ligne l'écrasait et la variable était morte.
CSRF_TRUSTED_ORIGINS = list(dict.fromkeys(
    list(CSRF_TRUSTED_ORIGINS) + list(CORS_ALLOWED_ORIGINS)))  # noqa: F405

# ASEC48 — `NUM_PROXIES` (base.py, CRX30 ; primitive ASEC15
# `core.throttling.ip_de_requete`) : derrière Caddy → nginx, nginx réécrit
# `$remote_addr` (realip) puis l'AJOUTE à X-Forwarded-For — le dernier saut
# est le visiteur, donc 1 (le défaut de base.py hors tests). 0 ou une valeur
# illisible mettrait tout Internet dans UN seau de limitation (REMOTE_ADDR =
# nginx) : refusé au démarrage, la variable nommée. Sous le test runner
# (TESTING), base.py laisse délibérément NUM_PROXIES à None : pas de garde.
if not NUM_PROXIES and not TESTING:  # noqa: F405
    raise RuntimeError(
        "NUM_PROXIES doit valoir au moins 1 en production (chaîne Caddy → "
        "nginx → Django : 1). Retirez NUM_PROXIES du .env du serveur ou posez "
        "NUM_PROXIES=1.")

# ASEC48 — `manage.py check --deploy` LISIBLE : le contrôle de déploiement de
# drf-spectacular régénère tout le schéma OpenAPI et émet ~600 avertissements
# de documentation (W001/W002) qui noient les contrôles de sécurité. Le schéma
# est déjà gardé en CI (scripts/check_openapi_schema.py, job backend-openapi).
SPECTACULAR_SETTINGS = {
    **SPECTACULAR_SETTINGS,  # noqa: F405
    'ENABLE_DJANGO_DEPLOY_CHECK': False,
}

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
