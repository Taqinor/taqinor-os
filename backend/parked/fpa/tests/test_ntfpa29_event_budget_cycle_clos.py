"""NTFPA29 — événement domaine budget_cycle_clos : le signal se déclenche une
fois par clôture, testé par un abonné factice."""
from datetime import date

from django.test import TestCase

from authentication.models import Company
from core import events
from apps.fpa.models import CycleBudgetaire
from apps.fpa.services import clore_cycle


class TestBudgetCycleClos(TestCase):
    def setUp(self):
        self.company, _ = Company.objects.get_or_create(
            slug='ntfpa29-co', defaults={'nom': 'NTFPA29 Co'})
        self.cycle = CycleBudgetaire.objects.create(
            company=self.company, nom='Budget 2027',
            date_debut=date(2027, 1, 1), date_fin=date(2027, 12, 31),
            statut=CycleBudgetaire.Statut.OUVERT_SAISIE)

    def test_signal_declenche_une_fois_a_la_cloture(self):
        recu = []

        def _abonne(sender, **kwargs):
            recu.append(kwargs)

        events.budget_cycle_clos.connect(_abonne, weak=False)
        try:
            clore_cycle(self.cycle)
        finally:
            events.budget_cycle_clos.disconnect(_abonne)

        self.assertEqual(len(recu), 1)
        self.assertEqual(recu[0]['cycle_id'], self.cycle.pk)
        self.assertEqual(recu[0]['company'], self.company)
        self.assertIn('totaux', recu[0])
        self.cycle.refresh_from_db()
        self.assertEqual(self.cycle.statut, CycleBudgetaire.Statut.CLOS)
