"""WOW-CI3 — le raccourci de génération du schéma OpenAPI reste dérivable.

``scripts/check_openapi_schema.py`` (contrôle CI ``backend-openapi``) fait
introspecter UNE seule fois par drf-spectacular l'arbre d'URLs monté DEUX fois
(``api/django/`` et ``api/v1/``, cf. YAPIC7), puis reconstitue mécaniquement le
miroir ``api/v1/``. La moitié versionnée du contrat n'est donc plus observée
directement : ces tests remplacent cette observation par des invariants.

Ils ne génèrent AUCUN schéma (aucune vue instanciée, aucune base contactée) :
ils vérifient l'URLconf dérivée et la fonction d'expansion.
"""
from django.core.exceptions import ImproperlyConfigured
from django.test import SimpleTestCase
from django.urls import URLResolver
from drf_spectacular import drainage

from erp_agentique import openapi_check, urls as urls_racine


def _route(entree):
    return getattr(entree.pattern, '_route', None)


class UrlconfDeriveeTests(SimpleTestCase):
    """L'URLconf du contrôle = la racine RÉELLE moins le seul montage v1."""

    def test_un_seul_montage_v1_a_la_racine(self):
        montages = [e for e in urls_racine.urlpatterns if _route(e) == 'api/v1/']
        self.assertEqual(len(montages), 1)
        self.assertIsInstance(montages[0], URLResolver)

    def test_v1_monte_le_meme_objet_que_api_django(self):
        """L'identité (``is``) est ce qui rend le miroir dérivable."""
        v1 = next(e for e in urls_racine.urlpatterns if _route(e) == 'api/v1/')
        interne = next(e for e in urls_racine.urlpatterns
                       if _route(e) == 'api/django/')
        self.assertIs(v1.urlconf_name, interne.urlconf_name)

    def test_urlpatterns_derivee_retire_exactement_le_montage_v1(self):
        racine = urls_racine.urlpatterns
        derivee = openapi_check.urlpatterns
        self.assertEqual(len(derivee), len(racine) - 1)
        self.assertEqual([e for e in derivee if _route(e) == 'api/v1/'], [])
        # Tout le reste est conservé, dans l'ordre, par identité d'objet.
        self.assertEqual(derivee, [e for e in racine if _route(e) != 'api/v1/'])

    def test_prefixes_sans_jumeau_couvrent_le_public_et_le_jwt(self):
        """Les routes montées HORS de `_APP_URLS` n'ont pas de miroir v1."""
        prefixes = openapi_check._prefixes_sans_jumeau_v1()
        self.assertIn('/api/django/public/', prefixes)
        self.assertIn('/api/django/token/', prefixes)
        for prefixe in prefixes:
            self.assertTrue(prefixe.startswith('/api/django/'), prefixe)
            self.assertNotEqual(prefixe, '/api/django/')

    def test_le_generateur_vise_l_urlconf_derivee_par_defaut(self):
        generateur = openapi_check.SchemaGeneratorAliasV1()
        self.assertEqual(generateur.urlconf, 'erp_agentique.openapi_check')


class CacheSourceLocationTests(SimpleTestCase):
    """Le cache de `drainage._get_source_location` est déplafonné, pas altéré."""

    def setUp(self):
        self.origine = drainage._get_source_location
        self.addCleanup(setattr, drainage, '_get_source_location', self.origine)

    def test_le_cache_est_deplafonne(self):
        self.assertTrue(openapi_check.elargir_cache_source_location())
        self.assertIsNone(drainage._get_source_location.cache_info().maxsize)

    def test_les_valeurs_rendues_sont_inchangees(self):
        attendu = self.origine(SimpleTestCase)
        openapi_check.elargir_cache_source_location()
        self.assertEqual(drainage._get_source_location(SimpleTestCase), attendu)

    def test_appliquer_deux_fois_est_sans_effet(self):
        self.assertTrue(openapi_check.elargir_cache_source_location())
        elargi = drainage._get_source_location
        self.assertTrue(openapi_check.elargir_cache_source_location())
        self.assertIs(drainage._get_source_location, elargi)

    def test_une_structure_amont_inattendue_ne_fait_pas_echouer(self):
        drainage._get_source_location = lambda obj: (None, None)
        self.assertFalse(openapi_check.elargir_cache_source_location())


