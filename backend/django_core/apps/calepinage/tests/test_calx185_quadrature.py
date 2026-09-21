"""CALX185 — σ se COMPOSE en quadrature, sur des composantes sourcées.

Ce que ce fichier garde : ``sigma_total = sqrt(Σ σᵢ²)`` n'admet QUE des
composantes sourcées, vaut exactement la composante unique quand il n'y en a
qu'une, croît quand une composante s'ajoute — et une composante sans
provenance est REFUSÉE en la nommant, jamais comptée ni ignorée en silence.

La forme du bloc est celle du contrat committé
``contract_samples/calepinage_incertitude.json`` (CALX144) : ce fichier la
relit pour que le service et le contrat ne puissent pas diverger.

Aucune base de données, aucun réseau.

Run :
    python manage.py test apps.calepinage.tests.test_calx185_quadrature
"""
from __future__ import annotations

import json
import math
import pathlib
import unittest

from apps.calepinage.services.incertitude import (
    COMPOSANTE_BIAIS, COMPOSANTE_METEO, COMPOSANTE_MODELE,
    IncertitudeInvalide, METHODE_QUADRATURE, PORTEE_ANNUELLE, SOURCE_PVGIS,
    SOURCE_SOCIETE, SOURCE_TEXTE, bloc_incertitude,
)
from apps.calepinage.services.p50p90 import bankable

ECHANTILLONS = (pathlib.Path(__file__).resolve().parents[1]
                / 'contract_samples')

CONTRAT = json.loads((ECHANTILLONS / 'calepinage_incertitude.json')
                     .read_text(encoding='utf-8'))

#: Une production d'essai — un PLACEHOLDER, aucune installation réelle.
PRODUCTION_ESSAI = 13000.0

#: Deux années observées : de quoi MESURER la composante météo.
DEUX_ANNEES = {2019: 12500.0, 2020: 13500.0}


def _saisi(cle, valeur_pct, *, source='societe', reference='Étude interne'):
    return {cle: {'valeur': valeur_pct, 'source': source,
                  'reference': reference}}


class FormeDuBlocTest(unittest.TestCase):
    """Le service rend EXACTEMENT les clés du contrat committé."""

    def test_les_clefs_sont_celles_du_contrat(self):
        attendu = sorted(CONTRAT['exemple']['incertitude'])
        bloc = bloc_incertitude(PRODUCTION_ESSAI,
                                totaux_par_annee=DEUX_ANNEES)
        self.assertEqual(sorted(bloc), attendu)

    def test_chaque_composante_porte_les_cinq_champs_du_contrat(self):
        attendu = set(CONTRAT['exemple']['incertitude']['composantes'][0])
        bloc = bloc_incertitude(
            PRODUCTION_ESSAI, totaux_par_annee=DEUX_ANNEES,
            reglages=_saisi('sigma_modele_pct', 3.0))
        self.assertEqual(len(bloc['composantes']), 2)
        for composante in bloc['composantes']:
            self.assertEqual(set(composante), attendu)

    def test_la_portee_est_declaree_annuelle(self):
        bloc = bloc_incertitude(PRODUCTION_ESSAI,
                                totaux_par_annee=DEUX_ANNEES)
        self.assertEqual(bloc['portee'], PORTEE_ANNUELLE)

    def test_toute_composante_publiee_est_sourcee_et_referencee(self):
        bloc = bloc_incertitude(
            PRODUCTION_ESSAI, totaux_par_annee=DEUX_ANNEES,
            reglages={**_saisi('sigma_modele_pct', 3.0),
                      **_saisi('sigma_biais_meteo_pct', 2.0,
                               source='texte', reference='PVsyst')})
        self.assertEqual(len(bloc['composantes']), 3)
        for composante in bloc['composantes']:
            self.assertIn(composante['source'],
                          (SOURCE_PVGIS, SOURCE_SOCIETE, SOURCE_TEXTE))
            self.assertTrue(composante['reference'].strip(),
                            composante['nom'])


class QuadratureTest(unittest.TestCase):
    """La propriété : σ croît, et vaut la composante unique quand elle est seule."""

    def test_une_seule_composante_vaut_exactement_cette_composante(self):
        bloc = bloc_incertitude(PRODUCTION_ESSAI,
                                totaux_par_annee=DEUX_ANNEES)
        self.assertEqual(len(bloc['composantes']), 1)
        self.assertAlmostEqual(bloc['sigma_total'],
                               bloc['composantes'][0]['sigma_relatif'],
                               places=6)
        self.assertEqual(bloc['methode'], METHODE_QUADRATURE)

    def test_sigma_total_croit_quand_une_composante_s_ajoute(self):
        seule = bloc_incertitude(PRODUCTION_ESSAI,
                                 totaux_par_annee=DEUX_ANNEES)
        deux = bloc_incertitude(PRODUCTION_ESSAI,
                                totaux_par_annee=DEUX_ANNEES,
                                reglages=_saisi('sigma_modele_pct', 3.0))
        trois = bloc_incertitude(
            PRODUCTION_ESSAI, totaux_par_annee=DEUX_ANNEES,
            reglages={**_saisi('sigma_modele_pct', 3.0),
                      **_saisi('sigma_biais_meteo_pct', 2.0)})
        self.assertLess(seule['sigma_total'], deux['sigma_total'])
        self.assertLess(deux['sigma_total'], trois['sigma_total'])

    def test_sigma_total_est_la_racine_de_la_somme_des_carres(self):
        bloc = bloc_incertitude(
            PRODUCTION_ESSAI, totaux_par_annee=DEUX_ANNEES,
            reglages={**_saisi('sigma_modele_pct', 3.0),
                      **_saisi('sigma_biais_meteo_pct', 2.0)})
        attendu = math.sqrt(sum(c['sigma_relatif'] ** 2
                                for c in bloc['composantes']))
        self.assertAlmostEqual(bloc['sigma_total'], attendu, places=6)

    def test_les_trois_composantes_de_pvsyst_sont_nommees(self):
        bloc = bloc_incertitude(
            PRODUCTION_ESSAI, totaux_par_annee=DEUX_ANNEES,
            reglages={**_saisi('sigma_modele_pct', 3.0),
                      **_saisi('sigma_biais_meteo_pct', 2.0)})
        self.assertEqual([c['nom'] for c in bloc['composantes']],
                         [COMPOSANTE_METEO, COMPOSANTE_MODELE,
                          COMPOSANTE_BIAIS])


