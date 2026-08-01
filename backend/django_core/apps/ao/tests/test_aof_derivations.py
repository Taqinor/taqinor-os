"""AOF114 — le registre de dérivation reproduit le bilan de stockage FRDISI.

    python -m unittest apps.ao.tests.test_aof_derivations -v
"""
import unittest

from apps.ao.fabrique import derivations as der


def entrees_frdisi(**remplacements):
    """La configuration RÉELLE après la bascule de batterie du 27/07.

    3 piles de 6 packs LFP 51,2 V / 314 Ah : 16,08 kWh par pack, 96,48 kWh et
    307,2 V par banc, 289,44 kWh installés, besoin nocturne 284,4 kWh.
    """
    base = {
        'piles': 3, 'packs_par_pile': 6,
        'tension_pack_v': 51.2, 'capacite_pack_ah': 314.0,
        'besoin_nocturne_kwh': 284.4,
        'modules_raccordes': 560, 'puissance_dc_kwc': 350.0,
        'calibre_onduleur_kw': 110.0, 'productible_kwh_kwc': 1651.0,
    }
    base.update(remplacements)
    return base


class TestCasFrdisi(unittest.TestCase):

    def setUp(self):
        self.d = der.deriver(entrees_frdisi())

    def test_capacite_pack(self):
        self.assertAlmostEqual(self.d['capacite_pack_kwh'], 16.0768, places=4)

    def test_tension_de_banc_307_2_v(self):
        self.assertAlmostEqual(self.d['tension_banc_v'], 307.2, places=1)

    def test_capacite_de_banc_96_5_kwh(self):
        """Le dossier écrit « 96,48 » : c'est 6 × 16,08, un ARRONDI propagé.

        Le pack réel fait 51,2 V × 314 Ah = 16,0768 kWh ; le banc fait donc
        96,4608 kWh, pas 96,48. L'écart (1,9 Wh) est sans effet technique mais
        il illustre EXACTEMENT le défaut que ce registre supprime : un chiffre
        arrondi pour l'affichage puis réutilisé comme donnée de calcul. Le
        registre calcule en pleine précision et n'arrondit qu'à l'affichage —
        les deux affichent « 96,5 kWh ».
        """
        self.assertAlmostEqual(self.d['capacite_banc_kwh'], 96.4608, places=4)
        self.assertEqual('%.1f' % self.d['capacite_banc_kwh'], '96.5')
        self.assertEqual('%.1f' % (6 * round(16.0768, 2)), '96.5')

    def test_capacite_installee_289_4_kwh(self):
        self.assertEqual('%.1f' % self.d['capacite_installee_kwh'], '289.4')

    def test_dix_huit_packs(self):
        self.assertEqual(self.d['packs_total'], 18)

    def test_couverture_nocturne_100_pct_avec_5_kwh_de_marge(self):
        self.assertEqual(self.d['couverture_nocturne_pct'], 100.0)
        self.assertAlmostEqual(self.d['marge_nocturne_kwh'], 5.0, places=0)

    def test_chaines_de_16(self):
        self.assertEqual(self.d['chaines_completes'], 35)
        self.assertEqual(self.d['modules_hors_chaine'], 0)

    def test_onduleurs_et_ratio_dc_ac_conforme(self):
        self.assertEqual(self.d['onduleurs_necessaires'], 3)
        self.assertAlmostEqual(self.d['puissance_ac_kw'], 330.0, places=6)
        self.assertAlmostEqual(self.d['ratio_dc_ac'], 350.0 / 330.0, places=6)
        self.assertTrue(self.d['conforme_cps'])

    def test_production_annuelle_sur_le_productible_du_dossier(self):
        self.assertAlmostEqual(self.d['production_annuelle_kwh'],
                               350.0 * 1651.0, places=3)


class TestAucuneGrandeurDeriveeNEstSaisie(unittest.TestCase):

    def test_fournir_une_grandeur_derivee_est_refuse(self):
        for cle in ('capacite_installee_kwh', 'ratio_dc_ac',
                    'couverture_nocturne_pct', 'onduleurs_necessaires'):
            with self.assertRaises(der.ValeurSaisieInterdite, msg=cle):
                der.deriver(entrees_frdisi(**{cle: 999}))

    def test_le_message_nomme_la_grandeur_fautive(self):
        with self.assertRaises(der.ValeurSaisieInterdite) as cm:
            der.deriver(entrees_frdisi(capacite_installee_kwh=289.4))
        self.assertIn('capacite_installee_kwh', str(cm.exception))

    def test_le_registre_est_la_seule_naissance_possible(self):
        """Toute grandeur publiée par `deriver` a une règle qui la produit."""
        for cle in der.deriver(entrees_frdisi()):
            self.assertIn(cle, der.PAR_CLE, cle)


