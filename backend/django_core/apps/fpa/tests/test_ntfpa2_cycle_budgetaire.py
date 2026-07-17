"""NTFPA2 — CycleBudgetaire : machine d'états gardée, transitions illégales → 400."""
from datetime import date

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from authentication.models import Company
from apps.fpa.models import CycleBudgetaire

User = get_user_model()


class TestCycleBudgetaireStateMachine(TestCase):
    def setUp(self):
        self.company, _ = Company.objects.get_or_create(
            slug='ntfpa2-co', defaults={'nom': 'NTFPA2 Co'})
        self.user = User.objects.create_user(
            username='ntfpa2-admin', password='x', company=self.company,
            is_superuser=True)
        self.client = APIClient()
        self.client.force_authenticate(self.user)
        self.cycle = CycleBudgetaire.objects.create(
            company=self.company, nom='Budget 2027',
            date_debut=date(2027, 1, 1), date_fin=date(2027, 12, 31))

    def test_ouvrir_saisie_depuis_brouillon(self):
        resp = self.client.post(
            f'/api/django/fpa/cycles-budgetaires/{self.cycle.pk}/ouvrir-saisie/')
        self.assertEqual(resp.status_code, 200)
        self.cycle.refresh_from_db()
        self.assertEqual(self.cycle.statut, CycleBudgetaire.Statut.OUVERT_SAISIE)

    def test_clore_refuse_depuis_brouillon(self):
        resp = self.client.post(
            f'/api/django/fpa/cycles-budgetaires/{self.cycle.pk}/clore/')
        self.assertEqual(resp.status_code, 400)

    def test_ouvrir_saisie_refuse_deux_fois(self):
        self.client.post(
            f'/api/django/fpa/cycles-budgetaires/{self.cycle.pk}/ouvrir-saisie/')
        resp = self.client.post(
            f'/api/django/fpa/cycles-budgetaires/{self.cycle.pk}/ouvrir-saisie/')
        self.assertEqual(resp.status_code, 400)

    def test_clore_puis_reouverture_refusee(self):
        self.client.post(
            f'/api/django/fpa/cycles-budgetaires/{self.cycle.pk}/ouvrir-saisie/')
        resp = self.client.post(
            f'/api/django/fpa/cycles-budgetaires/{self.cycle.pk}/clore/')
        self.assertEqual(resp.status_code, 200)
        self.cycle.refresh_from_db()
        self.assertTrue(self.cycle.clos)
        resp2 = self.client.post(
            f'/api/django/fpa/cycles-budgetaires/{self.cycle.pk}/ouvrir-saisie/')
        self.assertEqual(resp2.status_code, 400)
