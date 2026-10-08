"""AMOT15 (C-AMOT-013) — les figures d'étude entrent dans LA chaîne de calcul.

* la production imprimée est celle du moteur devis (D-ACAL-6) : une production
  posée par le calepinage (``production_source='calepinage'``) n'est plus
  recopiée ni dans ``roi`` ni dans l'étude rendue ;
* une ``economies_annuelles`` SAISIE alimente ``compute_cashflow_payback``
  option par option (prix de l'option, dégradation, provision) : ``roi_s`` /
  ``roi_a`` = premier croisement de ``cashflow_sans/avec``, ``net_gain_*`` =
  ``cashflow_*[-1]`` — plus de payback linéaire.

Rejoue VA b24 / VB / VC s6 (ROI 4,5 ans imprimé sous une courbe qui croise en
année 8). Test-du-test : remettre ``roi["roi_s"] = round(_ref_total / eco, 1)``
⇒ ``test_payback_egal_croisement_par_option`` échoue.
"""
from django.test import SimpleTestCase, TestCase

from apps.ventes.quote_engine.builder import build_quote_data
from apps.ventes.quote_engine.pricing import (
    calculate_savings_roi, compute_cashflow_payback)
from apps.ventes.tests._quote_engine_common import (
    DEUX_OPTIONS, make_client, make_company, make_devis, make_user)


def _croisement(cumuls):
    """Année (interpolée) du premier cumul ≥ 0, comme le moteur."""
    for i, c in enumerate(cumuls):
        if c >= 0:
            prev = cumuls[i - 1] if i else None
            return i + 1 if prev is None else i + (0 - prev) / (c - prev)
    return None


class EconomieImposeePureTests(SimpleTestCase):
    def test_payback_par_cashflow_sur_le_prix_de_chaque_option(self):
        roi = calculate_savings_roi(
            6.0, 60000.0, 95000.0, economie_imposee=10000,
            inverter_cost_sans=8000.0, inverter_cost_avec=15000.0,
            stockage_present=True)
        self.assertTrue(roi.get('economie_saisie'))
        self.assertEqual(roi['eco_s_ann'], 10000)
        self.assertEqual(roi['eco_a_ann'], 10000)
        cf_s = compute_cashflow_payback(
            60000.0, 10000, inverter_replace_cost=8000.0)
        self.assertEqual(roi['roi_s'], cf_s['payback_years'])
        self.assertEqual(roi['cashflow_sans'], cf_s['cumulative'])
        self.assertEqual(roi['net_gain_sans'], roi['cashflow_sans'][-1])
        self.assertEqual(roi['net_gain_avec'], roi['cashflow_avec'][-1])
        self.assertGreater(roi['roi_a'], roi['roi_s'])
        self.assertNotEqual(roi['roi_s'], round(60000.0 / 10000, 1))
        self.assertAlmostEqual(roi['roi_s'], _croisement(roi['cashflow_sans']),
                               delta=0.1)
        self.assertAlmostEqual(roi['roi_a'], _croisement(roi['cashflow_avec']),
                               delta=0.1)
        self.assertEqual(sum(roi['eco_s_monthly']), 10000)

    def test_sans_economie_imposee_sortie_inchangee(self):
        a = calculate_savings_roi(6.0, 60000.0, 95000.0)
        b = calculate_savings_roi(6.0, 60000.0, 95000.0, economie_imposee=None)
        self.assertEqual(a, b)
        self.assertNotIn('economie_saisie', a)


class EtudeUneChaineTests(TestCase):
    def setUp(self):
        self.company = make_company()
        self.user = make_user(self.company)
        self.client_ = make_client(self.company)

    def _devis(self, ref, etude):
        params = dict(DEUX_OPTIONS)
        params.update(etude)
        return make_devis(self.company, self.user, self.client_, [
            ('Panneau mono 550W', '10', '1100'),
            ('Onduleur réseau Huawei 5kW', '1', '8000'),
            ('Onduleur hybride Deye 5kW', '1', '12000'),
            ('Batterie Dyness 5kWh', '1', '15000'),
        ], reference=ref, etude_params=params)

    def test_production_calepinage_non_collee(self):
        devis = self._devis('DEV-AMOT15-0001', {
            'production_annuelle': 10890, 'economies_annuelles': 16500,
            'production_source': 'calepinage'})
        data = build_quote_data(devis, {'pdf_mode': 'full'})
        self.assertNotEqual(data['prod_kwh'], 10890)
        self.assertNotEqual(data['eco_s_ann'], 16500)

    def test_payback_egal_croisement_par_option(self):
        devis = self._devis('DEV-AMOT15-0002', {
            'production_annuelle': 9000, 'economies_annuelles': 9000})
        data = build_quote_data(devis, {'pdf_mode': 'full'})
        self.assertEqual(data['eco_s_ann'], 9000)
        self.assertAlmostEqual(data['roi_s'],
                               _croisement(data['cashflow_sans']), delta=0.1)
        self.assertAlmostEqual(data['roi_a'],
                               _croisement(data['cashflow_avec']), delta=0.1)
        self.assertEqual(data['savings_method']['source'], 'saisie')

    def test_payback_sans_sur_prix_sans(self):
        devis = self._devis('DEV-AMOT15-0003', {
            'production_annuelle': 9000, 'economies_annuelles': 9000})
        data = build_quote_data(devis, {'pdf_mode': 'full'})
        self.assertLess(data['roi_s'], data['roi_a'])

    def test_hypothese_kwh_kwc_du_moteur(self):
        devis = self._devis('DEV-AMOT15-0004', {
            'production_annuelle': 10890, 'production_source': 'calepinage'})
        data = build_quote_data(devis, {'pdf_mode': 'full'})
        kwc = data['puissance_kwc']
        attendu = f"{int(round(data['prod_kwh'] / kwc)):,}".replace(',', ' ')
        items = (data.get('hypotheses') or {}).get('items') or []
        self.assertTrue(any(attendu in h for h in items), items)

    def test_regles_d_origine_payback_lineaire(self):
        devis = self._devis('DEV-AMOT15-0005', {
            'production_annuelle': 9000, 'economies_annuelles': 9000})
        devis.regles_calcul = 1
        data = build_quote_data(devis, {'pdf_mode': 'full'})
        self.assertEqual(data['roi_s'], data['roi_a'])
