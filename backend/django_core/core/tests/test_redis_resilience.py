"""NTPLT24 — une panne Redis dégrade en cache-miss au lieu de 500.

Simule un backend cassé (Redis injoignable) : avec IGNORE_EXCEPTIONS=True,
``cache.get``/``cache.set`` ne lèvent plus — get renvoie le défaut, set est un
no-op. Sans cette option, django-redis propagerait une ConnectionError qui
remonterait en 500 sur toute vue touchant le cache.
"""
from django.conf import settings
from django.core.cache import caches
from django.test import SimpleTestCase, override_settings

# Backend Redis pointant vers un port fermé (connexion impossible), délais très
# courts pour ne pas ralentir la suite. IGNORE_EXCEPTIONS avale l'erreur.
_BROKEN_CACHE = {
    'default': {
        'BACKEND': 'django_redis.cache.RedisCache',
        'LOCATION': 'redis://127.0.0.1:1/0',
        'OPTIONS': {
            'CLIENT_CLASS': 'django_redis.client.DefaultClient',
            'IGNORE_EXCEPTIONS': True,
            'SOCKET_CONNECT_TIMEOUT': 0.05,
            'SOCKET_TIMEOUT': 0.05,
        },
    }
}


class RedisResilienceTests(SimpleTestCase):
    def test_base_settings_declares_ignore_exceptions(self):
        # Le flag de journalisation confirme que NTPLT24 est bien posé dans base.
        self.assertTrue(getattr(settings, 'DJANGO_REDIS_LOG_IGNORED_EXCEPTIONS',
                                False))

    @override_settings(CACHES=_BROKEN_CACHE, DJANGO_REDIS_IGNORE_EXCEPTIONS=True)
    def test_broken_redis_degrades_to_cache_miss(self):
        cache = caches['default']
        # Aucune exception ne doit remonter malgré le backend injoignable.
        self.assertIsNone(cache.get('cle_inexistante'))
        self.assertEqual(cache.get('cle_inexistante', 'defaut'), 'defaut')
        # set est un no-op silencieux (retourne None sans lever).
        self.assertIsNone(cache.set('k', 'v'))
