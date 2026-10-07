"""ASTK55 — le bus déclare ``reception_fournisseur_annulee`` (C-ASTK-011).

Jumeau d'annulation de ``reception_fournisseur_confirmee`` : émis par stock
(ASTK56) quand une réception confirmée est annulée, consommé par installations
(ASTK57 : extourne GR/IR, séries « retourné », re-plafonnage YPROC10). Ce test
fige la DÉCLARATION : signal réel dans ``core.events``, entrée au catalogue
NTPLT12 et attente explicite côté couverture tant qu'aucun abonné n'existe.
"""
from django.dispatch import Signal
from django.test import SimpleTestCase

from core import event_catalog, event_coverage, events


class SignalAnnulationReceptionTests(SimpleTestCase):
    NOM = 'reception_fournisseur_annulee'

    def test_signal_declare_dans_core_events(self):
        signal = getattr(events, self.NOM, None)
        self.assertIsInstance(signal, Signal)
        self.assertIn(self.NOM, event_coverage.declared_signals())

    def test_signal_distinct_de_la_confirmation(self):
        self.assertIsNot(
            events.reception_fournisseur_annulee,
            events.reception_fournisseur_confirmee,
        )

    def test_decrit_au_catalogue_avec_les_lignes_annulees(self):
        entree = event_catalog.CATALOG.get(self.NOM)
        self.assertIsNotNone(entree, 'absent de core.event_catalog.CATALOG')
        self.assertIn('reception', entree['payload'])
        self.assertIn('lignes', entree['payload'])
        self.assertTrue(entree['description'])

    def test_catalogue_coherent_avec_le_bus(self):
        # Test-du-test : retirer l'entrée du catalogue => ce test échoue.
        self.assertNotIn(self.NOM, event_coverage.uncatalogued_events())
        self.assertNotIn(self.NOM, event_coverage.catalogued_but_undeclared())

    def test_couverture_attend_le_signal(self):
        # Soit un abonné réel (ASTK57), soit une réservation explicite :
        # jamais un orphelin silencieux.
        signal = events.reception_fournisseur_annulee
        self.assertTrue(
            event_coverage.signal_has_receiver(signal)
            or self.NOM in event_coverage.ALLOWED_UNCONSUMED,
        )
