"""ADOC137 — « Mon équipe » sert `peut_gerer` (vrai pour l'admin portail seul).

Constat (C-ADOC-050) : l'enveloppe ne disait pas à l'écran si l'utilisateur
connecté pouvait inviter/révoquer. Contrat : ``mon_equipe.json`` (ADOC111).

Run :
    python manage.py test apps.portail.tests.test_adoc_mon_equipe_peut_gerer -v2
"""
import itertools
import json
import pathlib

from django.test import TestCase
from rest_framework.test import APIClient

from apps.crm.models import Client
from apps.portail.services import (
    accepter_invitation_portail,
    inviter_membre_portail,
    provisionner_compte_portail_client,
)
from authentication.models import Company

_seq = itertools.count(1)

CONTRAT = json.loads(
    (pathlib.Path(__file__).resolve().parents[1]
     / 'contract_samples' / 'mon_equipe.json')
    .read_text(encoding='utf-8'))

URL = '/api/django/portail/mon-equipe/'


class MonEquipePeutGererTests(TestCase):
    def setUp(self):
        n = next(_seq)
        self.co, _ = Company.objects.get_or_create(
            slug=f'adoc137-{n}', defaults={'nom': f'ADOC137 {n}'})
        client = Client.objects.create(
            company=self.co, nom='Client', prenom=f'ADOC137-{n}',
            email=f'adoc137-{n}@example.invalid')
        self.admin, _ = provisionner_compte_portail_client(self.co, client.id)
        self.admin.must_change_password = False
        self.admin.save(update_fields=['must_change_password'])
        invitation = inviter_membre_portail(
            self.co, client.id, f'membre-{n}@example.invalid', 'ecriture')
        self.membre = accepter_invitation_portail(
            invitation.token_invitation, 'motdepasse-membre-12345')
        inviter_membre_portail(
            self.co, client.id, f'attente-{n}@example.invalid', 'lecture')

    def _lire(self, user):
        api = APIClient()
        api.force_authenticate(user=user)
        res = api.get(URL)
        self.assertEqual(res.status_code, 200, res.content)
        return res.json()

    def test_peut_gerer_conforme_contrat(self):
        self.assertEqual(CONTRAT['forme_serveur'], 'complete')
        admin = self._lire(self.admin)
        membre = self._lire(self.membre)
        for corps in (admin, membre):
            # Clés de l'enveloppe ET d'une ligne == clés du contrat.
            self.assertEqual(set(corps), set(CONTRAT['exemple']))
            self.assertEqual(set(corps['results'][0]),
                             set(CONTRAT['exemple']['results'][0]))
        self.assertIs(admin['peut_gerer'], True)
        self.assertIs(membre['peut_gerer'], False)
        self.assertEqual(len(admin['results']), 2)
