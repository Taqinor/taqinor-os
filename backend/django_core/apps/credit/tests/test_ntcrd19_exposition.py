"""NTCRD19 — rapport d'exposition consolidée : total encours = somme des
encours individuels, tri stable par risque, export xlsx."""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.credit.models import LimiteCredit
from apps.crm.models import Client
from apps.ventes.models import Facture

User = get_user_model()
MONTH = timezone.now().strftime('%Y%m')


def make_company(slug='ntcrd19-co', nom='NTCRD19 Co'):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


class NTCRD19ExpositionTests(TestCase):
    def setUp(self):
        self.company = make_company()
        self.user = User.objects.create_user(
            username='ntcrd19_user', password='x', role_legacy='responsable',
            company=self.company)
        self.api = auth(self.user)
        self.c1 = Client.objects.create(
            company=self.company, nom='Alpha', email='a19@example.com')
        self.c2 = Client.objects.create(
            company=self.company, nom='Beta', email='b19@example.com')

    def _facture(self, client, n, ttc):
        return Facture.objects.create(
            company=self.company, reference=f'FAC-{MONTH}-N19{n:03d}',
            client=client, statut=Facture.Statut.EMISE,
            montant_ttc=Decimal(ttc), created_by=self.user)

    def test_total_encours_matches_sum(self):
        from apps.credit.selectors import encours_client, rapport_exposition
        self._facture(self.c1, 1, '10000')
        self._facture(self.c2, 2, '20000')
        lignes = rapport_exposition(self.company)
        total_rapport = sum(ligne['encours'] for ligne in lignes)
        total_direct = encours_client(self.c1) + encours_client(self.c2)
        self.assertEqual(total_rapport, total_direct)

    def test_sorted_by_risk_desc(self):
        # c2 en dépassement (limite basse) doit passer avant c1 (pas de limite).
        LimiteCredit.objects.create(
            company=self.company, client=self.c2, montant_limite=Decimal('1000'))
        self._facture(self.c2, 3, '5000')
        r = self.api.get('/api/django/credit/exposition/')
        self.assertEqual(r.status_code, 200, r.data)
        ids = [ligne['client_id'] for ligne in r.data['resultats']]
        self.assertEqual(ids[0], self.c2.id)

    def test_xlsx_export(self):
        self._facture(self.c1, 4, '10000')
        r = self.api.get('/api/django/credit/exposition/?export=xlsx')
        self.assertEqual(r.status_code, 200)
        self.assertIn('spreadsheetml', r['Content-Type'])
        self.assertTrue(r.content[:2] == b'PK')  # xlsx = zip
