"""NTCRD24 — commande ``credit_recalcul_scores`` : idempotente, ne modifie
aucune donnée métier (rapport/log seulement)."""
from decimal import Decimal
from io import StringIO

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TestCase
from django.utils import timezone

from authentication.models import Company
from apps.credit.models import LimiteCredit
from apps.crm.models import Client
from apps.ventes.models import Facture

User = get_user_model()
MONTH = timezone.now().strftime('%Y%m')


def make_company(slug='ntcrd24-co', nom='NTCRD24 Co'):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


class NTCRD24RecalculScoresTests(TestCase):
    def setUp(self):
        self.company = make_company()
        self.user = User.objects.create_user(
            username='ntcrd24_user', password='x', role_legacy='responsable',
            company=self.company)
        self.client_obj = Client.objects.create(
            company=self.company, nom='Client', email='ntcrd24@example.com')
        LimiteCredit.objects.create(
            company=self.company, client=self.client_obj,
            montant_limite=Decimal('10000'))
        Facture.objects.create(
            company=self.company, reference=f'FAC-{MONTH}-N24001',
            client=self.client_obj, statut=Facture.Statut.EMISE,
            montant_ttc=Decimal('5000'), created_by=self.user)

    def test_command_runs_and_reports(self):
        out = StringIO()
        call_command('credit_recalcul_scores', '--company', self.company.id,
                     stdout=out)
        output = out.getvalue()
        self.assertIn(f'client={self.client_obj.id}', output)
        self.assertIn('recalculé', output)

    def test_command_is_non_destructive(self):
        before = LimiteCredit.objects.get(client=self.client_obj).montant_limite
        call_command('credit_recalcul_scores', '--company', self.company.id,
                     stdout=StringIO())
        after = LimiteCredit.objects.get(client=self.client_obj).montant_limite
        self.assertEqual(before, after)
