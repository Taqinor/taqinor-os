"""CALX170 — la conversion continu → alternatif suit la courbe, ou rien.

Aucune base, aucun réseau : une fiche d'onduleur POSTICHE (les mêmes clés que
``specs_for_produit`` publie) et quatre heures de production continue.

Run :
    python manage.py test apps.calepinage.tests.test_calx170_onduleur
"""
from __future__ import annotations

import unittest

from apps.calepinage.services import etapes
from apps.calepinage.services.chaine_pertes import appliquer_chaine
from apps.calepinage.services.etapes import onduleur

#: Quatre heures à 1, 2, 3 et 4 kW continus : 10 kWh DC.
SERIE = {
    'pas_minutes': 60,
    'colonne_energie': 'p_dc_kw',
    'points': [
        {'mois': 6, 'heure': 9, 'p_dc_kw': 1.0},
        {'mois': 6, 'heure': 10, 'p_dc_kw': 2.0},
        {'mois': 6, 'heure': 11, 'p_dc_kw': 3.0},
        {'mois': 6, 'heure': 12, 'p_dc_kw': 4.0},
    ],
}

#: Une courbe η(P) d'essai : (% de PNom, η %), abscisse croissante.
COURBE = [
    {'charge_pct': 10, 'rendement_pct': 90.0},
    {'charge_pct': 20, 'rendement_pct': 95.0},
    {'charge_pct': 50, 'rendement_pct': 97.0},
    {'charge_pct': 100, 'rendement_pct': 98.0},
]

ELECTRIQUE = {
    'chainage': {'modules': 10, 'modules_par_chaine': 10,
                 'puissance_module_wc': 500.0},
    'onduleurs': [{'reference': 'Onduleur d’essai', 'nombre': 1,
                   'taille_kw': 5.0}],
}


def contexte(fiche=None, **extras):
    base = {
        'fiche_onduleur': dict(fiche if fiche is not None else {}),
        'fiche_module': {'vmp_v': 40.0},
        'electrique': {'chainage': dict(ELECTRIQUE['chainage']),
                       'onduleurs': [dict(ELECTRIQUE['onduleurs'][0])]},
        'reglages_simulation': {},
        'postes_saisis': [],
    }
    base.update(extras)
    return base


class CourbeTest(unittest.TestCase):

    def setUp(self):
        self.serie, self.etape = onduleur.appliquer(
            SERIE,
            contexte(fiche={'ac_kw': 5.0, 'rendement_par_charge': COURBE,
                            'rendement_euro_pct': 96.0}))
        self.entree = self.etape['entree']

    def test_la_courbe_prime_sur_le_rendement_europeen(self):
        self.assertEqual(self.entree['champ'],
                         'fiche_onduleur.rendement_par_charge')
        self.assertEqual(self.etape['source'], 'fiche')
        self.assertIn('PV*SOL', self.etape['reference'])

    def test_la_serie_declare_le_porteur_alternatif(self):
        self.assertEqual(self.serie['colonne_energie'], 'p_ac_kw')

    def test_p_ac_kw_est_ecrit_sur_chaque_point(self):
        for point in self.serie['points']:
            self.assertIn('p_ac_kw', point)
            self.assertIsNotNone(point['p_ac_kw'])

    def test_chaque_heure_porte_son_rendement_interpole(self):
        # 1 kW = 20 % de 5 kW → 95 % ; 2 kW = 40 % → 96,333 % ;
        # 3 kW = 60 % → 97,2 % ; 4 kW = 80 % → 97,6 %.
        attendus = [0.95, 2.0 * 0.963333333, 3.0 * 0.972, 4.0 * 0.976]
        obtenus = [point['p_ac_kw'] for point in self.serie['points']]
        for attendu, obtenu in zip(attendus, obtenus):
            self.assertAlmostEqual(obtenu, attendu, places=6)

    def test_l_energie_alternative_est_celle_de_la_courbe(self):
        self.assertAlmostEqual(etapes.energie_kwh(self.serie), 9.696666667,
                               places=6)

    def test_la_serie_continue_n_est_pas_modifiee(self):
        self.assertEqual(etapes.energie_kwh(SERIE), 10.0)

    def test_la_puissance_nominale_est_declaree(self):
        self.assertEqual(self.entree['puissance_nominale_kw'], 5.0)
        self.assertIn('ac_kw', self.entree['base_puissance_nominale'])

    def test_aucune_heure_hors_courbe_ici(self):
        self.assertEqual(self.entree['heures_hors_courbe'], 0)


