"""NTCRD30/31 — grâce petits montants (seuil de tolérance) + bypass par rôle."""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase

from authentication.models import Company
from apps.credit.models import LimiteCredit, ReglageCredit
from apps.credit.services import verifier_hold_credit
from apps.crm.models import Client
from apps.roles.models import Role

User = get_user_model()


def make_company(slug='ntcrd30-co', nom='NTCRD30 Co'):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


class NTCRD30And31Tests(TestCase):
    def setUp(self):
        self.company = make_company()
        self.client_obj = Client.objects.create(
            company=self.company, nom='Client', email='ntcrd30@example.com')
        LimiteCredit.objects.create(
            company=self.company, client=self.client_obj,
            montant_limite=Decimal('1000'),
            mode_hold=LimiteCredit.ModeHold.BLOCAGE)

    def test_tolerance_grace_small_overrun(self):
        # Seuil 200, dépassement 150 (transaction 1150 vs limite 1000).
        ReglageCredit.objects.create(
            company=self.company,
            seuil_tolerance_depassement=Decimal('200'))
        result = verifier_hold_credit(self.client_obj, Decimal('1150'))
        self.assertTrue(result['autorise'])

    def test_tolerance_does_not_cover_large_overrun(self):
        ReglageCredit.objects.create(
            company=self.company,
            seuil_tolerance_depassement=Decimal('200'))
        result = verifier_hold_credit(self.client_obj, Decimal('5000'))
        self.assertFalse(result['autorise'])

    def test_role_bypass(self):
        role = Role.objects.create(
            company=self.company, nom='Direction Générale', permissions=[])
        user = User.objects.create_user(
            username='ntcrd31_dg', password='x', role_legacy='normal',
            company=self.company, role=role)
        ReglageCredit.objects.create(
            company=self.company, roles_bypass_hold=['Direction Générale'])
        result = verifier_hold_credit(
            self.client_obj, Decimal('5000'), user=user)
        self.assertTrue(result['autorise'])
        self.assertTrue(result['bypass_role'])

    def test_role_not_listed_no_bypass(self):
        role = Role.objects.create(
            company=self.company, nom='Commercial', permissions=[])
        user = User.objects.create_user(
            username='ntcrd31_com', password='x', role_legacy='normal',
            company=self.company, role=role)
        ReglageCredit.objects.create(
            company=self.company, roles_bypass_hold=['Direction Générale'])
        result = verifier_hold_credit(
            self.client_obj, Decimal('5000'), user=user)
        self.assertFalse(result['autorise'])
        self.assertFalse(result['bypass_role'])
