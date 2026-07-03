"""
XFAC6 — Pénalités & intérêts de retard par niveau de relance.

Un niveau paramétré à 10 %/an + 100 MAD affiche la pénalité exacte sur la
lettre J+30, la facturation optionnelle crée une facture de pénalités
séparée, taux 0 = comportement actuel byte-identique, tests.

Run :
    docker compose exec django_core python manage.py test \
        apps.ventes.tests.test_xfac6_penalites_relance -v 2
"""
from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.crm.models import Client
from apps.ventes.models import Facture, FollowupLevel

User = get_user_model()
MONTH = timezone.now().strftime('%Y%m')


def make_company(slug='xfac6-co', nom='XFAC6 Co'):
    from authentication.models import Company
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


def make_client(company, email='xfac6@example.com'):
    return Client.objects.create(
        company=company, nom='Retard', prenom='Client',
        email=email, telephone='+212600000054', adresse='Casablanca',
    )


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


class XFAC6PenalitesRelanceTests(TestCase):
    def setUp(self):
        self.company = make_company()
        self.client_obj = make_client(self.company)
        self.admin = User.objects.create_user(
            username='xfac6_admin', password='x', role_legacy='admin',
            company=self.company,
        )
        self.api = auth(self.admin)
        today = timezone.now().date()
        self.facture = Facture.objects.create(
            company=self.company, reference=f'FAC-{MONTH}-0001',
            client=self.client_obj, statut=Facture.Statut.EMISE,
            montant_ht=Decimal('8333.33'), montant_tva=Decimal('1666.67'),
            montant_ttc=Decimal('10000'), created_by=self.admin,
            date_echeance=today - timedelta(days=30),
        )
        self.niveau_j30 = FollowupLevel.objects.create(
            company=self.company, ordre=2, nom='Mise en demeure',
            delai_jours=30, taux_interet_annuel=Decimal('10.00'),
            frais_fixes=Decimal('100.00'),
        )

    def test_calcul_penalite_exact_at_j30(self):
        """10 000 MAD × 10 %/an × 30/365 + 100 MAD."""
        attendu = (
            Decimal('10000') * Decimal('10') / 100 * Decimal('30') / 365
            + Decimal('100')
        ).quantize(Decimal('0.01'))
        penalite = self.niveau_j30.calcul_penalite(Decimal('10000'), 30)
        self.assertEqual(penalite, attendu)

    def test_taux_zero_returns_zero_byte_identical(self):
        niveau = FollowupLevel.objects.create(
            company=self.company, ordre=0, nom='Rappel', delai_jours=7)
        self.assertEqual(
            niveau.calcul_penalite(Decimal('10000'), 10), Decimal('0.00'))

    def test_relances_list_exposes_penalite(self):
        r = self.api.get('/api/django/ventes/relances/')
        self.assertEqual(r.status_code, 200)
        row = next(x for x in r.data if x['id'] == self.facture.id)
        self.assertIsNotNone(row['niveau'])
        self.assertIn('penalite', row['niveau'])
        self.assertNotEqual(row['niveau']['penalite'], '0.00')

    def test_facturer_penalites_creates_separate_facture(self):
        r = self.api.post(
            f'/api/django/ventes/factures/{self.facture.id}/'
            'facturer-penalites/', {}, format='json')
        self.assertEqual(r.status_code, 201, r.data)
        self.assertNotEqual(r.data['reference'], self.facture.reference)
        self.assertTrue(r.data['libelle'].startswith('Pénalités de retard'))
        # La facture d'origine n'est jamais modifiée dans son montant_du.
        self.facture.refresh_from_db()
        self.assertEqual(self.facture.montant_du, Decimal('10000'))

    def test_facturer_penalites_rejects_when_no_level_reached(self):
        self.facture.date_echeance = timezone.now().date()
        self.facture.save(update_fields=['date_echeance'])
        r = self.api.post(
            f'/api/django/ventes/factures/{self.facture.id}/'
            'facturer-penalites/', {}, format='json')
        self.assertEqual(r.status_code, 400)

    def test_lettre_relance_pdf_includes_penalite(self):
        r = self.api.get(
            f'/api/django/ventes/factures/{self.facture.id}/'
            'lettre-relance-pdf/')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r['Content-Type'], 'application/pdf')
