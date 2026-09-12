"""NTSRV3 — Canal WhatsApp entrant SAV (webhook GATED par clé).

Critère d'acceptation :
  * sans clé configurée, l'endpoint renvoie 404 et rien ne crashe au
    démarrage (la clé est lue à l'APPEL, jamais à l'import) ;
  * avec clé, un message d'un numéro connu crée (puis rattache) un ticket
    WhatsApp ; un numéro inconnu ne crée aucun ticket orphelin ;
  * redélivrance Meta (même identifiant de message) → aucun doublon.

Run :
    docker compose exec django_core python manage.py test apps.sav.tests_ntsrv3 -v 2
"""
from django.core.cache import cache
from django.test import TestCase, override_settings

from authentication.models import Company
from apps.crm.models import Client
from apps.sav.models import Ticket, TicketActivity
from apps.sav.services import extraire_message_whatsapp

URL = '/api/django/sav/webhooks/whatsapp-inbound/'


def _payload_meta(message_id='wamid.1', telephone='212600112233',
                  texte='Mon onduleur est en panne'):
    return {'entry': [{'changes': [{'value': {'messages': [{
        'id': message_id, 'from': telephone, 'text': {'body': texte},
    }]}}]}]}


class NTSRV3GatingTest(TestCase):
    def setUp(self):
        cache.clear()

    def test_sans_cle_lendpoint_repond_404(self):
        resp = self.client.post(URL, _payload_meta(),
                                content_type='application/json')
        self.assertEqual(resp.status_code, 404)
        self.assertEqual(Ticket.objects.count(), 0)

    @override_settings(WHATSAPP_BUSINESS_API_KEY='')
    def test_cle_vide_equivaut_a_absente(self):
        resp = self.client.post(URL, _payload_meta(),
                                content_type='application/json')
        self.assertEqual(resp.status_code, 404)


@override_settings(WHATSAPP_BUSINESS_API_KEY='cle-test-ntsrv3')
class NTSRV3InboundTest(TestCase):
    def setUp(self):
        cache.clear()
        self.company, _ = Company.objects.get_or_create(
            slug='sav-ntsrv3', defaults={'nom': 'Sav Co NTSRV3'})
        self.client_obj = Client.objects.create(
            company=self.company, nom='Client', prenom='NTSRV3',
            telephone='0600112233')

    def _post(self, payload):
        # Le tenant est résolu CÔTÉ SERVEUR (jamais depuis le corps) : on fixe
        # explicitement la société cible du récepteur, comme en production.
        with self.settings(SAV_WHATSAPP_COMPANY_ID=self.company.pk):
            return self.client.post(URL, payload,
                                    content_type='application/json')

    def test_numero_connu_ouvre_un_ticket_whatsapp(self):
        resp = self._post(_payload_meta())
        self.assertEqual(resp.status_code, 201, resp.content)
        ticket = Ticket.objects.get()
        self.assertEqual(ticket.client, self.client_obj)
        self.assertEqual(ticket.canal_ouverture, Ticket.CanalOuverture.WHATSAPP)
        self.assertTrue(TicketActivity.objects.filter(
            ticket=ticket, kind=TicketActivity.Kind.WHATSAPP).exists())

    def test_second_message_se_rattache_au_meme_ticket(self):
        self._post(_payload_meta(message_id='wamid.A'))
        resp = self._post(_payload_meta(message_id='wamid.B',
                                        texte='Toujours rien'))
        self.assertEqual(resp.status_code, 200, resp.content)
        self.assertEqual(Ticket.objects.count(), 1)
        self.assertEqual(TicketActivity.objects.filter(
            kind=TicketActivity.Kind.WHATSAPP).count(), 2)

    def test_redelivrance_du_meme_message_est_idempotente(self):
        self._post(_payload_meta(message_id='wamid.DUP'))
        resp = self._post(_payload_meta(message_id='wamid.DUP'))
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(Ticket.objects.count(), 1)
        self.assertEqual(TicketActivity.objects.filter(
            kind=TicketActivity.Kind.WHATSAPP).count(), 1)

    def test_numero_inconnu_ne_cree_aucun_ticket(self):
        resp = self._post(_payload_meta(telephone='212699999999'))
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(Ticket.objects.count(), 0)

    def test_charge_utile_sans_message_renvoie_400(self):
        self.assertEqual(self._post({'entry': []}).status_code, 400)

    def test_forme_plate_acceptee(self):
        resp = self._post({'message_id': 'plat-1', 'from': '212600112233',
                           'text': 'Bonjour'})
        self.assertEqual(resp.status_code, 201, resp.content)


class NTSRV3ParsingTest(TestCase):
    def test_extraction_forme_meta(self):
        self.assertEqual(
            extraire_message_whatsapp(_payload_meta()),
            ('wamid.1', '212600112233', 'Mon onduleur est en panne'))

    def test_extraction_forme_plate(self):
        self.assertEqual(
            extraire_message_whatsapp(
                {'message_id': 'x', 'from': '212600000000', 'text': 'Salut'}),
            ('x', '212600000000', 'Salut'))

    def test_charge_inattendue_ne_leve_jamais(self):
        for charge in (None, [], {}, {'entry': [None]},
                       {'entry': [{'changes': [{'value': {}}]}]}):
            self.assertEqual(extraire_message_whatsapp(charge),
                             (None, None, None))
