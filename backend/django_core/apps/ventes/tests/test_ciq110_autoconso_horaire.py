"""CIQ110 — autoconsommation C&I heure par heure et régime d'injection.

Charge : archétypes SOURCÉS CIQ107 (bureau = BDEW G1, hôtel = NREL ComStock
small hotel) mis en jours types par ``courbe_declaree`` (CIQ108). Production :
la chaîne PVGIS vendorisée par ville (CIQ109, aucun appel réseau). Module pur :
aucune base.
"""
import ast
import json
import unittest
from pathlib import Path

from apps.parametres.pvgis_profils import (
    SAISONS,
    productible_mensuel,
    profil_production_journalier,
    vers_heure_locale,
)
from apps.ventes.moteur_ci.autoconso import bilan_horaire
from apps.ventes.moteur_ci.charge import courbe_declaree
from apps.ventes.moteur_ci.production import bloc_production_ci
from apps.ventes.quote_engine.constants_82_21 import PLAFOND_INJECTION_PCT
from apps.ventes.quote_engine.pricing import PRODUCTION_DERATE

RACINE = Path(__file__).resolve().parent.parent
CHEMIN = RACINE / 'moteur_ci' / 'autoconso.py'
CONTRAT = RACINE / 'contract_samples' / 'etude_ci_preview.json'


def _production(ville='Casablanca'):
    formes = {}
    for saison in SAISONS:
        resolu = profil_production_journalier(saison=saison, ville=ville)
        if resolu:
            formes[saison] = vers_heure_locale(resolu[0])
    mensuel, source = productible_mensuel(ville=ville)
    bloc, _h, _a = bloc_production_ci(
        productible_mensuel=mensuel, formes_saison=formes, derate=PRODUCTION_DERATE,
        coordonnees_figees={'lat': None, 'lon': None, 'date_appel': '2026-10-05'},
        source=source)
    return bloc['jours_types'], sum(bloc['kwh_kwc_mensuel'])


def _charge(categorie, kwh_mois):
    jours, _prov, _al = courbe_declaree({}, [kwh_mois] * 12, annee_reference=2025,
                                        archetype=categorie)
    return jours


class AutoconsoHoraireTests(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.prod, cls.kwh_par_kwc = _production()

    def _kwc_r1(self, kwh_mois):
        """Taille dont la production annuelle = la consommation annuelle (r = 1)."""
        return kwh_mois * 12 / self.kwh_par_kwc

    def test_production_au_dela_de_la_charge_diurne_marginal_nul(self):
        charge = _charge('bureau', 500)
        # Charge de 500 kWh/mois : à 1 MWc, la production dépasse la charge à
        # CHAQUE heure produisante ; un pas de 5 kWc n'ajoute que du surplus.
        b1, _ = bilan_horaire(charge, self.prod, 1000, tension='bt')
        b2, _ = bilan_horaire(charge, self.prod, 1005, tension='bt')
        self.assertEqual(b2['autoconso_kwh'] - b1['autoconso_kwh'], 0)
        self.assertGreater(b2['surplus_kwh'], b1['surplus_kwh'])

    def test_hotel_et_bureau_couvertures_differentes_jamais_55_80(self):
        kwh = 10000
        kwc = self._kwc_r1(kwh)
        hotel, _ = bilan_horaire(_charge('hotel', kwh), self.prod, kwc, tension='bt')
        bureau, _ = bilan_horaire(_charge('bureau', kwh), self.prod, kwc, tension='bt')
        self.assertNotEqual(hotel['taux_couverture'], bureau['taux_couverture'])
        for b in (hotel, bureau):
            self.assertNotIn(b['taux_couverture'], (0.55, 0.8))
            self.assertAlmostEqual(
                b['taux_couverture'], b['autoconso_kwh'] / (kwh * 12), delta=0.002)

    def test_bt_aucune_valorisation_meme_avec_revente(self):
        charge = _charge('bureau', 2000)
        b, alertes = bilan_horaire(charge, self.prod, 60, tension='bt', revente_choisie=True)
        self.assertGreater(b['surplus_kwh'], 0)
        self.assertEqual(b['injecte_valorise_kwh'], 0)
        self.assertEqual(b['non_valorise_kwh'], b['surplus_kwh'])
        self.assertIn('revente_non_ouverte', [a['code'] for a in alertes])

    def test_mt_avec_revente_injecte_plafonne(self):
        charge = _charge('bureau', 2000)
        b, alertes = bilan_horaire(charge, self.prod, 100, tension='mt', revente_choisie=True)
        plafond = b['production_kwh'] * PLAFOND_INJECTION_PCT / 100
        self.assertGreater(b['surplus_kwh'], plafond)
        self.assertLessEqual(b['injecte_valorise_kwh'], plafond + 1)
        self.assertGreater(b['injecte_valorise_kwh'], 0)
        self.assertEqual(b['injecte_valorise_kwh'] + b['non_valorise_kwh'], b['surplus_kwh'])
        self.assertIn('plafond_injection_atteint', [a['code'] for a in alertes])

    def test_mt_sans_revente_egal_bt(self):
        charge = _charge('bureau', 2000)
        mt, _ = bilan_horaire(charge, self.prod, 60, tension='mt')
        bt, _ = bilan_horaire(charge, self.prod, 60, tension='bt')
        self.assertEqual(mt, bt)
        self.assertEqual(mt['injecte_valorise_kwh'], 0)

    def test_bureau_g1_r1_couverture_horaire_sous_formule_annuelle(self):
        # W5-03 : BDEW G1 × PVGIS, bureau dimensionné à 100 % de sa
        # consommation — autoconsommation horaire ≈ 58 %, pas les 82 % de la
        # formule annuelle « production × part diurne » plafonnée à la conso.
        kwh = 10000
        b, _ = bilan_horaire(_charge('bureau', kwh), self.prod, self._kwc_r1(kwh), tension='bt')
        formule_annuelle = 0.82
        self.assertLess(b['taux_couverture'], formule_annuelle)
        self.assertLess(b['taux_couverture'], 1.0)

    def test_forme_du_contrat(self):
        contrat = json.loads(CONTRAT.read_text(encoding='utf-8'))['exemple']['bilan']
        b, _ = bilan_horaire(_charge('bureau', 3000), self.prod, 20, tension='bt')
        self.assertEqual(set(b), set(contrat))
        self.assertEqual(set(b['par_mois'][0]), set(contrat['par_mois'][0]))
        self.assertEqual(set(b['horaire'][0]), set(contrat['horaire'][0]))
        self.assertEqual(len(b['horaire'][0]['autoconso_kwh']), 24)
        self.assertEqual(len(b['par_mois']), 12)
        # Σ des jours types = consommation déclarée
        self.assertAlmostEqual(sum(m['consommation_kwh'] for m in b['par_mois']), 36000, delta=12)


class GardeAstTests(unittest.TestCase):
    def test_module_pur_sans_taux_fixe(self):
        arbre = ast.parse(CHEMIN.read_text(encoding='utf-8'))
        for noeud in ast.walk(arbre):
            if isinstance(noeud, ast.ImportFrom):
                self.assertIn(noeud.module, (
                    'apps.ventes.solar_design', 'apps.ventes.quote_engine.constants_82_21'))
            elif isinstance(noeud, ast.Import):
                self.fail(f'import inattendu : {noeud.names[0].name}')
            elif (isinstance(noeud, ast.Constant) and isinstance(noeud.value, float)
                  and 0 < noeud.value < 1):
                self.fail(f'constante flottante (taux fixe ?) : {noeud.value}')


if __name__ == '__main__':
    unittest.main()
