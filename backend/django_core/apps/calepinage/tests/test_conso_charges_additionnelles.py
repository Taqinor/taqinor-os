"""CAL154 — véhicule électrique et pompe à chaleur AJOUTÉS à la courbe.

Ce qui est tenu :

* chaque charge est visible SÉPARÉMENT dans le bilan ;
* aucun COP ni kWh/100 km par défaut — la saisie est obligatoire, et le refus
  nomme le champ ;
* retirer une charge rend le bilan initial AU KWH PRÈS.

Tests PURS : aucune base, aucun réseau.
"""
from __future__ import annotations

import unittest

from apps.calepinage.services.charges import (
    ChargeInvalide, ajouter_charges, courbe_pac, courbe_vehicule,
)

BASE = [1.0] * 24

VEHICULE = dict(km_par_jour=50.0, kwh_par_100km=16.0,
                fenetre_recharge=[22, 23, 0, 1])
PAC = dict(puissance_kw=3.0, cop=3.5, heures_fonctionnement=[6, 7, 18, 19])


class VehiculeTest(unittest.TestCase):

    def test_l_energie_vient_des_kilometres_et_de_la_consommation_saisis(self):
        charge = courbe_vehicule(**VEHICULE)
        self.assertEqual(charge['energie_journaliere_kwh'], 8.0)
        self.assertAlmostEqual(sum(charge['courbe']), 8.0, places=6)

    def test_l_energie_tombe_dans_la_fenetre_saisie_et_nulle_part_ailleurs(self):
        charge = courbe_vehicule(**VEHICULE)
        for heure, valeur in enumerate(charge['courbe']):
            attendu = heure in {22, 23, 0, 1}
            self.assertEqual(valeur > 0, attendu, heure)

    def test_le_rendement_de_recharge_saisi_augmente_l_energie_prise(self):
        sans = courbe_vehicule(**VEHICULE)
        avec = courbe_vehicule(**dict(VEHICULE, rendement_recharge_pct=90.0))
        self.assertGreater(avec['energie_journaliere_kwh'],
                           sans['energie_journaliere_kwh'])

    def test_sans_rendement_saisi_l_hypothese_est_annoncee(self):
        charge = courbe_vehicule(**VEHICULE)
        self.assertTrue(any('rendement' in h for h in charge['hypotheses']))

    def test_aucun_kwh_par_100km_par_defaut(self):
        entree = dict(VEHICULE)
        entree.pop('kwh_par_100km')
        with self.assertRaises(ChargeInvalide) as refus:
            courbe_vehicule(**entree)
        self.assertEqual(refus.exception.champ, 'vehicule.kwh_par_100km')

    def test_aucune_fenetre_par_defaut(self):
        entree = dict(VEHICULE)
        entree.pop('fenetre_recharge')
        with self.assertRaises(ChargeInvalide) as refus:
            courbe_vehicule(**entree)
        self.assertEqual(refus.exception.champ, 'vehicule.fenetre_recharge')

    def test_une_heure_hors_bornes_est_refusee(self):
        with self.assertRaises(ChargeInvalide):
            courbe_vehicule(**dict(VEHICULE, fenetre_recharge=[25]))


class PacTest(unittest.TestCase):

    def test_l_energie_electrique_est_la_thermique_divisee_par_le_cop(self):
        charge = courbe_pac(**PAC)
        self.assertAlmostEqual(charge['energie_journaliere_kwh'],
                               3.0 * 4 / 3.5, places=4)

    def test_le_facteur_de_saison_saisi_pondere_la_charge(self):
        hiver = courbe_pac(**dict(PAC, facteur_saison=1.6))
        reference = courbe_pac(**PAC)
        self.assertAlmostEqual(
            hiver['energie_journaliere_kwh'],
            1.6 * reference['energie_journaliere_kwh'], places=3)

    def test_aucun_cop_par_defaut(self):
        entree = dict(PAC)
        entree.pop('cop')
        with self.assertRaises(ChargeInvalide) as refus:
            courbe_pac(**entree)
        self.assertEqual(refus.exception.champ, 'pac.cop')

    def test_sans_facteur_de_saison_l_hypothese_est_annoncee(self):
        charge = courbe_pac(**PAC)
        self.assertTrue(any('saison' in h for h in charge['hypotheses']))


class BilanTest(unittest.TestCase):

    def test_chaque_charge_est_visible_separement(self):
        bilan = ajouter_charges(BASE, [courbe_vehicule(**VEHICULE),
                                       courbe_pac(**PAC)])
        types = [charge['type'] for charge in bilan['charges']]
        self.assertEqual(types, ['vehicule', 'pac'])
        self.assertEqual(bilan['charges'][0]['energie_kwh'], 8.0)

    def test_les_totaux_se_referment(self):
        bilan = ajouter_charges(BASE, [courbe_vehicule(**VEHICULE),
                                       courbe_pac(**PAC)])
        self.assertAlmostEqual(
            bilan['total_kwh'],
            bilan['total_base_kwh'] + bilan['total_charges_kwh'], places=4)

    def test_retirer_une_charge_rend_le_bilan_initial_au_kwh_pres(self):
        sans = ajouter_charges(BASE, [])
        avec = ajouter_charges(BASE, [courbe_vehicule(**VEHICULE)])
        de_nouveau_sans = ajouter_charges(avec['courbe_de_base'], [])
        self.assertEqual(de_nouveau_sans['courbe'], sans['courbe'])
        self.assertEqual(de_nouveau_sans['total_kwh'], sans['total_kwh'])

    def test_la_courbe_de_base_n_est_jamais_modifiee_sur_place(self):
        origine = list(BASE)
        ajouter_charges(BASE, [courbe_vehicule(**VEHICULE)])
        self.assertEqual(BASE, origine)

    def test_une_charge_d_une_autre_periode_est_refusee(self):
        annuel = courbe_vehicule(**dict(VEHICULE, longueur=48))
        with self.assertRaises(ChargeInvalide) as refus:
            ajouter_charges(BASE, [annuel])
        self.assertEqual(refus.exception.champ, 'charges[0]')

    def test_sur_une_annee_la_charge_se_repete_chaque_jour(self):
        charge = courbe_vehicule(**dict(VEHICULE, longueur=48))
        self.assertAlmostEqual(sum(charge['courbe']), 16.0, places=6)


if __name__ == '__main__':  # pragma: no cover
    unittest.main()
