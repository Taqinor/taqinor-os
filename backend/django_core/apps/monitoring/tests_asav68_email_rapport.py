"""ASAV68 — l'échec d'envoi du rapport O&M est détecté : 502 en français et
AUCUNE notification interne « Rapport envoyé » ; un envoi réussi répond 200.
SMTP réel sur un port fermé, aucun mock de l'envoi.

Run :
    python manage.py test apps.monitoring.tests_asav68_email_rapport -v2
"""
from decimal import Decimal
from unittest import mock

from django.contrib.auth import get_user_model
from django.core import mail
from django.test import TestCase, override_settings
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.crm.models import Client
from apps.installations.models import Installation
from apps.monitoring.models import MonitoringConfig
from apps.notifications.models import Notification
from authentication.models import Company

User = get_user_model()


class EmailRapportTests(TestCase):

    def setUp(self):
        self.company, _ = Company.objects.get_or_create(
            slug='asav68-co', defaults={'nom': 'ASAV68 Co'})
        user = User.objects.create_user(
            username='asav68_admin', password='x', role_legacy='admin',
            company=self.company)
        self.api = APIClient()
        self.api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
        client = Client.objects.create(
            company=self.company, nom='Client', prenom='ASAV68',
            email='asav68-client@example.invalid')
        inst = Installation.objects.create(
            company=self.company, reference='CHT-ASAV68', client=client,
            puissance_installee_kwc=Decimal('5.00'))
        self.config = MonitoringConfig.objects.create(
            company=self.company, installation=inst,
            expected_annual_kwh=Decimal('6000'))
        self.url = (f'/api/django/monitoring/configs/{self.config.pk}'
                    '/email-om-report/')

    def _notifs(self):
        return Notification.objects.filter(
            company=self.company, event_type='monitoring_rapport').count()

    @override_settings(
        EMAIL_BACKEND='django.core.mail.backends.smtp.EmailBackend',
        EMAIL_HOST='127.0.0.1', EMAIL_PORT=1, EMAIL_USE_TLS=False,
        EMAIL_USE_SSL=False, EMAIL_TIMEOUT=2)
    def test_smtp_ko_502_sans_notification(self):
        with mock.patch('apps.monitoring.report.render_om_report_pdf',
                        return_value=b'%PDF-1.4'):
            r = self.api.post(self.url, {}, format='json')
        self.assertEqual(r.status_code, 502, r.content)
        self.assertTrue(r.data['detail'].startswith('Envoi impossible'))
        self.assertEqual(self._notifs(), 0)

    @override_settings(
        EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend')
    def test_envoi_ok(self):
        with mock.patch('apps.monitoring.report.render_om_report_pdf',
                        return_value=b'%PDF-1.4'):
            r = self.api.post(self.url, {}, format='json')
        self.assertEqual(r.status_code, 200, r.content)
        self.assertTrue(r.data['sent'])
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(self._notifs(), 1)

    @override_settings(
        EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend')
    def test_corps_invalide_400_nomme(self):
        """CI #993 api-fuzz-pr (cas JNK86P) : ``{"period": null, "recipient":
        "0"}`` faisait une 500 (``html.escape(None)`` dans le gabarit) → 400
        nommant chaque champ ; rien n'est envoyé ni notifié."""
        cas = [
            ({'period': None, 'recipient': '0'}, {'period', 'recipient'}),
            ({'period': 'annual'}, {'period'}),
            ({'recipient': 'pas-un-email'}, {'recipient'}),
            ({'recipient': ['a@example.com']}, {'recipient'}),
        ]
        for corps, champs in cas:
            with self.subTest(corps=corps):
                r = self.api.post(self.url, corps, format='json')
                self.assertEqual(r.status_code, 400, r.content)
                for champ in champs:
                    self.assertIn(champ, r.content.decode())
        self.assertEqual(len(mail.outbox), 0)
        self.assertEqual(self._notifs(), 0)

    @override_settings(
        EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend')
    def test_periode_trimestrielle_et_destinataire_explicite(self):
        with mock.patch('apps.monitoring.report.render_om_report_pdf',
                        return_value=b'%PDF-1.4'):
            r = self.api.post(self.url, {
                'period': 'quarterly', 'recipient': 'autre@example.com',
            }, format='json')
        self.assertEqual(r.status_code, 200, r.content)
        self.assertEqual(mail.outbox[0].to, ['autre@example.com'])
        self.assertIn('trimestriel', mail.outbox[0].subject)
