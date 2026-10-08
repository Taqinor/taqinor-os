"""APAR19 — canaux de notification honnêtes (C-APAR-025).

WhatsApp n'a AUCUN transport serveur : le journal ne dit plus « envoyé » mais
« non envoyé : canal non configuré » ; ``_dispatch_email`` renvoie le vrai
résultat de ``send()`` (0 message remis ⇒ « échec »). La préférence stockée
n'est jamais effacée.
"""
import datetime
from unittest import mock

from django.contrib.auth import get_user_model
from django.core.mail.backends.base import BaseEmailBackend
from django.test import TestCase, override_settings
from django.utils import timezone

from apps.audit.models import AuditLog
from authentication.models import Company

from .models import NotificationPreference
from .services import _dispatch_email, _dispatch_whatsapp, notify
from .types_evenements import EventType

User = get_user_model()
_MERCREDI_14H = timezone.make_aware(datetime.datetime(2026, 7, 8, 14, 0))


class BackendQuiEchoue(BaseEmailBackend):
    """Backend réel au sens Django : n'en remet aucun (comme un SMTP refusé
    en ``fail_silently``)."""

    def send_messages(self, email_messages):
        return 0


@override_settings(
    EMAIL_BACKEND='apps.notifications.tests_apar19_canaux_honnetes.BackendQuiEchoue')
class CanauxHonnetesTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='APAR19')
        self.user = User.objects.create_user(
            username='apar19', password='pw', company=self.company,
            email='apar19@example.ma', phone_number='+212600000000')
        self.pref = NotificationPreference.objects.create(
            user=self.user, company=self.company,
            event_type=EventType.LEAD_ASSIGNED, whatsapp=True, email=True)

    def _notify(self):
        with mock.patch('apps.notifications.services.timezone.now',
                        return_value=_MERCREDI_14H), \
                mock.patch('apps.notifications.services._is_email_configured',
                           return_value=True):
            with self.captureOnCommitCallbacks(execute=True):
                notify(self.user, EventType.LEAD_ASSIGNED, 'Titre', body='Corps')

    def test_whatsapp_jamais_envoye_sans_transport(self):
        self.assertFalse(_dispatch_whatsapp(self.user, 'Titre', 'Corps'))

    def test_dispatch_email_renvoie_le_vrai_resultat(self):
        with mock.patch('apps.notifications.services._is_email_configured',
                        return_value=True):
            self.assertFalse(_dispatch_email(self.user, 'Titre', 'Corps'))

    def test_journal_honnete(self):
        self._notify()
        wa = AuditLog.objects.get(action=AuditLog.Action.WHATSAPP)
        self.assertIn('whatsapp (non envoyé : canal non configuré)', wa.detail)
        self.assertNotIn('(envoyé)', wa.detail)
        mail = AuditLog.objects.get(action=AuditLog.Action.EMAIL)
        self.assertIn('email (échec)', mail.detail)

    def test_preference_whatsapp_conservee(self):
        self._notify()
        self.pref.refresh_from_db()
        self.assertTrue(self.pref.whatsapp)


class EmailReussiTests(TestCase):
    def test_backend_locmem_compte_comme_envoye(self):
        company = Company.objects.create(nom='APAR19 ok')
        user = User.objects.create_user(
            username='apar19ok', password='pw', company=company,
            email='ok@example.ma')
        with mock.patch('apps.notifications.services._is_email_configured',
                        return_value=True):
            self.assertTrue(_dispatch_email(user, 'Titre', 'Corps'))
