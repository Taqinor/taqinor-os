"""
XFAC4 — Retenue à la source subie côté client (RAS TVA 2024 / RAS honoraires)
sur factures clients.

Une facture 10 000 TTC payée 9 250 + RAS 750 passe ``payee``, la retenue
apparaît dans l'état des attestations en attente, la réception de
l'attestation se coche avec justificatif, tests (solde exact, scoping).

Run :
    docker compose exec django_core python manage.py test \
        apps.ventes.tests.test_xfac4_retenue_subie -v 2
"""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.crm.models import Client
from apps.ventes.models import Facture, RetenueSubie

User = get_user_model()
MONTH = timezone.now().strftime('%Y%m')


def make_company(slug='xfac4-co', nom='XFAC4 Co'):
    from authentication.models import Company
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


def make_client(company, email='xfac4@example.com'):
    return Client.objects.create(
        company=company, nom='RAS', prenom='Client',
        email=email, telephone='+212600000052', adresse='Casablanca',
    )


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


class XFAC4RetenueSubieTests(TestCase):
    def setUp(self):
        self.company = make_company()
        self.client_obj = make_client(self.company)
        self.admin = User.objects.create_user(
            username='xfac4_admin', password='x', role_legacy='admin',
            company=self.company,
        )
        self.api = auth(self.admin)
        self.facture = Facture.objects.create(
            company=self.company, reference=f'FAC-{MONTH}-0001',
            client=self.client_obj, statut=Facture.Statut.EMISE,
            montant_ht=Decimal('8333.33'), montant_tva=Decimal('1666.67'),
            montant_ttc=Decimal('10000'), created_by=self.admin,
        )

    def _url(self):
        return (f'/api/django/ventes/paiements/factures/{self.facture.id}/'
                'paiement-avec-retenue/')

    def test_paiement_avec_retenue_soldes_facture_exactly(self):
        """9 250 payé + 750 RAS (taux 8.108...%) soldent exactement 10 000."""
        # taux = 750 / 9250 * 100 (base = montant + retenue, arrondi 2 déc.)
        taux = (Decimal('750') / Decimal('9250') * 100).quantize(Decimal('0.01'))
        r = self.api.post(self._url(), {
            'montant': '9250', 'date_paiement': timezone.now().date().isoformat(),
            'mode': 'virement', 'type_retenue': 'ras_tva', 'taux': str(taux),
        }, format='json')
        self.assertEqual(r.status_code, 201, r.data)
        self.facture.refresh_from_db()
        self.assertEqual(self.facture.statut, Facture.Statut.PAYEE)
        self.assertEqual(self.facture.montant_du, Decimal('0'))
        retenue = RetenueSubie.objects.get(facture=self.facture)
        self.assertFalse(retenue.attestation_recue)

    def test_retenue_appears_in_attestations_en_attente(self):
        taux = Decimal('7.5')
        self.api.post(self._url(), {
            'montant': '9000', 'date_paiement': timezone.now().date().isoformat(),
            'mode': 'virement', 'type_retenue': 'ras_tva', 'taux': str(taux),
        }, format='json')
        r = self.api.get(
            '/api/django/ventes/paiements/attestations-ras-en-attente/')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(len(r.data), 1)
        self.assertFalse(r.data[0]['attestation_recue'])

    def test_attestation_recue_marks_with_justificatif(self):
        self.api.post(self._url(), {
            'montant': '9000', 'date_paiement': timezone.now().date().isoformat(),
            'mode': 'virement', 'type_retenue': 'ras_tva', 'taux': '7.5',
        }, format='json')
        retenue = RetenueSubie.objects.get(facture=self.facture)
        r = self.api.post(
            f'/api/django/ventes/paiements/retenues/{retenue.id}/'
            'attestation-recue/',
            {'attestation_fichier': 'minio-key/attestation.pdf'}, format='json')
        self.assertEqual(r.status_code, 200, r.data)
        retenue.refresh_from_db()
        self.assertTrue(retenue.attestation_recue)
        self.assertEqual(retenue.attestation_fichier, 'minio-key/attestation.pdf')
        self.assertIsNotNone(retenue.attestation_date)

    def test_cross_company_facture_404(self):
        other_company = make_company(slug='xfac4-other', nom='Other Co')
        other_admin = User.objects.create_user(
            username='xfac4_other_admin', password='x', role_legacy='admin',
            company=other_company,
        )
        other_api = auth(other_admin)
        r = other_api.post(self._url(), {
            'montant': '1000', 'date_paiement': timezone.now().date().isoformat(),
            'mode': 'virement', 'type_retenue': 'ras_tva', 'taux': '5',
        }, format='json')
        self.assertEqual(r.status_code, 404)

    def test_taux_out_of_range_rejected(self):
        r = self.api.post(self._url(), {
            'montant': '9000', 'date_paiement': timezone.now().date().isoformat(),
            'mode': 'virement', 'type_retenue': 'ras_tva', 'taux': '150',
        }, format='json')
        self.assertEqual(r.status_code, 400)
