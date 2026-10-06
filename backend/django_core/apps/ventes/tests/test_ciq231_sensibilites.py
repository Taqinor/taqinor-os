"""CIQ231 — sensibilités industrielles calculées sur les SEULES valeurs
saisies par Reda (``TariffSettings.sensibilites_ci``), base à 0 %
d'indexation, aucun scénario par défaut.

SimpleTestCase : aucune base.
"""
import copy
import json
import os

from django.test import SimpleTestCase

from apps.ventes import economie_ci as eco
from apps.ventes import tarif_ci
from apps.ventes.quote_engine import pricing

_ICI = os.path.dirname(__file__)

TARIF_MT = tarif_ci.tarif_applicable({
    'contrat': 'mt_general', 'base_tarifs': 'ht', 'provenance': 'facture',
    'date_facture': '2026-08-31',
    'mt': {'tarif_pointe': 1.6, 'tarif_pleines': 1.1, 'tarif_creuses': 0.8}})
TARIF_MT_DECLARE = {
    'contrat': 'mt_general', 'base_tarifs': 'ht', 'provenance': 'facture',
    'date_facture': '2026-08-31',
    'mt': {'tarif_pointe': 1.6, 'tarif_pleines': 1.1, 'tarif_creuses': 0.8}}
INVESTISSEMENT = {'ht': 300000.0, 'ttc': 360000.0}


def _apercu_contrat():
    with open(os.path.join(_ICI, os.pardir, 'contract_samples',
                           'etude_ci_preview.json'), encoding='utf-8') as fh:
        apercu = copy.deepcopy(json.load(fh)['exemple'])
    apercu['entrees_resolues']['tension'] = {'valeur': 'mt',
                                             'provenance': None}
    return apercu


def _apercu_main():
    """Un seul jour type (juin, 30 jours) : 10 h GMT produit 40 pour une
    charge de 100 ; 12 h GMT produit 100 pour une charge de 50 (surplus 50).
    Les deux heures sont en heures PLEINES (été, 7-18 h GMT)."""
    auto = [0.0] * 24
    surplus = [0.0] * 24
    charge = [0.0] * 24
    auto[10], charge[10] = 40.0, 100.0
    auto[12], surplus[12], charge[12] = 50.0, 50.0, 50.0
    return {
        'entrees_resolues': {'tension': {'valeur': 'mt'},
                             'tva_recuperable': {'valeur': 'oui'}},
        'profil_charge': {'jours_types': [
            {'mois': 6, 'type_jour': 'ouvre', 'nb_jours': 30,
             'charge_kwh': charge}]},
        'bilan': {'production_kwh': (40.0 + 100.0) * 30,
                  'horaire': [{'mois': 6, 'type_jour': 'ouvre',
                               'nb_jours': 30, 'autoconso_kwh': auto,
                               'surplus_kwh': surplus}]},
        'alertes': [],
    }


def _bloc(apercu, scenarios, mode='industriel'):
    return eco.assembler_economie_ci(
        apercu, tarif_declare=TARIF_MT_DECLARE, investissement=INVESTISSEMENT,
        mode_installation=mode, reglages={'sensibilites_ci': scenarios})


def _retour_manuel(investissement, economie1, *, idx=0.0, deg=None):
    """Retour simple recalculé À LA MAIN : première année où le cumul
    (−investissement + Σ économies indexées et dégradées) devient ≥ 0."""
    deg = pricing.PANEL_DEGRADATION if deg is None else deg
    cumul = -investissement
    for annee in range(1, 26):
        cumul += economie1 * (1 + idx) ** (annee - 1) \
            * (1 - deg) ** (annee - 1)
        if cumul >= 0:
            return annee
    return None


class SensibilitesTest(SimpleTestCase):
    def test_reglage_vide_liste_vide_et_motif(self):
        bloc = _bloc(_apercu_contrat(), [])
        self.assertEqual(bloc['sensibilites'], [])
        omis = {o['cle']: o['motif'] for o in bloc['omissions']}
        self.assertEqual(omis['sensibilites'], eco.MOTIF_SANS_SENSIBILITE)

    def test_tarif_plus_10_retour_recalcule(self):
        bloc = _bloc(_apercu_main(), [
            {'cle': 'tarif_kwh', 'variation_pct': 10,
             'source': 'hausse ONEE annoncée (test)'}])
        # Base à la main : 90 kWh/j × 30 j × 1,1 MAD (pleines) = 2 970 MAD.
        self.assertAlmostEqual(bloc['economie_annee1']['total_mad'], 2970.0)
        sc = bloc['sensibilites'][0]
        self.assertAlmostEqual(sc['economie_annee1_mad'], 2970.0 * 1.1,
                               places=1)
        self.assertEqual(sc['retour_ans'],
                         _retour_manuel(300000.0, 2970.0 * 1.1))
        self.assertEqual(sc['source'], 'hausse ONEE annoncée (test)')

    def test_indexation_plus_2_publiee_sans_refus(self):
        bloc = _bloc(_apercu_contrat(), [
            {'cle': 'indexation_tarif', 'variation_pct': 2,
             'source': 'historique ONEE publié (test)'}])
        sc = bloc['sensibilites'][0]
        self.assertEqual(sc['cle'], 'indexation_tarif')
        self.assertNotIn('motif', sc)
        self.assertIsNotNone(sc['tri_pct'])
        # La base reste à 0 % d'indexation (QX39).
        hyp = {h['cle']: h['valeur'] for h in bloc['flux_ht']['hypotheses']}
        self.assertEqual(hyp['indexation_pct'], 0.0)
        self.assertGreater(sc['tri_pct'], bloc['indicateurs']['tri_pct'])

    def test_quatre_scenarios_quatre_publies_en_plus_de_la_base(self):
        scenarios = [
            {'cle': 'indexation_tarif', 'variation_pct': 2, 'source': 's1'},
            {'cle': 'degradation', 'variation_pct': 1, 'source': 's2'},
            {'cle': 'tarif_kwh', 'variation_pct': -10, 'source': 's3'},
            {'cle': 'production', 'variation_pct': -10, 'source': 's4'}]
        bloc = _bloc(_apercu_contrat(), scenarios)
        self.assertEqual([s['cle'] for s in bloc['sensibilites']],
                         [s['cle'] for s in scenarios])
        self.assertIsNotNone(bloc['indicateurs']['retour_ans'])

    def test_production_moins_10_recalcul_horaire(self):
        bloc = _bloc(_apercu_main(), [
            {'cle': 'production', 'variation_pct': -10,
             'source': 'P90 saisi (test)'}])
        sc = bloc['sensibilites'][0]
        # À la main : 10 h → min(36, 100) = 36 ; 12 h → min(90, 50) = 50 ;
        # (36 + 50) × 30 j × 1,1 = 2 838 MAD, soit −4,4 % (< 10 %).
        self.assertAlmostEqual(sc['economie_annee1_mad'], 2838.0, places=2)
        baisse = 1 - sc['economie_annee1_mad'] / 2970.0
        self.assertLess(baisse, 0.10)
        self.assertGreater(baisse, 0.0)

    def test_commercial_sensibilites_vides(self):
        bloc = _bloc(_apercu_contrat(), [
            {'cle': 'tarif_kwh', 'variation_pct': 10, 'source': 's'}],
            mode='commercial')
        self.assertEqual(bloc['sensibilites'], [])
        self.assertNotIn('sensibilites',
                         [o['cle'] for o in bloc['omissions']])
