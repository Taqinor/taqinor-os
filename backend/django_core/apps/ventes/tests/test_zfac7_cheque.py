"""
ZFAC7 — Numéro de chèque / banque tirée sur un paiement par chèque.

``Paiement`` gagne deux champs additifs nullable (``numero_cheque``,
``banque_tiree``) affichés/saisis uniquement quand ``mode=cheque`` ; purement
additif, aucun impact sur les autres modes.

Run :
    docker compose exec django_core python manage.py test \
        apps.ventes.tests.test_zfac7_cheque -v 2
"""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.crm.models import Client
from apps.ventes.models import Facture, Paiement

User = get_user_model()
MONTH = timezone.now().strftime('%Y%m')


def make_company(slug='zfac7-co', nom='ZFAC7 Co'):
    from authentication.models import Company
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


def make_client(company, email='zfac7@example.com'):
    return Client.objects.create(
        company=company, nom='Cheque', prenom='Client',
        email=email, telephone='+212600000059', adresse='Casablanca',
    )


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


class ZFAC7ChequePaiementTests(TestCase):
    def setUp(self):
        self.company = make_company()
        self.client_obj = make_client(self.company)
        self.admin = User.objects.create_user(
            username='zfac7_admin', password='x', role_legacy='admin',
            company=self.company,
        )
        self.api = auth(self.admin)
        self.facture = Facture.objects.create(
            company=self.company, reference=f'FAC-{MONTH}-9001',
            client=self.client_obj, statut=Facture.Statut.EMISE,
            montant_ht=Decimal('4166.67'), montant_tva=Decimal('833.33'),
            montant_ttc=Decimal('5000'), created_by=self.admin,
        )

    def test_cheque_payment_records_numero_and_banque(self):
        paiement = Paiement.objects.create(
            company=self.company, facture=self.facture, montant=Decimal('2000'),
            date_paiement=timezone.now().date(), mode='cheque',
            numero_cheque='0012345', banque_tiree='Attijariwafa Bank',
            created_by=self.admin,
        )
        paiement.refresh_from_db()
        self.assertEqual(paiement.numero_cheque, '0012345')
        self.assertEqual(paiement.banque_tiree, 'Attijariwafa Bank')

    def test_virement_payment_leaves_cheque_fields_blank(self):
        paiement = Paiement.objects.create(
            company=self.company, facture=self.facture, montant=Decimal('2000'),
            date_paiement=timezone.now().date(), mode='virement',
            created_by=self.admin,
        )
        self.assertEqual(paiement.numero_cheque, '')
        self.assertEqual(paiement.banque_tiree, '')

    def test_paiement_list_serializes_cheque_fields(self):
        Paiement.objects.create(
            company=self.company, facture=self.facture, montant=Decimal('2000'),
            date_paiement=timezone.now().date(), mode='cheque',
            numero_cheque='0099887', banque_tiree='BMCE Bank',
            created_by=self.admin,
        )
        r = self.api.get('/api/django/ventes/paiements/')
        self.assertEqual(r.status_code, 200)
        data = r.data.get('results', r.data)
        found = next(
            (p for p in data if p.get('numero_cheque') == '0099887'), None)
        self.assertIsNotNone(found)
        self.assertEqual(found['banque_tiree'], 'BMCE Bank')

    def test_recu_pdf_shows_cheque_details(self):
        paiement = Paiement.objects.create(
            company=self.company, facture=self.facture, montant=Decimal('2000'),
            date_paiement=timezone.now().date(), mode='cheque',
            numero_cheque='0055667', banque_tiree='Banque Populaire',
            created_by=self.admin,
        )
        r = self.api.get(
            f'/api/django/ventes/paiements/{paiement.id}/recu-pdf/')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r['Content-Type'], 'application/pdf')
