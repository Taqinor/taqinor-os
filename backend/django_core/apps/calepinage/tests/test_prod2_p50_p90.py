"""CAL142 — P50/P90 d'un calepinage, y compris SANS devis.

Ce qui est tenu ici :

* un SEUL moteur de statistiques — celui de ``ventes`` — et AUCUNE perte
  appliquée deux fois (la production PVGIS porte déjà celles de CAL139) ;
* σ MESURÉ quand la fenêtre couvre plusieurs années, ANNONCÉ comme hypothèse
  quand elle n'en couvre qu'une ;
* rien n'est calculé sans production : ``None``, jamais ``0``.

Tests PURS : aucune base, aucun réseau (transport PVGIS injecté, réponse
enregistrée).
"""
from __future__ import annotations

import json
import pathlib
import unittest

from apps.calepinage.services.p50p90 import (
    ORIGINE_ABSENTE, ORIGINE_MESUREE, bankable, variabilite_interannuelle,
)
from apps.calepinage.services.pertes_politique import politique_de_pertes
from apps.calepinage.services.production import production_du_layout
from apps.calepinage.services.pvgis_serie import _Cache, ClientPvgis

FIXTURES = pathlib.Path(__file__).resolve().parent / 'fixtures_pvgis'

POSTES_ESSAI = [{'poste': 'onduleur', 'pct': 2.5, 'source': 'fiche'}]


class SigmaTest(unittest.TestCase):

    def test_une_seule_annee_ne_mesure_aucun_ecart_type(self):
        sigma, origine, annees = variabilite_interannuelle({2020: 13000.0})
        self.assertIsNone(sigma)
        self.assertEqual(origine, ORIGINE_ABSENTE)
        self.assertEqual(annees, 1)

    def test_aucune_annee_du_tout(self):
        self.assertEqual(variabilite_interannuelle({}),
                         (None, ORIGINE_ABSENTE, 0))
        self.assertEqual(variabilite_interannuelle(None),
                         (None, ORIGINE_ABSENTE, 0))

    def test_sigma_est_l_ecart_type_relatif_des_annees_observees(self):
        sigma, origine, annees = variabilite_interannuelle(
            {2018: 1000.0, 2019: 1100.0, 2020: 900.0})
        self.assertEqual(origine, ORIGINE_MESUREE)
        self.assertEqual(annees, 3)
        # σ = écart-type d'échantillon / moyenne — recalculé ici à la main
        # pour que le test ne se contente pas de relire l'implémentation.
        moyenne = 1000.0
        variance = ((1000 - moyenne) ** 2 + (1100 - moyenne) ** 2
                    + (900 - moyenne) ** 2) / 2.0
        self.assertAlmostEqual(sigma, (variance ** 0.5) / moyenne, places=9)

    def test_des_annees_identiques_donnent_un_sigma_nul_mais_MESURE(self):
        sigma, origine, _ = variabilite_interannuelle(
            {2019: 1000.0, 2020: 1000.0})
        self.assertEqual(sigma, 0.0)
        self.assertEqual(origine, ORIGINE_MESUREE)


