"""ASAV30 — `/suivi/:token` sert l'état annulé / fusionné d'un ticket, le
compteur portail exclut les tickets annulés, et la satisfaction est refusée
sur un ticket annulé.

Run :
    python manage.py test apps.sav.tests_asav30_suivi_annule -v2
"""
from django.core.cache import cache
from django.test import TestCase
from rest_framework.test import APIClient

from authentication.models import Company
from apps.crm.models import Client
from apps.sav.models import Ticket
from apps.sav.selectors import tickets_ouverts_client

PUBLIC = '/api/django/public/sav/ticket/{}/'


class SuiviAnnuleTests(TestCase):

    def setUp(self):
        cache.clear()
        self.company, _ = Company.objects.get_or_create(
            slug='asav30-co', defaults={'nom': 'ASAV30 Co'})
        self.client_obj = Client.objects.create(
            company=self.company, nom='Client', prenom='ASAV30')
        self.api = APIClient()
        self.vivant = self._ticket('SAV-A30-1')
        self.annule = self._ticket('SAV-A30-2', annule=True,
                                   motif_annulation='Erreur de saisie')
        self.fusionne = self._ticket(
            'SAV-A30-3', annule=True,
            motif_annulation=f'Doublon de {self.vivant.reference}')

    def _ticket(self, ref, **kw):
        t = Ticket.objects.create(
            company=self.company, reference=ref, client=self.client_obj,
            type=Ticket.Type.CORRECTIF, **kw)
        t.ensure_share_token()
        return t

    def test_public_annule(self):
        r = self.api.get(PUBLIC.format(self.annule.share_token))
        self.assertEqual(r.status_code, 200, r.content)
        self.assertTrue(r.data['annule'])
        self.assertEqual(r.data['statut_display'], 'Annulé')
        self.assertIsNone(r.data['fusionne_dans_reference'])

    def test_public_fusionne(self):
        r = self.api.get(PUBLIC.format(self.fusionne.share_token))
        self.assertTrue(r.data['annule'])
        self.assertEqual(r.data['fusionne_dans_reference'],
                         self.vivant.reference)

    def test_public_vivant(self):
        r = self.api.get(PUBLIC.format(self.vivant.share_token))
        self.assertFalse(r.data['annule'])
        self.assertEqual(r.data['statut_display'], 'Nouveau')

    def test_compteur_portail(self):
        self.assertEqual(
            tickets_ouverts_client(self.company, self.client_obj.id), 1)

    def test_satisfaction_annule_409(self):
        Ticket.objects.filter(pk=self.annule.pk).update(
            statut=Ticket.Statut.RESOLU)
        r = self.api.post(
            PUBLIC.format(self.annule.share_token) + 'satisfaction/',
            {'note': 5}, format='json')
        self.assertEqual(r.status_code, 409, r.content)
