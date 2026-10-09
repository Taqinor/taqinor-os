"""AMOT15 (C-AMOT-013) — les figures d'étude entrent dans LA chaîne de calcul.

* la production imprimée est celle du moteur devis (D-ACAL-6) : une
  production posée par le calepinage n'est plus recopiée ;
* une ``economies_annuelles`` saisie alimente ``compute_cashflow_payback``
  option par option (prix de l'option, dégradation, provision onduleur) :
  ``roi_*`` = croisement de la courbe ``cashflow_*``, ``net_gain_*`` = fin de
  courbe — plus de payback linéaire ;
* la ligne d'hypothèse « ≈ N kWh par kWc » dérive de la production du moteur.

Moteur réel (``build_quote_data`` → ``pricing.calculate_savings_roi``), aucun
mock. Test-du-test : remettre ``roi["roi_s"] = round(_ref_total / eco, 1)``
⇒ ``test_payback_egal_croisement_par_option`` échoue.
"""
from django.test import TestCase

from apps.ventes.quote_engine.builder import build_quote_data, clean_pdf_options
from apps.ventes.tests._quote_engine_common import (
    make_client, make_company, make_devis, make_user,
)

_DEUX = [
    ('Panneau mono 710W', '14', '1200'),
    ('Onduleur réseau Huawei 10kW', '1', '16000'),
    ('Onduleur hybride Deye 10kW', '1', '24000'),
    ('Batterie Dyness 10kWh', '1', '30000'),
]
_ECO = 16500


def _croisement(cumul):
    """Premier passage du cumul (liste annuelle) à zéro, interpolé."""
    prec = None
    for i, val in enumerate(cumul):
        if val >= 0:
            depart = prec if prec is not None else val
            span = val - depart
            frac = (0 - depart) / span if span else 0.0
            return i + frac if prec is not None else 0.0
        prec = val
    return None


class EtudeUneChaineTests(TestCase):
    def setUp(self):
        self.company = make_company(slug='amot15-co', nom='AMOT15')
        self.user = make_user(self.company)
        self.client_obj = make_client(self.company)
        self.n = 0

    def _devis(self, lignes, etude):
        self.n += 1
        return make_devis(self.company, self.user, self.client_obj, lignes,
                          reference=f'DEV-AMOT15-{self.n}',
                          etude_params=etude)

    @staticmethod
    def _data(devis):
        return build_quote_data(devis, clean_pdf_options({'pdf_mode': 'full'}))

    def test_production_calepinage_non_collee(self):
        lignes = _DEUX[:2]
        temoin = self._data(self._devis(lignes, {'scenario': 'Sans batterie'}))
        data = self._data(self._devis(lignes, {
            'scenario': 'Sans batterie', 'production_annuelle': 10890,
            'production_source': 'calepinage'}))
        self.assertNotEqual(data['prod_kwh'], 10890)
        self.assertEqual(data['prod_kwh'], temoin['prod_kwh'])
        self.assertEqual(data['etude']['production_annuelle'],
                         temoin['prod_kwh'])

    def test_payback_egal_croisement_par_option(self):
        data = self._data(self._devis(_DEUX, {
            'scenario': 'Les deux (Sans + Avec)',
            'production_annuelle': 12000, 'economies_annuelles': _ECO}))
        self.assertEqual(data['nb_options'], 2)
        for opt in ('sans', 'avec'):
            cumul = data[f'cashflow_{opt}']
            self.assertTrue(cumul, opt)
            roi = data['roi_s' if opt == 'sans' else 'roi_a']
            self.assertAlmostEqual(roi, _croisement(cumul), delta=0.1)
            self.assertEqual(data[f'net_gain_{opt}'], cumul[-1])
        self.assertEqual(data['eco_s_ann'], _ECO)
        self.assertEqual(data['eco_a_ann'], _ECO)
        self.assertAlmostEqual(sum(data['eco_s_monthly']), _ECO, delta=6)

    def test_payback_sans_sur_prix_sans(self):
        data = self._data(self._devis(_DEUX, {
            'scenario': 'Les deux (Sans + Avec)',
            'production_annuelle': 12000, 'economies_annuelles': _ECO}))
        # Année 1 de la courbe « sans » = −prix de l'option SANS + économie.
        self.assertAlmostEqual(data['cashflow_sans'][0],
                               -float(data['total_sans']) + _ECO, delta=1)
        self.assertAlmostEqual(data['cashflow_avec'][0],
                               -float(data['total_avec']) + _ECO, delta=1)
        self.assertLess(data['roi_s'], data['roi_a'])

    def test_hypothese_kwh_kwc_du_moteur(self):
        data = self._data(self._devis(_DEUX[:2], {
            'scenario': 'Sans batterie', 'production_annuelle': 10890,
            'production_source': 'calepinage'}))
        par_kwc = f"{int(round(data['prod_kwh'] / data['puissance_kwc'])):,}"
        par_kwc = par_kwc.replace(',', ' ')
        items = data['hypotheses']['items']
        self.assertTrue(any(f'≈ {par_kwc} kWh par kWc' in it for it in items),
                        items)
        faux = f"{int(round(10890 / data['puissance_kwc'])):,}".replace(',', ' ')
        self.assertFalse(any(f'≈ {faux} kWh par kWc' in it for it in items))
