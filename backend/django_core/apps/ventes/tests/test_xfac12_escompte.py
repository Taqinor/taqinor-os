"""
XFAC12 — Escompte pour règlement anticipé (ex. 2/10 net 30).

Une facture 2 %/10 j payée à J+7 au montant net passe ``payee`` avec
l'escompte tracé, payée à J+15 le plein tarif reste dû, mention PDF
correcte, tests.

Run :
    docker compose exec django_core python manage.py test \
        apps.ventes.tests.test_xfac12_escompte -v 2
"""
from datetime import timedelta
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


def make_company(slug='xfac12-co', nom='XFAC12 Co'):
    from authentication.models import Company
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


def make_client(company, email='xfac12@example.com'):
    return Client.objects.create(
        company=company, nom='Escompte', prenom='Client',
        email=email, telephone='+212600000061', adresse='Casablanca',
    )


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


class XFAC12EscompteTests(TestCase):
    def setUp(self):
        self.company = make_company()
        self.client_obj = make_client(self.company)
        self.admin = User.objects.create_user(
            username='xfac12_admin', password='x', role_legacy='admin',
            company=self.company,
        )
        self.api = auth(self.admin)
        self.emission = timezone.now().date() - timedelta(days=7)
        self.facture = Facture.objects.create(
            company=self.company, reference=f'FAC-{MONTH}-0001',
            client=self.client_obj, statut=Facture.Statut.EMISE,
            montant_ht=Decimal('8333.33'), montant_tva=Decimal('1666.67'),
            montant_ttc=Decimal('10000'), created_by=self.admin,
            escompte_pct=Decimal('2.00'), escompte_jours=10,
        )
        # Forcer la date d'émission (auto_now_add) via update direct.
        Facture.objects.filter(pk=self.facture.pk).update(
            date_emission=self.emission)
        self.facture.refresh_from_db()

    def test_paid_at_j7_net_amount_soldes_and_traces_escompte(self):
        """2 % de 10 000 = 200 → net 9 800 payé à J+7 (fenêtre 10j) solde."""
        r = self.api.post(
            f'/api/django/ventes/factures/{self.facture.id}/'
            'enregistrer-paiement/',
            {'montant': '9800', 'date_paiement': timezone.now().date().isoformat(),
             'mode': 'virement'}, format='json')
        self.assertEqual(r.status_code, 201, r.data)
        self.facture.refresh_from_db()
        self.assertEqual(self.facture.statut, Facture.Statut.PAYEE)
        self.assertEqual(self.facture.montant_du, Decimal('0'))
        paiement = Paiement.objects.get(facture=self.facture)
        self.assertEqual(paiement.escompte_montant, Decimal('200.00'))

    def test_paid_at_j15_full_amount_still_due_no_escompte(self):
        """Hors fenêtre (J+15 > 10j) : plein tarif net_attendu ne matche pas,
        un règlement partiel de 9800 reste dû (pas d'escompte automatique)."""
        Facture.objects.filter(pk=self.facture.pk).update(
            date_emission=timezone.now().date() - timedelta(days=15))
        self.facture.refresh_from_db()
        r = self.api.post(
            f'/api/django/ventes/factures/{self.facture.id}/'
            'enregistrer-paiement/',
            {'montant': '9800', 'date_paiement': timezone.now().date().isoformat(),
             'mode': 'virement'}, format='json')
        self.assertEqual(r.status_code, 201, r.data)
        self.facture.refresh_from_db()
        self.assertEqual(self.facture.statut, Facture.Statut.EMISE)
        self.assertEqual(self.facture.montant_du, Decimal('200.00'))
        paiement = Paiement.objects.get(facture=self.facture)
        self.assertEqual(paiement.escompte_montant or Decimal('0'), Decimal('0'))

    def test_full_payment_within_window_unaffected(self):
        """Un règlement au PLEIN tarif (pas le net) reste un paiement normal,
        sans escompte automatique (le client n'a pas demandé l'escompte)."""
        r = self.api.post(
            f'/api/django/ventes/factures/{self.facture.id}/'
            'enregistrer-paiement/',
            {'montant': '10000', 'date_paiement': timezone.now().date().isoformat(),
             'mode': 'virement'}, format='json')
        self.assertEqual(r.status_code, 201, r.data)
        self.facture.refresh_from_db()
        self.assertEqual(self.facture.statut, Facture.Statut.PAYEE)
        paiement = Paiement.objects.get(facture=self.facture)
        self.assertEqual(paiement.escompte_montant or Decimal('0'), Decimal('0'))

    def test_no_escompte_configured_byte_identical(self):
        facture2 = Facture.objects.create(
            company=self.company,
            reference=f'FAC-{MONTH}-0002',
            client=self.client_obj, statut=Facture.Statut.EMISE,
            montant_ht=Decimal('4166.67'), montant_tva=Decimal('833.33'),
            montant_ttc=Decimal('5000'), created_by=self.admin,
        )
        r = self.api.post(
            f'/api/django/ventes/factures/{facture2.id}/enregistrer-paiement/',
            {'montant': '4900', 'date_paiement': timezone.now().date().isoformat(),
             'mode': 'virement'}, format='json')
        self.assertEqual(r.status_code, 201, r.data)
        facture2.refresh_from_db()
        self.assertEqual(facture2.montant_du, Decimal('100'))
        self.assertEqual(facture2.statut, Facture.Statut.EMISE)

    def test_escompte_mention_on_facture(self):
        mention = self.facture.escompte_mention
        self.assertIsNotNone(mention)
        self.assertEqual(mention['pct'], Decimal('2.00'))
        self.assertEqual(mention['jours'], 10)
        self.assertEqual(mention['montant'], Decimal('200.00'))
