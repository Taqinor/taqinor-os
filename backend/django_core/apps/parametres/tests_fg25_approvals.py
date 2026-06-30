"""FG25 — politiques d'approbation configurables (au-delà de la remise)."""
from decimal import Decimal

from django.test import TestCase
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.roles.models import Role, ADMIN_PERMISSIONS
from apps.parametres.models_approvals import ApprovalPolicy

User = get_user_model()


def _company(slug='fg25-co', nom='FG25 Co'):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


class FG25ApprovalPolicyTest(TestCase):
    def setUp(self):
        self.company = _company()
        self.admin_role = Role.objects.create(
            company=self.company, nom='Administrateur',
            permissions=list(ADMIN_PERMISSIONS), est_systeme=True)
        self.admin = User.objects.create_user(
            username='fg25_admin', password='pw', role_legacy='admin',
            role=self.admin_role, company=self.company)
        self.api = APIClient()
        token = str(AccessToken.for_user(self.admin))
        self.api.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')

    def test_create_policy_forces_company(self):
        r = self.api.post('/api/django/parametres/approbations/', {
            'action_type': 'purchase_order', 'seuil': '50000',
            'approver_tier': 'admin', 'enabled': True,
        }, format='json')
        self.assertEqual(r.status_code, 201, r.content)
        p = ApprovalPolicy.objects.get(pk=r.data['id'])
        self.assertEqual(p.company_id, self.company.id)
        self.assertEqual(p.action_type, 'purchase_order')

    def test_requires_approval_helper(self):
        ApprovalPolicy.objects.create(
            company=self.company, action_type='expense',
            seuil=Decimal('1000'), enabled=True)
        self.assertTrue(ApprovalPolicy.requires_approval(
            self.company, 'expense', amount=2000))
        self.assertFalse(ApprovalPolicy.requires_approval(
            self.company, 'expense', amount=500))
        # Type sans politique → jamais d'approbation (inerte).
        self.assertFalse(ApprovalPolicy.requires_approval(
            self.company, 'contract', amount=999999))

    def test_disabled_policy_is_inert(self):
        ApprovalPolicy.objects.create(
            company=self.company, action_type='refund',
            seuil=Decimal('0'), enabled=False)
        self.assertFalse(ApprovalPolicy.requires_approval(
            self.company, 'refund', amount=10000))

    def test_unique_per_company_action(self):
        ApprovalPolicy.objects.create(
            company=self.company, action_type='contract', enabled=True)
        r = self.api.post('/api/django/parametres/approbations/', {
            'action_type': 'contract', 'approver_tier': 'admin',
        }, format='json')
        self.assertEqual(r.status_code, 400, r.content)

    def test_write_requires_admin_tier(self):
        viewer = User.objects.create_user(
            username='fg25_viewer', password='pw', role_legacy='utilisateur',
            company=self.company)
        api = APIClient()
        api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(viewer)}')
        r = api.post('/api/django/parametres/approbations/', {
            'action_type': 'expense', 'approver_tier': 'admin',
        }, format='json')
        self.assertEqual(r.status_code, 403)
