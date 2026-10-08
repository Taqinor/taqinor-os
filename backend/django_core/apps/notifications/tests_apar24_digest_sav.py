"""APAR24 — le récapitulatif quotidien ne compte que les tickets SAV ouverts
NON annulés, lus via ``sav.selectors`` (C-APAR-030) : annuler un ticket
« nouveau » fait baisser « SAV ouverts » d'une unité.
"""
import inspect

from django.test import TestCase

from authentication.models import Company

from . import digests


class DigestSavTests(TestCase):
    def setUp(self):
        from apps.crm.models import Client
        self.company = Company.objects.create(nom='APAR24')
        self.client_sav = Client.objects.create(
            company=self.company, nom='Client APAR24')

    def _ticket(self, ref, **kw):
        from apps.sav.models import Ticket
        return Ticket.objects.create(
            company=self.company, client=self.client_sav, reference=ref,
            statut=Ticket.Statut.NOUVEAU, **kw)

    def test_annulation_fait_baisser_le_compte(self):
        ticket = self._ticket('SAV-APAR24-1')
        self.assertEqual(digests._count_sav_ouverts(self.company), 1)
        type(ticket).objects.filter(pk=ticket.pk).update(annule=True)
        self.assertEqual(digests._count_sav_ouverts(self.company), 0)

    def test_frontiere_selectors(self):
        source = inspect.getsource(digests._count_sav_ouverts)
        self.assertNotIn('apps.sav.models', source)
        self.assertIn('apps.sav.selectors', source)
