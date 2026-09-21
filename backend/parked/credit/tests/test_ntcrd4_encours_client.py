"""NTCRD4 — sélecteur ``encours_client`` : Σ factures ouvertes (hors
ANNULEE/PAYEE), composé au-dessus du sélecteur ventes EXISTANT
``encours_clients_par_tiers`` (YLEDG13) — jamais un nouvel import direct de
``apps.ventes.models``/``apps.facturation.models`` ni une modification de
``apps.ventes.selectors`` (hors périmètre de ce lane, voir docstring du
sélecteur)."""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from apps.crm.models import Client
from apps.ventes.models import Facture

User = get_user_model()
MONTH = timezone.now().strftime('%Y%m')


def make_company(slug='ntcrd4-co', nom='NTCRD4 Co'):
    from authentication.models import Company
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


class NTCRD4EncoursClientTests(TestCase):
    def setUp(self):
        self.company = make_company()
        self.user = User.objects.create_user(
            username='ntcrd4_user', password='x', role_legacy='responsable',
            company=self.company)
        self.client_obj = Client.objects.create(
            company=self.company, nom='Client', email='ntcrd4@example.com')

    def _facture(self, n, statut, ttc):
        return Facture.objects.create(
            company=self.company, reference=f'FAC-{MONTH}-N4{n:03d}',
            client=self.client_obj, statut=statut,
            montant_ht=Decimal(ttc) / Decimal('1.2'),
            montant_tva=Decimal(ttc) - Decimal(ttc) / Decimal('1.2'),
            montant_ttc=Decimal(ttc), created_by=self.user)

    def test_encours_zero_without_documents(self):
        from apps.credit.selectors import encours_client
        self.assertEqual(encours_client(self.client_obj), Decimal('0'))

    def test_encours_sums_open_factures_excludes_closed(self):
        from apps.credit.selectors import encours_client
        self._facture(1, Facture.Statut.EMISE, '10000')
        self._facture(2, Facture.Statut.PAYEE, '5000')
        self._facture(3, Facture.Statut.ANNULEE, '9000')
        self.assertEqual(encours_client(self.client_obj), Decimal('10000'))

    def test_encours_cross_client_isolation(self):
        from apps.credit.selectors import encours_client
        other = Client.objects.create(
            company=self.company, nom='Autre', email='ntcrd4-other@example.com')
        self._facture(4, Facture.Statut.EMISE, '3000')
        self.assertEqual(encours_client(other), Decimal('0'))
