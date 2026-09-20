"""CAL131 — les sections se calculent sur les LONGUEURS DU PLAN.

Le plan à deux pans est le cas de référence : la liaison DC dimensionnante est
la plus longue des deux, mesurée sur les CENTRES DE MODULES POSÉS, à quoi
s'ajoutent la descente et la liaison coffret → onduleur, qui elles sont
SAISIES (aucun plan ne les porte).

Les deux refus tenus par ce test :

* longueur inconnue ⇒ AUCUNE section publiée (jamais le forfait de 15 m du
  devis) ;
* norme non sélectionnée ⇒ calcul OMIS (règle D5, CAL130).

Run :
    python manage.py test apps.calepinage.tests.test_elec_cables_longueurs_plan -v2
"""
from django.test import SimpleTestCase

from apps.calepinage.services.cables import (
    ORIGINE_MIXTE, ORIGINE_SAISIE, cables_du_calepinage, longueur_ac,
    longueur_dc,
)
from apps.calepinage.services.chaines import concevoir_par_pan
from apps.calepinage.services.electrique import temperatures_site
from apps.calepinage.services.norme import norme_applicable

MODULE = {
    'vmp_v': 41.5, 'voc_v': 49.6, 'isc_a': 18.4, 'imp_a': 17.1,
    'pmax_wc': 710.0, 'temp_coeff_voc_pct_c': -0.27,
    'temp_coeff_pmax_pct_c': -0.35,
}
ONDULEUR = {
    'n_mppt': 2, 'mppt_v_min': 150.0, 'mppt_v_max': 800.0,
    'v_max_abs': 1000.0, 'i_max_mppt_a': 26.0, 'isc_max_mppt_a': 45.0,
    'ac_kw': 10.0, 'phases': 3,
}
NORME_FR = norme_applicable({'imagerie': {'pays': 'fr'},
                             'norme_electrique': {}})
NORME_MA = norme_applicable({'imagerie': {'pays': 'ma'},
                             'norme_electrique': {}})


def _panneaux(nombre, x0, ecart=1.2):
    return [{'cx': x0 + rang * ecart, 'cy': 0.0} for rang in range(nombre)]


LAYOUT = {'version': 2, 'zones': [
    {'label': 'PAN-A', 'geometry': {
        'count': 6, 'azimuthDeg': 180.0, 'tiltDeg': 15.0,
        'panels': _panneaux(6, 0.0)}},
    {'label': 'PAN-B', 'geometry': {
        'count': 6, 'azimuthDeg': 90.0, 'tiltDeg': 15.0,
        'panels': _panneaux(6, 10.0)}},
]}

CHEMINEMENT = {
    'pans': {'PAN-A': {'point_collecte': {'cx': 0.0, 'cy': 0.0}},
             'PAN-B': {'point_collecte': {'cx': 10.0, 'cy': 0.0}}},
    'descente_m': 6.0,
    'coffret_vers_onduleur_m': 4.0,
    'onduleur_vers_tgbt_m': 12.0,
}


def _conception():
    return concevoir_par_pan(
        LAYOUT, module_specs=MODULE, onduleur_specs=ONDULEUR,
        temperatures=temperatures_site(
            saisie={'temperature_min_c': -5.0, 'temperature_max_c': 70.0}),
        onduleur_designation='Onduleur d essai')


class LongueursTest(SimpleTestCase):
    """La longueur vient du plan, et elle DIT d'où elle vient."""

    def test_la_course_dc_est_celle_du_pan_le_plus_long(self):
        longueur, manques = longueur_dc(LAYOUT, CHEMINEMENT)

        self.assertEqual(manques, ())
        # 6 modules espacés de 1,2 m → 6 m du point de collecte, + 6 m de
        # descente + 4 m vers l'onduleur.
        self.assertAlmostEqual(longueur.valeur_m, 6.0 + 6.0 + 4.0, places=2)
        self.assertEqual(longueur.origine, ORIGINE_MIXTE)
        self.assertEqual(len(longueur.composantes), 3)

    def test_un_pan_sans_point_de_collecte_empeche_la_mesure(self):
        cheminement = dict(CHEMINEMENT, pans={
            'PAN-A': CHEMINEMENT['pans']['PAN-A']})

        longueur, manques = longueur_dc(LAYOUT, cheminement)

        self.assertIsNone(longueur)
        self.assertIn('PAN-B', manques[0])

    def test_la_descente_non_saisie_empeche_la_mesure(self):
        cheminement = {cle: valeur for cle, valeur in CHEMINEMENT.items()
                       if cle != 'descente_m'}

        longueur, manques = longueur_dc(LAYOUT, cheminement)

        self.assertIsNone(longueur)
        self.assertIn('descente verticale', manques[0])

    def test_la_liaison_ac_est_saisie_et_le_dit(self):
        longueur, manques = longueur_ac(CHEMINEMENT)

        self.assertEqual(manques, ())
        self.assertEqual(longueur.valeur_m, 12.0)
        self.assertEqual(longueur.origine, ORIGINE_SAISIE)

    def test_sans_liaison_ac_saisie_aucun_forfait(self):
        longueur, manques = longueur_ac({})

        self.assertIsNone(longueur)
        self.assertIn('aucun forfait', manques[0])


class CablesPubliesTest(SimpleTestCase):
    """Chaque câble porte section, critère, chute, longueur et origine."""

    def test_les_deux_cables_sont_dimensionnes(self):
        resultat = cables_du_calepinage(
            _conception(), cheminement=CHEMINEMENT, norme=NORME_FR,
            layout=LAYOUT)
        reperes = {cable['repere']: cable for cable in resultat['cables']}

        self.assertEqual(sorted(reperes), ['W1', 'W2'])
        for cable in reperes.values():
            self.assertGreater(cable['section_mm2'], 0)
            self.assertTrue(cable['critere_dimensionnant'])
            self.assertIsNotNone(cable['chute_tension_pct'])
            self.assertTrue(cable['longueur_origine'])
            self.assertTrue(cable['regle_source'])
        self.assertAlmostEqual(reperes['W1']['longueur_m'], 16.0, places=2)
        self.assertAlmostEqual(reperes['W2']['longueur_m'], 12.0, places=2)

    def test_longueur_dc_inconnue_ne_publie_aucune_section_dc(self):
        cheminement = {'onduleur_vers_tgbt_m': 12.0}

        resultat = cables_du_calepinage(
            _conception(), cheminement=cheminement, norme=NORME_FR,
            layout=LAYOUT)
        reperes = [cable['repere'] for cable in resultat['cables']]

        self.assertNotIn('W1', reperes)
        self.assertIsNone(resultat['longueurs']['dc'])
        self.assertTrue(resultat['omissions'])

    def test_sans_norme_selectionnee_le_calcul_est_omis(self):
        resultat = cables_du_calepinage(
            _conception(), cheminement=CHEMINEMENT, norme=NORME_MA,
            layout=LAYOUT)

        self.assertEqual(resultat['cables'], [])
        self.assertIn('OMIS', resultat['omissions'][0])

    def test_sans_chaine_il_n_y_a_rien_a_dimensionner(self):
        vide = concevoir_par_pan(
            {'zones': []}, module_specs=MODULE, onduleur_specs=ONDULEUR,
            temperatures=temperatures_site(
                saisie={'temperature_min_c': -5.0,
                        'temperature_max_c': 70.0}))

        resultat = cables_du_calepinage(vide, cheminement=CHEMINEMENT,
                                        norme=NORME_FR, layout=LAYOUT)

        self.assertEqual(resultat['cables'], [])
        self.assertIn("pas de liaison", resultat['omissions'][0])