class TestChaineRejouee(unittest.TestCase):

    def test_changer_le_pack_rejoue_toute_la_chaine(self):
        """La bascule de batterie : on change l'ÉQUIPEMENT, pas les bilans."""
        avant = der.deriver(entrees_frdisi())
        apres = der.deriver(entrees_frdisi(capacite_pack_ah=280.0))
        for cle in ('capacite_pack_kwh', 'capacite_banc_kwh',
                    'capacite_installee_kwh', 'capacite_utile_kwh',
                    'marge_nocturne_kwh', 'couverture_nocturne_pct'):
            self.assertNotEqual(avant[cle], apres[cle], cle)
        # La tension de banc, elle, ne dépend PAS de la capacité du pack.
        self.assertEqual(avant['tension_banc_v'], apres['tension_banc_v'])

    def test_un_pack_plus_petit_casse_la_couverture_nocturne(self):
        apres = der.deriver(entrees_frdisi(capacite_pack_ah=200.0))
        self.assertLess(apres['couverture_nocturne_pct'], 100.0)
        self.assertLess(apres['marge_nocturne_kwh'], 0)
        self.assertTrue(der.controles_cps(apres))

    def test_dependants_liste_ce_qui_bouge(self):
        touches = der.dependants('capacite_pack_ah')
        self.assertIn('capacite_installee_kwh', touches)
        self.assertIn('couverture_nocturne_pct', touches)
        self.assertNotIn('ratio_dc_ac', touches)

    def test_chaine_de_derivation_ordonnee(self):
        chaine = der.chaine_de_derivation('capacite_installee_kwh')
        self.assertEqual(
            chaine[-1], 'capacite_installee_kwh')
        self.assertIn('capacite_pack_kwh', chaine)
        self.assertLess(chaine.index('capacite_pack_kwh'),
                        chaine.index('capacite_banc_kwh'))

    def test_deriver_est_deterministe(self):
        self.assertEqual(der.deriver(entrees_frdisi()),
                         der.deriver(entrees_frdisi()))


class TestConformiteCps(unittest.TestCase):

    def test_ratio_hors_bande_signale(self):
        d = der.deriver(entrees_frdisi(puissance_dc_kwc=350.0,
                                       calibre_onduleur_kw=500.0))
        self.assertFalse(d['conforme_cps'])
        self.assertTrue(any('DC/AC' in a for a in der.controles_cps(d)))

    def test_bande_cps_serree_sans_calibre_adapte_est_signalee(self):
        """Aucun nombre d'onduleurs de 110 kW ne tient la bande 1,00–1,05.

        3 onduleurs donnent 1,06 (au-dessus du plafond), 4 donnent 0,795 (sous
        le plancher : de l'onduleur payé pour rien). Le registre ne choisit pas
        le moins pire en silence — il calibre au plafond et DÉCLARE la
        non-conformité, ce qui renvoie la décision au CPS.
        """
        serree = der.deriver(entrees_frdisi(), defauts=dict(
            der.DEFAUTS, ratio_dc_ac_max=1.05))
        self.assertEqual(serree['onduleurs_necessaires'], 4)
        self.assertFalse(serree['conforme_cps'])
        self.assertTrue(any('DC/AC' in a for a in der.controles_cps(serree)))

    def test_bande_cps_serree_tenue_avec_le_bon_calibre(self):
        serree = der.deriver(entrees_frdisi(calibre_onduleur_kw=87.5),
                             defauts=dict(der.DEFAUTS, ratio_dc_ac_max=1.05))
        self.assertEqual(serree['onduleurs_necessaires'], 4)
        self.assertAlmostEqual(serree['ratio_dc_ac'], 1.0, places=6)
        self.assertTrue(serree['conforme_cps'])
        self.assertEqual(der.controles_cps(serree), ())

    def test_modules_hors_chaine_signales(self):
        d = der.deriver(entrees_frdisi(modules_raccordes=563))
        self.assertEqual(d['modules_hors_chaine'], 3)
        self.assertTrue(any('hors chaîne' in a for a in der.controles_cps(d)))

    def test_dossier_conforme_sans_anomalie(self):
        self.assertEqual(der.controles_cps(der.deriver(entrees_frdisi())), ())


class TestExplication(unittest.TestCase):

    def test_explication_generee(self):
        phrase = der.explication('capacite_installee_kwh', entrees_frdisi())
        self.assertIn('Capacité installée', phrase)
        self.assertIn('3', phrase)

    def test_explication_du_ratio(self):
        self.assertIn('Ratio DC/AC',
                      der.explication('ratio_dc_ac', entrees_frdisi()))

    def test_grandeur_inconnue_leve(self):
        with self.assertRaises(KeyError):
            der.chaine_de_derivation('inventee')
        with self.assertRaises(KeyError):
            der.deriver(entrees_frdisi(), cles=('inventee',))


class TestCalculPartiel(unittest.TestCase):

    def test_cles_restreintes_calculent_leurs_dependances(self):
        d = der.deriver(entrees_frdisi(), cles=('capacite_installee_kwh',))
        self.assertIn('capacite_pack_kwh', d)
        self.assertNotIn('ratio_dc_ac', d)

    def test_entrees_incompletes_ne_font_pas_planter(self):
        d = der.deriver({'piles': 3, 'packs_par_pile': 6})
        self.assertEqual(d['packs_total'], 18)
        self.assertNotIn('capacite_installee_kwh', d)


if __name__ == '__main__':
    unittest.main()
