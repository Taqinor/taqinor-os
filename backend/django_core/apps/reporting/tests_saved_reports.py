"""N79 — Tests des rapports sauvegardés : portée société + envoi planifié."""
from django.contrib.auth import get_user_model
from django.core import mail
from django.test import TestCase, override_settings
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company

from .models import SavedReport
from .scheduled_reports import email_saved_reports

User = get_user_model()


def _auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


class SavedReportModelTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='ScopeCo')
        self.other = Company.objects.create(nom='OtherCo')
        self.user = User.objects.create_user(
            username='owner', password='x', role_legacy='responsable',
            company=self.company)
        self.api = _auth(self.user)

    def test_create_forces_company_and_owner_server_side(self):
        # On tente d'injecter une autre société via le corps : elle est ignorée.
        res = self.api.post('/api/django/reporting/saved-reports/', {
            'name': 'Mon rapport', 'target_kind': 'sales',
            'schedule': 'daily', 'recipients': 'a@b.com',
            'company': self.other.id,  # doit être ignoré
        }, format='json')
        self.assertEqual(res.status_code, 201, res.data)
        sr = SavedReport.objects.get(id=res.data['id'])
        self.assertEqual(sr.company, self.company)
        self.assertEqual(sr.owner, self.user)

    def test_list_is_company_scoped(self):
        SavedReport.objects.create(company=self.company, name='À moi')
        SavedReport.objects.create(company=self.other, name='Pas à moi')
        res = self.api.get('/api/django/reporting/saved-reports/')
        self.assertEqual(res.status_code, 200)
        results = res.data['results'] if 'results' in res.data else res.data
        names = {r['name'] for r in results}
        self.assertIn('À moi', names)
        self.assertNotIn('Pas à moi', names)

    def test_cannot_fetch_other_company_report(self):
        other_sr = SavedReport.objects.create(
            company=self.other, name='Étranger')
        res = self.api.get(
            f'/api/django/reporting/saved-reports/{other_sr.id}/')
        self.assertEqual(res.status_code, 404)

    def test_recipient_list_parsing(self):
        sr = SavedReport.objects.create(
            company=self.company, name='R',
            recipients='a@b.com, c@d.com;e@f.com\ng@h.com')
        self.assertEqual(
            sr.recipient_list(), ['a@b.com', 'c@d.com', 'e@f.com', 'g@h.com'])


@override_settings(
    EMAIL_BACKEND='django.core.mail.backends.console.EmailBackend')
class ScheduledReportNoEmailTests(TestCase):
    """Sans email configuré (backend console), la tâche est un NO-OP propre."""

    def setUp(self):
        self.company = Company.objects.create(nom='NoMailCo')

    def test_task_noop_without_email_configured(self):
        SavedReport.objects.create(
            company=self.company, name='Quotidien', target_kind='sales',
            schedule='daily', recipients='boss@example.com')
        # is_email_configured() est False pour le backend console → aucun envoi.
        sent = email_saved_reports()
        self.assertEqual(sent, 0)
        self.assertEqual(len(mail.outbox), 0)


@override_settings(
    EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend',
    ANYMAIL={'BREVO_API_KEY': 'test-key'})
class ScheduledReportSelectionTests(TestCase):
    """Avec une configuration email présente, la tâche sélectionne les rapports
    DUS et envoie le .xlsx en pièce jointe."""

    def setUp(self):
        self.company = Company.objects.create(nom='DueCo')

    def test_selects_due_daily_report_and_emails_xlsx(self):
        SavedReport.objects.create(
            company=self.company, name='Ventes quotidien', target_kind='sales',
            schedule='daily', recipients='boss@example.com')
        # Un rapport schedule='none' ne doit JAMAIS partir.
        SavedReport.objects.create(
            company=self.company, name='Jamais', target_kind='sales',
            schedule='none', recipients='boss@example.com')
        # Un rapport daily sans destinataire ne part pas non plus.
        SavedReport.objects.create(
            company=self.company, name='Sans dest', target_kind='sales',
            schedule='daily', recipients='')
        sent = email_saved_reports()
        self.assertEqual(sent, 1)
        self.assertEqual(len(mail.outbox), 1)
        msg = mail.outbox[0]
        self.assertEqual(msg.to, ['boss@example.com'])
        self.assertEqual(len(msg.attachments), 1)
        name, _content, mimetype = msg.attachments[0]
        self.assertTrue(name.endswith('.xlsx'))
        self.assertIn('spreadsheetml', mimetype)
        # last_sent_at horodaté sur envoi réussi.
        sr = SavedReport.objects.get(name='Ventes quotidien')
        self.assertIsNotNone(sr.last_sent_at)

    def test_weekly_only_sent_on_monday(self):
        SavedReport.objects.create(
            company=self.company, name='Hebdo', target_kind='service',
            schedule='weekly', recipients='boss@example.com')
        from unittest import mock
        from datetime import datetime
        try:
            from zoneinfo import ZoneInfo
            tz = ZoneInfo('Africa/Casablanca')
        except Exception:  # pragma: no cover
            tz = None
        # Un mardi : weekly NON dû.
        tuesday = datetime(2026, 6, 16, 6, 0, tzinfo=tz)
        with mock.patch(
                'apps.reporting.scheduled_reports._casablanca_now',
                return_value=tuesday):
            self.assertEqual(email_saved_reports(), 0)
        self.assertEqual(len(mail.outbox), 0)
        # Un lundi : weekly dû.
        monday = datetime(2026, 6, 15, 6, 0, tzinfo=tz)
        with mock.patch(
                'apps.reporting.scheduled_reports._casablanca_now',
                return_value=monday):
            self.assertEqual(email_saved_reports(), 1)
        self.assertEqual(len(mail.outbox), 1)
