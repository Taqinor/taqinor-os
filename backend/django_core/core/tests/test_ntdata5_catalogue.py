"""NTDATA5 — catalogue de datasets enrichi (métadonnées BI par champ).

Couvre :
  * `register_dataset(field_meta=...)` : label FR + type par champ ;
  * RÉTRO-COMPATIBILITÉ : un dataset sans `field_meta` garde le rendu d'avant
    (chaque champ = dimension portant son propre nom) et `fields` reste une
    simple liste de noms ;
  * un type de champ inconnu est REFUSÉ à l'enregistrement ;
  * `describe_dataset` sépare mesures / dimensions / temps ;
  * l'endpoint `GET core/data-explorer/datasets/[<name>/]` ;
  * un champ sous permission n'est pas PROPOSÉ à un lecteur qui ne peut pas
    l'interroger.

Découplage : le dataset de test porte sur un modèle de FONDATION (Company /
CustomUser) — aucun import d'app domaine.
"""
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIRequestFactory, force_authenticate

from authentication.models import Company
from core import data_explorer
from core.views import DataExplorerDatasetsView

User = get_user_model()


def _provider(company, user):
    return User.objects.filter(company=company)


class CatalogueEnrichiTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.company = Company.objects.create(nom='NTDATA5 SA',
                                             slug='ntdata5-sa')
        cls.user = User.objects.create_user(
            username='ntdata5_u', password='x', company=cls.company)

    def setUp(self):
        data_explorer.register_dataset(
            'ntdata5_avec_meta', 'Avec méta',
            ['id', 'username', 'date_joined'], _provider,
            field_meta={
                'id': {'label': 'Utilisateurs', 'type': 'mesure'},
                'date_joined': {'label': 'Inscription', 'type': 'temps'},
            })
        data_explorer.register_dataset(
            'ntdata5_sans_meta', 'Sans méta', ['id', 'username'], _provider)

    def test_type_de_champ_inconnu_refuse(self):
        with self.assertRaises(ValueError):
            data_explorer.register_dataset(
                'ntdata5_mauvais', 'Mauvais', ['id'], _provider,
                field_meta={'id': {'type': 'chiffre'}})

    def test_catalogue_porte_label_et_type(self):
        catalogue = {d['name']: d for d in data_explorer.list_datasets()}
        champs = {c['name']: c for c in catalogue['ntdata5_avec_meta']['champs']}
        self.assertEqual(champs['id']['type'], data_explorer.TYPE_MESURE)
        self.assertEqual(champs['id']['label'], 'Utilisateurs')
        self.assertEqual(champs['date_joined']['type'],
                         data_explorer.TYPE_TEMPS)
        # Champ SANS méta déclarée → dimension portant son propre nom.
        self.assertEqual(champs['username']['type'],
                         data_explorer.TYPE_DIMENSION)
        self.assertEqual(champs['username']['label'], 'username')

    def test_retro_compatible_sans_field_meta(self):
        catalogue = {d['name']: d for d in data_explorer.list_datasets()}
        sans = catalogue['ntdata5_sans_meta']
        self.assertEqual(sans['fields'], ['id', 'username'])
        self.assertTrue(all(c['type'] == data_explorer.TYPE_DIMENSION
                            for c in sans['champs']))

    def test_describe_dataset_separe_mesures_et_dimensions(self):
        schema = data_explorer.describe_dataset('ntdata5_avec_meta')
        self.assertEqual(schema['mesures'], ['id'])
        self.assertEqual(schema['temps'], ['date_joined'])
        self.assertEqual(schema['dimensions'], ['username'])

    def test_describe_dataset_inconnu(self):
        with self.assertRaises(data_explorer.DatasetInconnu):
            data_explorer.describe_dataset('ntdata5_absent')

    def test_champ_sous_permission_absent_du_catalogue(self):
        from apps.roles.models import Role

        data_explorer.register_dataset(
            'ntdata5_gated', 'Gated', ['id', 'username'], _provider,
            gated_fields={'username': 'can_view_buy_prices'})
        role = Role.objects.create(company=self.company,
                                   nom='NTDATA5 sans achat', permissions=[])
        lecteur = User.objects.create_user(
            username='ntdata5_lecteur', password='x', company=self.company,
            role=role)
        schema = data_explorer.describe_dataset('ntdata5_gated', lecteur)
        self.assertEqual(schema['fields'], ['id'])
        # Sans acteur (appel historique) : rendu complet, inchangé.
        self.assertEqual(
            data_explorer.describe_dataset('ntdata5_gated')['fields'],
            ['id', 'username'])


class CatalogueEndpointTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.company = Company.objects.create(nom='NTDATA5 API',
                                             slug='ntdata5-api')
        cls.user = User.objects.create_user(
            username='ntdata5_api', password='x', company=cls.company)

    def setUp(self):
        self.factory = APIRequestFactory()
        data_explorer.register_dataset(
            'ntdata5_api_ds', 'API', ['id', 'username'], _provider,
            field_meta={'id': {'label': 'Lignes', 'type': 'mesure'}})

    def _get(self, url, **kwargs):
        request = self.factory.get(url)
        force_authenticate(request, user=self.user)
        return DataExplorerDatasetsView.as_view()(request, **kwargs)

    def test_liste_des_datasets(self):
        reponse = self._get('/api/django/core/data-explorer/datasets/')
        self.assertEqual(reponse.status_code, status.HTTP_200_OK)
        noms = {d['name'] for d in reponse.data['datasets']}
        self.assertIn('ntdata5_api_ds', noms)

    def test_detail_d_un_dataset(self):
        reponse = self._get(
            '/api/django/core/data-explorer/datasets/ntdata5_api_ds/',
            name='ntdata5_api_ds')
        self.assertEqual(reponse.status_code, status.HTTP_200_OK)
        self.assertEqual(reponse.data['mesures'], ['id'])
        self.assertEqual(reponse.data['dimensions'], ['username'])

    def test_detail_dataset_inconnu_404(self):
        reponse = self._get(
            '/api/django/core/data-explorer/datasets/absent/', name='absent')
        self.assertEqual(reponse.status_code, status.HTTP_404_NOT_FOUND)