class ComposanteSansSourceTest(unittest.TestCase):
    """Un chiffre sans origine n'entre pas dans σ, et on dit lequel."""

    def test_une_composante_sans_source_est_refusee_en_la_nommant(self):
        with self.assertRaises(IncertitudeInvalide) as capture:
            bloc_incertitude(
                PRODUCTION_ESSAI, totaux_par_annee=DEUX_ANNEES,
                reglages=_saisi('sigma_biais_meteo_pct', 2.0, source=''))
        self.assertEqual(capture.exception.champ, 'sigma_biais_meteo_pct')
        self.assertIn('Biais long terme', capture.exception.motif)
        self.assertIn('source', capture.exception.motif)

    def test_le_refus_vaut_pour_chaque_composante_saisie(self):
        for cle in ('sigma_modele_pct', 'sigma_biais_meteo_pct',
                    'sigma_meteo_saisi_pct'):
            with self.subTest(cle=cle):
                with self.assertRaises(IncertitudeInvalide) as capture:
                    bloc_incertitude(PRODUCTION_ESSAI,
                                     reglages=_saisi(cle, 3.0, source=''))
                self.assertEqual(capture.exception.champ, cle)


class AucuneComposanteTest(unittest.TestCase):
    """Sans composante sourcée : des nuls et un motif, jamais un chiffre."""

    def test_aucune_composante_laisse_sigma_nul_avec_un_motif(self):
        bloc = bloc_incertitude(PRODUCTION_ESSAI,
                                totaux_par_annee={2020: PRODUCTION_ESSAI})
        self.assertEqual(bloc['composantes'], [])
        self.assertIsNone(bloc['sigma_total'])
        self.assertIsNone(bloc['methode'])
        self.assertTrue(bloc['motif_refus'].strip())

    def test_p50_reste_servi_et_les_autres_quantiles_sont_nuls(self):
        quantiles = bloc_incertitude(
            PRODUCTION_ESSAI,
            totaux_par_annee={2020: PRODUCTION_ESSAI})['quantiles']
        self.assertEqual(quantiles['p50_kwh'], PRODUCTION_ESSAI)
        for cle, valeur in quantiles.items():
            if cle != 'p50_kwh':
                self.assertIsNone(valeur, cle)

    def test_jamais_un_motif_quand_sigma_existe(self):
        bloc = bloc_incertitude(PRODUCTION_ESSAI,
                                totaux_par_annee=DEUX_ANNEES)
        self.assertEqual(bloc['motif_refus'], '')

    def test_sans_production_tout_est_nul(self):
        bloc = bloc_incertitude(None)
        self.assertIsNone(bloc['portee'])
        self.assertIsNone(bloc['sigma_total'])
        for valeur in bloc['quantiles'].values():
            self.assertIsNone(valeur)
        self.assertTrue(bloc['motif_refus'].strip())


class QuantilesSuiventSigmaTest(unittest.TestCase):
    """P90 s'éloigne de P50 quand σ croît — la propriété qui compte."""

    def test_p90_s_eloigne_de_p50_quand_sigma_croit(self):
        seule = bloc_incertitude(PRODUCTION_ESSAI,
                                 totaux_par_annee=DEUX_ANNEES)['quantiles']
        trois = bloc_incertitude(
            PRODUCTION_ESSAI, totaux_par_annee=DEUX_ANNEES,
            reglages={**_saisi('sigma_modele_pct', 3.0),
                      **_saisi('sigma_biais_meteo_pct', 2.0)})['quantiles']
        self.assertLess(trois['p90_kwh'], seule['p90_kwh'])
        self.assertLess(trois['p75_kwh'], seule['p75_kwh'])

    def test_bankable_consomme_le_sigma_compose(self):
        """``p50p90.bankable`` emploie σ TOTAL, pas la seule météo."""
        seule = bankable(PRODUCTION_ESSAI, totaux_par_annee=DEUX_ANNEES)
        compose = bankable(
            PRODUCTION_ESSAI, totaux_par_annee=DEUX_ANNEES,
            reglages={**_saisi('sigma_modele_pct', 3.0),
                      **_saisi('sigma_biais_meteo_pct', 2.0)})
        self.assertGreater(compose['annual_variability'],
                           seule['annual_variability'])
        self.assertLess(compose['p90_kwh'], seule['p90_kwh'])

    def test_bankable_dit_de_quoi_sigma_est_fait(self):
        commentaire = bankable(
            PRODUCTION_ESSAI, totaux_par_annee=DEUX_ANNEES,
            reglages=_saisi('sigma_modele_pct', 3.0))['commentaire']
        self.assertIn('quadrature', commentaire)
        self.assertIn(COMPOSANTE_MODELE, commentaire)


if __name__ == '__main__':  # pragma: no cover
    unittest.main()
