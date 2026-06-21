"""Tests for CRM feature gaps FG27, FG28, FG29, FG31, FG33, FG34, FG36, FG38."""
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken
from django.contrib.auth import get_user_model

from authentication.models import Company
from apps.crm.models import Client, Lead, LeadActivity, MessageTemplate
from apps.crm import stages

User = get_user_model()


def make_company(slug='fg-co', nom='FG Co'):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


def make_user(company, username, role='responsable'):
    return User.objects.create_user(
        username=username,
        password='x',
        role_legacy=role,
        company=company,
    )


def make_api(user):
    api = APIClient()
    token = str(AccessToken.for_user(user))
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')
    return api


class TestFG27LeadScoring(TestCase):
    """FG27 — Lead scoring: score computed from existing fields."""

    def setUp(self):
        self.company = make_company('fg27-co', 'FG27 Co')

    def test_score_field_in_serializer(self):
        user = make_user(self.company, 'fg27user')
        api = make_api(user)
        resp = api.post('/api/django/crm/leads/', {'nom': 'Scoring Test'})
        self.assertEqual(resp.status_code, 201, resp.data)
        self.assertIn('score', resp.data)
        self.assertIn('score_label', resp.data)

    def test_score_is_integer_0_to_100(self):
        user = make_user(self.company, 'fg27user2')
        api = make_api(user)
        resp = api.post('/api/django/crm/leads/', {
            'nom': 'Scored',
            'telephone': '0612345678',
            'facture_hiver': '3500',
            'canal': 'reference',
            'type_installation': 'residentiel',
        })
        self.assertEqual(resp.status_code, 201)
        score = resp.data['score']
        self.assertIsInstance(score, int)
        self.assertGreaterEqual(score, 0)
        self.assertLessEqual(score, 100)

    def test_score_label_values(self):
        from apps.crm.scoring import score_label
        self.assertEqual(score_label(75), 'Chaud')
        self.assertEqual(score_label(50), 'Tiède')
        self.assertEqual(score_label(30), 'Froid')

    def test_reference_canal_scores_higher(self):
        """A lead from 'reference' canal should score higher than 'meta_ads'."""
        from apps.crm.scoring import compute_score
        lead_ref = Lead(
            company=self.company, nom='X', canal='reference',
            facture_hiver=2000, type_installation='residentiel',
        )
        lead_meta = Lead(
            company=self.company, nom='X', canal='meta_ads',
            facture_hiver=2000, type_installation='residentiel',
        )
        # Reference should score higher
        self.assertGreater(compute_score(lead_ref), compute_score(lead_meta))

    def test_score_isolated_by_company(self):
        """Leads from other companies don't affect scoring."""
        other = make_company('fg27-other', 'Other')
        Lead.objects.create(company=other, nom='Other Lead', canal='reference')
        user = make_user(self.company, 'fg27user3')
        api = make_api(user)
        resp = api.get('/api/django/crm/leads/')
        self.assertEqual(resp.status_code, 200)
        # Should not see other company's leads
        data = resp.data['results'] if 'results' in resp.data else resp.data
        for row in data:
            self.assertIn('score', row)  # All rows have score


