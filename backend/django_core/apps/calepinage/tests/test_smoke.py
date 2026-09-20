"""CAL4 — l'app « calepinage » est réellement chargée et câblée.

Ce que ce test prouve (sans base de données) :

* l'app est dans ``INSTALLED_APPS`` et son ``AppConfig`` est bien le nôtre ;
* son ``module_manifest`` est complet et conforme au patron ``apps/ao/apps.py``
  (clé unique, ``sku`` solaire, dépendances crm/ventes, catégorie Commercial) ;
* la clé de module est EXACTEMENT le 2ᵉ segment d'URL (``/api/django/
  calepinage/``) — c'est ce qui permet au gatage 404 des modules désactivés de
  viser le bon module SANS entrée ``PREFIX_TO_MODULE`` ;
* le manifeste plateforme (``platform.py``, ARC28) existe, vise le bon module
  et ne MENT sur aucune surface : toutes vides au jour 1 ;
* les routes du module sont montées (``apps.calepinage.urls`` résout).

Run :
    python manage.py test apps.calepinage.tests.test_smoke -v2
"""
from django.apps import apps as django_apps
from django.test import SimpleTestCase
from django.urls import get_resolver


class ManifesteModuleTest(SimpleTestCase):
    """Le manifeste ODX2 du module et son câblage INSTALLED_APPS."""

    def setUp(self):
        self.config = django_apps.get_app_config('calepinage')

    def test_app_chargee(self):
        self.assertEqual(self.config.name, 'apps.calepinage')

    def test_manifeste_complet(self):
        manifeste = self.config.module_manifest
        self.assertEqual(manifeste['key'], 'calepinage')
        self.assertEqual(manifeste['sku'], 'solar_core')
        self.assertEqual(manifeste['label'], 'Calepinage')
        self.assertEqual(manifeste['categorie'], 'Commercial')
        self.assertTrue(manifeste['installable'])
        self.assertTrue(manifeste['description'].strip())

    def test_depend_de_crm_et_ventes(self):
        """La création part d'un lead/client (crm) ou d'un devis (ventes)."""
        self.assertEqual(sorted(self.config.module_manifest['depends']),
                         ['crm', 'ventes'])

    def test_dependances_resolvent(self):
        """Chaque dépendance déclarée est une clé de manifeste RÉELLE."""
        cles = {
            getattr(cfg, 'module_manifest', {}).get('key')
            for cfg in django_apps.get_app_configs()
            if getattr(cfg, 'module_manifest', None)
        }
        for depend in self.config.module_manifest['depends']:
            self.assertIn(depend, cles)

    def test_cle_de_module_unique(self):
        """Aucune autre app ne revendique la clé ``calepinage``."""
        porteurs = [
            cfg.name for cfg in django_apps.get_app_configs()
            if getattr(cfg, 'module_manifest', {}).get('key') == 'calepinage'
        ]
        self.assertEqual(porteurs, ['apps.calepinage'])


class ManifestePlateformeTest(SimpleTestCase):
    """ARC28 — ``platform.py`` existe et ne déclare aucune surface non câblée."""

    def test_chaque_surface_declaree_est_cablee(self):
        """L'invariant est « déclaré = câblé », pas « tout est vide ».

        Les trois surfaces ci-dessous ont été câblées DANS LE MÊME LOT
        (CAL27 recherche globale, CAL26 chatter ``records``, ARC31 champs
        perso) : les exiger vides revenait à interdire le câblage que la
        tâche demandait. On fige donc leur contenu EXACT — plus fort qu'un
        « non vide » —, et on garde vides celles que ``platform.py`` déclare
        délibérément non câblées.
        """
        from apps.calepinage.platform import PLATFORM

        self.assertEqual(PLATFORM['module'], 'calepinage')
        self.assertEqual(PLATFORM['searchable_models'],
                         ['calepinage.calepinage'])
        self.assertEqual(PLATFORM['record_targets'],
                         ['calepinage.calepinage'])
        self.assertEqual(PLATFORM['customfield_models'], ['calepinage'])
        for surface in ('import_specs', 'automation_state_fields',
                        'kpi_providers'):
            self.assertEqual(PLATFORM[surface], [], surface)
        self.assertEqual(PLATFORM['agent_actions_module'], '')


class CablageUrlsTest(SimpleTestCase):
    """Les routes du module sont montées sous le bon préfixe."""

    def test_prefixe_monte(self):
        prefixes = {
            str(motif.pattern)
            for motif in get_resolver().url_patterns
        }
        self.assertTrue(
            any('calepinage' in p for p in prefixes)
            or self._monte_sous_api_django(),
            "Le préfixe 'calepinage/' n'est pas monté dans erp_agentique/urls.")

    def _monte_sous_api_django(self):
        """Les routes du module vivent sous ``api/django/`` (include imbriqué)."""
        for motif in get_resolver().url_patterns:
            for enfant in getattr(motif, 'url_patterns', []):
                if 'calepinage' in str(enfant.pattern):
                    return True
        return False

    def test_module_urls_importable(self):
        from apps.calepinage import urls

        self.assertIsInstance(urls.urlpatterns, list)
