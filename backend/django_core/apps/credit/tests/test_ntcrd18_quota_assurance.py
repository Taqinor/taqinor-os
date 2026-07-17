"""NTCRD18 — ``quota_assurance_utilise`` : client sans police → garanti=None
(pas de fausse alerte) ; dépassement garantie signalé sans blocage."""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from authentication.models import Company
from apps.credit.models import EncoursGarantiClient, PoliceAssuranceCredit
from apps.crm.models import Client
from apps.ventes.models import Facture

User = get_user_model()
MONTH = timezone.now().strftime('%Y%m')


def make_company(slug='ntcrd18-co', nom='NTCRD18 Co'):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


class NTCRD18QuotaAssuranceTests(TestCase):
    def setUp(self):
        self.company = make_company()
        self.user = User.objects.create_user(
            username='ntcrd18_user', password='x', role_legacy='responsable',
            company=self.company)
        self.client_obj = Client.objects.create(
            company=self.company, nom='Client', email='ntcrd18@example.com')

    def _facture(self, n, ttc):
        return Facture.objects.create(
            company=self.company, reference=f'FAC-{MONTH}-N18{n:03d}',
            client=self.client_obj, statut=Facture.Statut.EMISE,
            montant_ttc=Decimal(ttc), created_by=self.user)

    def test_client_without_police_no_false_alert(self):
        from apps.credit.selectors import quota_assurance_utilise
        result = quota_assurance_utilise(self.client_obj)
        self.assertIsNone(result['garanti'])
        self.assertFalse(result['depasse_garantie'])

    def test_depassement_garantie_signaled_not_blocking(self):
        from apps.credit.selectors import quota_assurance_utilise
        police = PoliceAssuranceCredit.objects.create(
            company=self.company, assureur='Coface', actif=True)
        EncoursGarantiClient.objects.create(
            company=self.company, police=police, client=self.client_obj,
            montant_garanti=Decimal('10000'),
            statut_agrement=EncoursGarantiClient.StatutAgrement.ACCORDE)
        self._facture(1, '15000')
        result = quota_assurance_utilise(self.client_obj)
        self.assertEqual(result['garanti'], Decimal('10000'))
        self.assertTrue(result['depasse_garantie'])
        self.assertGreater(result['pct'], 1.0)

    def test_en_attente_agrement_not_counted(self):
        from apps.credit.selectors import quota_assurance_utilise
        police = PoliceAssuranceCredit.objects.create(
            company=self.company, assureur='Atradius', actif=True)
        EncoursGarantiClient.objects.create(
            company=self.company, police=police, client=self.client_obj,
            montant_garanti=Decimal('10000'),
            statut_agrement=EncoursGarantiClient.StatutAgrement.EN_ATTENTE)
        result = quota_assurance_utilise(self.client_obj)
        self.assertIsNone(result['garanti'])