class BankableTest(unittest.TestCase):

    def test_aucune_perte_n_est_appliquee_une_seconde_fois(self):
        """P50 = la production donnée, à l'arrondi près — pas 0,8 × elle."""
        resultat = bankable(10000.0, kwc=8.0)
        self.assertEqual(resultat['p50_kwh'], 10000.0)

    def test_les_quantiles_descendent_dans_le_bon_ordre(self):
        # CALX184 — il faut un σ MESURÉ pour qu'un quantile existe : sans
        # années observées, il n'y a plus rien à ordonner.
        resultat = bankable(10000.0, totaux_par_annee={
            2019: 9800.0, 2020: 10200.0})
        self.assertLess(resultat['p90_kwh'], resultat['p75_kwh'])
        self.assertLess(resultat['p75_kwh'], resultat['p50_kwh'])

    def test_sigma_mesure_est_publie_avec_son_origine_et_ses_annees(self):
        resultat = bankable(10000.0, totaux_par_annee={
            2018: 9800.0, 2019: 10200.0, 2020: 10000.0})
        self.assertEqual(resultat['sigma_source'], ORIGINE_MESUREE)
        self.assertEqual(resultat['sigma_annees'], 3)
        self.assertIn('MESURÉ', resultat['commentaire'])

    def test_une_seule_annee_refuse_les_quantiles_et_le_dit(self):
        # CALX184 — le repli non sourcé a été supprimé : une seule année sans
        # réglage société ne donne plus AUCUN quantile, et le dit.
        resultat = bankable(10000.0, totaux_par_annee={2020: 10000.0})
        self.assertEqual(resultat['sigma_source'], ORIGINE_ABSENTE)
        self.assertIsNone(resultat['annual_variability'])
        self.assertIsNone(resultat['p90_kwh'])
        self.assertIn('une seule année', resultat['commentaire'])

    def test_un_sigma_mesure_plus_faible_resserre_le_p90(self):
        stable = bankable(10000.0, totaux_par_annee={
            2019: 10000.0, 2020: 10050.0})
        agite = bankable(10000.0, totaux_par_annee={
            2019: 8000.0, 2020: 12000.0})
        self.assertGreater(stable['p90_kwh'], agite['p90_kwh'])

    def test_sans_production_rien_n_est_calcule_et_surtout_pas_zero(self):
        for absente in (None, 0, -5):
            with self.subTest(valeur=absente):
                resultat = bankable(absente)
                self.assertIsNone(resultat['p50_kwh'])
                self.assertIsNone(resultat['p90_kwh'])
                self.assertIsNone(resultat['annual_variability'])


class SansDevisTest(unittest.TestCase):
    """CAL142 — le calepinage PUBLIE ses quantiles sans aucun devis."""

    def setUp(self):
        self.charge = json.loads(
            (FIXTURES / 'seriescalc_casablanca_sud.json')
            .read_text(encoding='utf-8'))

    def transport(self, url, timeout_s):
        return 200, json.dumps(self.charge)

    def calculer(self):
        client = ClientPvgis(self.transport, cache=_Cache(),
                             dormir=lambda _s: None)
        return production_du_layout(
            {'zones': [{'id': 'z1', 'label': 'PAN-SUD',
                        'geometry': {'count': 12, 'kwc': 8.64,
                                     'azimuthDeg': 180.0, 'tiltDeg': 15.0}}]},
            lat=33.5731, lon=-7.5898,
            politique=politique_de_pertes(POSTES_ESSAI), client=client,
            annee_debut=2020, annee_fin=2020)

    def test_le_total_porte_p50_et_refuse_les_quantiles_sans_sigma(self):
        # La fenêtre de cette fixture ne porte qu'UNE année : depuis CALX184,
        # P50 reste servi et les quantiles sont refusés, jamais forfaitisés.
        resultat = self.calculer()
        total = resultat['production']['total']
        self.assertIsNotNone(total['p50_kwh'])
        self.assertIsNone(total['p75_kwh'])
        self.assertIsNone(total['p90_kwh'])
        self.assertIsNone(total['annual_variability'])
        self.assertEqual(total['annual_variability_source'],
                         ORIGINE_ABSENTE)

    def test_aucun_pan_ne_recoit_de_quantile_sans_sigma(self):
        ligne = self.calculer()['production']['par_pan'][0]
        self.assertIsNotNone(ligne['p50_kwh'])
        self.assertIsNone(ligne['p75_kwh'])
        self.assertIsNone(ligne['p90_kwh'])

    def test_l_origine_de_sigma_est_dite_dans_les_avertissements(self):
        avis = self.calculer()['avertissements']
        self.assertTrue(any('σ' in a for a in avis))

    def test_un_pan_vide_ne_recoit_aucun_quantile_invente(self):
        client = ClientPvgis(self.transport, cache=_Cache(),
                             dormir=lambda _s: None)
        resultat = production_du_layout(
            {'zones': [{'id': 'z1', 'label': 'PAN-NU',
                        'geometry': {'count': 0, 'kwc': 0.0,
                                     'azimuthDeg': 180.0, 'tiltDeg': 15.0}}]},
            lat=33.5731, lon=-7.5898,
            politique=politique_de_pertes(POSTES_ESSAI), client=client,
            annee_debut=2020, annee_fin=2020)
        total = resultat['production']['total']
        self.assertIsNone(total['p50_kwh'])
        self.assertIsNone(total['p90_kwh'])
        self.assertIsNone(resultat['production']['par_pan'][0]['p90_kwh'])


if __name__ == '__main__':  # pragma: no cover
    unittest.main()
