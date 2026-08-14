"""NTCRM19 — Analytics de la salle de vente (nb vues, dernière vue) +
résumé consommé par la fiche lead."""
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from authentication.models import Company
from apps.crm.models import Lead, SalleVente
from apps.crm.selectors import salle_vente_analytics, salle_vente_summary_for_lead
from apps.roles.models import Role

User = get_user_model()


class SalleVenteAnalyticsSelectorTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(
            nom='Taqinor NTCRM19', slug='taqinor-ntcrm19')
        self.lead = Lead.objects.create(company=self.company, nom='Lead SV19')
        self.salle = SalleVente.objects.create(
            company=self.company, lead=self.lead, titre='Salle NTCRM19')

    def test_zero_vue(self):
        analytics = salle_vente_analytics(self.salle)
        self.assertEqual(analytics['nb_vues'], 0)
        self.assertIsNone(analytics['derniere_vue'])

    def test_compteur_a_jour_apres_3_visites(self):
        public_api = APIClient()
        for _ in range(3):
            resp = public_api.get(f'/api/django/crm/salle-vente/{self.salle.token}/')
            self.assertEqual(resp.status_code, 200)
        analytics = salle_vente_analytics(self.salle)
        self.assertEqual(analytics['nb_vues'], 3)
        self.assertIsNotNone(analytics['derniere_vue'])

    def test_resume_pour_lead_apparait_sur_la_fiche(self):
        public_api = APIClient()
        public_api.get(f'/api/django/crm/salle-vente/{self.salle.token}/')
        public_api.get(f'/api/django/crm/salle-vente/{self.salle.token}/')
        public_api.get(f'/api/django/crm/salle-vente/{self.salle.token}/')
        summary = salle_vente_summary_for_lead(self.company, self.lead.pk)
        self.assertEqual(summary['nb_vues'], 3)

    def test_resume_none_sans_salle(self):
        autre_lead = Lead.objects.create(company=self.company, nom='Sans salle')
        self.assertIsNone(
            salle_vente_summary_for_lead(self.company, autre_lead.pk))


class SalleVenteAnalyticsEndpointTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(
            nom='Taqinor NTCRM19b', slug='taqinor-ntcrm19b')
        self.role = Role.objects.create(
            company=self.company, nom='Commercial', permissions=['crm_creer'])
        self.user = User.objects.create_user(
            username='vendeur_ntcrm19', password='x',
            company=self.company, role=self.role)
        self.api = APIClient()
        self.api.force_authenticate(self.user)

    def test_endpoint_salle_analytics(self):
        lead = Lead.objects.create(company=self.company, nom='Lead endpoint')
        salle = SalleVente.objects.create(
            company=self.company, lead=lead, titre='Salle endpoint')
        resp = self.api.get(f'/api/django/crm/salles-vente/{salle.pk}/analytics/')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertIn('nb_vues', resp.data)

    def test_endpoint_lead_salle_vente_analytics_apparait_sur_la_fiche(self):
        lead = Lead.objects.create(company=self.company, nom='Lead fiche')
        SalleVente.objects.create(
            company=self.company, lead=lead, titre='Salle fiche')
        resp = self.api.get(
            f'/api/django/crm/leads/{lead.pk}/salle-vente-analytics/')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertIn('nb_vues', resp.data)
