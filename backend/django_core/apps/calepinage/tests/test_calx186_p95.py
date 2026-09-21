"""CALX186 — P95 rejoint les quantiles publiés, et P99 n'y entre pas.

Ce que ce fichier garde :

* l'ORDRE est strict dès que σ > 0 — ``p50 > p75 > p90 > p95`` : un P95 qui
  passerait au-dessus d'un P90 rendrait la page illisible pour une banque ;
* σ = 0 (deux années rigoureusement identiques, une mesure, pas une absence)
  rend les QUATRE égaux : c'est la conséquence arithmétique, pas un repli ;
* la CONTINUITÉ avec le chemin historique : les quantiles calculés ici
  retombent sur ``simulate_bankable_yield`` pour P75 et P90 à 0,1 % près. La
  table à deux entrées du moteur de ventes est remplacée par la fonction
  quantile de la loi normale, sans déplacer les chiffres déjà publiés ;
* P99 n'est PAS publié (question fondateur ouverte Q3).

Aucune base de données, aucun réseau.

Run :
    python manage.py test apps.calepinage.tests.test_calx186_p95
"""
from __future__ import annotations

import statistics
import unittest

from apps.calepinage.services.incertitude import (
    DEPASSEMENTS, bloc_incertitude,
)
from apps.calepinage.services.p50p90 import bankable
from apps.ventes.solar_design import simulate_bankable_yield

#: Une production d'essai — un PLACEHOLDER, aucune installation réelle.
PRODUCTION_ESSAI = 13000.0

#: L'ordre attendu des quantiles publiés, du moins au plus conservateur.
ORDRE = ('p50_kwh', 'p75_kwh', 'p90_kwh', 'p95_kwh')


def _reglage_meteo(valeur_pct):
    """Un σ météo SAISI et sourcé : le levier le plus simple pour faire
    varier σ sans fabriquer une fausse série d'années."""
    return {'sigma_meteo_saisi_pct': {'valeur': valeur_pct,
                                      'source': 'societe',
                                      'reference': 'Étude interne'}}


class QuantilesPubliesTest(unittest.TestCase):

    def test_les_quatre_quantiles_sont_publies(self):
        quantiles = bloc_incertitude(
            PRODUCTION_ESSAI, reglages=_reglage_meteo(4.8))['quantiles']
        self.assertEqual(sorted(quantiles), sorted(ORDRE))

    def test_p99_n_est_pas_publie(self):
        quantiles = bloc_incertitude(
            PRODUCTION_ESSAI, reglages=_reglage_meteo(4.8))['quantiles']
        self.assertNotIn('p99_kwh', quantiles,
                         'P99 reste une question fondateur ouverte : une '
                         "queue à 1 % sur une loi ajustée sur peu d'années "
                         'prêterait à confusion.')
        self.assertNotIn('p99_kwh', [cle for cle, _ in DEPASSEMENTS])

    def test_bankable_publie_aussi_p95(self):
        resultat = bankable(PRODUCTION_ESSAI, reglages=_reglage_meteo(4.8))
        self.assertIsNotNone(resultat['p95_kwh'])
        self.assertLess(resultat['p95_kwh'], resultat['p90_kwh'])


class OrdreStrictTest(unittest.TestCase):

    def test_l_ordre_est_strict_des_que_sigma_est_positif(self):
        for pourcent in (0.5, 2.0, 4.8, 9.0):
            with self.subTest(sigma_pct=pourcent):
                quantiles = bloc_incertitude(
                    PRODUCTION_ESSAI,
                    reglages=_reglage_meteo(pourcent))['quantiles']
                valeurs = [quantiles[cle] for cle in ORDRE]
                for avant, apres in zip(valeurs, valeurs[1:]):
                    self.assertGreater(avant, apres)

    def test_un_sigma_nul_rend_les_quatre_egaux(self):
        """Deux années identiques : σ = 0 est une MESURE, pas une absence."""
        bloc = bloc_incertitude(
            PRODUCTION_ESSAI,
            totaux_par_annee={2019: PRODUCTION_ESSAI, 2020: PRODUCTION_ESSAI})
        self.assertEqual(bloc['sigma_total'], 0.0)
        valeurs = {bloc['quantiles'][cle] for cle in ORDRE}
        self.assertEqual(valeurs, {PRODUCTION_ESSAI})

    def test_sans_sigma_seul_p50_survit(self):
        quantiles = bloc_incertitude(
            PRODUCTION_ESSAI,
            totaux_par_annee={2020: PRODUCTION_ESSAI})['quantiles']
        self.assertEqual(quantiles['p50_kwh'], PRODUCTION_ESSAI)
        for cle in ORDRE[1:]:
            self.assertIsNone(quantiles[cle], cle)


class ContinuiteAvecLeMoteurDeVentesTest(unittest.TestCase):
    """Les chiffres déjà publiés ne bougent pas — à 0,1 % près."""

    def _pertes_neutres(self):
        from apps.ventes.solar_design import DEFAULT_LOSS_FACTORS
        return {poste: 0.0 for poste in DEFAULT_LOSS_FACTORS}

    def test_p75_et_p90_retombent_sur_simulate_bankable_yield(self):
        for pourcent in (2.0, 4.8, 6.5, 9.0):
            with self.subTest(sigma_pct=pourcent):
                sigma = pourcent / 100.0
                attendu = simulate_bankable_yield(
                    PRODUCTION_ESSAI, loss_factors=self._pertes_neutres(),
                    annual_variability=sigma, include_p75=True)
                obtenu = bloc_incertitude(
                    PRODUCTION_ESSAI,
                    reglages=_reglage_meteo(pourcent))['quantiles']
                for cle in ('p75_kwh', 'p90_kwh'):
                    ecart = abs(obtenu[cle] - attendu[cle]) / attendu[cle]
                    self.assertLess(
                        ecart, 0.001,
                        f'{cle} : écart de {ecart:.5%} avec le moteur de '
                        'ventes — la fonction quantile a déplacé un chiffre '
                        'déjà publié.')

    def test_p95_suit_la_meme_loi_normale(self):
        sigma = 0.048
        quantiles = bloc_incertitude(
            PRODUCTION_ESSAI, reglages=_reglage_meteo(4.8))['quantiles']
        loi = statistics.NormalDist()
        attendu = PRODUCTION_ESSAI * (1.0 + loi.inv_cdf(1.0 - 0.95) * sigma)
        self.assertAlmostEqual(quantiles['p95_kwh'], attendu, places=1)


if __name__ == '__main__':  # pragma: no cover
    unittest.main()
