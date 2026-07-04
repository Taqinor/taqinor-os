"""
XFAC13 — Abandon de créance (write-off) avec motifs + tolérance petits écarts.

Un solde de 0,50 MAD sous tolérance se solde automatiquement à
l'encaissement ; un abandon manuel exige un motif et sort la facture des
impayés/balance âgée ; l'écriture est équilibrée et respecte le verrou de
période.

Run :
    docker compose exec django_core python manage.py test \
        apps.ventes.tests.test_xfac13_abandon_creance -v 2
"""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.crm.models import Client
from apps.parametres.models import CompanyProfile
from apps.ventes.models import Facture

User = get_user_model()
MONTH = timezone.now().strftime('%Y%m')


def make_company(slug='xfac13-co', nom='XFAC13 Co'):
    from authentication.models import Company
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


def make_client(company, email='xfac13@example.com'):
    return Client.objects.create(
        company=company, nom='Abandon', prenom='Client',
        email=email, telephone='+212600000062', adresse='Casablanca',
    )


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


class XFAC13AbandonCreanceTests(TestCase):
    def setUp(self):
        self.company = make_company()
        self.client_obj = make_client(self.company)
        self.admin = User.objects.create_user(
            username='xfac13_admin', password='x', role_legacy='admin',
            company=self.company,
        )
        self.api = auth(self.admin)
        self.facture = Facture.objects.create(
            company=self.company, reference=f'FAC-{MONTH}-0101',
            client=self.client_obj, statut=Facture.Statut.EMISE,
            montant_ht=Decimal('8333.33'), montant_tva=Decimal('1666.67'),
            montant_ttc=Decimal('10000'), created_by=self.admin,
        )

    def test_manual_abandon_requires_motif(self):
        r = self.api.post(
            f'/api/django/ventes/factures/{self.facture.id}/'
            'abandonner-solde/', {}, format='json')
        self.assertEqual(r.status_code, 400, r.data)
        self.facture.refresh_from_db()
        self.assertEqual(self.facture.statut, Facture.Statut.EMISE)

    def test_manual_abandon_with_motif_soldes_facture(self):
        r = self.api.post(
            f'/api/django/ventes/factures/{self.facture.id}/'
            'abandonner-solde/', {'motif': 'irrecouvrable'}, format='json')
        self.assertEqual(r.status_code, 200, r.data)
        self.facture.refresh_from_db()
        self.assertEqual(self.facture.statut, Facture.Statut.PAYEE)
        self.assertEqual(self.facture.montant_du, Decimal('0'))
        self.assertEqual(self.facture.abandon_motif, 'irrecouvrable')
        self.assertEqual(self.facture.abandon_montant, Decimal('10000'))
        self.assertFalse(self.facture.abandon_auto)
        self.assertIsNotNone(self.facture.abandon_date)

    def test_manual_abandon_posts_balanced_entry(self):
        self.api.post(
            f'/api/django/ventes/factures/{self.facture.id}/'
            'abandonner-solde/', {'motif': 'liquidation'}, format='json')
        from apps.compta.models import EcritureComptable, LigneEcriture
        ecriture = EcritureComptable.objects.filter(
            company=self.company).latest('id')
        lignes = LigneEcriture.objects.filter(ecriture=ecriture)
        total_debit = sum((ln.debit for ln in lignes), Decimal('0'))
        total_credit = sum((ln.credit for ln in lignes), Decimal('0'))
        self.assertEqual(total_debit, total_credit)
        self.assertEqual(total_debit, Decimal('10000'))
        numeros = sorted(ln.compte.numero for ln in lignes)
        self.assertEqual(numeros, ['3421', '6585'])

    def test_abandon_on_cancelled_facture_refused(self):
        self.facture.statut = Facture.Statut.ANNULEE
        self.facture.save(update_fields=['statut'])
        r = self.api.post(
            f'/api/django/ventes/factures/{self.facture.id}/'
            'abandonner-solde/', {'motif': 'irrecouvrable'}, format='json')
        self.assertEqual(r.status_code, 400, r.data)

    def test_abandon_with_no_residual_refused(self):
        self.facture.statut = Facture.Statut.PAYEE
        self.facture.save(update_fields=['statut'])
        r = self.api.post(
            f'/api/django/ventes/factures/{self.facture.id}/'
            'abandonner-solde/', {'motif': 'irrecouvrable'}, format='json')
        self.assertEqual(r.status_code, 400, r.data)

    def test_auto_writeoff_under_tolerance_on_payment(self):
        """Tolérance société activée : un résiduel de 0,50 MAD sous le seuil
        de 1 MAD se solde automatiquement à l'encaissement d'un paiement
        partiel qui laisse ce résiduel."""
        profile = CompanyProfile.get(company=self.company)
        profile.tolerance_ecart_reglement = Decimal('1.00')
        profile.save(update_fields=['tolerance_ecart_reglement'])
        r = self.api.post(
            f'/api/django/ventes/factures/{self.facture.id}/'
            'enregistrer-paiement/',
            {'montant': '9999.50',
             'date_paiement': timezone.now().date().isoformat(),
             'mode': 'virement'}, format='json')
        self.assertEqual(r.status_code, 201, r.data)
        self.facture.refresh_from_db()
        self.assertEqual(self.facture.statut, Facture.Statut.PAYEE)
        self.assertEqual(self.facture.montant_du, Decimal('0'))
        self.assertTrue(self.facture.abandon_auto)
        self.assertEqual(self.facture.abandon_motif, 'ecart_reglement')
        self.assertEqual(self.facture.abandon_montant, Decimal('0.50'))

    def test_residual_above_tolerance_not_written_off(self):
        """Un résiduel AU-DESSUS du seuil reste dû (comportement inchangé)."""
        profile = CompanyProfile.get(company=self.company)
        profile.tolerance_ecart_reglement = Decimal('1.00')
        profile.save(update_fields=['tolerance_ecart_reglement'])
        r = self.api.post(
            f'/api/django/ventes/factures/{self.facture.id}/'
            'enregistrer-paiement/',
            {'montant': '9990',
             'date_paiement': timezone.now().date().isoformat(),
             'mode': 'virement'}, format='json')
        self.assertEqual(r.status_code, 201, r.data)
        self.facture.refresh_from_db()
        self.assertEqual(self.facture.statut, Facture.Statut.EMISE)
        self.assertEqual(self.facture.montant_du, Decimal('10.00'))
        self.assertFalse(self.facture.abandon_auto)

    def test_zero_tolerance_byte_identical_behaviour(self):
        """Tolérance par défaut (0) : un résiduel de 0,50 MAD reste dû,
        comportement historique strictement inchangé."""
        r = self.api.post(
            f'/api/django/ventes/factures/{self.facture.id}/'
            'enregistrer-paiement/',
            {'montant': '9999.50',
             'date_paiement': timezone.now().date().isoformat(),
             'mode': 'virement'}, format='json')
        self.assertEqual(r.status_code, 201, r.data)
        self.facture.refresh_from_db()
        self.assertEqual(self.facture.statut, Facture.Statut.EMISE)
        self.assertEqual(self.facture.montant_du, Decimal('0.50'))
        self.assertFalse(self.facture.abandon_auto)
