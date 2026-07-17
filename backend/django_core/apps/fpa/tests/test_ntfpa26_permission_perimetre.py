"""NTFPA26 — périmètre par département : un responsable ne peut pas éditer le
budget d'un autre département même en modifiant l'URL/ID (403 testé)."""
from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from authentication.models import Company
from apps.fpa.models import (
    Categorie, CycleBudgetaire, Departement, LigneBudgetDepartement,
)

User = get_user_model()


class TestPerimetreDepartement(TestCase):
    def setUp(self):
        self.company, _ = Company.objects.get_or_create(
            slug='ntfpa26-co', defaults={'nom': 'NTFPA26 Co'})
        self.resp_a = User.objects.create_user(
            username='ntfpa26-a', password='x', company=self.company)
        self.cycle = CycleBudgetaire.objects.create(
            company=self.company, nom='Budget 2027',
            date_debut=date(2027, 1, 1), date_fin=date(2027, 12, 31),
            statut=CycleBudgetaire.Statut.OUVERT_SAISIE)
        self.dept_a = Departement.objects.create(
            company=self.company, code='A', nom='Dept A', responsable=self.resp_a)
        self.dept_b = Departement.objects.create(
            company=self.company, code='B', nom='Dept B')
        self.ligne_b = LigneBudgetDepartement.objects.create(
            company=self.company, cycle=self.cycle, departement=self.dept_b,
            categorie=Categorie.IT, mois=1, montant_prevu=Decimal('1000'))
        self.client = APIClient()
        self.client.force_authenticate(self.resp_a)

    def test_responsable_a_ne_voit_pas_le_budget_de_b(self):
        resp = self.client.get(
            '/api/django/fpa/lignes-budget-departement/',
            {'cycle': self.cycle.pk})
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        rows = data['results'] if isinstance(data, dict) else data
        self.assertEqual(rows, [])

    def test_responsable_a_ne_peut_pas_editer_ligne_de_b(self):
        resp = self.client.patch(
            f'/api/django/fpa/lignes-budget-departement/{self.ligne_b.pk}/',
            {'montant_prevu': 9999})
        # Hors périmètre : soit 404 (filtré du queryset), soit 403 (garde).
        self.assertIn(resp.status_code, (403, 404))

    def test_responsable_a_ne_peut_pas_creer_ligne_pour_b(self):
        resp = self.client.post('/api/django/fpa/lignes-budget-departement/', {
            'cycle': self.cycle.pk, 'departement': self.dept_b.pk,
            'categorie': Categorie.IT, 'mois': 2, 'montant_prevu': 500,
        })
        self.assertEqual(resp.status_code, 403)
