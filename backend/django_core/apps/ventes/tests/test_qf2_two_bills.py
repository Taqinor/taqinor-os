"""QF2 — Two-bills real-savings model (facture sans vs avec solaire, par tranche).

Covers the pure ``two_bills_savings`` math, its integration in
``calculate_savings_roi`` (economies become facture_sans − facture_avec when
real consumption + a tariff table exist), the builder exposure
(``facture_sans_solaire`` / ``facture_avec_solaire_*`` / ``savings_model``)
and the honest degrade path (no data → old estimate, flagged).

Run:
    docker compose exec django_core python manage.py test \
        apps.ventes.tests.test_qf2_two_bills -v 2
"""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import SimpleTestCase, TestCase

from apps.ventes.quote_engine.pricing import (
    ONEE_TRANCHES,
    _weighted_kwh_price,
    calculate_savings_roi,
    two_bills_savings,
)

User = get_user_model()


def _onee_annual_bill(kwh_month):
    return _weighted_kwh_price(kwh_month, ONEE_TRANCHES) * kwh_month * 12


class TestTwoBillsSavingsPure(SimpleTestCase):
    """two_bills_savings — pure per-tranche math."""

    def test_math_correct_per_tranche_partial_coverage(self):
        """conso 3600 kWh/an, prod 6200, ratio 0.30 → residual valued per tranche."""
        out = two_bills_savings(6200, 3600, 0.30, utility="onee")
        self.assertIsNotNone(out)
        facture_sans = _onee_annual_bill(300)          # 300 kWh/mois
        autoconso = 6200 * 0.30                        # 1860 < 3600 → cap not hit
        residual_m = (3600 - autoconso) / 12           # 145 kWh/mois
        facture_avec = _onee_annual_bill(residual_m)
        self.assertEqual(out["facture_sans"], round(facture_sans))
        self.assertEqual(out["facture_avec"], round(facture_avec))
        # chain is exact on the ROUNDED bills (internally consistent display)
        self.assertEqual(out["economie"],
                         round(facture_sans) - round(facture_avec))
        self.assertEqual(out["autoconso_kwh"], round(autoconso))
        self.assertFalse(out["approximatif"])

    def test_self_consumption_capped_at_consumption(self):
        """Production above consumption: savings cap at the FULL bill — the
        surplus injected to the grid is never valued (loi 82-21)."""
        out = two_bills_savings(6200, 3600, 0.60, utility="onee")
        # 6200 × 0.60 = 3720 > 3600 → autoconso capped at conso, residual 0.
        self.assertEqual(out["autoconso_kwh"], 3600)
        self.assertEqual(out["facture_avec"], 0)
        self.assertEqual(out["economie"], out["facture_sans"])
        # NEVER above the full bill (no injection bonus).
        self.assertLessEqual(out["economie"], round(_onee_annual_bill(300)) + 1)

    def test_lydec_flagged_approximatif(self):
        out = two_bills_savings(6200, 3600, 0.30, utility="lydec")
        self.assertTrue(out["approximatif"])

    def test_returns_none_without_table_or_data(self):
        self.assertIsNone(two_bills_savings(6200, 3600, 0.30))         # no table
        self.assertIsNone(two_bills_savings(6200, 0, 0.30, utility="onee"))
        self.assertIsNone(two_bills_savings(0, 3600, 0.30, utility="onee"))
        self.assertIsNone(two_bills_savings(6200, 3600, 0, utility="onee"))
        self.assertIsNone(two_bills_savings("x", "y", 0.3, utility="onee"))


class TestCalculateSavingsRoiTwoBills(SimpleTestCase):
    """calculate_savings_roi switches to the two-bills model when real data exists."""

    def test_two_bills_model_used_with_utility_and_conso(self):
        roi = calculate_savings_roi(
            5.0, 50000, 80000, utility="onee", conso_annuelle_kwh=6000)
        self.assertEqual(roi["savings_model"], "factures")
        self.assertIsNotNone(roi["facture_sans"])
        self.assertIsNotNone(roi["facture_avec_s"])
        self.assertIsNotNone(roi["facture_avec_a"])
        # economies = facture_sans − facture_avec per option
        self.assertEqual(roi["eco_s_ann"],
                         roi["facture_sans"] - roi["facture_avec_s"])
        self.assertEqual(roi["eco_a_ann"],
                         roi["facture_sans"] - roi["facture_avec_a"])
        # option 2 self-consumes more → lower residual bill, higher savings
        self.assertGreaterEqual(roi["eco_a_ann"], roi["eco_s_ann"])
        self.assertFalse(roi["savings_estimated"])

    def test_monthly_series_follow_two_bills_totals(self):
        roi = calculate_savings_roi(
            5.0, 50000, 80000, utility="onee", conso_annuelle_kwh=6000)
        self.assertAlmostEqual(sum(roi["eco_s_monthly"]), roi["eco_s_ann"],
                               delta=12)
        self.assertAlmostEqual(sum(roi["eco_a_monthly"]), roi["eco_a_ann"],
                               delta=12)

    def test_no_consumption_degrades_to_flagged_estimate(self):
        """Without real consumption, the OLD estimate applies and is labelled."""
        roi = calculate_savings_roi(5.0, 50000, 80000, utility="onee")
        self.assertEqual(roi["savings_model"], "estimation")
        self.assertIsNone(roi["facture_sans"])
        # old formula: production × autoconso × prix
        self.assertEqual(roi["eco_s_ann"],
                         round(roi["prod_kwh"] * roi["autoconso_sans"]
                               * roi["tarif_kwh"]))

    def test_seller_flat_tarif_override_keeps_old_model(self):
        roi = calculate_savings_roi(
            5.0, 50000, 80000, tarif_kwh_override=1.75,
            utility="onee", conso_annuelle_kwh=6000)
        self.assertEqual(roi["savings_model"], "estimation")
        self.assertEqual(roi["eco_s_ann"],
                         round(roi["prod_kwh"] * roi["autoconso_sans"] * 1.75))

    def test_no_data_at_all_still_flagged_estimated(self):
        roi = calculate_savings_roi(5.0, 50000, 80000)
        self.assertEqual(roi["savings_model"], "estimation")
        self.assertTrue(roi["savings_estimated"])
        self.assertGreater(roi["eco_s_ann"], 0)   # honest estimate, never blank


