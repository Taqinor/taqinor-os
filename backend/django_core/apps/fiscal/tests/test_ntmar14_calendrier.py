"""NTMAR14 — Calendrier fiscal marocain complet par obligation.

Critère : une company voit son calendrier annuel d'échéances fiscales daté
sans saisie manuelle."""
from django.test import TestCase

from apps.fiscal.models import EcheanceFiscale, ObligationFiscale
from apps.fiscal.services import calendrier, seed_obligations_standard

from ._fixtures import make_company


class SeedObligationsTests(TestCase):
    def test_seed_is_idempotent_and_additive(self):
        company = make_company('fiscal-seed', 'Fiscal Seed')
        created1 = seed_obligations_standard(company)
        self.assertEqual(len(created1), len(ObligationFiscale.objects.filter(
            company=company)))
        # Personnalisation : on change une règle existante.
        obligation = ObligationFiscale.objects.get(
            company=company, type_obligation=ObligationFiscale.Type.TVA)
        obligation.regle_echeance = '15 du mois suivant'
        obligation.save(update_fields=['regle_echeance'])
        # Un second seed n'écrase JAMAIS la personnalisation.
        created2 = seed_obligations_standard(company)
        self.assertEqual(created2, [])
        obligation.refresh_from_db()
        self.assertEqual(obligation.regle_echeance, '15 du mois suivant')


class CalendrierTests(TestCase):
    def setUp(self):
        self.company = make_company('fiscal-cal', 'Fiscal Cal')
        seed_obligations_standard(self.company)

    def test_calendrier_materializes_dated_deadlines(self):
        echeances = calendrier(self.company, 2026)
        self.assertGreater(len(echeances), 0)
        for echeance in echeances:
            self.assertIsNotNone(echeance.date_limite)
            self.assertEqual(echeance.company, self.company)

    def test_calendrier_monthly_obligation_has_twelve_occurrences(self):
        calendrier(self.company, 2026)
        tva = ObligationFiscale.objects.get(
            company=self.company, type_obligation=ObligationFiscale.Type.TVA)
        self.assertEqual(
            EcheanceFiscale.objects.filter(
                company=self.company, obligation=tva,
                periode_debut__year=2026).count(),
            12)

    def test_calendrier_is_idempotent(self):
        first = calendrier(self.company, 2026)
        second = calendrier(self.company, 2026)
        self.assertEqual(len(first), len(second))
        self.assertEqual({e.id for e in first}, {e.id for e in second})

    def test_date_limite_parses_du_mois_suivant_rule(self):
        calendrier(self.company, 2026)
        tva = ObligationFiscale.objects.get(
            company=self.company, type_obligation=ObligationFiscale.Type.TVA)
        janvier = EcheanceFiscale.objects.get(
            company=self.company, obligation=tva,
            periode_debut__year=2026, periode_debut__month=1)
        # « 20 du mois suivant » -> 20 février 2026.
        self.assertEqual(janvier.date_limite.month, 2)
        self.assertEqual(janvier.date_limite.day, 20)
