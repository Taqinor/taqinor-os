"""Tests for the CRM Lead/Opportunity model and API."""
from django.test import TestCase
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.crm.models import Lead
from apps.crm import stages

User = get_user_model()


def make_company(slug='lead-co', nom='Lead Co'):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


class TestLeadModel(TestCase):
    def setUp(self):
        self.company = make_company()

    def test_default_stage_is_nouveau(self):
        lead = Lead.objects.create(company=self.company, nom='Alaoui')
        # Canonical default = NEW, French label = Nouveau.
        self.assertEqual(lead.stage, stages.NEW)
        self.assertEqual(lead.stage, 'NEW')
        self.assertEqual(lead.get_stage_display(), 'Nouveau')

    def test_default_source_is_native(self):
        lead = Lead.objects.create(company=self.company, nom='Bennani')
        self.assertEqual(lead.source, Lead.Source.OS_NATIVE)

    def test_stage_choices_match_canonical_stages(self):
        choice_keys = [c[0] for c in Lead._meta.get_field('stage').choices]
        self.assertEqual(choice_keys, stages.STAGES)
        # And exactly the canonical 6.
        self.assertEqual(len(choice_keys), 6)

    def test_external_ref_uniqueness(self):
        Lead.objects.create(
            company=self.company, nom='X',
            source=Lead.Source.ODOO_IMPORT_TEST,
            external_system='odoo', external_id='42',
        )
        # Same (company, system, external_id) must not duplicate.
        from django.db import IntegrityError, transaction
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                Lead.objects.create(
                    company=self.company, nom='X dup',
                    source=Lead.Source.ODOO_IMPORT_TEST,
                    external_system='odoo', external_id='42',
                )


class TestLeadAPI(TestCase):
    def setUp(self):
        self.company = make_company()
        self.other = make_company(slug='other-co', nom='Other Co')
        self.user = User.objects.create_user(
            username='lead_api_user', password='x', role_legacy='responsable',
            company=self.company,
        )
        self.api = APIClient()
        token = str(AccessToken.for_user(self.user))
        self.api.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')

    def test_list_scoped_to_company(self):
        Lead.objects.create(company=self.company, nom='Mine')
        Lead.objects.create(company=self.other, nom='Theirs')
        resp = self.api.get('/api/django/crm/leads/')
        self.assertEqual(resp.status_code, 200)
        data = resp.data['results'] if 'results' in resp.data else resp.data
        names = [row['nom'] for row in data]
        self.assertIn('Mine', names)
        self.assertNotIn('Theirs', names)

    def test_create_forces_company_and_defaults(self):
        resp = self.api.post('/api/django/crm/leads/', {'nom': 'Nouveau Lead'})
        self.assertEqual(resp.status_code, 201, resp.data)
        lead = Lead.objects.get(nom='Nouveau Lead')
        self.assertEqual(lead.company_id, self.company.id)
        self.assertEqual(lead.stage, stages.NEW)

    def test_filter_by_source_and_stage(self):
        Lead.objects.create(company=self.company, nom='Imported',
                            source=Lead.Source.ODOO_IMPORT_TEST,
                            external_system='odoo', external_id='1')
        Lead.objects.create(company=self.company, nom='Native')
        resp = self.api.get('/api/django/crm/leads/?source=odoo_import_test')
        data = resp.data['results'] if 'results' in resp.data else resp.data
        names = [row['nom'] for row in data]
        self.assertEqual(names, ['Imported'])


