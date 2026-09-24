"""CALX265 — rattacher une clé tarifaire à chaque charge déclarée.

Ce qui est tenu :

* ``cle_tarifaire`` (chaîne libre SAISIE) portée par une charge est
  republiée dans ``detail[]`` + un agrégat ``energie_par_cle`` ;
* clé absente ⇒ la charge est comptée au tarif du foyer (clé ``'foyer'``)
  et la mention le DIT dans les hypothèses du bilan — JAMAIS un second
  tarif supposé ;
* ``courbe_de_base`` reste INTACTE (propriété existante, non-régression).

Test PUR : aucune base, aucun réseau, aucun prix.
"""
from __future__ import annotations

import unittest

from apps.calepinage.services.charges import ajouter_charges, courbe_vehicule

BASE = [1.0] * 24

VEHICULE = dict(km_par_jour=100.0, kwh_par_100km=15.0,
                fenetre_recharge=[22, 23, 0, 1])
PAC_COMME_CHARGE = dict(type='pac', libelle='Pompe à chaleur',
                        courbe=[0.5] * 24, hypotheses=[])


class CleTarifaireParChargeTest(unittest.TestCase):

    def test_deux_cles_donnent_deux_entrees_dont_la_somme_egale_le_total(self):
        ve = courbe_vehicule(**VEHICULE)
        ve['cle_tarifaire'] = 've'
        pac = dict(PAC_COMME_CHARGE)
        pac['cle_tarifaire'] = 'pac'

        bilan = ajouter_charges(BASE, [ve, pac])

        self.assertEqual(set(bilan['energie_par_cle']), {'ve', 'pac'})
        self.assertAlmostEqual(
            sum(bilan['energie_par_cle'].values()),
            bilan['total_charges_kwh'], places=2)
        self.assertEqual(bilan['charges'][0]['cle_tarifaire'], 've')
        self.assertEqual(bilan['charges'][1]['cle_tarifaire'], 'pac')
        self.assertEqual(bilan['hypotheses'], [])

    def test_charges_sans_cle_donnent_une_seule_entree_foyer_et_l_hypothese(self):
        ve = courbe_vehicule(**VEHICULE)  # aucune cle_tarifaire attribuée
        pac = dict(PAC_COMME_CHARGE)  # idem

        bilan = ajouter_charges(BASE, [ve, pac])

        self.assertEqual(set(bilan['energie_par_cle']), {'foyer'})
        self.assertAlmostEqual(
            bilan['energie_par_cle']['foyer'], bilan['total_charges_kwh'],
            places=2)
        self.assertTrue(any('foyer' in h.lower() for h in bilan['hypotheses']))
        for charge in bilan['charges']:
            self.assertEqual(charge['cle_tarifaire'], 'foyer')

    def test_courbe_de_base_reste_intacte(self):
        ve = courbe_vehicule(**VEHICULE)
        ve['cle_tarifaire'] = 've'
        bilan = ajouter_charges(BASE, [ve])
        self.assertEqual(bilan['courbe_de_base'], BASE)


if __name__ == '__main__':  # pragma: no cover
    unittest.main()
