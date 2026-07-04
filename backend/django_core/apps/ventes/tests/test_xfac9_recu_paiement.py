"""
XFAC9 — Reçu de paiement (quittance) PDF + envoi automatique.

Chaque paiement produit un reçu PDF correct (montant en lettres,
affectations, solde), l'email part quand configuré, trace EmailLog, tests
(rendu, scoping cross-company 404).

Run :
    docker compose exec django_core python manage.py test \
        apps.ventes.tests.test_xfac9_recu_paiement -v 2
"""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.crm.models import Client
from apps.ventes.models import EmailLog, Facture, Paiement
from apps.ventes.utils.nombre_lettres import montant_en_lettres

User = get_user_model()
MONTH = timezone.now().strftime('%Y%m')


def make_company(slug='xfac9-co', nom='XFAC9 Co'):
    from authentication.models import Company
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


def make_client(company, email='xfac9@example.com'):
    return Client.objects.create(
        company=company, nom='Recu', prenom='Client',
        email=email, telephone='+212600000058', adresse='Casablanca',
    )


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


class NombreEnLettresTests(TestCase):
    def test_simple_amount(self):
        self.assertEqual(
            montant_en_lettres(Decimal('1250.50')),
            'Mille-deux-cent-cinquante dirhams et cinquante centimes')

    def test_round_amount_no_centimes(self):
        self.assertEqual(
            montant_en_lettres(Decimal('5000.00')),
            'Cinq-mille dirhams')

    def test_one_thousand_invariable(self):
        self.assertTrue(
            montant_en_lettres(Decimal('1000')).startswith('Mille'))


class XFAC9RecuPaiementTests(TestCase):
    def setUp(self):
        self.company = make_company()
        self.client_obj = make_client(self.company)
        self.admin = User.objects.create_user(
            username='xfac9_admin', password='x', role_legacy='admin',
            company=self.company,
        )
        self.api = auth(self.admin)
        self.facture = Facture.objects.create(
            company=self.company, reference=f'FAC-{MONTH}-0001',
            client=self.client_obj, statut=Facture.Statut.EMISE,
            montant_ht=Decimal('4166.67'), montant_tva=Decimal('833.33'),
            montant_ttc=Decimal('5000'), created_by=self.admin,
        )
        self.paiement = Paiement.objects.create(
            company=self.company, facture=self.facture, montant=Decimal('2000'),
            date_paiement=timezone.now().date(), mode='virement',
            created_by=self.admin,
        )

    def test_recu_pdf_renders(self):
        r = self.api.get(
            f'/api/django/ventes/paiements/{self.paiement.id}/recu-pdf/')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r['Content-Type'], 'application/pdf')

    def test_recu_pdf_scoping_cross_company_404(self):
        other_company = make_company(slug='xfac9-other', nom='Other Co')
        other_admin = User.objects.create_user(
            username='xfac9_other_admin', password='x', role_legacy='admin',
            company=other_company,
        )
        other_api = auth(other_admin)
        r = other_api.get(
            f'/api/django/ventes/paiements/{self.paiement.id}/recu-pdf/')
        self.assertEqual(r.status_code, 404)

    def test_envoyer_recu_sends_and_logs(self):
        r = self.api.post(
            f'/api/django/ventes/paiements/{self.paiement.id}/envoyer-recu/',
            {}, format='json')
        self.assertEqual(r.status_code, 201, r.data)
        self.assertEqual(r.data['statut'], 'envoye')
        log = EmailLog.objects.filter(facture=self.facture).first()
        self.assertIsNotNone(log)
        self.assertIn('Quittance', log.sujet)

    def test_envoyer_recu_no_destinataire_logs_echec(self):
        self.client_obj.email = ''
        self.client_obj.save(update_fields=['email'])
        r = self.api.post(
            f'/api/django/ventes/paiements/{self.paiement.id}/envoyer-recu/',
            {}, format='json')
        self.assertEqual(r.status_code, 201)
        self.assertEqual(r.data['statut'], 'echec')

    def test_recu_pdf_for_avance_non_affectee(self):
        avance = Paiement.objects.create(
            company=self.company, client=self.client_obj, facture=None,
            statut_affectation=Paiement.StatutAffectation.NON_AFFECTE,
            montant=Decimal('3000'), date_paiement=timezone.now().date(),
            mode='virement', created_by=self.admin,
        )
        r = self.api.get(
            f'/api/django/ventes/paiements/{avance.id}/recu-pdf/')
        self.assertEqual(r.status_code, 200)