class TestLeadBills(TestCase):
    """A lead stores its electricity bill, with the summer-differs toggle."""

    def setUp(self):
        self.company = make_company()
        self.user = User.objects.create_user(
            username='lead_bill_user', password='x',
            role_legacy='responsable', company=self.company,
        )
        self.api = APIClient()
        token = str(AccessToken.for_user(self.user))
        self.api.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')

    def test_lead_stores_bills_and_toggle(self):
        resp = self.api.post('/api/django/crm/leads/', {
            'nom': 'Bennis', 'telephone': '+212600000003',
            'facture_hiver': '650', 'facture_ete': '420',
            'ete_differente': True,
        }, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        lead = Lead.objects.get(pk=resp.data['id'])
        self.assertEqual(str(lead.facture_hiver), '650.00')
        self.assertEqual(str(lead.facture_ete), '420.00')
        self.assertTrue(lead.ete_differente)

    def test_toggle_off_single_bill(self):
        resp = self.api.post('/api/django/crm/leads/', {
            'nom': 'Sefrioui', 'facture_hiver': '533.50',
            'ete_differente': False,
        }, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        lead = Lead.objects.get(pk=resp.data['id'])
        # Arbitrary typed value kept exactly (no snapping).
        self.assertEqual(str(lead.facture_hiver), '533.50')
        self.assertFalse(lead.ete_differente)
        self.assertIsNone(lead.facture_ete)

    def test_client_link_not_writable_from_browser(self):
        from apps.crm.models import Client
        sneaky = Client.objects.create(
            company=self.company, nom='Sneaky', email='sneaky@example.com')
        resp = self.api.post('/api/django/crm/leads/', {
            'nom': 'Hack', 'client': sneaky.id,
        }, format='json')
        self.assertEqual(resp.status_code, 201)
        self.assertIsNone(Lead.objects.get(pk=resp.data['id']).client_id)


class TestResolveClientForLead(TestCase):
    """Lead → client resolution: reuse, match by email, else create. Never duplicates."""

    def setUp(self):
        from apps.crm.models import Client
        self.company = make_company()
        self.Client = Client

    def test_reuses_already_linked_client(self):
        from apps.crm.services import resolve_client_for_lead
        client = self.Client.objects.create(
            company=self.company, nom='Linked', email='linked@example.com')
        lead = Lead.objects.create(
            company=self.company, nom='Linked', client=client)
        self.assertEqual(resolve_client_for_lead(lead).id, client.id)
        self.assertEqual(self.Client.objects.count(), 1)

    def test_matches_existing_client_by_email(self):
        from apps.crm.services import resolve_client_for_lead
        existing = self.Client.objects.create(
            company=self.company, nom='Match', email='Match@Example.com')
        lead = Lead.objects.create(
            company=self.company, nom='Match', email='match@example.com')
        resolved = resolve_client_for_lead(lead)
        self.assertEqual(resolved.id, existing.id)
        lead.refresh_from_db()
        self.assertEqual(lead.client_id, existing.id)
        self.assertEqual(self.Client.objects.count(), 1)  # no duplicate

    def test_creates_client_from_lead_without_email(self):
        from apps.crm.services import resolve_client_for_lead
        lead = Lead.objects.create(
            company=self.company, nom='Nouveau', prenom='Prospect',
            telephone='+212600000004', ville='Rabat',
        )
        resolved = resolve_client_for_lead(lead)
        self.assertEqual(resolved.nom, 'Nouveau')
        self.assertEqual(resolved.company_id, self.company.id)
        self.assertIsNone(resolved.email)
        # Second resolution reuses the same client (persisted link).
        self.assertEqual(resolve_client_for_lead(lead).id, resolved.id)
        self.assertEqual(self.Client.objects.count(), 1)

    def test_email_match_is_company_scoped(self):
        from apps.crm.services import resolve_client_for_lead
        other = make_company(slug='other-bills-co', nom='Other')
        self.Client.objects.create(
            company=other, nom='Foreign', email='shared@example.com')
        lead = Lead.objects.create(
            company=self.company, nom='Local', email='shared@example.com')
        resolved = resolve_client_for_lead(lead)
        # Must NOT link the other company's client.
        self.assertEqual(resolved.company_id, self.company.id)
        self.assertEqual(self.Client.objects.count(), 2)
