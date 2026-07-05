"""QW5 — Alias the EXISTING QJ27 proposal contact/otp endpoints under the
`ventes/` mount (the site calls THIS mount, not `public/`) + contract fixes:

  * `apps/ventes/urls.py` aliases `proposal/<token>/contact/` and
    `proposal/<token>/otp/` to the SAME views as `public/` (no duplicated
    logic) — the site's real call target (`proposition.ts:contactEndpoint`)
    now resolves instead of 404;
  * `channel` (what the site actually sends) is read as an alias of `canal`;
  * `revision_kind` (WJ54) is persisted in the chatter note + notification;
  * the canal->label map covers question/voice/revision, not just
    whatsapp/rappel;
  * message truncation aligned to 2000 (was 500, silently clipping a
    legitimate message);
  * the 1h idempotency lock is scoped per link+channel (a 'question' no
    longer suppresses a distinct 'rappel' for an hour);
  * a 'rappel' channel poses contact_preference=phone_ok on the lead and
    fires the QW4 distinct callback notification.
"""
from django.core.cache import cache
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from authentication.models import Company
from apps.crm.models import Client, Lead, LeadActivity
from apps.notifications.models import EventType, Notification
from apps.ventes.models import Devis, ShareLink

User = get_user_model()


def _company(slug):
    return Company.objects.create(nom=slug, slug=slug)


def _user(company, username, supervisor=None, role=None):
    return User.objects.create_user(
        username=username, password='x', company=company,
        supervisor=supervisor, role=role, role_legacy='responsable')


class QW5AliasBase(TestCase):
    def setUp(self):
        cache.clear()
        self.company = _company('qw5-co')
        self.boss = _user(self.company, 'qw5-boss')
        self.owner = _user(self.company, 'qw5-owner', supervisor=self.boss)
        self.client_obj = Client.objects.create(
            company=self.company, nom='Bennani', telephone='0612345678')
        self.lead = Lead.objects.create(
            company=self.company, nom='Bennani', telephone='0612345678',
            owner=self.owner)
        self.devis = Devis.objects.create(
            company=self.company, reference='DEV-QW5-0001',
            client=self.client_obj, lead=self.lead,
            statut=Devis.Statut.BROUILLON, created_by=self.owner)
        self.link = ShareLink.for_devis(self.devis)
        self.api = APIClient()

    def _post_ventes_mount(self, token=None, body=None):
        token = token or self.link.token
        return self.api.post(
            f'/api/django/ventes/proposal/{token}/contact/',
            body or {}, format='json')


class VentesMountAliasTests(QW5AliasBase):
    """La route existait déjà sous public/ (404 sous ventes/) — QW5 l'aliase."""

    def test_ventes_mount_no_longer_404s(self):
        resp = self._post_ventes_mount(body={'channel': 'rappel'})
        self.assertEqual(resp.status_code, 200, resp.content)
        self.assertFalse(resp.data['already_sent'])

    def test_ventes_mount_reuses_same_view_as_public_mount(self):
        # Deux appels via les DEUX mounts avec des CANAUX différents (pour ne
        # pas se heurter au verrou idempotence par canal) doivent tous deux
        # aboutir à une notification sur le MÊME lead.
        self._post_ventes_mount(body={'channel': 'rappel'})
        self.api.post(
            f'/api/django/public/proposal/{self.link.token}/contact/',
            {'canal': 'whatsapp'}, format='json')
        notifs = Notification.objects.filter(
            event_type=EventType.CLIENT_CONTACT_REQUEST, recipient=self.owner)
        self.assertEqual(notifs.count(), 2)

    def test_otp_alias_under_ventes_mount(self):
        resp = self.api.post(
            f'/api/django/ventes/proposal/{self.link.token}/otp/',
            {}, format='json')
        # ESIGN_OTP_ENABLED défaut OFF → no-op réussi (comportement identique
        # à aujourd'hui), mais l'important est que ce ne soit PLUS un 404.
        self.assertEqual(resp.status_code, 200, resp.content)


