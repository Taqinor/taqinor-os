"""QX36 — les réponses email ne tombent plus dans le vide.

  * le handler ventes route une réponse référencée DEV-… vers le fil du devis
    (chatter + notification vendeur) ;
  * la tâche beat ``poll_inbound_mailboxes`` dispatche les messages relevés ;
  * les emails sortants portent un Reply-To vers la boîte entrante.
"""
from decimal import Decimal
from unittest import mock

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.utils import timezone

from authentication.models import Company
from apps.crm.models import Client
from apps.ventes.models import Devis, EmailLog
from apps.ventes.inbound_email import ventes_inbound_handler

User = get_user_model()
MONTH = timezone.now().strftime('%Y%m')


class _StubMessage:
    def __init__(self, subject='', body='', from_email=''):
        self.subject = subject
        self.body = body
        self.from_email = from_email


class Qx36InboundEmailTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='QX36 Co')
        self.owner = User.objects.create_user(
            username='qx36_seller', password='x', role_legacy='commercial',
            company=self.company, email='seller@example.com')
        self.client_obj = Client.objects.create(
            company=self.company, nom='Client', prenom='QX36',
            email='client@example.com', telephone='+212600000048')
        self.devis = Devis.objects.create(
            company=self.company, reference=f'DEV-{MONTH}-QX3601',
            client=self.client_obj, statut=Devis.Statut.ENVOYE,
            taux_tva=Decimal('20'), created_by=self.owner)

    def test_reply_lands_on_devis_chatter(self):
        msg = _StubMessage(
            subject=f'Re: votre devis {self.devis.reference}',
            body='Bonjour, je suis intéressé, on avance ?',
            from_email='client@example.com')
        log = ventes_inbound_handler(msg, self.company)
        self.assertIsNotNone(log)
        self.assertEqual(log.devis_id, self.devis.id)
        self.assertEqual(log.direction, EmailLog.Direction.ENTRANT)
        # Une note apparaît dans le chatter du devis.
        bodies = [a.body or '' for a in self.devis.activites.all()]
        self.assertTrue(any('Réponse email' in b for b in bodies))

    def test_reply_notifies_seller(self):
        from apps.notifications.models import Notification, EventType
        msg = _StubMessage(
            subject=f'Re: {self.devis.reference}', body='Merci',
            from_email='client@example.com')
        ventes_inbound_handler(msg, self.company)
        notif = Notification.objects.filter(
            recipient=self.owner, event_type=EventType.DEVIS_REPLY).first()
        self.assertIsNotNone(notif)
        self.assertIn(str(self.devis.id), notif.link)

    def test_unmatched_reply_creates_nothing(self):
        msg = _StubMessage(subject='Question générale', body='Bonjour',
                           from_email='inconnu@nowhere.test')
        log = ventes_inbound_handler(msg, self.company)
        self.assertIsNone(log)

    def test_poll_inbound_mailboxes_dispatches(self):
        from apps.ventes.scheduled import poll_inbound_mailboxes
        with mock.patch(
                'core.email_intake.poll_mailbox',
                return_value={'fetched': 2, 'handled': 2}) as pm:
            res = poll_inbound_mailboxes()
        self.assertTrue(pm.called)
        self.assertEqual(res['fetched'], 2)

    @override_settings(INBOUND_REPLY_EMAIL='replies@taqinor.ma',
                       EMAIL_BACKEND='django.core.mail.backends.locmem.'
                                     'EmailBackend')
    def test_outbound_sets_reply_to(self):
        from django.core import mail
        from apps.ventes.email_service import _send
        mail.outbox = []
        ok, err = _send('client@example.com', 'Sujet', 'Corps')
        self.assertTrue(ok, err)
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].reply_to, ['replies@taqinor.ma'])
