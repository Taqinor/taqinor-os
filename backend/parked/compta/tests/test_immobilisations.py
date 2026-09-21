"""Tests API du registre des immobilisations (FG118).

Couvre : société posée côté serveur (jamais du corps de requête), isolation
entre sociétés (A ne voit pas les immobilisations de B), corps ``company``
ignoré, accès cross-société en 404, filtre par catégorie, et la TVA/coût TTC
dérivés. Calque le style de ``test_api.py`` (deux sociétés, APIClient + JWT).
"""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company

from apps.compta.models import Immobilisation

User = get_user_model()


def make_company(slug, nom):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


def make_user(company, username, role='responsable'):
    return User.objects.create_user(
        username=username, password='x', company=company, role_legacy=role)


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


def rows(resp):
    data = resp.data
    return data['results'] if isinstance(data, dict) and 'results' in data else data


class ImmobilisationApiTests(TestCase):
    URL = '/api/django/compta/immobilisations/'

    def setUp(self):
        self.co_a = make_company('immo-a', 'Immo A')
        self.co_b = make_company('immo-b', 'Immo B')
        self.user_a = make_user(self.co_a, 'immo-user-a')
        self.user_b = make_user(self.co_b, 'immo-user-b')

    def _make_immo(self, company, libelle='Camionnette', **kwargs):
        defaults = dict(
            libelle=libelle,
            categorie=Immobilisation.Categorie.VEHICULE,
            cout=Decimal('100000'),
            taux_tva=Decimal('20.00'),
            date_acquisition='2026-01-15',
        )
        defaults.update(kwargs)
        return Immobilisation.objects.create(company=company, **defaults)

    def test_create_forces_company_serveur(self):
        api = auth(self.user_a)
        payload = {
            'libelle': 'Perceuse Bosch',
            'categorie': 'outillage',
            'cout': '1500',
            'taux_tva': '20',
            'date_acquisition': '2026-02-01',
        }
        resp = api.post(self.URL, payload, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        immo = Immobilisation.objects.get(id=resp.data['id'])
        self.assertEqual(immo.company, self.co_a)  # posée côté serveur

    def test_create_ignore_company_du_corps(self):
        # Un company injecté dans le corps est ignoré : on reste sur celle du user.
        api = auth(self.user_a)
        payload = {
            'libelle': 'Établi',
            'categorie': 'mobilier',
            'cout': '800',
            'taux_tva': '20',
            'date_acquisition': '2026-02-01',
            'company': self.co_b.id,
        }
        resp = api.post(self.URL, payload, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        immo = Immobilisation.objects.get(id=resp.data['id'])
        self.assertEqual(immo.company, self.co_a)

    def test_list_isolation(self):
        self._make_immo(self.co_a, 'Camionnette A')
        self._make_immo(self.co_b, 'Camionnette B')
        api_a = auth(self.user_a)
        resp = api_a.get(self.URL)
        self.assertEqual(resp.status_code, 200)
        libelles = {r['libelle'] for r in rows(resp)}
        self.assertEqual(libelles, {'Camionnette A'})
        for r in rows(resp):
            self.assertTrue(
                Immobilisation.objects.filter(
                    id=r['id'], company=self.co_a).exists())

    def test_retrieve_cross_company_404(self):
        immo_b = self._make_immo(self.co_b, 'Privée B')
        api_a = auth(self.user_a)
        resp = api_a.get(f'{self.URL}{immo_b.id}/')
        self.assertEqual(resp.status_code, 404)

    def test_filter_par_categorie(self):
        self._make_immo(self.co_a, 'Camion', categorie='vehicule')
        self._make_immo(self.co_a, 'Visseuse', categorie='outillage')
        api = auth(self.user_a)
        resp = api.get(self.URL, {'categorie': 'outillage'})
        self.assertEqual(resp.status_code, 200)
        libelles = {r['libelle'] for r in rows(resp)}
        self.assertEqual(libelles, {'Visseuse'})

    def test_tva_et_ttc_derives(self):
        api = auth(self.user_a)
        payload = {
            'libelle': 'PC Portable',
            'categorie': 'informatique',
            'cout': '10000',
            'taux_tva': '20',
            'date_acquisition': '2026-03-01',
        }
        resp = api.post(self.URL, payload, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        self.assertEqual(Decimal(resp.data['montant_tva']), Decimal('2000.00'))
        self.assertEqual(Decimal(resp.data['cout_ttc']), Decimal('12000.00'))

    def test_cout_negatif_rejete(self):
        api = auth(self.user_a)
        payload = {
            'libelle': 'Coût invalide',
            'categorie': 'materiel',
            'cout': '-5',
            'taux_tva': '20',
            'date_acquisition': '2026-03-01',
        }
        resp = api.post(self.URL, payload, format='json')
        self.assertEqual(resp.status_code, 400)

    def test_acces_refuse_role_normal(self):
        co = make_company('immo-normal', 'Immo Normal')
        normal = make_user(co, 'immo-normal-user', role='normal')
        api = auth(normal)
        resp = api.get(self.URL)
        self.assertEqual(resp.status_code, 403)