class ChannelAliasContractTests(QW5AliasBase):
    def test_channel_key_read_as_alias_of_canal(self):
        resp = self._post_ventes_mount(body={'channel': 'whatsapp'})
        self.assertEqual(resp.status_code, 200)
        note = LeadActivity.objects.filter(
            lead=self.lead, kind=LeadActivity.Kind.NOTE,
            body__contains='WhatsApp').first()
        self.assertIsNotNone(note)

    def test_legacy_canal_key_still_accepted(self):
        resp = self._post_ventes_mount(body={'canal': 'whatsapp'})
        self.assertEqual(resp.status_code, 200)
        note = LeadActivity.objects.filter(
            lead=self.lead, kind=LeadActivity.Kind.NOTE,
            body__contains='WhatsApp').first()
        self.assertIsNotNone(note)

    def test_revision_kind_persisted_in_chatter(self):
        resp = self._post_ventes_mount(body={
            'channel': 'revision', 'revision_kind': 'kwc',
            'message': 'Je voudrais plus de puissance'})
        self.assertEqual(resp.status_code, 200)
        note = LeadActivity.objects.filter(
            lead=self.lead, kind=LeadActivity.Kind.NOTE,
            body__contains='modification').first()
        self.assertIsNotNone(note)
        self.assertIn('kWc', note.body)

    def test_question_and_voice_canals_get_distinct_labels(self):
        for channel, expected_snippet in (
            ('question', 'question'),
            ('voice', 'vocale'),
        ):
            token = ShareLink.for_devis(self.devis).token
            resp = self.api.post(
                f'/api/django/ventes/proposal/{token}/contact/',
                {'channel': channel}, format='json')
            self.assertEqual(resp.status_code, 200)
            note = LeadActivity.objects.filter(
                lead=self.lead, kind=LeadActivity.Kind.NOTE,
                body__icontains=expected_snippet).first()
            self.assertIsNotNone(note, f'canal {channel} sans note distincte')

    def test_message_truncated_at_2000_not_500(self):
        long_message = 'x' * 1800
        resp = self._post_ventes_mount(body={
            'channel': 'question', 'message': long_message})
        self.assertEqual(resp.status_code, 200)
        note = LeadActivity.objects.filter(
            lead=self.lead, kind=LeadActivity.Kind.NOTE,
            body__icontains='question').first()
        self.assertIsNotNone(note)
        # Le message de 1800 caractères doit survivre EN ENTIER (pas coupé à 500).
        self.assertIn('x' * 1800, note.body)


class PerChannelIdempotencyLockTests(QW5AliasBase):
    def test_question_does_not_suppress_a_distinct_rappel(self):
        r1 = self._post_ventes_mount(body={'channel': 'question'})
        self.assertFalse(r1.data['already_sent'])
        # Un "rappel" DISTINCT juste après doit PASSER (avant QW5: bloqué 1h
        # par le verrou global du lien).
        r2 = self._post_ventes_mount(body={'channel': 'rappel'})
        self.assertFalse(r2.data['already_sent'])

    def test_same_channel_twice_is_deduped(self):
        r1 = self._post_ventes_mount(body={'channel': 'rappel'})
        r2 = self._post_ventes_mount(body={'channel': 'rappel'})
        self.assertFalse(r1.data['already_sent'])
        self.assertTrue(r2.data['already_sent'])


class RappelChannelCallbackObligationTests(QW5AliasBase):
    """QW5 <-> QW4 — un canal 'rappel' depuis la proposition pose
    contact_preference=phone_ok et déclenche la notification distincte."""

    def test_rappel_channel_sets_contact_preference_phone_ok(self):
        self._post_ventes_mount(body={'channel': 'rappel'})
        self.lead.refresh_from_db()
        self.assertEqual(self.lead.contact_preference, Lead.ContactPreference.PHONE_OK)

    def test_rappel_channel_fires_distinct_callback_notification(self):
        self._post_ventes_mount(body={'channel': 'rappel'})
        self.assertTrue(Notification.objects.filter(
            recipient=self.owner,
            event_type=EventType.LEAD_CALLBACK_REQUESTED).exists())

    def test_whatsapp_channel_never_sets_contact_preference(self):
        self._post_ventes_mount(body={'channel': 'whatsapp'})
        self.lead.refresh_from_db()
        self.assertIsNone(self.lead.contact_preference)
