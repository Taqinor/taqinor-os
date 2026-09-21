"""NTCRD43 — intégration au chatter unifié records : une décision de
dérogation apparaît dans le flux d'activité générique du client."""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.contrib.contenttypes.models import ContentType
from django.test import TestCase

from authentication.models import Company
from apps.credit.models import DerogationCredit
from apps.credit.services import approuver_derogation
from apps.crm.models import Client
from apps.records.models import Activity

User = get_user_model()


def make_company(slug='ntcrd43-co', nom='NTCRD43 Co'):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


class NTCRD43RecordsChatterTests(TestCase):
    def setUp(self):
        self.company = make_company()
        self.admin = User.objects.create_user(
            username='ntcrd43_admin', password='x', role_legacy='admin',
            company=self.company)
        self.client_obj = Client.objects.create(
            company=self.company, nom='Client', email='ntcrd43@example.com')

    def test_approval_logged_in_client_feed(self):
        d = DerogationCredit.objects.create(
            company=self.company, client=self.client_obj,
            montant_demande=Decimal('5000'))
        approuver_derogation(d, self.admin)
        ct = ContentType.objects.get_for_model(Client)
        activites = Activity.objects.filter(
            content_type=ct, object_id=self.client_obj.id)
        self.assertTrue(activites.exists())
        self.assertIn('Dérogation', activites.first().body)

    def test_credit_targets_declared_in_platform(self):
        from apps.credit.platform import PLATFORM
        self.assertIn('credit.limitecredit', PLATFORM['record_targets'])
        self.assertIn('credit.derogationcredit', PLATFORM['record_targets'])
