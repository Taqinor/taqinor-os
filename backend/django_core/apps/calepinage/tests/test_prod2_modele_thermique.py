"""CAL140 — la perte thermique : calculée depuis la fiche, ou annoncée.

Les DEUX chemins sont vérifiés, comme l'exige la tâche :

* fiche COMPLÈTE (NOCT, ou Uc/Uv, + coefficient γ) ⇒ perte calculée heure par
  heure et étiquetée « fiche produit » ;
* fiche INCOMPLÈTE ⇒ aucun calcul, le poste forfaitaire est CONSERVÉ et
  ANNONCÉ comme hypothèse (jamais présenté comme un calcul).

Les températures employées viennent de l'année météo type RÉELLE enregistrée
pour Casablanca (``tests/fixtures_pvgis/tmy_casablanca.json``) : aucune
température n'est fabriquée à la main.
"""
from __future__ import annotations

import json
import pathlib
import unittest

from apps.calepinage.services.thermique import (
    MODELE_FAIMAN, MODELE_NOCT, TEMPERATURE_STC_C, perte_thermique,
    poste_thermique, temperature_cellule,
)

FIXTURES = pathlib.Path(__file__).resolve().parent / 'fixtures_pvgis'

#: Fiche COMPLÈTE au sens de CAL111 (les noms sont ceux de
#: ``apps.stock.selectors.specs_for_produit``). Les valeurs sont celles d'un
#: module cristallin courant — elles servent la MÉCANIQUE, pas un chiffrage.
FICHE_FAIMAN = {
    'uc_w_m2k': 29.0, 'uv_w_m3sk': 0.0, 'temp_coeff_pmax_pct_c': -0.35,
}
FICHE_NOCT = {'noct_c': 45.0, 'temp_coeff_pmax_pct_c': -0.35}


def points_tmy():
    charge = json.loads(
        (FIXTURES / 'tmy_casablanca.json').read_text(encoding='utf-8'))
    lignes = charge['outputs']['tmy_hourly']
    return [{'t2m_c': ligne.get('T2m'), 'gh_w_m2': ligne.get('G(h)'),
             'ws10m': ligne.get('WS10m')} for ligne in lignes]


class TemperatureCelluleTest(unittest.TestCase):

    def test_faiman_ajoute_l_echauffement_du_a_l_irradiance(self):
        t = temperature_cellule(t_air_c=20.0, irradiance_w_m2=800.0,
                                modele=MODELE_FAIMAN, uc_w_m2k=29.0,
                                uv_w_m3sk=0.0)
        self.assertAlmostEqual(t, 20.0 + 800.0 / 29.0, places=6)

    def test_le_vent_refroidit_la_cellule(self):
        sans = temperature_cellule(t_air_c=20.0, irradiance_w_m2=800.0,
                                   modele=MODELE_FAIMAN, uc_w_m2k=25.0,
                                   uv_w_m3sk=1.2, vent_m_s=0.0)
        avec = temperature_cellule(t_air_c=20.0, irradiance_w_m2=800.0,
                                   modele=MODELE_FAIMAN, uc_w_m2k=25.0,
                                   uv_w_m3sk=1.2, vent_m_s=5.0)
        self.assertLess(avec, sans)

    def test_noct_respecte_sa_propre_definition(self):
        """Aux conditions NOCT (800 W/m², 20 °C d'air), T_cellule = NOCT."""
        t = temperature_cellule(t_air_c=20.0, irradiance_w_m2=800.0,
                                modele=MODELE_NOCT, noct_c=45.0)
        self.assertAlmostEqual(t, 45.0, places=6)

    def test_sans_parametre_aucune_temperature_n_est_inventee(self):
        self.assertIsNone(temperature_cellule(
            t_air_c=20.0, irradiance_w_m2=800.0, modele=MODELE_FAIMAN))
        self.assertIsNone(temperature_cellule(
            t_air_c=None, irradiance_w_m2=800.0, modele=MODELE_NOCT,
            noct_c=45.0))


