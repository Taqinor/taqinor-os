"""AMOT58 (C-AMOT-024) — le rendement aller-retour de la batterie n'est déduit
qu'UNE fois : en modèle HORAIRE (énergie déjà nette de stockage), le cashflow
ne le re-déduit plus (``battery_share = 0``) — flux de l'année 1 de la courbe
= économie annuelle imprimée, et ``roi_a`` = croisement de cette courbe.

Moteur horaire réel (``calculer_etude_horaire``) puis
``calculate_savings_roi`` réel. Test-du-test : remettre
``battery_share=_batt_part`` en horaire ⇒ ``test_horaire_flux_an1_egal_
economie`` échoue (flux an 1 = 0,9676 × économie).
"""
from django.test import SimpleTestCase

from apps.ventes import etude_horaire as EH
from apps.ventes.courbes_journalieres import OCCUPATION_PRESENCE
from apps.ventes.horaire import conso as HC
from apps.ventes.quote_engine.pricing import (
    calculate_savings_roi, compute_cashflow_payback,
)


class RendementBatterieTests(SimpleTestCase):
    def _bloc(self, kwc):
        conso, _s, _d = HC.profil_depuis_factures(facture_hiver_mad=1500)
        return EH.calculer_etude_horaire(
            kwc=kwc, conso_kwh_mensuelles=conso, ville='Casablanca',
            occupation=OCCUPATION_PRESENCE, batterie_kwh_utile=10.0,
            tranches=None, charges_fixes_mad=None)

    def test_horaire_flux_an1_egal_economie(self):
        kwc = 6.0
        bloc = self._bloc(kwc)
        # Casablanca résout depuis la table PVGIS vendorisée : hors réseau.
        self.assertIsNotNone(bloc)
        total_avec = 90000.0
        roi = calculate_savings_roi(kwc, 60000.0, total_avec,
                                    etude_horaire=bloc, battery_kwh=10.0)
        self.assertEqual(roi['savings_model'], 'horaire')
        for opt, total in (('sans', 60000.0), ('avec', total_avec)):
            eco = roi['eco_s_ann' if opt == 'sans' else 'eco_a_ann']
            cumul = roi[f'cashflow_{opt}']
            self.assertAlmostEqual(cumul[0] + total, eco, delta=1, msg=opt)
        # ``roi_a`` = croisement de LA courbe sans seconde déduction.
        une_fois = compute_cashflow_payback(total_avec, roi['eco_a_ann'])
        self.assertAlmostEqual(roi['roi_a'], une_fois['payback_years'],
                               delta=0.05)


class RendementImprimeHorsHoraireTests(SimpleTestCase):
    """RHOR6 (C-RHOR-006) — modèles « factures » / « estimation », niveau de
    règles 3 : l'économie « avec batterie » IMPRIMÉE est nette de la perte
    aller-retour de sa part stockée ; le flux de l'année 1 de la courbe = ce
    chiffre imprimé (déduction unique). Niveau 2 : imprimé brut, perte au
    seul cashflow (rendu d'origine)."""

    def _roi(self, regles_2710):
        return calculate_savings_roi(
            6.0, 60000.0, 90000.0, battery_kwh=10.0,
            regles_2710=regles_2710)

    def test_niveau_3_imprime_net_et_courbe_alignee(self):
        brut = self._roi(False)
        net = self._roi(True)
        self.assertNotEqual(net['savings_model'], 'horaire')
        self.assertLess(net['eco_a_ann'], brut['eco_a_ann'])
        self.assertEqual(net['eco_s_ann'], brut['eco_s_ann'])
        self.assertAlmostEqual(
            net['cashflow_avec'][0] + 90000.0, net['eco_a_ann'], delta=1)
        self.assertEqual(sum(net['eco_a_monthly']), net['eco_a_ann'])

    def test_niveau_2_garde_l_imprime_brut(self):
        brut = self._roi(False)
        self.assertGreater(
            brut['eco_a_ann'], brut['cashflow_avec'][0] + 90000.0 + 1)