class HorsCourbeTest(unittest.TestCase):
    """Au-delà des points publiés, la valeur la plus proche est TENUE."""

    def setUp(self):
        serie = dict(SERIE, points=[
            {'mois': 6, 'heure': 8, 'p_dc_kw': 0.1},
            {'mois': 6, 'heure': 13, 'p_dc_kw': 6.0},
        ])
        self.serie, self.etape = onduleur.appliquer(
            serie, contexte(fiche={'ac_kw': 5.0,
                                   'rendement_par_charge': COURBE}))

    def test_les_heures_hors_courbe_sont_comptees(self):
        self.assertEqual(self.etape['entree']['heures_hors_courbe'], 2)

    def test_la_valeur_tenue_est_celle_du_point_publie_le_plus_proche(self):
        # 0,1 kW = 2 % < 10 % → 90 % ; 6 kW = 120 % > 100 % → 98 %.
        valeurs = [point['p_ac_kw'] for point in self.serie['points']]
        self.assertAlmostEqual(valeurs[0], 0.1 * 0.90, places=9)
        self.assertAlmostEqual(valeurs[1], 6.0 * 0.98, places=9)


class CourbePlateEtRendementEuropeenTest(unittest.TestCase):
    """Propriété : une courbe plate à η constant = le rendement européen."""

    def test_meme_energie_exactement(self):
        plate = [{'charge_pct': 0, 'rendement_pct': 96.0},
                 {'charge_pct': 100, 'rendement_pct': 96.0}]
        par_courbe, _ = onduleur.appliquer(
            SERIE, contexte(fiche={'ac_kw': 5.0,
                                   'rendement_par_charge': plate}))
        a_plat, etape = onduleur.appliquer(
            SERIE, contexte(fiche={'ac_kw': 5.0, 'rendement_euro_pct': 96.0}))
        self.assertEqual(etapes.energie_kwh(par_courbe),
                         etapes.energie_kwh(a_plat))
        self.assertEqual(etapes.energie_kwh(a_plat), 9.6)
        self.assertIn('valeur UNIQUE', etape['entree']['motif'])


class PuissanceContinueEcriteTest(unittest.TestCase):
    """ACAL752 — ``p_dc_kw`` = la puissance ENTRANTE convertie en kW."""

    SERIE_W = {'pas_minutes': 60, 'colonne_energie': 'p_w', 'points': [
        {'mois': 6, 'heure': h, 'p_w': p}
        for h, p in ((9, 1000.0), (10, 2000.0), (11, 3000.0), (12, 4000.0),
                     (13, None))]}

    def _verifier(self, fiche):
        rendue, _ = onduleur.appliquer(self.SERIE_W, contexte(fiche=fiche))
        for point, attendu in zip(rendue['points'], (1.0, 2.0, 3.0, 4.0)):
            self.assertAlmostEqual(point['p_dc_kw'], attendu, places=12)
        self.assertIsNone(rendue['points'][4]['p_dc_kw'])
        self.assertAlmostEqual(
            sum(p['p_dc_kw'] or 0.0 for p in rendue['points']),
            etapes.energie_kwh(self.SERIE_W), places=9)
        self.assertEqual(rendue['colonne_energie'], 'p_ac_kw')
        for point in rendue['points'][:4]:
            self.assertLess(point['p_ac_kw'], point['p_dc_kw'])
        self.assertIsNone(rendue['points'][4]['p_ac_kw'])

    def test_a_plat_rendement_europeen_96(self):
        self._verifier({'ac_kw': 5.0, 'rendement_euro_pct': 96.0})

    def test_par_courbe(self):
        self._verifier({'ac_kw': 5.0, 'rendement_par_charge': COURBE})

    def test_etape_omise_serie_intacte(self):
        rendue, etape = onduleur.appliquer(self.SERIE_W, contexte(fiche={}))
        self.assertTrue(etape['motif_omission'])
        self.assertIs(rendue, self.SERIE_W)


