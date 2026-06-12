"""
Tests for lead-primary quote creation: a quote started from a lead carries
BOTH the lead and its resolved client, with no duplicate client records.

Run:
    docker compose exec django_core python manage.py test \
        apps.ventes.tests.test_lead_quotes -v 2
"""
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.crm.models import Client, Lead
from apps.ventes.models import Devis

User = get_user_model()


def make_company(slug='lead-devis-co'):
    from authentication.models import Company
    company, _ = Company.objects.get_or_create(
        slug=slug, defaults={'nom': 'Lead Devis Co'},
    )
    return company


class TestLeadQuoteCreation(TestCase):
    def setUp(self):
        self.company = make_company()
        self.user = User.objects.create_user(
            username='lead_devis_user', password='x',
            role_legacy='responsable', company=self.company,
        )
        self.api = APIClient()
        token = str(AccessToken.for_user(self.user))
        self.api.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')

    def _create_from_lead(self, lead, extra=None):
        payload = {
            'lead': lead.id,
            'statut': 'brouillon',
            'taux_tva': '20.00',
            'remise_globale': '0',
        }
        payload.update(extra or {})
        return self.api.post('/api/django/ventes/devis/', payload, format='json')

    def test_quote_from_lead_attaches_lead_and_resolved_client(self):
        lead = Lead.objects.create(
            company=self.company, nom='Tahiri', prenom='Yasmine',
            telephone='+212600000005', ville='Casablanca',
            facture_hiver=700, ete_differente=False,
        )
        resp = self._create_from_lead(lead)
        self.assertEqual(resp.status_code, 201, resp.data)
        devis = Devis.objects.get(pk=resp.data['id'])
        self.assertEqual(devis.lead_id, lead.id)
        self.assertIsNotNone(devis.client_id)
        lead.refresh_from_db()
        self.assertEqual(devis.client_id, lead.client_id)
        self.assertEqual(devis.client.nom, 'Tahiri')

    def test_second_quote_same_lead_reuses_client(self):
        lead = Lead.objects.create(
            company=self.company, nom='Mansouri', email='m@example.com')
        first = self._create_from_lead(lead)
        second = self._create_from_lead(lead)
        self.assertEqual(first.status_code, 201)
        self.assertEqual(second.status_code, 201)
        d1 = Devis.objects.get(pk=first.data['id'])
        d2 = Devis.objects.get(pk=second.data['id'])
        self.assertEqual(d1.client_id, d2.client_id)
        self.assertEqual(
            Client.objects.filter(company=self.company).count(), 1)

    def test_quote_from_lead_with_discount_kept_exactly(self):
        lead = Lead.objects.create(company=self.company, nom='Remise')
        resp = self._create_from_lead(lead, {'remise_globale': '7.5'})
        self.assertEqual(resp.status_code, 201, resp.data)
        devis = Devis.objects.get(pk=resp.data['id'])
        self.assertEqual(str(devis.remise_globale), '7.50')

    def test_quote_without_lead_or_client_rejected(self):
        resp = self.api.post('/api/django/ventes/devis/', {
            'statut': 'brouillon', 'taux_tva': '20.00', 'remise_globale': '0',
        }, format='json')
        self.assertEqual(resp.status_code, 400)

    def test_foreign_lead_rejected(self):
        other = make_company(slug='lead-devis-other')
        foreign = Lead.objects.create(company=other, nom='Foreign')
        resp = self._create_from_lead(foreign)
        self.assertEqual(resp.status_code, 400)

    def test_client_only_path_still_works(self):
        client = Client.objects.create(
            company=self.company, nom='Direct', email='direct@example.com')
        resp = self.api.post('/api/django/ventes/devis/', {
            'client': client.id, 'statut': 'brouillon',
            'taux_tva': '20.00', 'remise_globale': '0',
        }, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        devis = Devis.objects.get(pk=resp.data['id'])
        self.assertEqual(devis.client_id, client.id)
        self.assertIsNone(devis.lead_id)
