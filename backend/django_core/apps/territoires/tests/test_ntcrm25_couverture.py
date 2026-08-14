"""NTCRM25 — Rapport de couverture : leads récents non matchés par un
territoire actif.

Critère d'acceptation : un lead créé hors de tout territoire défini apparaît
dans le rapport de couverture avec sa région (ville).
"""
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from authentication.models import Company
from apps.crm.models import Lead
from apps.roles.models import Role
from apps.territoires.models import Territoire, TerritoireMembre, TerritoireRegle
from apps.territoires.selectors import rapport_couverture

User = get_user_model()


class CouvertureSelectorTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(
            nom='Taqinor NTCRM25', slug='taqinor-ntcrm25')
        self.role = Role.objects.create(
            company=self.company, nom='Commercial', permissions=['crm_creer'])
        self.commercial = User.objects.create_user(
            username='com_ntcrm25', password='x', company=self.company,
            role=self.role)
        # Territoire actif qui ne couvre QUE Tanger.
        territoire = Territoire.objects.create(company=self.company, nom='Nord')
        TerritoireRegle.objects.create(
            territoire=territoire, ordre=1,
            condition={'field': 'ville', 'operator': 'eq', 'value': 'Tanger'})
        TerritoireMembre.objects.create(territoire=territoire, utilisateur=self.commercial)

    def test_lead_hors_territoire_apparait_avec_sa_region(self):
        lead = Lead.objects.create(
            company=self.company, nom='Lead Errachidia', ville='Errachidia')
        rapport = rapport_couverture(self.company, jours=30)
        self.assertEqual(rapport['total_non_couverts'], 1)
        self.assertEqual(rapport['leads'][0]['lead_id'], lead.pk)
        self.assertEqual(rapport['leads'][0]['ville'], 'Errachidia')
        self.assertEqual(rapport['par_region'], {'Errachidia': 1})

    def test_lead_couvert_absent_du_rapport(self):
        Lead.objects.create(company=self.company, nom='Lead Tanger', ville='Tanger')
        rapport = rapport_couverture(self.company, jours=30)
        self.assertEqual(rapport['total_non_couverts'], 0)
        self.assertEqual(rapport['leads'], [])

    def test_autre_societe_jamais_dans_le_rapport(self):
        autre = Company.objects.create(nom='Autre', slug='autre-ntcrm25')
        Lead.objects.create(company=autre, nom='Lead autre societe', ville='Errachidia')
        rapport = rapport_couverture(self.company, jours=30)
        self.assertEqual(rapport['total_non_couverts'], 0)


class CouvertureEndpointTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(
            nom='Taqinor NTCRM25 API', slug='taqinor-ntcrm25-api')
        self.role = Role.objects.create(
            company=self.company, nom='Administrateur',
            permissions=['crm_creer', 'roles_gerer'])
        self.admin = User.objects.create_user(
            username='admin_ntcrm25', password='x', company=self.company,
            role=self.role)
        self.client_api = APIClient()
        self.client_api.force_authenticate(self.admin)

    def test_endpoint_couverture(self):
        Lead.objects.create(company=self.company, nom='Lead Nador', ville='Nador')
        resp = self.client_api.get('/api/django/territoires/couverture/')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['total_non_couverts'], 1)
        self.assertEqual(resp.data['par_region'], {'Nador': 1})