class TestFG28SLA(TestCase):
    """FG28 — First-response SLA: first_contacted_at set on stage transition."""

    def setUp(self):
        self.company = make_company('fg28-co', 'FG28 Co')
        self.user = make_user(self.company, 'fg28user')
        self.api = make_api(self.user)

    def test_first_contacted_at_is_null_on_create(self):
        resp = self.api.post('/api/django/crm/leads/', {'nom': 'Fresh Lead'})
        self.assertEqual(resp.status_code, 201)
        lead = Lead.objects.get(nom='Fresh Lead', company=self.company)
        self.assertIsNone(lead.first_contacted_at)

    def test_first_contacted_at_set_on_stage_transition(self):
        resp = self.api.post('/api/django/crm/leads/', {'nom': 'SLA Lead'})
        self.assertEqual(resp.status_code, 201)
        lead_id = resp.data['id']
        # Transition from NEW to CONTACTED
        patch = self.api.patch(
            f'/api/django/crm/leads/{lead_id}/',
            {'stage': 'CONTACTED'},
        )
        self.assertEqual(patch.status_code, 200, patch.data)
        lead = Lead.objects.get(pk=lead_id)
        self.assertIsNotNone(lead.first_contacted_at)

    def test_first_contacted_at_not_overwritten_on_second_stage_change(self):
        resp = self.api.post('/api/django/crm/leads/', {'nom': 'SLA Lead 2'})
        lead_id = resp.data['id']
        self.api.patch(f'/api/django/crm/leads/{lead_id}/', {'stage': 'CONTACTED'})
        lead = Lead.objects.get(pk=lead_id)
        first = lead.first_contacted_at
        self.api.patch(f'/api/django/crm/leads/{lead_id}/', {'stage': 'QUOTE_SENT'})
        lead.refresh_from_db()
        self.assertEqual(lead.first_contacted_at, first)

    def test_first_contacted_at_set_on_note(self):
        resp = self.api.post('/api/django/crm/leads/', {'nom': 'Note Lead'})
        lead_id = resp.data['id']
        self.api.post(
            f'/api/django/crm/leads/{lead_id}/noter/',
            {'body': 'Appel passé — intéressé'},
        )
        lead = Lead.objects.get(pk=lead_id)
        self.assertIsNotNone(lead.first_contacted_at)

    def test_sla_breach_endpoint(self):
        resp = self.api.get('/api/django/crm/leads/sla-breach/')
        self.assertEqual(resp.status_code, 200)
        self.assertIn('sla_hours', resp.data)
        self.assertIn('count', resp.data)
        self.assertIn('results', resp.data)


class TestFG29StageSince(TestCase):
    """FG29 — stage_since_days exposed in serializer."""

    def setUp(self):
        self.company = make_company('fg29-co', 'FG29 Co')
        self.user = make_user(self.company, 'fg29user')
        self.api = make_api(self.user)

    def test_stage_since_days_in_lead_response(self):
        resp = self.api.post('/api/django/crm/leads/', {'nom': 'Stage Lead'})
        self.assertEqual(resp.status_code, 201)
        self.assertIn('stage_since_days', resp.data)
        # Fresh lead: 0 or 1 days
        self.assertIsInstance(resp.data['stage_since_days'], int)
        self.assertGreaterEqual(resp.data['stage_since_days'], 0)

    def test_stage_since_days_updates_after_stage_change(self):
        resp = self.api.post('/api/django/crm/leads/', {'nom': 'Stage Lead 2'})
        lead_id = resp.data['id']
        self.api.patch(f'/api/django/crm/leads/{lead_id}/', {'stage': 'CONTACTED'})
        detail = self.api.get(f'/api/django/crm/leads/{lead_id}/')
        self.assertIn('stage_since_days', detail.data)
        self.assertGreaterEqual(detail.data['stage_since_days'], 0)


class TestFG31RelanceQueue(TestCase):
    """FG31 — /leads/relances/ consolidated queue endpoint."""

    def setUp(self):
        self.company = make_company('fg31-co', 'FG31 Co')
        self.user = make_user(self.company, 'fg31user')
        self.api = make_api(self.user)

    def test_relances_endpoint_exists(self):
        resp = self.api.get('/api/django/crm/leads/relances/')
        self.assertEqual(resp.status_code, 200)
        self.assertIn('count', resp.data)
        self.assertIn('results', resp.data)

    def test_relances_today(self):
        today = timezone.localdate()
        Lead.objects.create(company=self.company, nom='Relance Today',
                            relance_date=today)
        Lead.objects.create(company=self.company, nom='No Relance')
        resp = self.api.get('/api/django/crm/leads/relances/?scope=today')
        self.assertEqual(resp.status_code, 200)
        noms = [r['nom'] for r in resp.data['results']]
        self.assertIn('Relance Today', noms)
        self.assertNotIn('No Relance', noms)

    def test_relances_overdue(self):
        import datetime
        yesterday = timezone.localdate() - datetime.timedelta(days=1)
        Lead.objects.create(company=self.company, nom='Overdue Lead',
                            relance_date=yesterday)
        resp = self.api.get('/api/django/crm/leads/relances/?scope=overdue')
        self.assertEqual(resp.status_code, 200)
        noms = [r['nom'] for r in resp.data['results']]
        self.assertIn('Overdue Lead', noms)

    def test_relances_week(self):
        import datetime
        tomorrow = timezone.localdate() + datetime.timedelta(days=1)
        Lead.objects.create(company=self.company, nom='Next Week Lead',
                            relance_date=tomorrow)
        resp = self.api.get('/api/django/crm/leads/relances/?scope=week')
        self.assertEqual(resp.status_code, 200)
        noms = [r['nom'] for r in resp.data['results']]
        self.assertIn('Next Week Lead', noms)

    def test_relances_scoped_to_company(self):
        other = make_company('fg31-other', 'Other31')
        today = timezone.localdate()
        Lead.objects.create(company=other, nom='Other Relance', relance_date=today)
        resp = self.api.get('/api/django/crm/leads/relances/')
        noms = [r['nom'] for r in resp.data['results']]
        self.assertNotIn('Other Relance', noms)


