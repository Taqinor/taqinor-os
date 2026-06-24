"""
Tests for QJ14 — Server-side proposal email send action.

Covers:
  - POST /ventes/devis/{id}/envoyer-email/ sends an email via the locmem backend
    and creates an EmailLog record.
  - The devis is marked « envoyé » via mark_devis_sent (rule #4 — only path).
  - Idempotent: a second call on an already-envoyé devis still sends the email
    but does NOT re-stamp date_envoi or add a duplicate status chatter entry.
  - Company scoping: a request user from company A cannot reach a devis from B.
  - Missing email address (no client.email, no to_email body) → 400 + EmailLog
    with statut=echec.
  - A devis in a terminal status (accepté/refusé) is NOT regressed to envoyé,
    but the email is still delivered.

Run:
    docker compose exec django_core python manage.py test \
        apps.ventes.tests.test_qj14_email_send -v 2
"""
from django.test import TestCase, override_settings
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken
from django.contrib.auth import get_user_model

from apps.crm.models import Client
from apps.ventes.models import Devis, EmailLog, DevisActivity

User = get_user_model()


# ─── Helpers ───────────────────────────────────────────────────────────────────

def make_company(slug='qj14-co'):
    from authentication.models import Company
    return Company.objects.get_or_create(slug=slug, defaults={'nom': 'QJ14 Co'})[0]


def make_user(company, username=None):
    uname = username or f'u_{company.slug}'
    try:
        return User.objects.get(username=uname)
    except User.DoesNotExist:
        return User.objects.create_user(
            username=uname, password='x',
            role_legacy='responsable', company=company)


def make_client(company, email='client@test.ma'):
    return Client.objects.create(
        company=company, nom='Tahiri', prenom='Yasmine',
        email=email, telephone='+212611000001')


def make_devis(company, user, client, statut='brouillon', ref=None):
    return Devis.objects.create(
        company=company,
        reference=ref or f'DEV-QJ14-{statut}',
        client=client,
        statut=statut,
        created_by=user,
    )


def make_api(user):
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return client


def url(devis_id):
    return f'/api/django/ventes/devis/{devis_id}/envoyer-email/'


# ─── Tests ─────────────────────────────────────────────────────────────────────

