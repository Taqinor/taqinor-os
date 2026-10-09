"""ASAV27 — le second chemin portail → ticket (`portail/tickets/`) est retiré :
410 « Formulaire retiré », aucun ticket, aucun numéro consommé, même réponse
pour un jeton invalide.

Run :
    python manage.py test apps.sav.tests_asav27_portail_retire -v2
"""
from django.core.cache import cache
from django.test import TestCase

from authentication.models import Company
from apps.crm.models import Client
from apps.portail.models import ComptePortailClient
from apps.sav.models import SavSlaSettings, Ticket

URL = '/api/django/sav/portail/tickets/'


class PortailRetireTests(TestCase):

    def setUp(self):
        cache.clear()
        self.company, _ = Company.objects.get_or_create(
            slug='asav27-co', defaults={'nom': 'ASAV27 Co'})
        client = Client.objects.create(
            company=self.company, nom='Client', prenom='ASAV27')
        ComptePortailClient.objects.create(
            company=self.company, client=client, token_acces='jeton-asav27')
        sla = SavSlaSettings.get(self.company)
        sla.sla_breach_enabled = True
        sla.save()

    def _post(self, token):
        return self.client.post(
            URL, {'token': token, 'sujet': 'Panne', 'priorite': 'urgente',
                  'chantier': 999999}, content_type='application/json')

    def test_410_sans_ticket(self):
        avant = Ticket.objects.count()
        r = self._post('jeton-asav27')
        self.assertEqual(r.status_code, 410, r.content)
        self.assertIn('Mes demandes', r.json()['detail'])
        self.assertEqual(Ticket.objects.count(), avant)

    def test_jeton_invalide_meme_reponse(self):
        valide = self._post('jeton-asav27')
        invalide = self._post('jeton-inconnu')
        self.assertEqual(invalide.status_code, 410)
        self.assertEqual(valide.json(), invalide.json())
        self.assertEqual(Ticket.objects.count(), 0)
