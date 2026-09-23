"""CALX285 — le P90 passe dans le flux de trésorerie (``economie.py``).

Ce qui est prouvé (le « Done » de CALX285) :

* ``{'p50': 10000, 'p90': 9000}`` ⇒ DEUX jeux d'indicateurs, étiquetés par
  scénario, dont le retour P90 est STRICTEMENT plus long sur le cas de
  référence ; sur une grille (test de propriété), le P90 n'est jamais
  meilleur : retour ``>=`` (le retour est une année entière — une petite
  perte peut tenir dans la même année), VAN strictement plus faible, LCOE
  strictement plus élevé ;
* ``{'p50': 10000}`` seul ⇒ un seul jeu et ``omissions`` nomme ``p90`` —
  jamais un P90 dérivé d'un écart-type supposé ;
* la variabilité publiée porte son origine, et une origine ``hypothese`` est
  RÉPERCUTÉE dans ``hypotheses[].source`` ;
* l'économie du P90 est DÉRIVÉE au prorata de la production, et la dérivation
  est publiée avec sa formule ;
* le vocabulaire d'origine reprend celui du calepinage
  (``ORIGINE_MESUREE``/``ORIGINE_SAISIE``).

Fonction PURE : ce test n'a besoin d'AUCUNE base de données.

Run :
    python -m pytest apps/ventes/tests/test_calx285_p90_flux.py -q
"""
import itertools
import unittest

from apps.calepinage.services.p50p90 import ORIGINE_MESUREE, ORIGINE_SAISIE
from apps.ventes.economie import (ORIGINES_VARIABILITE, EconomieInvalide,
                                  economie_par_scenario)

COMMUNS = dict(investissement_mad=100000, economie_annee1_mad=12000,
               horizon_ans=20, taux_actualisation_pct=5, indexation_pct=0,
               degradation_pct=0)


def cles_omises(resultat):
    return {o['cle'] for o in resultat['omissions']}


class DeuxJeuxTest(unittest.TestCase):
    def test_p50_et_p90_deux_jeux_retour_p90_plus_long(self):
        resultat = economie_par_scenario(
            production_par_scenario={'p50': 10000, 'p90': 9000}, **COMMUNS)
        self.assertEqual(set(resultat['scenarios']), {'p50', 'p90'})
        p50, p90 = resultat['scenarios']['p50'], resultat['scenarios']['p90']
        for jeu in (p50, p90):
            self.assertEqual(set(jeu), {'van_mad', 'tri_pct', 'lcoe_mad_kwh',
                                        'retour_ans', 'retour_actualise_ans'})
        self.assertEqual(p50['retour_ans'], 9)
        self.assertGreater(p90['retour_ans'], p50['retour_ans'])
        self.assertLess(p90['van_mad'], p50['van_mad'])
        self.assertGreater(p90['lcoe_mad_kwh'], p50['lcoe_mad_kwh'])

    def test_propriete_le_p90_n_est_jamais_meilleur(self):
        for investissement, economie1, p90 in itertools.product(
                (60000, 100000, 180000), (9000, 12000, 30000),
                (8000, 9000, 9900)):
            parametres = dict(COMMUNS, investissement_mad=investissement,
                              economie_annee1_mad=economie1)
            resultat = economie_par_scenario(
                production_par_scenario={'p50': 10000, 'p90': p90},
                **parametres)
            jeu50 = resultat['scenarios']['p50']
            jeu90 = resultat['scenarios']['p90']
            with self.subTest(i=investissement, e=economie1, p90=p90):
                self.assertLess(jeu90['van_mad'], jeu50['van_mad'])
                self.assertGreater(jeu90['lcoe_mad_kwh'],
                                   jeu50['lcoe_mad_kwh'])
                if jeu50['retour_ans'] is not None \
                        and jeu90['retour_ans'] is not None:
                    self.assertGreaterEqual(jeu90['retour_ans'],
                                            jeu50['retour_ans'])

    def test_l_economie_p90_est_derivee_et_dite(self):
        resultat = economie_par_scenario(
            production_par_scenario={'p50': 10000, 'p90': 9000}, **COMMUNS)
        derivee = next(h for h in resultat['hypotheses']
                       if h['cle'] == 'economie_annee1_mad.p90')
        self.assertEqual(derivee['valeur'], 10800.0)
        self.assertIn('dérivé', derivee['source'])
        self.assertIn('p90', derivee['source'])

    def test_les_omissions_d_indicateur_sont_etiquetees_par_scenario(self):
        resultat = economie_par_scenario(
            production_par_scenario={'p50': 10000, 'p90': 9000},
            **dict(COMMUNS, taux_actualisation_pct=None))
        omises = cles_omises(resultat)
        self.assertIn('taux_actualisation_pct', omises)
        self.assertIn('p50.van_mad', omises)
        self.assertIn('p90.van_mad', omises)
        self.assertIsNone(resultat['scenarios']['p90']['van_mad'])
        # Une grandeur n'est jamais à la fois hypothèse et omission.
        retenues = {h['cle'] for h in resultat['hypotheses']}
        self.assertEqual(retenues & omises, set())