class TestBuilderTwoBillsExposure(TestCase):
    """build_quote_data exposes both bills + model, and persists them into the
    rendered etude params. No-data path stays honest."""

    def setUp(self):
        from authentication.models import Company
        from apps.crm.models import Client
        self.company, _ = Company.objects.get_or_create(
            slug='test-qf2-co', defaults={'nom': 'Test QF2 Co'})
        self.user = User.objects.create_user(
            username='qf2user', password='x', role_legacy='responsable',
            company=self.company)
        self.client_obj = Client.objects.create(
            company=self.company, nom='Farsi', prenom='Nora',
            email='n@example.com', telephone='+212600000001')

    def _devis(self, etude_params=None, reference='DEV-QF2-0001'):
        from apps.stock.models import Produit
        from apps.ventes.models import Devis, LigneDevis
        devis = Devis.objects.create(
            company=self.company, reference=reference, client=self.client_obj,
            statut='brouillon', taux_tva=Decimal('20.00'),
            remise_globale=Decimal('0'), created_by=self.user,
            etude_params=etude_params,
        )
        for desig, qty, pu in [
            ('Panneau mono 550W', '10', '1400'),
            ('Onduleur réseau 8kW', '1', '14000'),
        ]:
            produit = Produit.objects.create(
                company=self.company, nom=desig,
                sku=f'{reference[-6:]}-{desig[:10]}',
                prix_vente=Decimal(pu), prix_achat=Decimal('1'),
                quantite_stock=10)
            LigneDevis.objects.create(
                devis=devis, produit=produit, designation=desig,
                quantite=Decimal(qty), prix_unitaire=Decimal(pu),
                remise=Decimal('0'))
        return devis

    def test_bills_exposed_and_persisted_into_etude(self):
        from apps.ventes.quote_engine import build_quote_data
        devis = self._devis(
            etude_params={'distributeur': 'onee', 'conso_annuelle': 6000})
        data = build_quote_data(devis)
        self.assertEqual(data['savings_model'], 'factures')
        self.assertIsNotNone(data['facture_sans_solaire'])
        self.assertIsNotNone(data['facture_avec_solaire_s'])
        self.assertIsNotNone(data['facture_avec_solaire_a'])
        # economies shown = difference of the two bills (option 1)
        self.assertEqual(
            data['eco_s_ann'],
            data['facture_sans_solaire'] - data['facture_avec_solaire_s'])
        # persisted into the RENDERED etude params (same figures everywhere)
        self.assertEqual(data['etude']['facture_annuelle_sans_solaire'],
                         data['facture_sans_solaire'])
        self.assertEqual(data['etude']['facture_annuelle_avec_solaire_opt1'],
                         data['facture_avec_solaire_s'])
        self.assertEqual(data['etude']['economie_reelle_opt1'],
                         data['eco_s_ann'])
        self.assertFalse(data['factures_approximatif'])

    def test_lydec_bills_flagged_approximatif(self):
        from apps.ventes.quote_engine import build_quote_data
        devis = self._devis(
            etude_params={'distributeur': 'lydec', 'conso_annuelle': 6000},
            reference='DEV-QF2-0002')
        data = build_quote_data(devis)
        self.assertEqual(data['savings_model'], 'factures')
        self.assertTrue(data['factures_approximatif'])

    def test_no_data_path_is_honest(self):
        """No bill/consumption → old estimate, flagged, no fabricated bills."""
        from apps.ventes.quote_engine import build_quote_data
        devis = self._devis(reference='DEV-QF2-0003')
        data = build_quote_data(devis)
        self.assertEqual(data['savings_model'], 'estimation')
        self.assertIsNone(data['facture_sans_solaire'])
        self.assertIsNone(data['facture_avec_solaire_s'])
        self.assertTrue(data['savings_estimated'])
        self.assertNotIn('facture_annuelle_sans_solaire', data['etude'])

    def test_stored_etude_economies_take_precedence(self):
        """An industrial study with stored economies stays canonical (model 'etude')."""
        from apps.ventes.quote_engine import build_quote_data
        devis = self._devis(
            etude_params={
                'distributeur': 'onee', 'conso_annuelle': 120000,
                'production_annuelle': 12000, 'economies_annuelles': 21000,
            },
            reference='DEV-QF2-0004')
        data = build_quote_data(devis)
        self.assertEqual(data['savings_model'], 'etude')
        self.assertEqual(data['eco_s_ann'], 21000)
