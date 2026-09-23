"""CALX282 — le coût actualisé du kWh (LCOE) dans ``economie.py``.

Ce qui est prouvé (le « Done » de CALX282) :

* 100 000 MAD, aucune charge, 10 000 kWh/an, 10 ans, actualisation 0,
  dégradation 0 ⇒ ``1.0`` MAD/kWh EXACTEMENT ;
* avec une dégradation de 0,5 %/an, le LCOE est STRICTEMENT supérieur (test
  de propriété, sur une grille de cas) ;
* production nulle (ou absente) ⇒ ``None`` et le motif NOMME
  ``production_annuelle_kwh`` — jamais une division bornée ;
* sans taux d'actualisation, aucun LCOE (le calcul est actualisé par
  définition) ;
* le bloc économie (``flux_de_tresorerie``) publie le MÊME LCOE que la
  fonction, sur le même flux (charges et remplacements compris).

Fonction PURE : ce test n'a besoin d'AUCUNE base de données.

Run :
    python -m pytest apps/ventes/tests/test_calx282_lcoe.py -q
"""
import itertools
import unittest

from apps.ventes.economie import flux_de_tresorerie, lcoe


def reference(**surcharges):
    params = dict(investissement_mad=100000, charges_annuelles_mad=0,
                  production_annuelle_kwh=10000, horizon_ans=10,
                  taux_actualisation_pct=0, degradation_pct=0)
    params.update(surcharges)
    return lcoe(**params)


def motif(resultat, cle):
    return next(o['motif'] for o in resultat['omissions'] if o['cle'] == cle)


class LcoeTest(unittest.TestCase):
    def test_cas_de_reference_un_mad_par_kwh_exactement(self):
        self.assertEqual(reference()['lcoe_mad_kwh'], 1.0)

    def test_la_degradation_rencherit_strictement_le_kwh(self):
        self.assertGreater(reference(degradation_pct=0.5)['lcoe_mad_kwh'],
                           reference()['lcoe_mad_kwh'])
        for investissement, production, taux, horizon in itertools.product(
                (50000, 100000), (5000, 10000), (0, 3, 6), (10, 25)):
            with self.subTest(i=investissement, p=production, t=taux,
                              h=horizon):
                sans = reference(investissement_mad=investissement,
                                 production_annuelle_kwh=production,
                                 taux_actualisation_pct=taux,
                                 horizon_ans=horizon)['lcoe_mad_kwh']
                avec = reference(investissement_mad=investissement,
                                 production_annuelle_kwh=production,
                                 taux_actualisation_pct=taux,
                                 horizon_ans=horizon,
                                 degradation_pct=0.5)['lcoe_mad_kwh']
                self.assertGreater(avec, sans)

    def test_production_nulle_ou_absente_aucun_lcoe_et_motif_nomme(self):
        for production in (0, None):
            with self.subTest(production=production):
                resultat = reference(production_annuelle_kwh=production)
                self.assertIsNone(resultat['lcoe_mad_kwh'])
                self.assertIn('production_annuelle_kwh',
                              motif(resultat, 'lcoe_mad_kwh'))

    def test_sans_taux_aucun_lcoe(self):
        resultat = reference(taux_actualisation_pct=None)
        self.assertIsNone(resultat['lcoe_mad_kwh'])
        self.assertIn('taux_actualisation_pct',
                      motif(resultat, 'lcoe_mad_kwh'))

    def test_charges_et_actualisation(self):
        # 100 000 + 10 × 1 000 de charges, sans actualisation : 1,1 MAD/kWh.
        self.assertAlmostEqual(
            reference(charges_annuelles_mad=1000)['lcoe_mad_kwh'], 1.1,
            places=6)
        # Actualiser l'énergie (au dénominateur) renchérit le kWh quand
        # l'investissement est en année 0.
        self.assertGreater(reference(taux_actualisation_pct=5)['lcoe_mad_kwh'],
                           1.0)

    def test_degradation_absente_non_portee_et_dite(self):
        resultat = reference(degradation_pct=None)
        self.assertEqual(resultat['lcoe_mad_kwh'], 1.0)
        self.assertIn('degradation_pct',
                      {o['cle'] for o in resultat['omissions']})

    def test_le_bloc_economie_publie_le_meme_lcoe(self):
        onduleur = {'equipement': 'onduleur', 'annee': 6, 'mode': 'remplacer',
                    'montant_mad': 8000, 'source': 'devis fournisseur n° 4'}
        commun = dict(investissement_mad=100000, horizon_ans=20,
                      taux_actualisation_pct=4, degradation_pct=0.5,
                      charges_annuelles_mad=400, remplacements=[onduleur])
        bloc = flux_de_tresorerie(economie_annee1_mad=12000,
                                  production_annee1_kwh=10000, **commun)
        seul = lcoe(production_annuelle_kwh=10000, **commun)
        self.assertIsNotNone(bloc['lcoe_mad_kwh'])
        self.assertEqual(bloc['lcoe_mad_kwh'], seul['lcoe_mad_kwh'])

    def test_le_bloc_sans_production_omet_le_lcoe(self):
        bloc = flux_de_tresorerie(investissement_mad=100000,
                                  economie_annee1_mad=12000, horizon_ans=10,
                                  taux_actualisation_pct=0)
        self.assertIsNone(bloc['lcoe_mad_kwh'])
        self.assertIn('production_annee1_kwh', motif(bloc, 'lcoe_mad_kwh'))


if __name__ == '__main__':
    unittest.main()
