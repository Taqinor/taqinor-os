"""QW8 — un rappel demandé (phone_ok callback) part réellement par email.

Contexte : ``notifications.services.DEFAULT_PREFS['email'] = False`` — sans
opt-in, ``notify()`` n'envoie aucun email. QW8 pose un override par événement
(``EVENT_DEFAULT_OVERRIDES``) qui met ``email: True`` pour
``lead_callback_requested``/``lead_callback_sla_breach``. Ces tests prouvent
qu'une PROD configurée (clé Brevo posée) émet bien un ``EmailMessage`` sortant
sur un callback phone_ok — SANS aucune ``NotificationPreference`` opt-in.

On configure ``ANYMAIL['SENDINBLUE_API_KEY']`` (ce que ``is_email_configured``
regarde EN PREMIER, cf. correctif de clé QW8) pour simuler la prod, tout en
gardant le backend ``locmem`` afin de capturer ``mail.outbox`` sans réseau.
"""
import datetime
from unittest import mock

from django.contrib.auth import get_user_model
from django.core import mail
from django.test import TestCase, override_settings
from django.utils import timezone

from authentication.models import Company

from .models import EventType, Notification, NotificationPreference
from .services import notify

User = get_user_model()

# VX209(a) — `notify()` respecte désormais les heures calmes par défaut pour
# les événements non-critiques (`LEAD_CALLBACK_REQUESTED` en fait partie) :
# ces tests visent le canal email lui-même (QW8), pas les heures calmes —
# on fige l'horloge sur un mercredi en journée (jour ouvré par défaut, aucune
# config société) pour rester déterministe quelle que soit l'heure d'exécution
# de la CI.
_WEEKDAY_DAYTIME = timezone.make_aware(datetime.datetime(2026, 7, 8, 14, 0))

# PROD-like : clé Brevo posée (is_email_configured() la voit en premier) +
# backend locmem pour capter mail.outbox sans appel réseau.
CONFIGURED = dict(
    ANYMAIL={'SENDINBLUE_API_KEY': 'brevo-test-key'},
    EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend',
    DEFAULT_FROM_EMAIL='ventes@taqinor.ma',
)


@override_settings(**CONFIGURED)
class Qw8CallbackEmailTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='QW8 Co')
        self.user = User.objects.create_user(
            username='seller', password='pw',
            email='seller@example.com', company=self.company)
        mail.outbox = []

    def test_callback_requested_fires_outbound_email_when_configured(self):
        # Aucune NotificationPreference : l'email doit partir grâce à l'override
        # d'événement QW8 (email ON par défaut pour ce type), pas grâce à un
        # opt-in.
        self.assertFalse(NotificationPreference.objects.filter(
            user=self.user,
            event_type=EventType.LEAD_CALLBACK_REQUESTED).exists())

        with mock.patch(
                'apps.notifications.services.timezone.now',
                return_value=_WEEKDAY_DAYTIME):
            notif = notify(
                self.user, EventType.LEAD_CALLBACK_REQUESTED,
                'Rappel demandé',
                body='Le prospect a demandé à être rappelé.',
                link='/crm/leads?lead=1')

        # In-app créée ET un email sortant capté.
        self.assertIsNotNone(notif)
        self.assertEqual(len(mail.outbox), 1)
        msg = mail.outbox[0]
        self.assertEqual(msg.to, ['seller@example.com'])
        self.assertEqual(msg.from_email, 'ventes@taqinor.ma')
        self.assertIn('Rappel demandé', msg.subject)

    def test_generic_event_does_not_email_by_default(self):
        # Un événement SANS override reste email-OFF par défaut (preuve que le
        # canal n'est pas ouvert globalement — seul l'override QW8 l'ouvre).
        notify(self.user, EventType.LEAD_ASSIGNED, 'Nouveau lead',
               body='x', link='/crm/leads?lead=2')
        self.assertEqual(len(mail.outbox), 0)

    def test_no_email_when_unconfigured(self):
        # Sans configuration prod, le callback ne part pas par email (no-op sûr).
        with override_settings(
                ANYMAIL={},
                EMAIL_BACKEND='django.core.mail.backends.locmem.'
                              'EmailBackend'):
            mail.outbox = []
            notify(self.user, EventType.LEAD_CALLBACK_REQUESTED,
                   'Rappel demandé', body='y')
            self.assertEqual(len(mail.outbox), 0)
        # L'in-app a tout de même été créée pour les deux appels.
        self.assertTrue(Notification.objects.filter(
            recipient=self.user,
            event_type=EventType.LEAD_CALLBACK_REQUESTED).exists())