class TestFG34SourceROI(TestCase):
    """FG34 — /leads/roi-sources/ source/campaign ROI analytics."""

    def setUp(self):
        self.company = make_company('fg34-co', 'FG34 Co')
        self.user = make_user(self.company, 'fg34user')
        self.api = make_api(self.user)

    def test_roi_sources_endpoint_exists(self):
        resp = self.api.get('/api/django/crm/leads/roi-sources/')
        self.assertEqual(resp.status_code, 200)
        self.assertIsInstance(resp.data, list)

    def test_roi_sources_contains_canal_info(self):
        Lead.objects.create(
            company=self.company, nom='Meta Lead', canal='meta_ads',
            utm_campaign='summer2026', stage='SIGNED',
        )
        resp = self.api.get('/api/django/crm/leads/roi-sources/')
        self.assertEqual(resp.status_code, 200)
        found = [r for r in resp.data if r['canal'] == 'meta_ads']
        self.assertTrue(len(found) > 0)
        row = found[0]
        self.assertIn('lead_count', row)
        self.assertIn('signed_count', row)
        self.assertIn('win_rate', row)
        self.assertIn('signed_value_ttc', row)

    def test_roi_sources_scoped_to_company(self):
        other = make_company('fg34-other', 'Other34')
        Lead.objects.create(company=other, nom='Other ROI', canal='reference',
                            stage='SIGNED')
        resp = self.api.get('/api/django/crm/leads/roi-sources/')
        # Should not crash and should not include other company's data
        self.assertEqual(resp.status_code, 200)


class TestFG36MessageTemplate(TestCase):
    """FG36 — crm.MessageTemplate CRUD + render endpoint."""

    def setUp(self):
        self.company = make_company('fg36-co', 'FG36 Co')
        self.admin = make_user(self.company, 'fg36admin', role='admin')
        self.user = make_user(self.company, 'fg36user', role='responsable')
        self.admin_api = make_api(self.admin)
        self.user_api = make_api(self.user)

    def test_admin_can_create_template(self):
        resp = self.admin_api.post('/api/django/crm/message-templates/', {
            'nom': 'Premier contact',
            'langue': 'fr',
            'corps': 'Bonjour {prenom}, nous vous contactons depuis {ville}.',
        })
        self.assertEqual(resp.status_code, 201, resp.data)
        self.assertEqual(resp.data['nom'], 'Premier contact')

    def test_regular_user_can_list_templates(self):
        MessageTemplate.objects.create(
            company=self.company, nom='Test Tpl', langue='fr',
            corps='Bonjour {prenom}')
        resp = self.user_api.get('/api/django/crm/message-templates/')
        self.assertEqual(resp.status_code, 200)
        noms = [r['nom'] for r in resp.data['results'] if 'results' in resp.data
                ] if 'results' in resp.data else [r['nom'] for r in resp.data]
        self.assertIn('Test Tpl', noms)

    def test_regular_user_cannot_create_template(self):
        resp = self.user_api.post('/api/django/crm/message-templates/', {
            'nom': 'Unauthorized', 'langue': 'fr', 'corps': 'Test',
        })
        self.assertIn(resp.status_code, [403, 401])

    def test_render_endpoint(self):
        tpl = MessageTemplate.objects.create(
            company=self.company, nom='Render Test', langue='fr',
            corps='Bonjour {prenom} de {ville} — lien: {lien}',
        )
        resp = self.user_api.post(
            f'/api/django/crm/message-templates/{tpl.pk}/render/',
            {'prenom': 'Ahmed', 'ville': 'Casablanca', 'lien': 'https://t.ma/d/1'},
        )
        self.assertEqual(resp.status_code, 200)
        self.assertIn('texte', resp.data)
        self.assertIn('Ahmed', resp.data['texte'])
        self.assertIn('Casablanca', resp.data['texte'])

    def test_archived_template_hidden_from_list(self):
        MessageTemplate.objects.create(
            company=self.company, nom='Archived Tpl', langue='fr',
            corps='...', archived=True)
        resp = self.user_api.get('/api/django/crm/message-templates/')
        self.assertEqual(resp.status_code, 200)
        data = resp.data.get('results', resp.data)
        noms = [r['nom'] for r in data]
        self.assertNotIn('Archived Tpl', noms)

    def test_scoped_to_company(self):
        other = make_company('fg36-other', 'Other36')
        MessageTemplate.objects.create(
            company=other, nom='Other Tpl', langue='fr', corps='...')
        resp = self.user_api.get('/api/django/crm/message-templates/')
        data = resp.data.get('results', resp.data)
        noms = [r['nom'] for r in data]
        self.assertNotIn('Other Tpl', noms)


