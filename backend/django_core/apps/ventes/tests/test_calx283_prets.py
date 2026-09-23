"""CALX283 — les prêts : annuité, échéances constantes, in fine, différé.

Ce qui est prouvé (le « Done » de CALX283) :

* 100 000 MAD à 6 %/an sur 120 mois en ``annuite`` ⇒ mensualité
  1 110,21 MAD ± 0,01 (formule d'annuité de ``quote_engine/builder.py``,
  RELUE et non dupliquée) ;
* ``echeances_constantes`` ⇒ première échéance STRICTEMENT supérieure à la
  dernière (test de propriété, sur une grille) ;
* ``differe_mois = 12`` ⇒ les douze premières lignes ne portent que des
  intérêts et le capital restant dû est inchangé ;
* taux absent ⇒ refus nommant ``taux_annuel_pct`` (aucun taux de repli) ;
* les échéances entrent dans le flux de CALX281 : la part financée quitte
  l'année 0, le service de la dette est retranché année par année ;
* un prêt plus long que l'horizon, ou plus gros que l'investissement, est
  refusé en nommant ``pret.<champ>``.

Fonction PURE : ce test n'a besoin d'AUCUNE base de données.

Run :
    python -m pytest apps/ventes/tests/test_calx283_prets.py -q
"""
import itertools
import unittest

from apps.ventes.economie import (EconomieInvalide, flux_de_tresorerie,
                                  tableau_pret)
from apps.ventes.quote_engine.builder import _monthly_loan_payment

PRET = dict(principal_mad=100000, taux_annuel_pct=6, duree_mois=120,
            type_pret='annuite')


class AnnuiteTest(unittest.TestCase):
    def test_mensualite_1110_21(self):
        tableau = tableau_pret(**PRET)
        self.assertAlmostEqual(tableau['mensualite_mad'], 1110.21, delta=0.01)
        self.assertEqual(len(tableau['echeances']), 120)
        # Chaque échéance hors la dernière vaut la mensualité ; la dernière
        # solde l'arrondi au centime.
        for ligne in tableau['echeances'][:-1]:
            self.assertAlmostEqual(ligne['echeance_mad'], 1110.21, delta=0.01)
        self.assertEqual(tableau['echeances'][-1]['capital_restant_du_mad'],
                         0.0)
        # Tenue au centime : les capitaux remboursés soldent EXACTEMENT le
        # principal, sans dérive d'arrondi.
        self.assertAlmostEqual(
            sum(ligne['capital_mad'] for ligne in tableau['echeances']),
            100000, places=6)
        self.assertAlmostEqual(
            tableau['total_rembourse_mad'],
            sum(ligne['echeance_mad'] for ligne in tableau['echeances']),
            places=6)

    def test_la_mensualite_relit_la_formule_du_moteur_de_devis(self):
        for principal, taux, duree in itertools.product(
                (50000, 100000), (0, 4.5, 6), (84, 120)):
            with self.subTest(p=principal, t=taux, d=duree):
                tableau = tableau_pret(principal_mad=principal,
                                       taux_annuel_pct=taux, duree_mois=duree,
                                       type_pret='annuite')
                self.assertEqual(
                    tableau['mensualite_mad'],
                    _monthly_loan_payment(principal, taux / 100, duree))

    def test_taux_nul_sans_interets(self):
        tableau = tableau_pret(principal_mad=12000, taux_annuel_pct=0,
                               duree_mois=12, type_pret='annuite')
        self.assertEqual(tableau['total_interets_mad'], 0.0)
        self.assertEqual(tableau['total_rembourse_mad'], 12000.0)


class EcheancesConstantesTest(unittest.TestCase):
    def test_propriete_la_premiere_echeance_depasse_la_derniere(self):
        for principal, taux, duree in itertools.product(
                (20000, 100000), (1, 6, 9), (24, 120)):
            with self.subTest(p=principal, t=taux, d=duree):
                echeances = tableau_pret(
                    principal_mad=principal, taux_annuel_pct=taux,
                    duree_mois=duree,
                    type_pret='echeances_constantes')['echeances']
                self.assertGreater(echeances[0]['echeance_mad'],
                                   echeances[-1]['echeance_mad'])
                capitaux = {ligne['capital_mad'] for ligne in echeances[:-1]}
                self.assertEqual(len(capitaux), 1)
                self.assertEqual(echeances[-1]['capital_restant_du_mad'], 0.0)


