"""YEVNT7 — garde de couverture du bus d'événements & des EventType.

Miroir de l'esprit de ``scripts/check_stages.py`` : introspecte les signaux de
``core.events`` (et leurs récepteurs enregistrés), l'énum
``notifications.EventType`` (et ses producteurs ``notify()``), et échoue sur
tout orphelin non explicitement réservé — de sorte qu'un futur signal ou
EventType laissé non consommé casse le build au lieu de s'accumuler
silencieusement (comme les orphelins historiques YEVNT1/3/4).
"""
from django.test import SimpleTestCase

from core import event_coverage


class EventBusCoverageTests(SimpleTestCase):
    def test_every_signal_has_a_receiver_or_is_reserved(self):
        """Chaque signal de core.events a ≥1 récepteur, ou est réservé."""
        orphans = event_coverage.orphan_signals()
        self.assertEqual(
            orphans, set(),
            "Signaux core.events sans récepteur et non listés dans "
            "ALLOWED_UNCONSUMED (orphelins) : "
            f"{sorted(orphans)}. Câblez un récepteur (apps.py ready()) ou "
            "déclarez-les réservés dans core.event_coverage.ALLOWED_UNCONSUMED.",
        )

    def test_every_eventtype_has_a_producer_or_is_reserved(self):
        """Chaque EventType a ≥1 producteur notify(), ou est réservé."""
        unproduced = event_coverage.unproduced_eventtypes()
        self.assertEqual(
            unproduced, set(),
            "EventType déclarés sans producteur notify() et non listés dans "
            "ALLOWED_UNPRODUCED : "
            f"{sorted(unproduced)}. Ajoutez un site notify(EventType.X) ou "
            "déclarez-les réservés dans core.event_coverage.ALLOWED_UNPRODUCED.",
        )

    def test_every_receiver_points_to_an_existing_signal(self):
        """Aucun @receiver ne pointe un signal absent de core.events."""
        dangling = event_coverage.dangling_receiver_signals()
        self.assertEqual(
            dangling, set(),
            "Récepteurs (@receiver) pointant un signal inexistant dans "
            f"core.events : {sorted(dangling)}.",
        )

    def test_reserved_lists_stay_minimal(self):
        """Une réservation qui n'existe plus doit être retirée de sa liste."""
        signal_names = set(event_coverage.declared_signals())
        stale_signals = event_coverage.ALLOWED_UNCONSUMED - signal_names
        self.assertEqual(
            stale_signals, set(),
            f"ALLOWED_UNCONSUMED liste des signaux inconnus : {sorted(stale_signals)}",
        )
        members, _ = event_coverage.eventtype_coverage()
        stale_types = event_coverage.ALLOWED_UNPRODUCED - members
        self.assertEqual(
            stale_types, set(),
            f"ALLOWED_UNPRODUCED liste des EventType inconnus : {sorted(stale_types)}",
        )

    def test_coverage_recense_signals_and_eventtypes(self):
        """Le recensement remonte bien des signaux et des EventType réels."""
        self.assertIn("devis_accepted", event_coverage.declared_signals())
        members, produced = event_coverage.eventtype_coverage()
        self.assertIn("DEVIS_ACCEPTED", members)
        # DEVIS_ACCEPTED est produit (notifications.signals) — preuve que le
        # scan de producteurs fonctionne, pas juste une liste vide.
        self.assertIn("DEVIS_ACCEPTED", produced)
