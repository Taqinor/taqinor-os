"""XSAV26 — WhatsApp entrant -> ticket SAV (gated BSP).

Couvre :
  * un message d'un numéro reconnu comme `crm.Client` existant (matching
    `normalize_ma_phone`) crée un ticket SAV correctif s'il n'en a aucun
    d'ouvert ;
  * un second message du même client (ticket déjà ouvert) ajoute une note
    chatter au ticket ouvert le plus récent au lieu d'en créer un second ;
  * no-op total sans credentials BSP (WHATSAPP_ENABLED/WHATSAPP_ACCESS_TOKEN
    absents) — comportement actuel inchangé ;
  * un numéro INCONNU du SAV route toujours vers le lead existant (chemin
    XKB33 inchangé, aucun ticket créé).

Run :
    docker compose exec django_core python manage.py test apps.sav.tests_xsav26 -v 2
"""
import json
from unittest import mock

from django.contrib.auth import get_user_model
from django.test import RequestFactory, TestCase, override_settings

from authentication.models import Company
from apps.crm.models import Client
from apps.sav.models import Ticket

User = get_user_model()


def make_company(slug='sav-xsav26', nom='Sav Co XSAV26'):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


def _post_payload(payload_dict, env_overrides=None):
    from apps.notifications.views_whatsapp_bsp import WhatsAppBspWebhookView
    factory = RequestFactory()
    body = json.dumps(payload_dict).encode()
    request = factory.post(
        '/fake/webhook/', body, content_type='application/json')
    env = env_overrides or {}
    env.setdefault('WHATSAPP_BSP_APP_SECRET', '')
    with mock.patch.dict('os.environ', env, clear=False):
        return WhatsAppBspWebhookView.as_view()(request)


def _inbound_payload(wa_message_id='wamid.sav001', from_number='212611112222',
                     name='Client SAV', body='Ma pompe ne demarre plus'):
    return {
        'entry': [{
            'changes': [{
                'value': {
                    'contacts': [{
                        'profile': {'name': name}, 'wa_id': from_number,
                    }],
                    'messages': [{
                        'id': wa_message_id,
                        'from': from_number,
                        'type': 'text',
                        'text': {'body': body},
                    }],
                }
            }]
        }]
    }


class XSAV26WhatsAppEntrantTest(TestCase):
    def setUp(self):
        self.company = make_company()
        self.client_obj = Client.objects.create(
            company=self.company, nom='Client', prenom='SAV',
            telephone='0611112222',
            email='xsav26-client@example.invalid')

    def _env(self):
        return {'WHATSAPP_BSP_COMPANY_ID': str(self.company.pk)}

    def test_no_op_sans_cle_bsp(self):
        """Sans WHATSAPP_ENABLED/WHATSAPP_ACCESS_TOKEN, rien ne change."""
        with override_settings(WHATSAPP_ENABLED=False):
            resp = _post_payload(_inbound_payload(), self._env())
        self.assertEqual(resp.status_code, 200)
        self.assertFalse(
            Ticket.objects.filter(company=self.company).exists())

    def test_numero_reconnu_cree_un_ticket(self):
        with override_settings(
                WHATSAPP_ENABLED=True, WHATSAPP_ACCESS_TOKEN='tok'):
            resp = _post_payload(
                _inbound_payload(wa_message_id='wamid.sav-create'),
                self._env())
        self.assertEqual(resp.status_code, 200)
        ticket = Ticket.objects.get(company=self.company, client=self.client_obj)
        self.assertEqual(ticket.type, Ticket.Type.CORRECTIF)
        self.assertIn('demarre', ticket.description)
        self.assertIn(ticket.statut, Ticket.OPEN_STATUTS)

    def test_second_message_ajoute_note_au_ticket_ouvert(self):
        with override_settings(
                WHATSAPP_ENABLED=True, WHATSAPP_ACCESS_TOKEN='tok'):
            _post_payload(
                _inbound_payload(wa_message_id='wamid.sav-first'),
                self._env())
            resp = _post_payload(
                _inbound_payload(
                    wa_message_id='wamid.sav-second',
                    body='Toujours en panne, merci de revenir'),
                self._env())
        self.assertEqual(resp.status_code, 200)
        # Un seul ticket créé pour ce client (le second message est une note).
        self.assertEqual(
            Ticket.objects.filter(
                company=self.company, client=self.client_obj).count(), 1)
        ticket = Ticket.objects.get(
            company=self.company, client=self.client_obj)
        notes = ticket.activites.filter(
            kind='note', body__icontains='Toujours en panne')
        self.assertTrue(notes.exists())

    def test_numero_inconnu_route_toujours_vers_lead(self):
        """Un numéro qui ne matche aucun Client SAV ne crée aucun ticket —
        le chemin lead existant (XKB33) reste inchangé."""
        with override_settings(
                WHATSAPP_ENABLED=True, WHATSAPP_ACCESS_TOKEN='tok'):
            resp = _post_payload(
                _inbound_payload(
                    wa_message_id='wamid.sav-unknown',
                    from_number='212699999999'),
                self._env())
        self.assertEqual(resp.status_code, 200)
        self.assertFalse(
            Ticket.objects.filter(company=self.company).exists())
