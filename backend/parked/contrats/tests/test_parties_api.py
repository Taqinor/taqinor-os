"""Tests API des parties/signataires des contrats (``PartieContrat``).

Couvre : société posée côté serveur (jamais du corps), isolation entre sociétés
(A ne voit pas les parties de B), refus d'attacher une partie à un contrat d'une
autre société (400), 404 cross-tenant, persistance de ``ordre``/``type_partie``,
filtre ``?contrat=``, et la règle « au moins deux parties » à la finalisation.
"""
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company

from apps.contrats.models import Contrat, PartieContrat

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


class PartieContratApiTests(TestCase):
    BASE = '/api/django/contrats/parties/'

    def setUp(self):
        self.co_a = make_company('parties-a', 'A')
        self.co_b = make_company('parties-b', 'B')
        self.user_a = make_user(self.co_a, 'parties-a')
        self.user_b = make_user(self.co_b, 'parties-b')
        self.contrat_a = Contrat.objects.create(
            company=self.co_a, objet='Contrat A')
        self.contrat_b = Contrat.objects.create(
            company=self.co_b, objet='Contrat B')

    def _payload(self, contrat, **over):
        data = {
            'contrat': contrat.id,
            'type_partie': PartieContrat.TypePartie.CLIENT,
            'nom': 'ACME SARL',
            'ordre': 1,
        }
        data.update(over)
        return data

    def test_create_forces_company_server_side(self):
        api = auth(self.user_a)
        resp = api.post(self.BASE, self._payload(self.contrat_a), format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        obj = PartieContrat.objects.get(id=resp.data['id'])
        self.assertEqual(obj.company, self.co_a)
        self.assertEqual(obj.contrat, self.contrat_a)

    def test_create_ignores_company_in_body(self):
        api = auth(self.user_a)
        payload = self._payload(self.contrat_a, company=self.co_b.id)
        resp = api.post(self.BASE, payload, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        obj = PartieContrat.objects.get(id=resp.data['id'])
        self.assertEqual(obj.company, self.co_a)

    def test_ordre_and_role_persist(self):
        api = auth(self.user_a)
        payload = self._payload(
            self.contrat_a,
            type_partie=PartieContrat.TypePartie.PRESTATAIRE,
            ordre=3, nom='Taqinor', fonction='Gérant',
            email='g@taqinor.ma', telephone='0600000000')
        resp = api.post(self.BASE, payload, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        obj = PartieContrat.objects.get(id=resp.data['id'])
        self.assertEqual(obj.type_partie, PartieContrat.TypePartie.PRESTATAIRE)
        self.assertEqual(obj.ordre, 3)
        self.assertEqual(obj.fonction, 'Gérant')
        self.assertEqual(obj.email, 'g@taqinor.ma')

    def test_list_isolation(self):
        PartieContrat.objects.create(
            company=self.co_a, contrat=self.contrat_a, nom='Partie A')
        api_b = auth(self.user_b)
        resp = api_b.get(self.BASE)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(rows(resp)), 0)

    def test_cross_company_contrat_rejected(self):
        # user_a tries to attach a party to company B's contract -> 400
        api = auth(self.user_a)
        resp = api.post(self.BASE, self._payload(self.contrat_b), format='json')
        self.assertEqual(resp.status_code, 400, resp.data)
        self.assertEqual(PartieContrat.objects.count(), 0)

    def test_cross_tenant_detail_404(self):
        partie = PartieContrat.objects.create(
            company=self.co_a, contrat=self.contrat_a, nom='Partie A')
        api_b = auth(self.user_b)
        resp = api_b.get(f'{self.BASE}{partie.id}/')
        self.assertEqual(resp.status_code, 404)

    def test_filter_by_contrat(self):
        other = Contrat.objects.create(company=self.co_a, objet='Autre A')
        PartieContrat.objects.create(
            company=self.co_a, contrat=self.contrat_a, nom='P1')
        PartieContrat.objects.create(
            company=self.co_a, contrat=other, nom='P2')
        api = auth(self.user_a)
        resp = api.get(f'{self.BASE}?contrat={self.contrat_a.id}')
        self.assertEqual(resp.status_code, 200)
        data = rows(resp)
        self.assertEqual(len(data), 1)
        self.assertEqual(data[0]['nom'], 'P1')

    def test_role_normal_refuse(self):
        normal = make_user(self.co_a, 'parties-normal', role='normal')
        resp = auth(normal).get(self.BASE)
        self.assertEqual(resp.status_code, 403)

    def test_create_single_party_not_blocked(self):
        # The >=2 rule must NEVER block creating a single party.
        api = auth(self.user_a)
        resp = api.post(self.BASE, self._payload(self.contrat_a), format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        self.assertEqual(self.contrat_a.parties.count(), 1)

    def test_valider_parties_requires_two(self):
        PartieContrat.objects.create(
            company=self.co_a, contrat=self.contrat_a, nom='Seule partie')
        with self.assertRaises(ValidationError):
            self.contrat_a.valider_parties()
        PartieContrat.objects.create(
            company=self.co_a, contrat=self.contrat_a, nom='Deuxième partie',
            type_partie=PartieContrat.TypePartie.PRESTATAIRE)
        self.assertTrue(self.contrat_a.valider_parties())