@override_settings(EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend')
class TestEnvoyerEmailAction(TestCase):
    """POST envoyer-email/ — envoi, EmailLog, statut."""

    def setUp(self):
        self.company = make_company('qj14-main')
        self.user = make_user(self.company)
        self.api = make_api(self.user)
        self.client_obj = make_client(self.company, 'yasmine@test.ma')

    def test_email_sent_and_log_created(self):
        """An email is delivered and an EmailLog record is written."""
        devis = make_devis(self.company, self.user, self.client_obj, 'brouillon',
                           'DEV-QJ14-001')
        resp = self.api.post(url(devis.id), {}, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)

        # EmailLog created with statut=envoye
        log = EmailLog.objects.filter(devis=devis).first()
        self.assertIsNotNone(log)
        self.assertEqual(log.statut, EmailLog.Statut.ENVOYE)
        self.assertEqual(log.company, self.company)
        self.assertIn('yasmine@test.ma', log.to_email)

    def test_devis_marked_envoye_via_service(self):
        """The devis is flipped to « envoyé » through mark_devis_sent (rule #4)."""
        devis = make_devis(self.company, self.user, self.client_obj, 'brouillon',
                           'DEV-QJ14-002')
        self.assertEqual(devis.statut, 'brouillon')

        self.api.post(url(devis.id), {}, format='json')

        devis.refresh_from_db()
        self.assertEqual(devis.statut, 'envoye')
        self.assertIsNotNone(devis.date_envoi)

    def test_chatter_entry_written(self):
        """A chatter (DevisActivity) note is written after send."""
        devis = make_devis(self.company, self.user, self.client_obj, 'brouillon',
                           'DEV-QJ14-003')
        self.api.post(url(devis.id), {}, format='json')
        # At least one activity entry exists (from mark_devis_sent or chatter note)
        self.assertTrue(
            DevisActivity.objects.filter(devis=devis).exists(),
            'Expected at least one DevisActivity entry after email send')

    def test_idempotent_already_envoye(self):
        """Calling again on an already-envoyé devis sends the email but does NOT
        re-stamp date_envoi or add a duplicate status chatter entry."""
        devis = make_devis(self.company, self.user, self.client_obj, 'brouillon',
                           'DEV-QJ14-004')

        # First call — flips to envoyé
        self.api.post(url(devis.id), {}, format='json')
        devis.refresh_from_db()
        first_stamp = devis.date_envoi
        status_activities_before = DevisActivity.objects.filter(
            devis=devis, kind=DevisActivity.Kind.MODIFICATION,
            new_value='Envoyé').count()

        # Second call — email resent, no re-stamp
        resp = self.api.post(url(devis.id), {}, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)

        devis.refresh_from_db()
        self.assertEqual(devis.date_envoi, first_stamp,
                         'date_envoi must not change on re-send')
        status_activities_after = DevisActivity.objects.filter(
            devis=devis, kind=DevisActivity.Kind.MODIFICATION,
            new_value='Envoyé').count()
        self.assertEqual(
            status_activities_before, status_activities_after,
            'No duplicate status chatter entry on idempotent re-send')

    def test_custom_to_email_in_body(self):
        """Body to_email overrides client.email."""
        devis = make_devis(self.company, self.user, self.client_obj, 'brouillon',
                           'DEV-QJ14-005')
        resp = self.api.post(url(devis.id),
                             {'to_email': 'autre@dest.ma'}, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        log = EmailLog.objects.filter(devis=devis).last()
        self.assertIsNotNone(log)
        self.assertEqual(log.to_email, 'autre@dest.ma')

    def test_missing_email_returns_400_and_logs_echec(self):
        """No client email + no to_email in body → 400 + EmailLog echec."""
        client_no_email = Client.objects.create(
            company=self.company, nom='Inconnu', telephone='+212611000002')
        devis = make_devis(self.company, self.user, client_no_email, 'brouillon',
                           'DEV-QJ14-006')
        resp = self.api.post(url(devis.id), {}, format='json')
        self.assertEqual(resp.status_code, 400, resp.data)

        log = EmailLog.objects.filter(devis=devis).first()
        self.assertIsNotNone(log)
        self.assertEqual(log.statut, EmailLog.Statut.ECHEC)


@override_settings(EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend')
class TestEnvoyerEmailScoping(TestCase):
    """Company scoping: another company's devis must not be reachable."""

    def setUp(self):
        self.company_a = make_company('qj14-a')
        self.company_b = make_company('qj14-b')
        self.user_a = make_user(self.company_a, 'u_qj14a')
        self.client_b = make_client(self.company_b, 'b@test.ma')
        self.devis_b = make_devis(self.company_b, self.user_a, self.client_b,
                                  'brouillon', 'DEV-QJ14-B1')
        self.api_a = make_api(self.user_a)

    def test_cross_company_devis_returns_404(self):
        """User from company A cannot reach a devis from company B."""
        resp = self.api_a.post(url(self.devis_b.id), {}, format='json')
        self.assertEqual(resp.status_code, 404, resp.data)


@override_settings(EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend')
class TestEnvoyerEmailTerminalStatus(TestCase):
    """A terminal-status devis (accepté/refusé) is never regressed."""

    def setUp(self):
        self.company = make_company('qj14-term')
        self.user = make_user(self.company, 'u_qj14t')
        self.api = make_api(self.user)
        self.client_obj = make_client(self.company, 'term@test.ma')

    def test_accepted_devis_not_regressed(self):
        devis = make_devis(self.company, self.user, self.client_obj, 'accepte',
                           'DEV-QJ14-T1')
        resp = self.api.post(url(devis.id), {}, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)

        devis.refresh_from_db()
        self.assertEqual(devis.statut, 'accepte',
                         'accepté devis must not be regressed to envoyé')

    def test_refused_devis_not_regressed(self):
        devis = make_devis(self.company, self.user, self.client_obj, 'refuse',
                           'DEV-QJ14-T2')
        resp = self.api.post(url(devis.id), {}, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)

        devis.refresh_from_db()
        self.assertEqual(devis.statut, 'refuse',
                         'refusé devis must not be regressed to envoyé')
