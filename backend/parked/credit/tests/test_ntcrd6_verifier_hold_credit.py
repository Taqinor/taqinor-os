"""NTCRD6 — service ``verifier_hold_credit`` : couvre les 3 modes + limite
absente (toujours autorisé)."""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase

from apps.credit.models import LimiteCredit
from apps.crm.models import Client

User = get_user_model()


def make_company(slug='ntcrd6-co', nom='NTCRD6 Co'):
    from authentication.models import Company
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


class NTCRD6VerifierHoldCreditTests(TestCase):
    def setUp(self):
        self.company = make_company()
        self.client_obj = Client.objects.create(
            company=self.company, nom='Client', email='ntcrd6@example.com')

    def test_no_limite_always_authorized(self):
        from apps.credit.services import verifier_hold_credit
        result = verifier_hold_credit(self.client_obj, Decimal('1000000'))
        self.assertTrue(result['autorise'])
        self.assertIsNone(result['disponible'])

    def test_mode_aucun_always_authorized(self):
        from apps.credit.services import verifier_hold_credit
        LimiteCredit.objects.create(
            company=self.company, client=self.client_obj,
            montant_limite=Decimal('1000'), mode_hold=LimiteCredit.ModeHold.AUCUN)
        result = verifier_hold_credit(self.client_obj, Decimal('5000'))
        self.assertTrue(result['autorise'])

    def test_mode_avertissement_never_blocks(self):
        from apps.credit.services import verifier_hold_credit
        LimiteCredit.objects.create(
            company=self.company, client=self.client_obj,
            montant_limite=Decimal('1000'),
            mode_hold=LimiteCredit.ModeHold.AVERTISSEMENT)
        result = verifier_hold_credit(self.client_obj, Decimal('5000'))
        self.assertTrue(result['autorise'])
        self.assertEqual(result['mode'], 'avertissement')
        self.assertEqual(result['depassement'], Decimal('4000'))

    def test_mode_blocage_refuses_over_limit(self):
        from apps.credit.services import verifier_hold_credit
        LimiteCredit.objects.create(
            company=self.company, client=self.client_obj,
            montant_limite=Decimal('1000'),
            mode_hold=LimiteCredit.ModeHold.BLOCAGE)
        result = verifier_hold_credit(self.client_obj, Decimal('5000'))
        self.assertFalse(result['autorise'])
        self.assertEqual(result['depassement'], Decimal('4000'))

    def test_mode_blocage_allows_within_limit(self):
        from apps.credit.services import verifier_hold_credit
        LimiteCredit.objects.create(
            company=self.company, client=self.client_obj,
            montant_limite=Decimal('10000'),
            mode_hold=LimiteCredit.ModeHold.BLOCAGE)
        result = verifier_hold_credit(self.client_obj, Decimal('1000'))
        self.assertTrue(result['autorise'])
