"""FG25 — politiques d'approbation configurables (au-delà de la remise)."""
from decimal import Decimal

from django.test import TestCase
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.roles.models import Role
from apps.roles.permissions_registre import ADMIN_PERMISSIONS
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

    def test_apar44_route_approbations_retiree(self):
        # D-APAR-2 : l'écran Paramètres › Approbations et ses routes sont
        # retirés ; `discount_approval_threshold` reste l'unique réglage.
        for appel in (
            lambda: self.api.get('/api/django/parametres/approbations/'),
            lambda: self.api.post('/api/django/parametres/approbations/', {
                'action_type': 'purchase_order', 'seuil': '50000',
                'approver_tier': 'admin', 'enabled': True}, format='json'),
        ):
            self.assertEqual(appel().status_code, 404)
        self.assertFalse(ApprovalPolicy.objects.exists())

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
