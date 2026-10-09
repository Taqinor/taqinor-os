"""ASAV22 — une correction de ticket par PATCH laisse sa trace au chatter.

Run :
    python manage.py test apps.sav.tests_asav22_patch_chatter -v2
"""
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.crm.models import Client
from apps.installations.models import Installation
from apps.sav.models import Equipement, Ticket, TicketActivity
from apps.stock.models import Produit

User = get_user_model()
BASE = '/api/django/sav/tickets'


class PatchChatterTests(TestCase):

    def setUp(self):
        self.company, _ = Company.objects.get_or_create(
            slug='asav22-co', defaults={'nom': 'ASAV22 Co'})
        self.admin = User.objects.create_user(
            username='asav22_admin', password='x', role_legacy='admin',
            company=self.company)
        self.tech = User.objects.create_user(
            username='asav22_tech', password='x', role_legacy='admin',
            company=self.company)
        self.api = APIClient()
        self.api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.admin)}')
        self.client_obj = Client.objects.create(
            company=self.company, nom='Client', prenom='ASAV22')
        inst = Installation.objects.create(
            company=self.company, reference='CHT-ASAV22',
            client=self.client_obj)
        produit = Produit.objects.create(
            company=self.company, nom='Onduleur ASAV22', sku='OND-ASAV22',
            prix_achat=0, prix_vente=500)
        self.equipement = Equipement.objects.create(
            company=self.company, produit=produit, installation=inst,
            numero_serie='ASAV22-SN')
        r = self.api.post(f'{BASE}/', {
            'client': self.client_obj.pk, 'installation': inst.pk,
            'type': 'correctif', 'description': 'initial'}, format='json')
        self.assertEqual(r.status_code, 201, r.content)
        self.ticket = Ticket.objects.get(pk=r.data['id'])

    def _modifs(self):
        return TicketActivity.objects.filter(
            ticket=self.ticket, kind=TicketActivity.Kind.MODIFICATION)

    def test_patch_trace_champs_suivis(self):
        r = self.api.patch(f'{BASE}/{self.ticket.pk}/', {
            'priorite': 'urgente', 'description': 'corrigé',
            'technicien_responsable': self.tech.pk,
            'equipement': self.equipement.pk}, format='json')
        self.assertEqual(r.status_code, 200, r.content)
        champs = set(self._modifs().values_list('field', flat=True))
        self.assertTrue(
            {'priorite', 'description', 'technicien_responsable',
             'equipement'} <= champs, champs)
        self.assertEqual(
            set(self._modifs().values_list('user_id', flat=True)),
            {self.admin.pk})
        self.assertFalse(self._modifs().filter(visible_client=True).exists())

    def test_patch_sans_changement_muet(self):
        avant = self._modifs().count()
        r = self.api.patch(f'{BASE}/{self.ticket.pk}/', {
            'description': 'initial'}, format='json')
        self.assertEqual(r.status_code, 200, r.content)
        self.assertEqual(self._modifs().count(), avant)
