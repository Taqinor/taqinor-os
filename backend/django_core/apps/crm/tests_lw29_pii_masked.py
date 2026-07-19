"""LW29 — ``pii_masked`` : le masquage PII devient VISIBLE au lieu de
silencieux.

``LeadSerializer`` masque déjà telephone/email/adresse/whatsapp/gps pour les
utilisateurs sans ``can_view_client_pii`` (force read_only + null, drop
silencieux au PATCH — recon 02 §6). Ce test couvre le champ calculé
``pii_masked`` pour les DEUX profils : un rôle sans ``client_pii_voir`` doit
voir ``pii_masked: true`` + les champs PII à ``null`` ; un admin (repli
historique légacy) doit voir ``pii_masked: false`` + les valeurs réelles."""
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.crm.models import Lead
from apps.roles.models import Role

User = get_user_model()


def _company(slug='lw29-co', nom='LW29 Co'):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


def _api(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


class PiiMaskedFieldTests(TestCase):
    def setUp(self):
        self.company = _company()
        self.role_no_pii = Role.objects.create(
            company=self.company, nom='LW29 sans PII',
            permissions=['crm_voir'])
        self.role_pii = Role.objects.create(
            company=self.company, nom='LW29 avec PII',
            permissions=['crm_voir', 'client_pii_voir'])
        self.lead = Lead.objects.create(
            company=self.company, nom='LW29 Lead',
            telephone='0612345678', email='lead@example.com',
            adresse='12 rue du Soleil')

    def _detail_url(self):
        return f'/api/django/crm/leads/{self.lead.id}/'

    def test_pii_masked_true_and_telephone_null_without_permission(self):
        u = User.objects.create_user(
            username='lw29_masked', password='x',
            role=self.role_no_pii, company=self.company)
        resp = _api(u).get(self._detail_url())
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertTrue(resp.data['pii_masked'])
        self.assertIsNone(resp.data['telephone'])
        self.assertIsNone(resp.data['email'])
        self.assertIsNone(resp.data['adresse'])
        # Le nom (non-PII) reste visible.
        self.assertEqual(resp.data['nom'], 'LW29 Lead')

    def test_pii_masked_false_and_values_visible_with_permission(self):
        u = User.objects.create_user(
            username='lw29_visible', password='x',
            role=self.role_pii, company=self.company)
        resp = _api(u).get(self._detail_url())
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertFalse(resp.data['pii_masked'])
        self.assertEqual(resp.data['telephone'], '0612345678')
        self.assertEqual(resp.data['email'], 'lead@example.com')

    def test_pii_masked_false_for_legacy_admin_account(self):
        # Compte légacy sans rôle fin → repli historique (accès complet).
        u = User.objects.create_user(
            username='lw29_legacy', password='x', role_legacy='admin',
            company=self.company)
        resp = _api(u).get(self._detail_url())
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertFalse(resp.data['pii_masked'])
        self.assertEqual(resp.data['telephone'], '0612345678')

    def test_pii_masked_present_on_list_endpoint_too(self):
        # pii_masked (contrairement à chatter_recent) n'est PAS gated par
        # retrieve() — il doit rester cohérent sur la liste également.
        u = User.objects.create_user(
            username='lw29_list', password='x',
            role=self.role_no_pii, company=self.company)
        resp = _api(u).get('/api/django/crm/leads/')
        self.assertEqual(resp.status_code, 200, resp.data)
        rows = resp.data['results'] if 'results' in resp.data else resp.data
        self.assertTrue(all(row['pii_masked'] for row in rows))