class ExpansionMiroirTests(SimpleTestCase):
    """`etendre_miroir_v1` : même document, `operationId` translaté."""

    EXCLUS = ('/api/django/public/', '/api/django/token/')

    def _chemins(self):
        return {
            '/api/django/stock/produits/': {
                'get': {'operationId': 'django_stock_produits_list',
                        'tags': ['api'], 'responses': {'200': {}}},
                'post': {'operationId': 'django_stock_produits_create'},
            },
            '/api/django/public/devis/{token}/': {
                'get': {'operationId': 'django_public_devis_retrieve'},
            },
            '/api/public/leads/': {
                'get': {'operationId': 'public_leads_list'},
            },
        }

    def test_le_miroir_est_ajoute_avec_les_operationid_translates(self):
        chemins = self._chemins()
        ajoutes = openapi_check.etendre_miroir_v1(chemins, self.EXCLUS)
        self.assertEqual(ajoutes, 1)
        miroir = chemins['/api/v1/stock/produits/']
        self.assertEqual(miroir['get']['operationId'], 'v1_stock_produits_list')
        self.assertEqual(miroir['post']['operationId'], 'v1_stock_produits_create')
        # Tout le reste de l'opération est repris tel quel.
        self.assertEqual(miroir['get']['responses'], {'200': {}})

    def test_l_etiquette_auto_derivee_suit_le_prefixe(self):
        """`tags` vaut le 1er segment après le préfixe commun `/api` : le
        miroir porte donc `v1` là où l'original porte `django`. Une étiquette
        posée à la main traverse inchangée."""
        chemins = {
            '/api/django/stock/produits/': {
                'get': {'operationId': 'django_stock_produits_list',
                        'tags': ['django']}},
            '/api/django/crm/leads/': {
                'get': {'operationId': 'django_crm_leads_list',
                        'tags': ['CRM']}},
        }
        openapi_check.etendre_miroir_v1(chemins, self.EXCLUS)
        self.assertEqual(chemins['/api/v1/stock/produits/']['get']['tags'],
                         ['v1'])
        self.assertEqual(chemins['/api/v1/crm/leads/']['get']['tags'], ['CRM'])
        # L'original n'est pas touché.
        self.assertEqual(chemins['/api/django/stock/produits/']['get']['tags'],
                         ['django'])

    def test_les_routes_sans_jumeau_ne_sont_pas_miroitees(self):
        chemins = self._chemins()
        openapi_check.etendre_miroir_v1(chemins, self.EXCLUS)
        self.assertNotIn('/api/v1/public/devis/{token}/', chemins)
        self.assertNotIn('/api/v1/leads/', chemins)
        self.assertIn('/api/public/leads/', chemins)

    def test_le_miroir_est_une_copie_profonde(self):
        """Les POSTPROCESSING_HOOKS mutent en place : rien ne doit refluer."""
        chemins = self._chemins()
        openapi_check.etendre_miroir_v1(chemins, self.EXCLUS)
        chemins['/api/v1/stock/produits/']['get']['responses']['200']['x'] = 1
        self.assertEqual(
            chemins['/api/django/stock/produits/']['get']['responses'],
            {'200': {}})

    def test_un_operationid_sans_prefixe_django_fait_echouer(self):
        """Sonde d'une dérive du préfixe commun estimé par drf-spectacular."""
        chemins = {'/api/django/stock/produits/':
                   {'get': {'operationId': 'stock_produits_list'}}}
        with self.assertRaises(ImproperlyConfigured):
            openapi_check.etendre_miroir_v1(chemins, self.EXCLUS)

    def test_les_parametres_de_niveau_chemin_sont_recopies_tels_quels(self):
        chemins = {'/api/django/stock/produits/{id}/': {
            'parameters': [{'name': 'id', 'in': 'path'}],
            'get': {'operationId': 'django_stock_produits_retrieve'},
        }}
        openapi_check.etendre_miroir_v1(chemins, self.EXCLUS)
        miroir = chemins['/api/v1/stock/produits/{id}/']
        self.assertEqual(miroir['parameters'], [{'name': 'id', 'in': 'path'}])
        self.assertEqual(miroir['get']['operationId'],
                         'v1_stock_produits_retrieve')

    def test_expansion_idempotente_sur_le_nombre_d_operations(self):
        chemins = self._chemins()
        avant = sum(len(v) for v in chemins.values())
        openapi_check.etendre_miroir_v1(chemins, self.EXCLUS)
        apres = sum(len(v) for v in chemins.values())
        self.assertEqual(apres, avant + 2)