class FicheCompleteTest(unittest.TestCase):

    def setUp(self):
        self.points = points_tmy()

    def test_la_perte_est_calculee_et_etiquetee_fiche(self):
        resultat = perte_thermique(FICHE_FAIMAN, self.points)
        self.assertTrue(resultat['calculable'])
        self.assertEqual(resultat['source'], 'fiche')
        self.assertEqual(resultat['modele'], MODELE_FAIMAN)
        # La fixture ne garde que le 15 de chaque mois (voir son
        # ``_provenance``) : une centaine d'heures ensoleillées, pas 8760.
        self.assertGreater(resultat['heures_retenues'], 100)
        self.assertIsNotNone(resultat['pct'])
        # La perte est physiquement plausible sur une TMY marocaine, et
        # surtout elle est CALCULÉE : on vérifie l'ordre de grandeur, pas une
        # valeur attendue d'avance.
        self.assertGreater(resultat['pct'], 0.0)
        self.assertLess(resultat['pct'], 25.0)

    def test_faiman_prime_sur_noct_quand_les_deux_sont_la(self):
        fiche = dict(FICHE_FAIMAN, noct_c=45.0)
        self.assertEqual(perte_thermique(fiche, self.points)['modele'],
                         MODELE_FAIMAN)

    def test_l_absence_de_uv_est_une_hypothese_ANNONCEE(self):
        fiche = {'uc_w_m2k': 29.0, 'temp_coeff_pmax_pct_c': -0.35}
        resultat = perte_thermique(fiche, self.points)
        self.assertTrue(resultat['calculable'])
        self.assertIn('vent', resultat['motif'])
        self.assertIn('Uv', resultat['motif'])

    def test_la_moyenne_est_ponderee_par_l_irradiance(self):
        """Une heure de nuit ajoutée ne change RIEN à la perte publiée."""
        avec_nuit = list(self.points) + [
            {'t2m_c': 5.0, 'gh_w_m2': 0.0, 'ws10m': 0.0}] * 500
        self.assertEqual(perte_thermique(FICHE_FAIMAN, self.points)['pct'],
                         perte_thermique(FICHE_FAIMAN, avec_nuit)['pct'])

    def test_un_module_plus_chaud_perd_davantage(self):
        chaud = perte_thermique(dict(FICHE_NOCT, noct_c=48.0), self.points)
        froid = perte_thermique(dict(FICHE_NOCT, noct_c=42.0), self.points)
        self.assertGreater(chaud['pct'], froid['pct'])

    def test_a_25_degres_de_cellule_la_perte_est_nulle(self):
        points = [{'t2m_c': TEMPERATURE_STC_C, 'gi_w_m2': 800.0,
                   'ws10m': 0.0}]
        resultat = perte_thermique({'noct_c': 20.0,
                                    'temp_coeff_pmax_pct_c': -0.35}, points)
        self.assertAlmostEqual(resultat['pct'], 0.0, places=6)


class FicheIncompleteTest(unittest.TestCase):

    def setUp(self):
        self.points = points_tmy()

    def test_sans_noct_ni_uc_aucun_calcul_et_le_motif_le_dit(self):
        resultat = perte_thermique({'temp_coeff_pmax_pct_c': -0.35},
                                   self.points)
        self.assertFalse(resultat['calculable'])
        self.assertIsNone(resultat['pct'])
        self.assertIsNone(resultat['source'])
        self.assertIn('NOCT', resultat['motif'])
        self.assertIn('hypothèse', resultat['motif'])

    def test_sans_coefficient_de_puissance_aucun_calcul(self):
        resultat = perte_thermique({'noct_c': 45.0}, self.points)
        self.assertFalse(resultat['calculable'])
        self.assertIn('temp_coeff_pmax_pct_c', resultat['motif'])

    def test_fiche_absente_aucun_calcul(self):
        self.assertFalse(perte_thermique({}, self.points)['calculable'])
        self.assertFalse(perte_thermique(None, self.points)['calculable'])

    def test_serie_vide_aucun_calcul(self):
        resultat = perte_thermique(FICHE_FAIMAN, [])
        self.assertFalse(resultat['calculable'])
        self.assertIn('aucune heure ensoleillée', resultat['motif'])


class PosteThermiqueTest(unittest.TestCase):

    def setUp(self):
        self.points = points_tmy()

    def test_fiche_complete_donne_un_poste_source_fiche(self):
        poste, diagnostic = poste_thermique(FICHE_FAIMAN, self.points,
                                            forfait_pct=8.0)
        self.assertEqual(poste['source'], 'fiche')
        self.assertEqual(poste['pct'], diagnostic['pct'])
        self.assertNotEqual(poste['pct'], 8.0)

    def test_fiche_muette_conserve_le_forfait_en_l_annoncant(self):
        poste, diagnostic = poste_thermique({}, self.points, forfait_pct=8.0)
        self.assertEqual(poste['pct'], 8.0)
        self.assertEqual(poste['source'], 'hypothese')
        self.assertIn('forfait', poste['libelle'].lower())
        self.assertIn('hypothèse', poste['reference'])
        self.assertFalse(diagnostic['calculable'])

    def test_sans_forfait_aucun_poste_n_est_fabrique(self):
        poste, _ = poste_thermique({}, self.points)
        self.assertIsNone(poste)


if __name__ == '__main__':  # pragma: no cover
    unittest.main()
