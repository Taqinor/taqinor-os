"""CALX263 — modéliser la climatisation en BTU avec un EER saisi.

Ce qui est tenu :

* ``courbe_climatisation(*, btu, eer, heures_fonctionnement, facteur_saison)``
  calcule la puissance électrique = BTU/h ÷ EER — les DEUX sont SAISIS ;
* un EER absent est REFUSÉ en nommant ``clim.eer`` — jamais le défaut 9 de
  l'atelier (``AC_EER_DEFAULT_NON_INVERTER``,
  ``apps/web/src/lib/applianceConsumption.ts:649``), qui n'est JAMAIS
  importé ni reproduit ici ;
* ``clim`` entre dans ``TYPES_DE_CHARGE`` ;
* le retrait de la charge rend la courbe de base intacte (propriété déjà
  garantie par ``ajouter_charges`` pour tout type de charge).

12 000 BTU avec un EER 9 sur 8 h ⇒ 10,667 kWh/j ± 0,01 (BTU/h ÷ EER = W,
cité depuis ``applianceConsumption.ts:640-649`` comme exemple de calcul,
JAMAIS comme un défaut : ici l'EER est SAISI par le test, pas supposé par
le module).

Test PUR : aucune base, aucun réseau, aucun prix.
"""
from __future__ import annotations

import unittest

from apps.calepinage.services.charges import (
    TYPES_DE_CHARGE, ChargeInvalide, ajouter_charges, courbe_climatisation,
)


class ClimEntreDansTypesDeChargeTest(unittest.TestCase):

    def test_clim_est_un_type_de_charge_connu(self):
        self.assertIn('clim', TYPES_DE_CHARGE)


class CourbeClimatisationTest(unittest.TestCase):

    def test_12000_btu_eer_9_sur_8h_donne_10_667_kwh(self):
        charge = courbe_climatisation(btu=12000, eer=9,
                                      heures_fonctionnement=[13, 14, 15, 16,
                                                             17, 18, 19, 20])
        self.assertAlmostEqual(charge['energie_journaliere_kwh'], 10.667,
                               delta=0.01)
        self.assertEqual(charge['type'], 'clim')

    def test_eer_absent_est_refuse_en_nommant_clim_eer(self):
        with self.assertRaises(ChargeInvalide) as refus:
            courbe_climatisation(btu=12000, heures_fonctionnement=[13])
        self.assertEqual(refus.exception.champ, 'clim.eer')

    def test_aucun_eer_par_defaut_n_est_jamais_applique(self):
        # Le défaut de l'atelier (9) ne doit JAMAIS être injecté à la place
        # d'un EER manquant : la fonction refuse, elle ne complète pas.
        with self.assertRaises(ChargeInvalide):
            courbe_climatisation(btu=12000, heures_fonctionnement=[13])

    def test_btu_absent_est_refuse_en_nommant_clim_btu(self):
        with self.assertRaises(ChargeInvalide) as refus:
            courbe_climatisation(eer=9, heures_fonctionnement=[13])
        self.assertEqual(refus.exception.champ, 'clim.btu')

    def test_heures_fonctionnement_absentes_sont_refusees(self):
        with self.assertRaises(ChargeInvalide) as refus:
            courbe_climatisation(btu=12000, eer=9)
        self.assertEqual(refus.exception.champ, 'clim.heures_fonctionnement')


class RetraitDeLaChargeClimTest(unittest.TestCase):
    """CALX263 Done : le retrait de la charge rend la courbe de base intacte."""

    def test_courbe_de_base_intacte_avec_ou_sans_clim(self):
        base = [1.0] * 24
        clim = courbe_climatisation(btu=12000, eer=9,
                                    heures_fonctionnement=[13, 14])
        avec_clim = ajouter_charges(base, [clim])
        sans_clim = ajouter_charges(base, [])
        self.assertEqual(avec_clim['courbe_de_base'], base)
        self.assertEqual(sans_clim['courbe_de_base'], base)
        self.assertEqual(sans_clim['courbe'], base)


if __name__ == '__main__':  # pragma: no cover
    unittest.main()
