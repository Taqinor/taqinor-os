"""NTCRM30 — Notes de réunion structurées liées au plan de compte.

Modèle/serializer/viewset (RevueCompte) déjà scaffoldés par NTCRM10/11
(migration 0063) et le formulaire frontend déjà câblé (PACT105) — cette
lane ajoute la couverture backend manquante : critère d'acceptation, ajouter
une revue de compte l'affiche immédiatement dans la timeline du plan, triée
par date décroissante.
"""
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from authentication.models import Company
from apps.crm.models import Client, PlanCompte, RevueCompte
from apps.roles.models import Role

User = get_user_model()


class RevueCompteApiTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='Taqinor NTCRM30', slug='taqinor-ntcrm30')
        self.role = Role.objects.create(
            company=self.company, nom='Responsable', permissions=['crm_creer', 'crm_modifier'])
        self.user = User.objects.create_user(
            username='resp_ntcrm30', password='x', company=self.company, role=self.role)
        self.client_obj = Client.objects.create(company=self.company, nom='Compte NTCRM30')
        self.plan = PlanCompte.objects.create(company=self.company, client=self.client_obj)
        self.api = APIClient()
        self.api.force_authenticate(self.user)

    def test_ajouter_une_revue_apparait_immediatement_dans_la_timeline(self):
        resp = self.api.post('/api/django/crm/revues-compte/', {
            'plan': self.plan.pk, 'date_revue': '2026-08-01',
            'participants': 'Reda, Client X', 'decisions': 'Signer avant fin du mois',
            'prochaine_action': 'Envoyer le devis final', 'prochaine_action_date': '2026-08-10',
        })
        self.assertEqual(resp.status_code, 201, resp.data)
        self.assertEqual(resp.data['created_by'], self.user.id)

        detail = self.api.get(f'/api/django/crm/plans-compte/{self.plan.pk}/')
        self.assertEqual(detail.status_code, 200)
        self.assertEqual(len(detail.data['revues']), 1)
        self.assertEqual(detail.data['revues'][0]['decisions'], 'Signer avant fin du mois')

    def test_timeline_triee_par_date_decroissante(self):
        RevueCompte.objects.create(
            plan=self.plan, date_revue='2026-01-01', decisions='Ancienne revue')
        RevueCompte.objects.create(
            plan=self.plan, date_revue='2026-06-01', decisions='Revue récente')
        detail = self.api.get(f'/api/django/crm/plans-compte/{self.plan.pk}/')
        dates = [r['date_revue'] for r in detail.data['revues']]
        self.assertEqual(dates, ['2026-06-01', '2026-01-01'])

    def test_pas_de_fuite_cross_tenant(self):
        autre = Company.objects.create(nom='Autre NTCRM30', slug='autre-ntcrm30')
        autre_client = Client.objects.create(company=autre, nom='Compte autre société')
        autre_plan = PlanCompte.objects.create(company=autre, client=autre_client)
        RevueCompte.objects.create(
            plan=autre_plan, date_revue='2026-01-01', decisions='Revue autre société')
        resp = self.api.get('/api/django/crm/revues-compte/')
        self.assertEqual(resp.status_code, 200)
        plan_ids = [r['plan'] for r in resp.data.get('results', resp.data)]
        self.assertNotIn(autre_plan.pk, plan_ids)
