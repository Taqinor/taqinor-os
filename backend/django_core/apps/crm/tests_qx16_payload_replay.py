"""QX16 — « Jamais perdre un lead » becomes operational: payload replay
surface.

Covers:
  - read-only admin registration of WebsiteLeadPayload (no add/change/delete);
  - CRM endpoint lists failed/lead-less payloads by default, `?all=1` shows
    everything;
  - `replay` action rejoins the SAME mapping as the webhook
    (`_map_and_link_lead`), turning a forced mapping failure into a real Lead;
  - founder/manager notification fires when a webhook mapping fails.
"""
import json

from django.contrib.admin.sites import site as admin_site
from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company

from apps.crm.models import Lead, WebsiteLeadPayload
from apps.crm.webhooks import replay_website_lead_payload
from apps.notifications.models import Notification
from apps.roles.models import Role

User = get_user_model()
SECRET = 'test-secret-qx16'


def _auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


class WebsiteLeadPayloadAdminReadOnlyTests(TestCase):
    def test_registered_and_read_only(self):
        model_admin = admin_site._registry[WebsiteLeadPayload]
        self.assertFalse(model_admin.has_add_permission(None))
        self.assertFalse(model_admin.has_change_permission(None))
        self.assertFalse(model_admin.has_delete_permission(None))
        self.assertIn('processed', model_admin.list_display)
        self.assertIn('error', model_admin.list_display)
        self.assertIn('received_at', model_admin.list_display)
        self.assertIn('company', model_admin.list_display)
        self.assertIn('lead', model_admin.list_display)


class ReplayWebsiteLeadPayloadTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='Taqinor QX16', slug='taqinor-qx16')

    def test_forced_mapping_failure_is_replayable_to_a_real_lead(self):
        # Payload dont le mapping échouera : `band` n'est pas un dict (le
        # même genre de payload malformé que test_mapping_echoue_mais_le_brut_survit).
        raw = WebsiteLeadPayload.objects.create(
            company=self.company,
            payload={'fullName': 'Rejeu Test', 'phoneE164': '+212600555555',
                     'consent': True},
        )
        ok, detail, lead = replay_website_lead_payload(raw)
        self.assertTrue(ok, detail)
        self.assertIsNotNone(lead)
        raw.refresh_from_db()
        self.assertTrue(raw.processed)
        self.assertEqual(raw.lead, lead)
        self.assertEqual(Lead.objects.get(pk=lead.pk).telephone, '+212600555555')

    def test_replay_still_failing_leaves_payload_replayable(self):
        # Force un échec DÉTERMINISTE (patch) plutôt que de dépendre d'un
        # payload malformé qui pourrait devenir tolérant à l'avenir — voir
        # MappingFailureNotifiesManagersTests pour le même choix côté vue.
        from unittest.mock import patch
        raw = WebsiteLeadPayload.objects.create(
            company=self.company, payload={'fullName': 'Rejeu cassé'})
        with patch('apps.crm.webhooks._map_and_link_lead',
                   side_effect=ValueError('mapping cassé (test)')):
            ok, detail, lead = replay_website_lead_payload(raw)
        self.assertFalse(ok)
        self.assertIsNone(lead)
        raw.refresh_from_db()
        self.assertIn('mapping cassé', raw.error)

    def test_replay_no_company_anywhere_fails_cleanly(self):
        Company.objects.all().delete()
        raw = WebsiteLeadPayload.objects.create(
            company=None, payload={'fullName': 'Sans société'})
        ok, detail, lead = replay_website_lead_payload(raw)
        self.assertFalse(ok)
        self.assertIsNone(lead)

    def test_replay_idempotent_does_not_duplicate_lead_on_second_call(self):
        raw = WebsiteLeadPayload.objects.create(
            company=self.company,
            payload={'fullName': 'Deux Rejeux', 'phoneE164': '+212600666666',
                     'consent': True},
        )
        ok1, _, lead1 = replay_website_lead_payload(raw)
        self.assertTrue(ok1)
        ok2, _, lead2 = replay_website_lead_payload(raw)
        self.assertTrue(ok2)
        # Le deuxième rejeu retrouve le MÊME lead (dédup couche 1/2 du
        # mapping standard) — jamais un doublon.
        self.assertEqual(lead1.pk, lead2.pk)
        self.assertEqual(
            Lead.objects.filter(telephone='+212600666666').count(), 1)


class WebsiteLeadPayloadViewSetTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='Taqinor QX16 API', slug='taqinor-qx16-api')
        role = Role.objects.create(
            company=self.company, nom='Directeur',
            permissions=['crm_voir', 'crm_creer', 'crm_modifier'])
        self.user = User.objects.create_user(
            username='qx16_resp', password='x', company=self.company, role=role)
        self.api = _auth(self.user)

    def test_default_list_shows_only_actionable_payloads(self):
        WebsiteLeadPayload.objects.create(
            company=self.company, payload={}, processed=True,
            lead=Lead.objects.create(company=self.company, nom='OK'))
        errored = WebsiteLeadPayload.objects.create(
            company=self.company, payload={}, error='ValueError: x')
        r = self.api.get('/api/django/crm/website-lead-payloads/')
        self.assertEqual(r.status_code, 200, r.data)
        ids = [p['id'] for p in (r.data.get('results') or r.data)]
        self.assertIn(errored.pk, ids)
        self.assertEqual(len(ids), 1)

    def test_all_query_param_shows_everything(self):
        WebsiteLeadPayload.objects.create(
            company=self.company, payload={}, processed=True,
            lead=Lead.objects.create(company=self.company, nom='OK'))
        WebsiteLeadPayload.objects.create(
            company=self.company, payload={}, error='ValueError: x')
        r = self.api.get('/api/django/crm/website-lead-payloads/', {'all': 1})
        self.assertEqual(r.status_code, 200, r.data)
        ids = [p['id'] for p in (r.data.get('results') or r.data)]
        self.assertEqual(len(ids), 2)

    def test_replay_action_links_a_real_lead(self):
        raw = WebsiteLeadPayload.objects.create(
            company=self.company,
            payload={'fullName': 'Via API', 'phoneE164': '+212600777777',
                     'consent': True},
        )
        r = self.api.post(f'/api/django/crm/website-lead-payloads/{raw.pk}/replay/')
        self.assertEqual(r.status_code, 200, r.data)
        self.assertIsNotNone(r.data['payload']['lead'])

    def test_cross_company_isolation(self):
        other = Company.objects.create(nom='Autre QX16', slug='autre-qx16')
        WebsiteLeadPayload.objects.create(
            company=other, payload={}, error='ValueError: x')
        r = self.api.get('/api/django/crm/website-lead-payloads/')
        self.assertEqual(r.status_code, 200, r.data)
        results = r.data['results'] if 'results' in r.data else r.data
        ids = [p['id'] for p in results]
        self.assertEqual(ids, [])


@override_settings(WEBSITE_LEAD_WEBHOOK_SECRET=SECRET)
class MappingFailureNotifiesManagersTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='Taqinor QX16 Notif', slug='taqinor-qx16-notif')
        role = Role.objects.create(
            company=self.company, nom='Directeur', permissions=['crm_voir'])
        self.manager = User.objects.create_user(
            username='mgr_qx16', password='x', company=self.company, role=role)
        self.url = reverse('website-lead-webhook')

    def test_mapping_failure_notifies_manager(self):
        # Force un échec DÉTERMINISTE du mapping (patch), plutôt que de
        # dépendre d'un payload malformé qui pourrait rester tolérant à
        # l'avenir (comme `band` — déjà toléré par `_map_payload_to_fields`).
        from unittest.mock import patch
        with patch('apps.crm.webhooks._map_and_link_lead',
                   side_effect=ValueError('mapping cassé (test)')):
            res = self.client.post(
                self.url,
                data=json.dumps({'fullName': 'X', 'phoneE164': '+212600888888'}),
                content_type='application/json', HTTP_X_WEBHOOK_SECRET=SECRET)
        self.assertEqual(res.status_code, 202, res.content)
        self.assertTrue(Notification.objects.filter(
            recipient=self.manager, event_type='lead_new',
            link='/crm/payloads-site-web').exists())
