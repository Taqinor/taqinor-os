"""ASEC36 — webhook WhatsApp SAV entrant fermé.

Constat C-ASEC-012 (latent) : le récepteur AllowAny acceptait un POST non
signé, se repliait en silence sur « la première société » et répondait
différemment selon que l'expéditeur était un client connu ou non. Attendu :
secret absent → 503 ; signature absente/fausse → 401 ; numéro destinataire
non rattaché → 200 neutre sans écriture ; réponse identique quel que soit
l'expéditeur ; un message signé et rattaché → écrit dans LA société du
numéro.
"""
import hashlib
import hmac
import json

from django.core.cache import cache
from django.test import TestCase, override_settings

from apps.crm.models import Client
from apps.sav.models import Ticket, TicketActivity
from authentication.models import Company

URL = '/api/django/sav/webhooks/whatsapp-inbound/'
SECRET = 'secret-de-test-asec36'


def _payload(numero_dest, telephone='212600112233', message_id='wamid.1'):
    return {'entry': [{'changes': [{'value': {
        'metadata': {'phone_number_id': numero_dest},
        'messages': [{'id': message_id, 'from': telephone,
                      'text': {'body': 'Panne onduleur'}}],
    }}]}]}


def _signer(corps, secret=SECRET):
    return 'sha256=' + hmac.new(
        secret.encode(), corps, hashlib.sha256).hexdigest()


@override_settings(WHATSAPP_BUSINESS_API_KEY='cle-test-asec36')
class WebhookWhatsappSavTests(TestCase):
    def setUp(self):
        cache.clear()
        self.a = Company.objects.create(nom='ASEC36 A', slug='asec36-a')
        self.b = Company.objects.create(nom='ASEC36 B', slug='asec36-b')
        self.client_b = Client.objects.create(
            company=self.b, nom='Client', prenom='B',
            telephone='0600112233')
        self.numeros = {'NUM-A': self.a.pk, 'NUM-B': self.b.pk}

    def _post(self, payload, signature='auto', secret=SECRET):
        corps = json.dumps(payload).encode()
        extra = {}
        if signature == 'auto':
            extra['HTTP_X_HUB_SIGNATURE_256'] = _signer(corps)
        elif signature is not None:
            extra['HTTP_X_HUB_SIGNATURE_256'] = signature
        with self.settings(SAV_WHATSAPP_APP_SECRET=secret,
                           SAV_WHATSAPP_NUMEROS=self.numeros):
            return self.client.post(URL, data=corps,
                                    content_type='application/json', **extra)

    def _compteurs(self):
        return (Ticket.objects.count(), TicketActivity.objects.count())

    def test_sans_secret_503(self):
        avant = self._compteurs()
        resp = self._post(_payload('NUM-B'), secret='')
        self.assertEqual(resp.status_code, 503)
        self.assertIn('SAV_WHATSAPP_APP_SECRET', resp.json()['detail'])
        self.assertEqual(self._compteurs(), avant)

    def test_signature_absente_401(self):
        avant = self._compteurs()
        resp = self._post(_payload('NUM-B'), signature=None)
        self.assertEqual(resp.status_code, 401)
        self.assertEqual(self._compteurs(), avant)

    def test_signature_fausse_401(self):
        avant = self._compteurs()
        corps = json.dumps(_payload('NUM-B')).encode()
        resp = self._post(_payload('NUM-B'),
                          signature=_signer(corps, secret='autre-secret'))
        self.assertEqual(resp.status_code, 401)
        self.assertEqual(self._compteurs(), avant)

    def test_numero_inconnu_neutre(self):
        avant = self._compteurs()
        resp = self._post(_payload('NUM-INCONNU'))
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(self._compteurs(), avant)
        # Aucun repli « première société » : sans destinataire non plus.
        payload = _payload('NUM-B')
        del payload['entry'][0]['changes'][0]['value']['metadata']
        resp2 = self._post(payload)
        self.assertEqual(resp2.status_code, 200)
        self.assertEqual(self._compteurs(), avant)

    def test_reponse_identique_expediteur(self):
        connu = self._post(_payload('NUM-B', message_id='wamid.K'))
        inconnu = self._post(_payload('NUM-B', telephone='212699999999',
                                      message_id='wamid.U'))
        self.assertEqual(connu.status_code, inconnu.status_code)
        self.assertEqual(connu.content, inconnu.content)

    def test_message_signe_bonne_societe(self):
        resp = self._post(_payload('NUM-B'))
        self.assertEqual(resp.status_code, 200, resp.content)
        ticket = Ticket.objects.get()
        self.assertEqual(ticket.company_id, self.b.pk)
        self.assertEqual(ticket.client_id, self.client_b.pk)
        self.assertEqual(ticket.canal_ouverture,
                         Ticket.CanalOuverture.WHATSAPP)
        self.assertFalse(Ticket.objects.filter(company=self.a).exists())