class OmissionsNommeesTest(unittest.TestCase):

    def test_fiche_sans_rendement_omet_en_nommant_le_champ_et_le_produit(self):
        serie, etape = onduleur.appliquer(SERIE, contexte(fiche={}))
        self.assertIn(onduleur.CHAMP_FICHE_RENDEMENT,
                      etape['motif_omission'])
        self.assertIn('Onduleur d’essai', etape['motif_omission'])
        self.assertEqual(etapes.energie_kwh(serie), 10.0)
        self.assertNotIn('p_ac_kw', serie['points'][0])

    def test_plusieurs_courbes_par_tension_sans_tension_connue(self):
        deux = [
            {'charge_pct': 20, 'rendement_pct': 95.5, 'tension_v': 360},
            {'charge_pct': 100, 'rendement_pct': 97.6, 'tension_v': 360},
            {'charge_pct': 20, 'rendement_pct': 96.1, 'tension_v': 580},
            {'charge_pct': 100, 'rendement_pct': 98.1, 'tension_v': 580},
        ]
        _, etape = onduleur.appliquer(
            SERIE,
            contexte(fiche={'ac_kw': 5.0, 'rendement_par_charge': deux},
                     fiche_module={}))
        self.assertIn('PAR TENSION', etape['motif_omission'])

    def test_la_courbe_de_la_tension_la_plus_proche_est_retenue(self):
        deux = [
            {'charge_pct': 20, 'rendement_pct': 95.5, 'tension_v': 360},
            {'charge_pct': 100, 'rendement_pct': 97.6, 'tension_v': 360},
            {'charge_pct': 20, 'rendement_pct': 96.1, 'tension_v': 580},
            {'charge_pct': 100, 'rendement_pct': 98.1, 'tension_v': 580},
        ]
        # 10 modules × 40 V = 400 V → la courbe 360 V est la plus proche.
        serie, etape = onduleur.appliquer(
            SERIE,
            contexte(fiche={'ac_kw': 5.0, 'rendement_par_charge': deux}))
        self.assertEqual(etape['entree']['points_publies'], 2)
        self.assertAlmostEqual(serie['points'][0]['p_ac_kw'], 0.955,
                               places=6)

    def test_sans_nombre_d_onduleurs_la_courbe_n_a_pas_d_abscisse(self):
        _, etape = onduleur.appliquer(
            SERIE,
            contexte(fiche={'ac_kw': 5.0, 'rendement_par_charge': COURBE},
                     electrique={'chainage': dict(ELECTRIQUE['chainage'])}))
        self.assertIn('puissance nominale', etape['motif_omission'])

    def test_ac_kw_prime_sur_dc_max_kwc_pour_la_nominale(self):
        """17/11/2026 : ``dc_max_kwc`` = puissance PV maximale raccordable
        (le double de l'AC sur un hybride Deye), jamais la nominale : la
        courbe se pose sur ``ac_kw``, ``dc_max_kwc`` n'est qu'un repli."""
        _, etape = onduleur.appliquer(
            SERIE,
            contexte(fiche={'ac_kw': 5.0, 'dc_max_kwc': 10.0,
                            'rendement_par_charge': COURBE}))
        self.assertEqual(etape['entree']['puissance_nominale_kw'], 5.0)
        self.assertIn('ac_kw', etape['entree']['base_puissance_nominale'])
        _, repli = onduleur.appliquer(
            SERIE,
            contexte(fiche={'dc_max_kwc': 10.0,
                            'rendement_par_charge': COURBE}))
        self.assertEqual(repli['entree']['puissance_nominale_kw'], 10.0)
        self.assertIn('dc_max_kwc', repli['entree']['base_puissance_nominale'])

    def test_serie_sans_colonne_d_energie_est_omise(self):
        _, etape = onduleur.appliquer({'points': [{'t2m_c': 21.0}]},
                                      contexte(fiche={'ac_kw': 5.0}))
        self.assertTrue(etape['motif_omission'])


class DansLaCascadeTest(unittest.TestCase):
    """Le poste saisi « onduleur » est écarté, pas soustrait deux fois."""

    def setUp(self):
        self.contexte = contexte(
            fiche={'ac_kw': 5.0, 'rendement_euro_pct': 96.0},
            postes_saisis=[{'poste': 'onduleur', 'pct': 3.0,
                            'source': 'societe'}])
        self.serie, self.cascade = appliquer_chaine(SERIE, self.contexte)
        self.ligne = _ligne(self.cascade, 'onduleur')

    def test_la_perte_est_celle_du_rendement_et_pas_la_saisie(self):
        self.assertAlmostEqual(self.ligne['perte_pct'], 4.0, places=3)

    def test_la_saisie_est_publiee_ecartee(self):
        ecartee = self.ligne['entree']['saisie_ecartee']
        self.assertEqual(ecartee['poste'], 'onduleur')
        self.assertTrue(ecartee['motif'])

    def test_la_cascade_continue_en_alternatif(self):
        self.assertEqual(self.serie['colonne_energie'], 'p_ac_kw')


def _ligne(cascade, nom):
    for etape in cascade['etapes']:
        if etape['etape'] == nom:
            return etape
    raise AssertionError('étape « %s » absente de la cascade' % nom)
