"""ASAV35 — un message d'un fil connu ne crée jamais de ticket, même adressé à
l'alias d'une catégorie (« répondre à tous »). Les messages passent par le
registre réel de ``core.email_intake``.

Run :
    python manage.py test apps.sav.tests_asav35_alias_fil -v2
"""
from django.test import TestCase

from authentication.models import Company
from apps.crm.models import Client
from apps.sav.models import CategorieEquipement, Ticket, TicketEmailThread
from core.email_intake import InboundMessage, _dispatch

ALIAS = 'onduleurs-asav35@example.invalid'
CLIENT_EMAIL = 'client-asav35@example.invalid'


def _message(message_id, *, in_reply_to='', references=''):
    return InboundMessage(
        message_id=message_id, in_reply_to=in_reply_to,
        references=references, subject='Panne onduleur',
        from_email=CLIENT_EMAIL, from_name='Client', body='Ça ne démarre plus.',
        raw_headers={'To': ALIAS, 'From': CLIENT_EMAIL})


class AliasFilTests(TestCase):

    def setUp(self):
        self.company, _ = Company.objects.get_or_create(
            slug='asav35-co', defaults={'nom': 'ASAV35 Co'})
        Client.objects.create(
            company=self.company, nom='Client', prenom='ASAV35',
            email=CLIENT_EMAIL)
        CategorieEquipement.objects.create(
            company=self.company, nom='Onduleurs', alias_email=ALIAS)

    def _tickets(self):
        return Ticket.objects.filter(company=self.company)

    def test_premier_mail_cree(self):
        _dispatch([_message('<m1@x>')], self.company)
        self.assertEqual(self._tickets().count(), 1)

    def test_reponse_dans_fil_aucun_ticket(self):
        _dispatch([_message('<m1@x>')], self.company)
        ticket = self._tickets().get()
        reponse = _message('<m2@x>', in_reply_to='<m1@x>',
                           references='<m1@x>')
        _dispatch([reponse], self.company)
        self.assertEqual(self._tickets().count(), 1)
        self.assertFalse(self._tickets().filter(
            description__startswith='[email:<m2@x>]').exists())
        self.assertTrue(TicketEmailThread.objects.filter(
            ticket=ticket, message_id='<m2@x>').exists())
