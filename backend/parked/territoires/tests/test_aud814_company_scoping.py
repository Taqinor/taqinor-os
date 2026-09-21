"""AUD814 — `TerritoireRegle`/`TerritoireMembre` héritent de
`CompanyScopedModelViewSet` sur des modèles SANS champ `company` : avant le
fix, `get_queryset` appelait `super()` → `TenantMixin.get_queryset`
(`qs.filter(company=…)`) levait un `FieldError` → 500 sur list/retrieve, et
`territoire`/`utilisateur` en `PrimaryKeyRelatedField` non scopés acceptaient
un territoire/utilisateur d'une autre société (création cross-société).

Test ROUGE d'abord : GET liste rendait 500 ; POST cross-société rendait 201.
Après fix : GET → 200 (scopé à la société de l'appelant), POST cross-société
→ 400."""
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from authentication.models import Company
from apps.roles.models import Role
from apps.territoires.models import Territoire, TerritoireMembre, TerritoireRegle

User = get_user_model()


def _admin(company, username):
    role = Role.objects.create(
        company=company, nom=f'Admin {username}',
        permissions=['crm_creer', 'crm_voir', 'roles_gerer'])
    return User.objects.create_user(
        username=username, password='x', company=company, role=role)


class TerritoireRegleScopingTest(TestCase):
    def setUp(self):
        self.company_a = Company.objects.create(
            nom='AUD814 A', slug='aud814-a')
        self.company_b = Company.objects.create(
            nom='AUD814 B', slug='aud814-b')
        self.admin_a = _admin(self.company_a, 'aud814_admin_a')
        self.territoire_a = Territoire.objects.create(
            company=self.company_a, nom='Territoire A')
        self.territoire_b = Territoire.objects.create(
            company=self.company_b, nom='Territoire B')
        self.regle_a = TerritoireRegle.objects.create(
            territoire=self.territoire_a, ordre=1,
            condition={'field': 'ville', 'operator': 'eq', 'value': 'Rabat'})
        self.regle_b = TerritoireRegle.objects.create(
            territoire=self.territoire_b, ordre=1,
            condition={'field': 'ville', 'operator': 'eq', 'value': 'Fès'})
        self.api = APIClient()
        self.api.force_authenticate(self.admin_a)

    def test_list_returns_200_not_500_and_is_company_scoped(self):
        resp = self.api.get('/api/django/territoires/regles/')
        self.assertEqual(resp.status_code, 200, resp.content)
        ids = {row['id'] for row in resp.data['results']} \
            if isinstance(resp.data, dict) and 'results' in resp.data \
            else {row['id'] for row in resp.data}
        self.assertIn(self.regle_a.id, ids)
        self.assertNotIn(self.regle_b.id, ids)

    def test_retrieve_own_regle_ok(self):
        resp = self.api.get(f'/api/django/territoires/regles/{self.regle_a.id}/')
        self.assertEqual(resp.status_code, 200, resp.content)

    def test_retrieve_other_company_regle_is_404_not_500(self):
        resp = self.api.get(f'/api/django/territoires/regles/{self.regle_b.id}/')
        self.assertEqual(resp.status_code, 404, resp.content)

    def test_create_regle_with_cross_company_territoire_rejected(self):
        resp = self.api.post('/api/django/territoires/regles/', {
            'territoire': self.territoire_b.id,
            'ordre': 1,
            'condition': {'field': 'ville', 'operator': 'eq', 'value': 'Agadir'},
        }, format='json')
        self.assertEqual(resp.status_code, 400, resp.content)

    def test_create_regle_with_own_territoire_ok(self):
        resp = self.api.post('/api/django/territoires/regles/', {
            'territoire': self.territoire_a.id,
            'ordre': 2,
            'condition': {'field': 'ville', 'operator': 'eq', 'value': 'Agadir'},
        }, format='json')
        self.assertEqual(resp.status_code, 201, resp.content)


class TerritoireMembreScopingTest(TestCase):
    def setUp(self):
        self.company_a = Company.objects.create(
            nom='AUD814 Membre A', slug='aud814-membre-a')
        self.company_b = Company.objects.create(
            nom='AUD814 Membre B', slug='aud814-membre-b')
        self.admin_a = _admin(self.company_a, 'aud814_membre_admin_a')
        self.commercial_a = _admin(self.company_a, 'aud814_commercial_a')
        self.commercial_b = _admin(self.company_b, 'aud814_commercial_b')
        self.territoire_a = Territoire.objects.create(
            company=self.company_a, nom='Territoire membre A')
        self.territoire_b = Territoire.objects.create(
            company=self.company_b, nom='Territoire membre B')
        self.membre_a = TerritoireMembre.objects.create(
            territoire=self.territoire_a, utilisateur=self.commercial_a)
        self.membre_b = TerritoireMembre.objects.create(
            territoire=self.territoire_b, utilisateur=self.commercial_b)
        self.api = APIClient()
        self.api.force_authenticate(self.admin_a)

    def test_list_returns_200_not_500_and_is_company_scoped(self):
        resp = self.api.get('/api/django/territoires/membres/')
        self.assertEqual(resp.status_code, 200, resp.content)
        ids = {row['id'] for row in resp.data['results']} \
            if isinstance(resp.data, dict) and 'results' in resp.data \
            else {row['id'] for row in resp.data}
        self.assertIn(self.membre_a.id, ids)
        self.assertNotIn(self.membre_b.id, ids)

    def test_create_membre_with_cross_company_territoire_rejected(self):
        resp = self.api.post('/api/django/territoires/membres/', {
            'territoire': self.territoire_b.id,
            'utilisateur': self.commercial_a.id,
        }, format='json')
        self.assertEqual(resp.status_code, 400, resp.content)
        self.assertFalse(TerritoireMembre.objects.filter(
            territoire=self.territoire_b, utilisateur=self.commercial_a).exists())

    def test_create_membre_with_cross_company_utilisateur_rejected(self):
        resp = self.api.post('/api/django/territoires/membres/', {
            'territoire': self.territoire_a.id,
            'utilisateur': self.commercial_b.id,
        }, format='json')
        self.assertEqual(resp.status_code, 400, resp.content)
        self.assertFalse(TerritoireMembre.objects.filter(
            territoire=self.territoire_a, utilisateur=self.commercial_b).exists())

    def test_create_membre_same_company_ok(self):
        autre_commercial = _admin(self.company_a, 'aud814_autre_commercial_a')
        resp = self.api.post('/api/django/territoires/membres/', {
            'territoire': self.territoire_a.id,
            'utilisateur': autre_commercial.id,
        }, format='json')
        self.assertEqual(resp.status_code, 201, resp.content)
