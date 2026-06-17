"""N51/N52 — relevés de production (saisie manuelle) + règle de sous-performance.

Run :
    docker compose exec django_core python manage.py test apps.installations.tests_production -v 2
"""
from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.crm.models import Client
from apps.installations.models import Installation, ProductionReleve

User = get_user_model()


def make_company(slug='prod-co', nom='Prod Co'):
    from authentication.models import Company
    return Company.objects.get_or_create(slug=slug, defaults={'nom': nom})[0]


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


class ProductionReleveTests(TestCase):
    def setUp(self):
        self.company = make_company()
        self.resp_user = User.objects.create_user(
            username='prod_resp', password='x', role_legacy='responsable',
            company=self.company)
        self.client_obj = Client.objects.create(company=self.company, nom='C')
        self.inst = Installation.objects.create(
            company=self.company, reference='CHT-PROD-1', client=self.client_obj,
            puissance_installee_kwc=Decimal('10'),
            statut=Installation.Statut.RECEPTIONNE)
        self.api = auth(self.resp_user)

    def test_add_manual_releve_and_summary(self):
        url = f'/api/django/installations/chantiers/{self.inst.id}/production/'
        resp = self.api.post(url, {
            'periode_debut': '2026-01-01', 'periode_fin': '2026-01-31',
            'kwh_produit': '1200',
        }, format='json')
        self.assertEqual(resp.status_code, 201)
        # Source forcée côté serveur (jamais lue du corps).
        self.assertEqual(resp.data['source'], 'manuel')

        got = self.api.get(url)
        self.assertEqual(got.status_code, 200)
        self.assertEqual(len(got.data['releves']), 1)
        summary = got.data['summary']
        self.assertEqual(summary['total_kwh'], 1200.0)
        # Attendu janvier (31 j) = 10 kWc × 1600 × 31/365 ≈ 1358.9 kWh.
        self.assertIsNotNone(summary['total_attendu_kwh'])
        self.assertAlmostEqual(summary['total_attendu_kwh'], 1358.9, delta=1.0)
        self.assertIsNotNone(summary['performance_pct'])

    def test_summary_without_kwc_has_no_expected(self):
        self.inst.puissance_installee_kwc = None
        self.inst.save(update_fields=['puissance_installee_kwc'])
        ProductionReleve.objects.create(
            company=self.company, installation=self.inst,
            periode_debut=date(2026, 2, 1), periode_fin=date(2026, 2, 28),
            kwh_produit=Decimal('900'))
        url = f'/api/django/installations/chantiers/{self.inst.id}/production/'
        got = self.api.get(url)
        self.assertIsNone(got.data['summary']['total_attendu_kwh'])
        self.assertIsNone(got.data['summary']['performance_pct'])

    def test_delete_releve(self):
        r = ProductionReleve.objects.create(
            company=self.company, installation=self.inst,
            periode_debut=date(2026, 3, 1), periode_fin=date(2026, 3, 31),
            kwh_produit=Decimal('1000'))
        url = f'/api/django/installations/chantiers/{self.inst.id}/supprimer-production/'
        resp = self.api.post(url, {'releve': r.id}, format='json')
        self.assertEqual(resp.status_code, 200)
        self.assertFalse(ProductionReleve.objects.filter(id=r.id).exists())

    def test_invalid_period_rejected(self):
        url = f'/api/django/installations/chantiers/{self.inst.id}/production/'
        resp = self.api.post(url, {
            'periode_debut': '2026-01-31', 'periode_fin': '2026-01-01',
            'kwh_produit': '100',
        }, format='json')
        self.assertEqual(resp.status_code, 400)

    def test_no_sous_performance_when_threshold_off(self):
        # Seuil désactivé par défaut → jamais signalé, même très bas.
        ProductionReleve.objects.create(
            company=self.company, installation=self.inst,
            periode_debut=date(2026, 1, 1), periode_fin=date(2026, 1, 31),
            kwh_produit=Decimal('100'))
        url = f'/api/django/installations/chantiers/{self.inst.id}/production/'
        got = self.api.get(url)
        self.assertFalse(got.data['summary']['sous_performance'])

    def test_sous_performance_flagged_with_threshold(self):
        from apps.parametres.models import CompanyProfile
        prof = CompanyProfile.get(self.company)
        prof.seuil_sous_performance_pct = Decimal('80')
        prof.save(update_fields=['seuil_sous_performance_pct'])
        # 100 kWh sur janvier (attendu ≈1359) → ~7 % < 80 % → signalé.
        ProductionReleve.objects.create(
            company=self.company, installation=self.inst,
            periode_debut=date(2026, 1, 1), periode_fin=date(2026, 1, 31),
            kwh_produit=Decimal('100'))
        url = f'/api/django/installations/chantiers/{self.inst.id}/production/'
        got = self.api.get(url)
        self.assertTrue(got.data['summary']['sous_performance'])
        self.assertEqual(got.data['summary']['seuil_pct'], 80.0)

    def test_auto_ticket_created_once(self):
        from apps.parametres.models import CompanyProfile
        from apps.sav.models import Ticket
        prof = CompanyProfile.get(self.company)
        prof.seuil_sous_performance_pct = Decimal('80')
        prof.auto_ticket_sous_performance = True
        prof.save(update_fields=['seuil_sous_performance_pct',
                                 'auto_ticket_sous_performance'])
        url = f'/api/django/installations/chantiers/{self.inst.id}/production/'
        # 1er relevé sous le seuil → un ticket SAV est créé.
        r1 = self.api.post(url, {
            'periode_debut': '2026-01-01', 'periode_fin': '2026-01-31',
            'kwh_produit': '100'}, format='json')
        self.assertEqual(r1.status_code, 201)
        self.assertTrue(r1.data['summary']['ticket_cree'])
        self.assertEqual(Ticket.objects.filter(installation=self.inst).count(), 1)
        # 2e relevé encore sous le seuil → pas de second ticket (idempotent).
        r2 = self.api.post(url, {
            'periode_debut': '2026-02-01', 'periode_fin': '2026-02-28',
            'kwh_produit': '90'}, format='json')
        self.assertFalse(r2.data['summary']['ticket_cree'])
        self.assertEqual(Ticket.objects.filter(installation=self.inst).count(), 1)

    def test_no_auto_ticket_when_disabled(self):
        from apps.parametres.models import CompanyProfile
        from apps.sav.models import Ticket
        prof = CompanyProfile.get(self.company)
        prof.seuil_sous_performance_pct = Decimal('80')  # seuil ON, auto OFF
        prof.save(update_fields=['seuil_sous_performance_pct'])
        url = f'/api/django/installations/chantiers/{self.inst.id}/production/'
        resp = self.api.post(url, {
            'periode_debut': '2026-01-01', 'periode_fin': '2026-01-31',
            'kwh_produit': '100'}, format='json')
        self.assertTrue(resp.data['summary']['sous_performance'])
        self.assertFalse(resp.data['summary']['ticket_cree'])
        self.assertEqual(Ticket.objects.filter(installation=self.inst).count(), 0)

    def test_scoped_to_company(self):
        other = make_company(slug='prod-other', nom='Autre')
        other_inst = Installation.objects.create(
            company=other, reference='CHT-OTHER', client=Client.objects.create(
                company=other, nom='X'),
            statut=Installation.Statut.RECEPTIONNE)
        url = f'/api/django/installations/chantiers/{other_inst.id}/production/'
        resp = self.api.get(url)
        # Le chantier d'une autre société n'est pas visible (404).
        self.assertEqual(resp.status_code, 404)
