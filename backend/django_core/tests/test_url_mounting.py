"""WIR136 — montage d'URL identity/accessreview : une fois par préfixe.

Avant : ``apps.identity.urls`` était monté DEUX fois sous
``api/django/identity/`` (via ``_APP_URLS`` ET en autonome), et
``apps.accessreview.urls`` UNE seule fois en autonome — donc absent de
``api/v1/`` contrairement à toutes les autres apps.

Ces tests prouvent l'invariant d'APRÈS le nettoyage :

  * chaque URLconf d'app n'est monté qu'UNE fois par préfixe (``api/django/``
    et ``api/v1/``), donc exactement deux fois au total ;
  * AUCUNE route identity/accessreview n'a disparu : chaque motif déclaré par
    l'app est toujours joignable sous ``api/django/<app>/`` — la comparaison
    est faite motif par motif, pas sur un échantillon ;
  * les mêmes routes existent sous ``api/v1/`` et pointent la même vue ;
  * ``reverse()`` sans namespace rend toujours le chemin interne canonique
    ``api/django/…`` (invariant YAPIC7 : le second montage est namespacé
    ``v1``, il ne doit pas remporter la résolution des noms).

Pur URLconf, aucune base de données (``SimpleTestCase``).
"""
from importlib import import_module

from django.test import SimpleTestCase
from django.urls import URLPattern, URLResolver, get_resolver, resolve, reverse

LEGACY_PREFIX = 'api/django/'
V1_PREFIX = 'api/v1/'


def _mount_count(urlconf_module_name):
    """Combien de fois cet URLconf d'app est-il inclus dans l'arbre racine ?"""
    count = 0
    stack = list(get_resolver().url_patterns)
    while stack:
        entry = stack.pop()
        if isinstance(entry, URLResolver):
            name = getattr(entry.urlconf_name, '__name__', None)
            if name == urlconf_module_name:
                count += 1
            else:
                # Ne pas descendre DANS l'app comptée : ses propres includes
                # (router DRF) ne sont pas des montages racine.
                stack.extend(entry.url_patterns)
    return count


def _routes(patterns, prefix=''):
    """Motifs de route concrets (chaînes) sous `patterns`, préfixe compris."""
    routes = set()
    for entry in patterns:
        pattern = str(entry.pattern)
        if isinstance(entry, URLPattern):
            routes.add(prefix + pattern)
        elif isinstance(entry, URLResolver):
            routes |= _routes(entry.url_patterns, prefix + pattern)
    return routes


def _app_routes(app_urls_module):
    return _routes(import_module(app_urls_module).urlpatterns)


class SingleMountPerPrefixTests(SimpleTestCase):

    def test_identity_is_mounted_once_per_prefix(self):
        # 2 = api/django/ (via _APP_URLS) + api/v1/ (même liste, namespacée).
        # 3 signifierait le retour du montage autonome redondant.
        self.assertEqual(_mount_count('apps.identity.urls'), 2)

    def test_accessreview_is_mounted_once_per_prefix(self):
        self.assertEqual(_mount_count('apps.accessreview.urls'), 2)


class NoRouteLostTests(SimpleTestCase):
    """Chaque motif déclaré par l'app est toujours joignable, aux 2 préfixes."""

    def _assert_all_routes_present(self, app_urls_module, segment):
        declared = _app_routes(app_urls_module)
        self.assertTrue(declared, f'{app_urls_module} ne déclare aucune route')
        everything = _routes(get_resolver().url_patterns)
        for route in declared:
            for prefix in (LEGACY_PREFIX, V1_PREFIX):
                full = f'{prefix}{segment}/{route}'
                self.assertIn(
                    full, everything,
                    f'route perdue au nettoyage WIR136 : {full}',
                )

    def test_every_identity_route_is_still_reachable(self):
        self._assert_all_routes_present('apps.identity.urls', 'identity')

    def test_every_accessreview_route_is_still_reachable(self):
        self._assert_all_routes_present('apps.accessreview.urls', 'accessreview')


class CanonicalPathsResolveTests(SimpleTestCase):
    """Contrôle bout-en-bout sur des chemins concrets (résolution réelle)."""

    SAMPLES = (
        '/api/django/identity/login-banner/',
        '/api/django/identity/ip-allow-rules/',
        '/api/django/identity/scim/v2/acme/Users',
        '/api/django/accessreview/campaigns/',
        '/api/django/accessreview/sod-rules/',
    )

    def test_legacy_and_v1_resolve_to_the_same_view(self):
        for legacy in self.SAMPLES:
            with self.subTest(path=legacy):
                v1 = legacy.replace('/api/django/', '/api/v1/', 1)
                self.assertEqual(resolve(legacy).func, resolve(v1).func)

    def test_reverse_without_namespace_yields_the_canonical_prefix(self):
        # YAPIC7 : le montage v1 est namespacé, il ne doit jamais remporter
        # `reverse('<nom>')`.
        for name in ('identity-login-banner', 'scim-users'):
            with self.subTest(name=name):
                kwargs = {'company_slug': 'acme'} if name == 'scim-users' else {}
                self.assertTrue(
                    reverse(name, kwargs=kwargs).startswith('/api/django/'),
                )
        self.assertTrue(
            reverse('accessreview-campaign-list').startswith('/api/django/'),
        )
