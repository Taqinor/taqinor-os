"""Tests FG41 — plafond_credit client + endpoint credit-warning."""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.crm.models import Client
from apps.ventes.models import Facture, Paiement

User = get_user_model()
MONTH = timezone.now().strftime('%Y%m')
_CTR = [0]


def _nxt():
    _CTR[0] += 1
    return _CTR[0]


def make_company(slug='cw-co', nom='CW Co'):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


class TestCreditWarning(TestCase):
    def setUp(self):
        self.company = make_company()
        self.user = User.objects.create_user(
            username='cw_resp', password='x', role_legacy='responsable',
            company=self.company)
        self.api = auth(self.user)
        self.client_obj = Client.objects.create(
            company=self.company, nom='CW', prenom='Client',
            email='cw@example.com', telephone='+212600000070')

    def _facture(self, statut='emise', ttc=None):
        n = _nxt()
        f = Facture.objects.create(
            company=self.company, reference=f'FAC-{MONTH}-CW{n:04d}',
            client=self.client_obj, statut=statut, taux_tva=Decimal('20'),
            montant_ht=ttc and Decimal(str(ttc)) / Decimal('1.2'),
            montant_tva=ttc and Decimal(str(ttc)) / Decimal('6'),
            montant_ttc=ttc and Decimal(str(ttc)),
        )
        return f

    def _url(self, client_id=None):
        cid = client_id or self.client_obj.id
        return f'/api/django/ventes/clients/{cid}/credit-warning/'

    # ── Modèle ────────────────────────────────────────────────────────────────

    def test_plafond_credit_field_exists(self):
        """Client.plafond_credit est nullable DecimalField."""
        self.client_obj.plafond_credit = Decimal('50000')
        self.client_obj.save()
        self.client_obj.refresh_from_db()
        self.assertEqual(self.client_obj.plafond_credit, Decimal('50000'))

    def test_plafond_credit_nullable(self):
        """Sans plafond défini, plafond_credit=None."""
        self.assertIsNone(self.client_obj.plafond_credit)

    # ── Endpoint ──────────────────────────────────────────────────────────────

    def test_endpoint_no_plafond_no_facture(self):
        """Sans plafond ni facture, encours=0, depasse=False, message=None."""
        r = self.api.get(self._url())
        self.assertEqual(r.status_code, 200, r.data)
        self.assertIsNone(r.data['plafond'])
        self.assertEqual(r.data['encours'], '0')
        self.assertFalse(r.data['depasse'])
        self.assertIsNone(r.data['message'])

    def test_endpoint_with_plafond_not_exceeded(self):
        """Encours < plafond → depasse=False, message=None."""
        self.client_obj.plafond_credit = Decimal('100000')
        self.client_obj.save()
        self._facture(statut='emise', ttc=30000)  # 30k MAD TTC ouvert
        r = self.api.get(self._url())
        self.assertEqual(r.status_code, 200, r.data)
        self.assertFalse(r.data['depasse'])
        self.assertIsNone(r.data['message'])

    def test_endpoint_with_plafond_exceeded(self):
        """Encours > plafond → depasse=True, message renseigné."""
        self.client_obj.plafond_credit = Decimal('20000')
        self.client_obj.save()
        self._facture(statut='emise', ttc=30000)  # 30k > plafond 20k
        r = self.api.get(self._url())
        self.assertEqual(r.status_code, 200, r.data)
        self.assertTrue(r.data['depasse'])
        self.assertIsNotNone(r.data['message'])
        self.assertIn('Plafond', r.data['message'])

    def test_endpoint_with_new_montant_depassera(self):
        """?montant_ttc=X → calcule l'encours prévisionnel et depassera."""
        self.client_obj.plafond_credit = Decimal('50000')
        self.client_obj.save()
        self._facture(statut='emise', ttc=40000)  # 40k ouvert
        # Nouveau document : 15k → 55k > 50k
        r = self.api.get(self._url() + '?montant_ttc=15000')
        self.assertEqual(r.status_code, 200, r.data)
        self.assertTrue(r.data['depassera'])
        self.assertIsNotNone(r.data['encours_avec_nouveau'])
        self.assertIn('Plafond', r.data['message'])

    def test_endpoint_paid_facture_not_counted(self):
        """Une facture payée ne fait pas partie de l'encours."""
        self.client_obj.plafond_credit = Decimal('50000')
        self.client_obj.save()
        f = self._facture(statut='emise', ttc=60000)
        # Enregistrer paiement intégral → statut payée
        Paiement.objects.create(
            company=self.company, facture=f, montant=Decimal('60000'),
            date_paiement=timezone.now().date(), mode='virement',
            created_by=self.user)
        f.statut = 'payee'
        f.save(update_fields=['statut'])
        r = self.api.get(self._url())
        self.assertEqual(r.status_code, 200, r.data)
        self.assertFalse(r.data['depasse'])

    def test_endpoint_cross_company_404(self):
        """Un client d'une autre société est invisible (404)."""
        other_co, _ = Company.objects.get_or_create(
            slug='other-cw-co', defaults={'nom': 'Other CW Co'})
        other_client = Client.objects.create(
            company=other_co, nom='Other', email='other@cw.com',
            telephone='+212600000071')
        r = self.api.get(self._url(other_client.id))
        self.assertEqual(r.status_code, 404, r.data)

    # ── Selector ──────────────────────────────────────────────────────────────

    def test_selector_no_facture(self):
        from apps.crm.selectors import client_credit_warning
        result = client_credit_warning(self.client_obj)
        self.assertEqual(result['encours'], Decimal('0'))
        self.assertFalse(result['depasse'])

    def test_selector_encours_excludes_closed(self):
        """Les factures annulées ou payées ne comptent pas dans l'encours."""
        from apps.crm.selectors import client_credit_warning
        self.client_obj.plafond_credit = Decimal('10000')
        self.client_obj.save()
        self._facture(statut='payee', ttc=9000)
        self._facture(statut='annulee', ttc=9000)
        result = client_credit_warning(self.client_obj)
        self.assertEqual(result['encours'], Decimal('0'))
        self.assertFalse(result['depasse'])