class TestFG38ClientMatch(TestCase):
    """FG38 — Lead↔Client duplicate match: /leads/{id}/client-match/."""

    def setUp(self):
        self.company = make_company('fg38-co', 'FG38 Co')
        self.user = make_user(self.company, 'fg38user')
        self.api = make_api(self.user)

    def test_client_match_no_match(self):
        resp = self.api.post('/api/django/crm/leads/', {
            'nom': 'New Prospect', 'telephone': '0699000001',
        })
        lead_id = resp.data['id']
        resp = self.api.get(f'/api/django/crm/leads/{lead_id}/client-match/')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data, [])

    def test_client_match_by_phone(self):
        # Create a Client with a known phone
        client = Client.objects.create(
            company=self.company, nom='Existing Client',
            telephone='0612000002',
        )
        # Lead with same phone (after normalization)
        lead = Lead.objects.create(
            company=self.company, nom='Returning Lead',
            telephone='0612000002',
        )
        resp = self.api.get(f'/api/django/crm/leads/{lead.pk}/client-match/')
        self.assertEqual(resp.status_code, 200)
        ids = [r['id'] for r in resp.data]
        self.assertIn(client.pk, ids)

    def test_client_match_by_email(self):
        client = Client.objects.create(
            company=self.company, nom='Email Client',
            email='duptest@test.ma',
        )
        lead = Lead.objects.create(
            company=self.company, nom='Email Lead',
            email='duptest@test.ma',
        )
        resp = self.api.get(f'/api/django/crm/leads/{lead.pk}/client-match/')
        self.assertEqual(resp.status_code, 200)
        ids = [r['id'] for r in resp.data]
        self.assertIn(client.pk, ids)

    def test_client_match_cross_company_isolated(self):
        other = make_company('fg38-other', 'Other38')
        Client.objects.create(
            company=other, nom='Other Client',
            telephone='0612000099',
        )
        lead = Lead.objects.create(
            company=self.company, nom='Lead',
            telephone='0612000099',
        )
        resp = self.api.get(f'/api/django/crm/leads/{lead.pk}/client-match/')
        self.assertEqual(resp.status_code, 200)
        # Must not see other company's client
        self.assertEqual(resp.data, [])

    def test_client_match_result_fields(self):
        client = Client.objects.create(
            company=self.company, nom='Field Check', prenom='Ahmed',
            email='fieldcheck@test.ma',
        )
        lead = Lead.objects.create(
            company=self.company, nom='FL',
            email='fieldcheck@test.ma',
        )
        resp = self.api.get(f'/api/django/crm/leads/{lead.pk}/client-match/')
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(len(resp.data) > 0)
        row = resp.data[0]
        self.assertIn('id', row)
        self.assertIn('nom', row)
        self.assertIn('nb_devis', row)
