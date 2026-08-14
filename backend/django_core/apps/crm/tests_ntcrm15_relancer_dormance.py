"""NTCRM15 — Bouton one-click « créer une activité de relance » (widget
comptes dormants) : `POST /crm/clients/{id}/relancer-dormance/`."""
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from authentication.models import Company
from apps.crm.models import Client, Lead, LeadActivity
from apps.roles.models import Role

User = get_user_model()


class RelancerDormanceTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(
            nom='Taqinor NTCRM15', slug='taqinor-ntcrm15')
        self.role = Role.objects.create(
            company=self.company, nom='Commercial', permissions=['crm_creer'])
        self.user = User.objects.create_user(
            username='vendeur_ntcrm15', password='x',
            company=self.company, role=self.role)
        self.api = APIClient()
        self.api.force_authenticate(self.user)

    def test_cree_une_activite_liee_au_lead_le_plus_recent(self):
        client = Client.objects.create(company=self.company, nom='Client dormant')
        lead = Lead.objects.create(company=self.company, client=client, nom='Lead 1')
        resp = self.api.post(f'/api/django/crm/clients/{client.pk}/relancer-dormance/')
        self.assertEqual(resp.status_code, 201, resp.data)
        self.assertTrue(
            LeadActivity.objects.filter(
                lead=lead, kind=LeadActivity.Kind.NOTE,
                body__icontains='Relance dormance').exists())

    def test_404_si_aucun_lead_lie(self):
        client = Client.objects.create(company=self.company, nom='Client sans lead')
        resp = self.api.post(f'/api/django/crm/clients/{client.pk}/relancer-dormance/')
        self.assertEqual(resp.status_code, 404)
