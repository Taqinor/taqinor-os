"""NTCRM10 — Plan de compte (Account Planning) formel."""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from authentication.models import Company
from apps.crm.models import Client, PlanCompte
from apps.roles.models import Role

User = get_user_model()


class PlanCompteApiTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='Taqinor NTCRM10', slug='taqinor-ntcrm10')
        self.role = Role.objects.create(
            company=self.company, nom='Responsable', permissions=['crm_creer', 'crm_modifier'])
        self.user = User.objects.create_user(
            username='resp_ntcrm10', password='x', company=self.company, role=self.role)
        self.client_obj = Client.objects.create(company=self.company, nom='Compte stratégique')
        self.client_api = APIClient()
        self.client_api.force_authenticate(self.user)

    def test_creer_editer_voir_historique(self):
        resp = self.client_api.post('/api/django/crm/plans-compte/', {
            'client': self.client_obj.pk,
            'objectifs_strategiques': 'Doubler le CA en 2027',
            'potentiel_estime': '500000',
            'statut': 'brouillon',
        })
        self.assertEqual(resp.status_code, 201, resp.data)
        plan_id = resp.data['id']

        resp = self.client_api.patch(f'/api/django/crm/plans-compte/{plan_id}/', {
            'statut': 'actif',
            'potentiel_estime': '750000',
        })
        self.assertEqual(resp.status_code, 200, resp.data)
        plan = PlanCompte.objects.get(pk=plan_id)
        self.assertEqual(plan.statut, 'actif')
        self.assertEqual(plan.potentiel_estime, Decimal('750000'))

        resp = self.client_api.get(f'/api/django/crm/plans-compte/{plan_id}/historique/')
        self.assertEqual(resp.status_code, 200)
        kinds = [entry['kind'] for entry in resp.data]
        self.assertIn('creation', kinds)
        self.assertIn('modification', kinds)

    def test_revue_de_compte_apparait_en_timeline(self):
        plan = PlanCompte.objects.create(
            company=self.company, client=self.client_obj, created_by=self.user)
        resp = self.client_api.post('/api/django/crm/revues-compte/', {
            'plan': plan.pk, 'date_revue': '2026-07-15',
            'decisions': 'Augmenter la fréquence de contact.',
        })
        self.assertEqual(resp.status_code, 201, resp.data)
        resp = self.client_api.get(f'/api/django/crm/plans-compte/{plan.pk}/')
        self.assertEqual(len(resp.data['revues']), 1)
