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
        self.assertEqual(Lead.objects.get(pk=lead.pk).telephone, '212600555555')

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
        # Le deuxième rejeu retrouve le MÊME lead : les deux appels tombent
        # dans la garde anti-rejeu < 60 s du mapping standard — jamais un
        # doublon (un rejeu n'est pas une nouvelle soumission du visiteur).
        self.assertEqual(lead1.pk, lead2.pk)
        self.assertEqual(
            Lead.objects.filter(telephone='212600666666').count(), 1)


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


APPLY_ASYNC = 'apps.ventes.tasks.task_devis_automatique_depuis_lead.apply_async'


class ReplayAACQ30Tests(TestCase):
    """AACQ30 — rejeu idempotent et fidèle au webhook, à n'importe quel délai.

    Les lignes (a)/(b)/(c) sont fabriquées par un VRAI POST du webhook ; le
    rejeu passe par la vraie action ``replay``. Seul ``apply_async`` (Celery)
    est simulé ; le vieillissement se fait par ``update(date_creation=…)``."""

    def setUp(self):
        self.company = Company.objects.create(
            nom='Taqinor AACQ30', slug='taqinor-aacq30')
        ovr = override_settings(
            WEBSITE_LEAD_WEBHOOK_SECRET=SECRET,
            WEBSITE_LEADS_COMPANY_ID=self.company.pk)
        ovr.enable()
        self.addCleanup(ovr.disable)
        role = Role.objects.create(
            company=self.company, nom='Responsable',
            permissions=['crm_voir', 'crm_creer', 'crm_modifier'])
        self.user = User.objects.create_user(
            username='aacq30_resp', password='x', company=self.company,
            role=role)
        self.api = _auth(self.user)
        self.url = reverse('website-lead-webhook')

    def _post(self, data):
        return self.client.post(
            self.url, data=json.dumps(data), content_type='application/json',
            HTTP_X_WEBHOOK_SECRET=SECRET)

    def _vieillir(self):
        from datetime import timedelta

        from django.utils import timezone
        old = timezone.now() - timedelta(minutes=2)
        Lead.objects.filter(company=self.company).update(date_creation=old)
        WebsiteLeadPayload.objects.filter(company=self.company).update(
            received_at=old)

    def _replay(self, raw):
        return self.api.post(
            f'/api/django/crm/website-lead-payloads/{raw.pk}/replay/')

    def _payload_echoue(self, phone):
        from unittest.mock import patch
        with patch('apps.crm.webhooks._map_and_link_lead',
                   side_effect=ValueError('mapping cassé (test)')):
            res = self._post({'fullName': 'Rejeu AACQ30', 'phoneE164': phone,
                              'consent': True})
        self.assertEqual(res.status_code, 202, res.content)
        raw = WebsiteLeadPayload.objects.get(pk=res.json()['payload_id'])
        self.assertTrue(raw.error)
        return raw

    def _ids_liste(self):
        r = self.api.get('/api/django/crm/website-lead-payloads/')
        self.assertEqual(r.status_code, 200, r.data)
        return [p['id'] for p in (r.data.get('results') or r.data)]

    def test_rejeu_reussi_efface_erreur_et_sort_de_la_liste(self):
        from unittest.mock import patch
        raw = self._payload_echoue('+212600300001')
        self.assertIn(raw.pk, self._ids_liste())
        with patch(APPLY_ASYNC):
            r = self._replay(raw)
        self.assertEqual(r.status_code, 200, r.data)
        self.assertEqual(r.data['detail'], 'Lead créé.')
        raw.refresh_from_db()
        self.assertEqual(raw.error, '')
        self.assertTrue(raw.processed)
        self.assertIsNotNone(raw.lead_id)
        self.assertNotIn(raw.pk, self._ids_liste())

    def test_second_rejeu_au_dela_de_60s_ne_cree_pas_de_doublon(self):
        from unittest.mock import patch
        raw = self._payload_echoue('+212600300002')
        with patch(APPLY_ASYNC):
            r1 = self._replay(raw)
            self.assertEqual(r1.status_code, 200, r1.data)
            self._vieillir()
            r2 = self._replay(raw)
        self.assertEqual(r2.status_code, 200, r2.data)
        raw.refresh_from_db()
        self.assertEqual(
            r2.data['detail'],
            f'Déjà rattaché au lead #{raw.lead_id} — aucun nouveau lead.')
        self.assertEqual(r2.data['payload']['lead'], raw.lead_id)
        self.assertEqual(
            Lead.objects.filter(telephone='212600300002').count(), 1)

    def test_ping_engagement_refuse_sans_lead(self):
        from apps.crm.models import LeadActivity
        res = self._post({'qualified': False,
                          'event_type': 'proposal_first_view',
                          'phoneE164': '+212600300003'})
        self.assertEqual(res.status_code, 200, res.content)
        raw = WebsiteLeadPayload.objects.get(pk=res.json()['payload_id'])
        self.assertTrue(raw.processed)
        self.assertIsNone(raw.lead_id)
        self._vieillir()
        r = self._replay(raw)
        self.assertEqual(r.status_code, 422, r.data)
        self.assertEqual(r.data['detail'],
                         "Ping d'engagement : jamais rejoué en lead.")
        self.assertEqual(Lead.objects.filter(company=self.company).count(), 0)
        self.assertEqual(
            LeadActivity.objects.filter(company=self.company).count(), 0)
        raw.refresh_from_db()
        self.assertIsNone(raw.lead_id)

    def test_ligne_dedupliquee_refusee(self):
        from unittest.mock import patch
        data = {'fullName': 'Dédup AACQ30', 'phoneE164': '+212600300004',
                'consent': True}  # même corps ⇒ même empreinte (YDATA12)
        with patch(APPLY_ASYNC):
            first = self._post(data)
            second = self._post(data)
        self.assertEqual(first.status_code, 201, first.content)
        self.assertEqual(second.json()['detail'],
                         'Événement déjà traité (dédupliqué).')
        raw2 = WebsiteLeadPayload.objects.get(pk=second.json()['payload_id'])
        self.assertTrue(raw2.processed)
        self.assertIsNone(raw2.lead_id)
        self._vieillir()
        avant = Lead.objects.filter(company=self.company).count()
        r = self._replay(raw2)
        self.assertEqual(r.status_code, 422, r.data)
        self.assertEqual(
            r.data['detail'],
            "Événement déjà traité : la soumission d'origine a déjà sa fiche.")
        self.assertEqual(Lead.objects.filter(company=self.company).count(),
                         avant)
        self.assertEqual(
            Lead.objects.filter(telephone='212600300004').count(), 1)

    def test_rejeu_qui_cree_met_en_file_le_devis_auto(self):
        from unittest.mock import patch
        raw = self._payload_echoue('+212600300005')
        with patch(APPLY_ASYNC) as file_:
            r = self._replay(raw)
            self.assertEqual(r.status_code, 200, r.data)
            raw.refresh_from_db()
            self.assertEqual(file_.call_count, 1)
            self.assertEqual(file_.call_args.kwargs['args'],
                             [raw.lead_id, self.company.pk])
            # Second rejeu : aucun nouveau devis mis en file.
            self._vieillir()
            self._replay(raw)
            self.assertEqual(file_.call_count, 1)
