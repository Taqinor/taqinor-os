"""NTMFG1 — Nouvelle app `mrp` + modèle `PosteDeCharge` (work center).

Critère : CRUD company-scopé, code unique par société testé, cross-tenant
refusé (404), migration initiale propre."""
from django.db import IntegrityError, transaction
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.mrp.models import PosteDeCharge

from ._fixtures import make_company, make_user


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


class PosteDeChargeModelTests(TestCase):
    def test_code_unique_per_company(self):
        company = make_company('mrp-poste-1', 'MRP Poste 1')
        PosteDeCharge.objects.create(
            company=company, code='SERT-01', nom='Sertisseuse 1')
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                PosteDeCharge.objects.create(
                    company=company, code='SERT-01', nom='Sertisseuse doublon')

    def test_same_code_allowed_across_companies(self):
        company_a = make_company('mrp-poste-a', 'MRP Poste A')
        company_b = make_company('mrp-poste-b', 'MRP Poste B')
        PosteDeCharge.objects.create(
            company=company_a, code='SERT-01', nom='Sertisseuse A')
        # Ne doit PAS lever — le code n'est unique que PAR société.
        PosteDeCharge.objects.create(
            company=company_b, code='SERT-01', nom='Sertisseuse B')
        self.assertEqual(
            PosteDeCharge.objects.filter(code='SERT-01').count(), 2)


class PosteDeChargeApiTests(TestCase):
    def setUp(self):
        self.company = make_company('mrp-api-1', 'MRP API 1')
        self.other_company = make_company('mrp-api-2', 'MRP API 2')
        self.user = make_user(self.company, 'mrp-api-user')
        self.other_user = make_user(self.other_company, 'mrp-api-other')
        self.api = auth(self.user)

    def test_crud_company_scoped(self):
        resp = self.api.post('/api/django/mrp/postes-charge/', {
            'code': 'LIGNE-A', 'nom': 'Ligne assemblage A',
            'type_poste': 'ligne', 'capacite_heures_jour': '8.00',
            'cout_horaire': '45.00',
        }, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        poste_id = resp.data['id']

        resp = self.api.get('/api/django/mrp/postes-charge/')
        data = resp.data['results'] if isinstance(resp.data, dict) else resp.data
        self.assertEqual(len(data), 1)

        resp = self.api.patch(
            f'/api/django/mrp/postes-charge/{poste_id}/',
            {'cout_horaire': '50.00'}, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(resp.data['cout_horaire'], '50.00')

    def test_company_forced_server_side_not_from_body(self):
        resp = self.api.post('/api/django/mrp/postes-charge/', {
            'code': 'LIGNE-B', 'nom': 'Ligne B', 'company': 999999,
        }, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        poste = PosteDeCharge.objects.get(id=resp.data['id'])
        self.assertEqual(poste.company_id, self.company.id)

    def test_cross_tenant_retrieve_is_404(self):
        poste = PosteDeCharge.objects.create(
            company=self.other_company, code='X-01', nom='Poste étranger')
        resp = self.api.get(f'/api/django/mrp/postes-charge/{poste.id}/')
        self.assertEqual(resp.status_code, 404)

    def test_cross_tenant_list_does_not_leak(self):
        PosteDeCharge.objects.create(
            company=self.other_company, code='X-02', nom='Poste étranger 2')
        resp = self.api.get('/api/django/mrp/postes-charge/')
        data = resp.data['results'] if isinstance(resp.data, dict) else resp.data
        self.assertEqual(len(data), 0)