class UnSeulJeuTest(unittest.TestCase):
    def test_p50_seul_un_jeu_et_omission_p90(self):
        resultat = economie_par_scenario(
            production_par_scenario={'p50': 10000}, **COMMUNS)
        self.assertEqual(set(resultat['scenarios']), {'p50'})
        self.assertIn('p90', cles_omises(resultat))
        motif = next(o['motif'] for o in resultat['omissions']
                     if o['cle'] == 'p90')
        self.assertIn('écart-type', motif)

    def test_refus_nommes(self):
        cas = (({'p90': 9000}, 'production_par_scenario.p50'),
               ({'p50': 0}, 'production_par_scenario.p50'),
               ({'p50': 10000, 'p90': 11000}, 'production_par_scenario.p90'),
               ({'p50': 10000, 'p75': 9500}, 'production_par_scenario.p75'))
        for productions, champ in cas:
            with self.subTest(productions=productions):
                with self.assertRaises(EconomieInvalide) as refus:
                    economie_par_scenario(
                        production_par_scenario=productions, **COMMUNS)
                self.assertEqual(refus.exception.champ, champ)

    def test_la_production_ne_vient_que_des_scenarios(self):
        with self.assertRaises(EconomieInvalide) as refus:
            economie_par_scenario(
                production_par_scenario={'p50': 10000},
                production_annee1_kwh=10000, **COMMUNS)
        self.assertEqual(refus.exception.champ, 'production_annee1_kwh')


class VariabiliteTest(unittest.TestCase):
    def test_origine_hypothese_repercutee_dans_la_source(self):
        resultat = economie_par_scenario(
            production_par_scenario={'p50': 10000, 'p90': 9000},
            variabilite={'sigma_pct': 4.5, 'origine': 'hypothese',
                         'source': 'note interne du bureau d\'études'},
            **COMMUNS)
        variabilite = next(h for h in resultat['hypotheses']
                           if h['cle'] == 'variabilite_interannuelle_pct')
        self.assertEqual(variabilite['valeur'], 4.5)
        self.assertIn('hypothese', variabilite['source'])

    def test_origine_mesuree_publiee(self):
        resultat = economie_par_scenario(
            production_par_scenario={'p50': 10000, 'p90': 9000},
            variabilite={'sigma_pct': 3.1, 'origine': ORIGINE_MESUREE,
                         'source': 'PVGIS SARAH3, 2005-2020'},
            **COMMUNS)
        variabilite = next(h for h in resultat['hypotheses']
                           if h['cle'] == 'variabilite_interannuelle_pct')
        self.assertIn('mesuree', variabilite['source'])
        self.assertIn('PVGIS', variabilite['source'])

    def test_sans_variabilite_omission(self):
        resultat = economie_par_scenario(
            production_par_scenario={'p50': 10000}, **COMMUNS)
        self.assertIn('variabilite_interannuelle_pct', cles_omises(resultat))

    def test_variabilite_incomplete_refusee(self):
        cas = (({'origine': 'saisie', 'source': 's'}, 'variabilite.sigma_pct'),
               ({'sigma_pct': 3, 'origine': 'absente', 'source': 's'},
                'variabilite.origine'),
               ({'sigma_pct': 3, 'origine': 'saisie', 'source': ''},
                'variabilite.source'))
        for variabilite, champ in cas:
            with self.subTest(champ=champ):
                with self.assertRaises(EconomieInvalide) as refus:
                    economie_par_scenario(
                        production_par_scenario={'p50': 10000},
                        variabilite=variabilite, **COMMUNS)
                self.assertEqual(refus.exception.champ, champ)

    def test_le_vocabulaire_reprend_celui_du_calepinage(self):
        self.assertIn(ORIGINE_MESUREE, ORIGINES_VARIABILITE)
        self.assertIn(ORIGINE_SAISIE, ORIGINES_VARIABILITE)
        self.assertIn('hypothese', ORIGINES_VARIABILITE)


if __name__ == '__main__':
    unittest.main()