class DiffereTest(unittest.TestCase):
    def test_douze_mois_d_interets_seuls_capital_inchange(self):
        tableau = tableau_pret(**dict(PRET, differe_mois=12))
        self.assertEqual(len(tableau['echeances']), 120)
        for ligne in tableau['echeances'][:12]:
            self.assertEqual(ligne['capital_mad'], 0.0)
            self.assertEqual(ligne['echeance_mad'], ligne['interets_mad'])
            self.assertEqual(ligne['capital_restant_du_mad'], 100000.0)
            self.assertAlmostEqual(ligne['interets_mad'], 500.0, places=2)
        self.assertGreater(tableau['echeances'][12]['capital_mad'], 0)
        # L'amortissement tient sur les 108 mois restants.
        self.assertEqual(tableau['mensualite_mad'],
                         _monthly_loan_payment(100000, 0.06, 108))
        self.assertEqual(tableau['echeances'][-1]['capital_restant_du_mad'],
                         0.0)

    def test_differe_absent_aucun_differe(self):
        self.assertEqual(tableau_pret(**PRET)['differe_mois'], 0)

    def test_in_fine(self):
        echeances = tableau_pret(**dict(PRET, type_pret='in_fine'))[
            'echeances']
        self.assertTrue(all(ligne['capital_mad'] == 0.0
                            for ligne in echeances[:-1]))
        self.assertEqual(echeances[-1]['capital_mad'], 100000.0)


class RefusTest(unittest.TestCase):
    def test_taux_absent_refuse_en_le_nommant(self):
        with self.assertRaises(EconomieInvalide) as refus:
            tableau_pret(**dict(PRET, taux_annuel_pct=None))
        self.assertEqual(refus.exception.champ, 'taux_annuel_pct')

    def test_chaque_parametre_est_saisi(self):
        cas = (('principal_mad', None), ('principal_mad', 0),
               ('duree_mois', None), ('duree_mois', 10.5),
               ('type_pret', None), ('type_pret', 'leasing'),
               ('taux_annuel_pct', -1))
        for champ, valeur in cas:
            with self.subTest(champ=champ, valeur=valeur):
                with self.assertRaises(EconomieInvalide) as refus:
                    tableau_pret(**dict(PRET, **{champ: valeur}))
                self.assertEqual(refus.exception.champ, champ)

    def test_differe_qui_mange_toute_la_duree(self):
        with self.assertRaises(EconomieInvalide) as refus:
            tableau_pret(**dict(PRET, differe_mois=120))
        self.assertEqual(refus.exception.champ, 'differe_mois')


class InjectionDansLeFluxTest(unittest.TestCase):
    def test_les_echeances_entrent_dans_le_flux(self):
        tableau = tableau_pret(**PRET)
        bloc = flux_de_tresorerie(
            investissement_mad=120000, economie_annee1_mad=15000,
            horizon_ans=10, taux_actualisation_pct=0,
            pret=dict(PRET, source='offre bancaire n° 3'))
        # Seule la part non financée sort en année 0.
        self.assertEqual(bloc['flux'][0]['flux_mad'], -20000.0)
        service_annee1 = sum(ligne['echeance_mad']
                             for ligne in tableau['echeances'][:12])
        self.assertAlmostEqual(bloc['flux'][1]['flux_mad'],
                               15000 - service_annee1, places=2)
        # Tout le service de la dette est porté au flux, rien de plus.
        service_total = sum(15000 - ligne['flux_mad']
                            for ligne in bloc['flux'][1:])
        self.assertAlmostEqual(service_total, tableau['total_rembourse_mad'],
                               delta=0.05)
        pret = {h['cle']: h for h in bloc['hypotheses']
                if h['cle'].startswith('pret.')}
        self.assertEqual(pret['pret.taux_annuel_pct']['valeur'], 6)
        self.assertEqual(pret['pret.type_pret']['source'],
                         'offre bancaire n° 3')

    def test_sans_pret_achat_comptant(self):
        bloc = flux_de_tresorerie(investissement_mad=120000,
                                  economie_annee1_mad=15000, horizon_ans=10)
        self.assertEqual(bloc['flux'][0]['flux_mad'], -120000.0)

    def test_pret_au_dela_de_l_horizon_refuse(self):
        with self.assertRaises(EconomieInvalide) as refus:
            flux_de_tresorerie(investissement_mad=120000,
                               economie_annee1_mad=15000, horizon_ans=5,
                               pret=PRET)
        self.assertEqual(refus.exception.champ, 'pret.duree_mois')

    def test_pret_plus_gros_que_l_investissement_refuse(self):
        with self.assertRaises(EconomieInvalide) as refus:
            flux_de_tresorerie(investissement_mad=50000,
                               economie_annee1_mad=15000, horizon_ans=10,
                               pret=PRET)
        self.assertEqual(refus.exception.champ, 'pret.principal_mad')

    def test_taux_absent_dans_le_flux_nomme_pret_taux(self):
        with self.assertRaises(EconomieInvalide) as refus:
            flux_de_tresorerie(investissement_mad=120000,
                               economie_annee1_mad=15000, horizon_ans=10,
                               pret=dict(PRET, taux_annuel_pct=None))
        self.assertEqual(refus.exception.champ, 'pret.taux_annuel_pct')


if __name__ == '__main__':
    unittest.main()
