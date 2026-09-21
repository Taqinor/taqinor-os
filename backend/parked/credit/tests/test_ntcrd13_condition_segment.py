"""NTCRD13 — ConditionPaiementSegment + résolveur : un client sans segment
garde le comportement société par défaut (résolveur renvoie None)."""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase

from authentication.models import Company
from apps.credit.models import ConditionPaiementSegment, SegmentClientCredit
from apps.crm.models import Client

User = get_user_model()


def make_company(slug='ntcrd13-co', nom='NTCRD13 Co'):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


class NTCRD13ConditionSegmentTests(TestCase):
    def setUp(self):
        self.company = make_company()
        self.client_obj = Client.objects.create(
            company=self.company, nom='Client', email='ntcrd13@example.com')

    def test_client_without_segment_falls_back(self):
        from apps.credit.selectors import condition_paiement_client
        self.assertIsNone(condition_paiement_client(self.client_obj))

    def test_resolver_picks_segment_condition(self):
        from apps.credit.selectors import condition_paiement_client
        ConditionPaiementSegment.objects.create(
            company=self.company, segment='grand_compte',
            delai_paiement_jours=60, pct_acompte_defaut=Decimal('10'))
        SegmentClientCredit.objects.create(
            company=self.company, client=self.client_obj,
            segment='grand_compte')
        condition = condition_paiement_client(self.client_obj)
        self.assertIsNotNone(condition)
        self.assertEqual(condition.delai_paiement_jours, 60)

    def test_segment_without_condition_falls_back(self):
        from apps.credit.selectors import condition_paiement_client
        SegmentClientCredit.objects.create(
            company=self.company, client=self.client_obj, segment='inconnu')
        self.assertIsNone(condition_paiement_client(self.client_obj))
