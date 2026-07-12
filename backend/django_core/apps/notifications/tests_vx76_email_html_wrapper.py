"""VX76 — ``notify()`` porte désormais une alternative HTML brandée (wrapper
logo/en-tête navy/pied) sur le canal email, en plus du corps texte brut
existant (repli MIME conservé, additif, non cassant). Réutilise le patron
PROD-like de ``tests_qw8_callback_email.py`` (clé Brevo simulée + backend
locmem pour capter ``mail.outbox`` sans réseau)."""
import datetime
from unittest import mock

from django.contrib.auth import get_user_model
from django.core import mail
from django.test import TestCase, override_settings
from django.utils import timezone

from authentication.models import Company

from .models import EventType
from .services import notify

User = get_user_model()

# VX209(a) — `notify()` respecte désormais les heures calmes par défaut pour
# les événements non-critiques (`LEAD_CALLBACK_REQUESTED` en fait partie) ;
# ce test vise le wrapper HTML de l'email, pas les heures calmes — horloge
# figée sur un mercredi en journée pour rester déterministe.
_WEEKDAY_DAYTIME = timezone.make_aware(datetime.datetime(2026, 7, 8, 14, 0))

CONFIGURED = dict(
    ANYMAIL={'SENDINBLUE_API_KEY': 'brevo-test-key'},
    EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend',
    DEFAULT_FROM_EMAIL='ventes@taqinor.ma',
)


@override_settings(**CONFIGURED)
class Vx76NotifyHtmlWrapperTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='VX76 Notif Co')
        self.user = User.objects.create_user(
            username='vx76notif', password='pw',
            email='vx76notif@example.com', company=self.company)
        mail.outbox = []

    def test_notify_email_carries_html_alternative(self):
        with mock.patch(
                'apps.notifications.services.timezone.now',
                return_value=_WEEKDAY_DAYTIME):
            notify(
                self.user, EventType.LEAD_CALLBACK_REQUESTED,
                'Rappel demandé',
                body='Le prospect a demandé à être rappelé.',
                link='/crm/leads?lead=1')

        self.assertEqual(len(mail.outbox), 1)
        msg = mail.outbox[0]
        self.assertIn('Le prospect a demandé', msg.body)
        alternatives = getattr(msg, 'alternatives', [])
        html_alts = [c for c, mimetype in alternatives if mimetype == 'text/html']
        self.assertEqual(len(html_alts), 1)
        self.assertIn('VX76 Notif Co', html_alts[0])
        self.assertIn('Rappel demandé', html_alts[0])
