"""T11 — mécanisme de champs personnalisés (définitions + validation custom_data)."""
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.crm.models import Lead
from apps.customfields.models import CustomFieldDef
from authentication.models import Company

User = get_user_model()


class CFBase(TestCase):
    def setUp(self):
        self.company = Company.objects.get_or_create(
            slug='cf-co', defaults={'nom': 'CF Co'})[0]
        self.admin = User.objects.create_user(
            username='cf_admin', password='x', role_legacy='admin',
            company=self.company)
        self.api = APIClient()
        self.api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.admin)}')


class TestDefinitions(CFBase):
    def test_admin_creates_definition(self):
        resp = self.api.post('/api/django/custom-fields/definitions/', {
            'module': 'lead', 'code': 'origine_pub', 'libelle': 'Origine pub',
            'type': 'choice', 'options': ['Facebook', 'Google'],
            'obligatoire': True,
        }, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        self.assertTrue(CustomFieldDef.objects.filter(
            company=self.company, module='lead', code='origine_pub').exists())

    def test_scoped_to_company(self):
        other = Company.objects.create(slug='cf-other', nom='Autre')
        CustomFieldDef.objects.create(company=other, module='lead',
                                      code='x', libelle='X', type='text')
        resp = self.api.get('/api/django/custom-fields/definitions/?module=lead')
        self.assertEqual(resp.status_code, 200)
        rows = resp.data['results'] if isinstance(resp.data, dict) else resp.data
        self.assertEqual(len(rows), 0)  # rien de l'autre société


class TestCustomDataValidation(CFBase):
    def test_required_custom_field_enforced_and_stored(self):
        CustomFieldDef.objects.create(
            company=self.company, module='lead', code='budget',
            libelle='Budget', type='number', obligatoire=True)
        # Manquant → 400
        r1 = self.api.post('/api/django/crm/leads/',
                           {'nom': 'Sans budget'}, format='json')
        self.assertEqual(r1.status_code, 400)
        # Fourni → créé et stocké
        r2 = self.api.post('/api/django/crm/leads/',
                           {'nom': 'Avec budget', 'custom_data': {'budget': 50000}},
                           format='json')
        self.assertEqual(r2.status_code, 201, r2.data)
        lead = Lead.objects.get(id=r2.data['id'])
        self.assertEqual(lead.custom_data.get('budget'), 50000)

    def test_choice_validation(self):
        CustomFieldDef.objects.create(
            company=self.company, module='lead', code='canal_pub',
            libelle='Canal', type='choice', options=['A', 'B'])
        bad = self.api.post('/api/django/crm/leads/',
                            {'nom': 'X', 'custom_data': {'canal_pub': 'Z'}},
                            format='json')
        self.assertEqual(bad.status_code, 400)
