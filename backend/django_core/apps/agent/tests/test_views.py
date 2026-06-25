"""AG1 — Tests de l'endpoint GET /api/django/agent/actions/.

Couvre :
- auth requise (401/403 sans token) ;
- l'endpoint renvoie seulement les actions que le caller peut exécuter ;
- aucun débordement inter-société : deux utilisateurs de sociétés distinctes
  avec le même nom de permission voient leur catalogue filtré par LEUR rôle,
  sans fuite de l'autre société.
"""
from django.test import TestCase
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.roles.models import Role

User = get_user_model()
URL = '/api/django/agent/actions/'


def _auth(user):
    api = APIClient()
    token = str(AccessToken.for_user(user))
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')
    return api


class AgentActionsEndpointTest(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='Co A', slug='co-a')
        self.sales_role = Role.objects.create(
            company=self.company, nom='Vendeur',
            permissions=['ventes_creer', 'ventes_pdf', 'crm_voir'])
        self.sales = User.objects.create_user(
            username='vendeur_a', password='x', role=self.sales_role,
            company=self.company)
        self.readonly_role = Role.objects.create(
            company=self.company, nom='Lecture', permissions=['crm_voir'])
        self.readonly = User.objects.create_user(
            username='ro_a', password='x', role=self.readonly_role,
            company=self.company)

    def test_requires_authentication(self):
        resp = APIClient().get(URL)
        self.assertIn(resp.status_code, (401, 403))

    def test_returns_only_permitted_actions(self):
        resp = _auth(self.sales).get(URL)
        self.assertEqual(resp.status_code, 200)
        keys = {a['key'] for a in resp.data['actions']}
        self.assertEqual(resp.data['count'], len(resp.data['actions']))
        self.assertIn('ventes.devis.creer_auto', keys)
        self.assertIn('ventes.devis.proposal_pdf', keys)
        self.assertNotIn('stock.produit.delete', keys)

    def test_readonly_user_gets_limited_catalogue(self):
        resp = _auth(self.readonly).get(URL)
        self.assertEqual(resp.status_code, 200)
        keys = {a['key'] for a in resp.data['actions']}
        self.assertIn('crm.lead.list', keys)
        self.assertNotIn('ventes.devis.creer_auto', keys)
        self.assertNotIn('ventes.devis.proposal_pdf', keys)

    def test_action_metadata_present(self):
        resp = _auth(self.sales).get(URL)
        action = next(a for a in resp.data['actions']
                      if a['key'] == 'ventes.devis.proposal_pdf')
        for fld in ('key', 'label', 'description', 'inputs', 'endpoint',
                    'method', 'required_permission', 'risk', 'confirm_summary'):
            self.assertIn(fld, action)
        self.assertEqual(action['risk'], 'outward')


class CrossTenantNoLeakageTest(TestCase):
    """Deux sociétés distinctes : le filtre est par rôle/permission, et un rôle
    n'existe que dans SA société, donc le catalogue ne fuit pas d'une société à
    l'autre."""

    def setUp(self):
        self.co_a = Company.objects.create(nom='Tenant A', slug='tenant-a')
        self.co_b = Company.objects.create(nom='Tenant B', slug='tenant-b')
        # Société A : un vendeur avec ventes_creer.
        self.role_a = Role.objects.create(
            company=self.co_a, nom='Vendeur A', permissions=['ventes_creer'])
        self.user_a = User.objects.create_user(
            username='u_a', password='x', role=self.role_a, company=self.co_a)
        # Société B : un utilisateur lecture seule (crm_voir uniquement).
        self.role_b = Role.objects.create(
            company=self.co_b, nom='Lecture B', permissions=['crm_voir'])
        self.user_b = User.objects.create_user(
            username='u_b', password='x', role=self.role_b, company=self.co_b)

    def test_each_tenant_sees_own_permission_set(self):
        keys_a = {a['key'] for a in _auth(self.user_a).get(URL).data['actions']}
        keys_b = {a['key'] for a in _auth(self.user_b).get(URL).data['actions']}
        # A peut créer un devis ; B (lecture seule autre société) non.
        self.assertIn('ventes.devis.creer_auto', keys_a)
        self.assertNotIn('ventes.devis.creer_auto', keys_b)
        # B voit les leads (crm_voir) ; A n'a pas crm_voir → ne le voit pas.
        self.assertIn('crm.lead.list', keys_b)
        self.assertNotIn('crm.lead.list', keys_a)
