"""CALX184 — σ se MESURE, se SAISIT avec sa source, ou les quantiles sont nuls.

Ce que ce fichier garde : le repli non sourcé de ``apps/ventes/solar_design``
ne revient pas, sous aucune forme. Trois origines seulement sont admises pour
la variabilité interannuelle — mesurée sur la fenêtre PVGIS, saisie et sourcée
par la société (réglage CALX145), ou rien — et « rien » se lit dans le
résultat : P75/P90/P95 restent nuls et un motif français dit quoi renseigner.

Aucune base de données, aucun réseau.

Run :
    python manage.py test apps.calepinage.tests.test_calx184_sigma
"""
from __future__ import annotations

import pathlib
import unittest

from apps.calepinage.services.p50p90 import (
    CLE_SIGMA_METEO_SAISI, IncertitudeInvalide, ORIGINE_ABSENTE,
    ORIGINE_MESUREE, ORIGINE_SAISIE, bankable, variabilite_interannuelle,
)

#: Le module scanné par la garde d'import.
MODULE = pathlib.Path(__file__).resolve().parents[1]

#: Le nom du littéral banni, écrit par morceaux pour que la garde ne se
#: dénonce pas elle-même quand elle balaie son propre paquet.
BANNI = 'DEFAULT_ANNUAL' + '_VARIABILITY'

#: Les DEUX fichiers de test autorisés à écrire ce nom : celui-ci, qui porte
#: la garde, et celui de CALX144, qui interdit au contrat committé de publier
#: cette valeur. Un test qui interdit un nom doit pouvoir l'écrire.
CITATIONS_ADMISES = ('test_calx184_sigma.py',
                     'test_calx144_contrat_incertitude.py')

#: Une production d'essai — un PLACEHOLDER, aucune installation réelle.
PRODUCTION_ESSAI = 10000.0


def _reglage(valeur_pct, *, source='societe', reference='Étude interne'):
    """La forme CALX145 d'un réglage société : ``{valeur, source, reference}``."""
    return {CLE_SIGMA_METEO_SAISI: {'valeur': valeur_pct, 'source': source,
                                    'reference': reference}}


class ReplinNonSourceTest(unittest.TestCase):
    """Le littéral sans citation ne doit plus exister dans le module."""

    def test_le_litteral_sans_citation_n_est_plus_importe(self):
        fautifs = []
        for chemin in sorted(MODULE.rglob('*.py')):
            if 'migrations' in chemin.relative_to(MODULE).parts:
                continue
            if chemin.name in CITATIONS_ADMISES:
                continue
            if BANNI in chemin.read_text(encoding='utf-8'):
                fautifs.append(str(chemin.relative_to(MODULE)))
        self.assertEqual(fautifs, [], msg=(
            f'Le littéral « {BANNI} » de apps/ventes/solar_design.py n\'a '
            'aucune citation dans le dépôt : un P90 bâti dessus serait un '
            'chiffre sans origine (D-CALX 7). CALX184 le supprime.'))


class SigmaRefuseTest(unittest.TestCase):
    """Une seule année et aucun réglage : on refuse, on ne devine pas."""

    def test_une_seule_annee_sans_reglage_ne_publie_aucun_quantile(self):
        resultat = bankable(PRODUCTION_ESSAI,
                            totaux_par_annee={2020: PRODUCTION_ESSAI})
        self.assertIsNone(resultat['p75_kwh'])
        self.assertIsNone(resultat['p90_kwh'])
        # CALX186 publiera la clé ``p95_kwh`` : elle est nulle ici aussi.
        self.assertIsNone(resultat.get('p95_kwh'))
        self.assertIsNone(resultat['annual_variability'])
        self.assertEqual(resultat['sigma_source'], ORIGINE_ABSENTE)

    def test_le_refus_est_un_motif_francais_qui_dit_quoi_renseigner(self):
        motif = bankable(PRODUCTION_ESSAI,
                         totaux_par_annee={2020: PRODUCTION_ESSAI})[
            'commentaire']
        self.assertIn('σ', motif)
        self.assertIn('une seule année', motif)
        self.assertIn('réglages de simulation', motif)
        self.assertNotIn('hypoth', motif.lower(),
                         "Plus aucune « hypothèse » : il n'y a plus de "
                         'valeur de repli à annoncer.')

    def test_p50_reste_servi_quand_sigma_est_refuse(self):
        """P50 n'est pas déduit de σ : c'est la production simulée."""
        resultat = bankable(PRODUCTION_ESSAI, kwc=8.0,
                            totaux_par_annee={2020: PRODUCTION_ESSAI})
        self.assertEqual(resultat['p50_kwh'], PRODUCTION_ESSAI)
        self.assertIsNotNone(resultat['specific_yield_kwh_kwc'])

    def test_aucune_annee_du_tout_refuse_aussi(self):
        resultat = bankable(PRODUCTION_ESSAI)
        self.assertIsNone(resultat['p90_kwh'])
        self.assertEqual(resultat['sigma_source'], ORIGINE_ABSENTE)


class SigmaMesureTest(unittest.TestCase):
    """Le chemin qui existait déjà, et qui reste le premier servi."""

    def test_cinq_annees_donnent_un_sigma_mesure_sur_cinq_annees(self):
        resultat = bankable(PRODUCTION_ESSAI, totaux_par_annee={
            2016: 9800.0, 2017: 10200.0, 2018: 10000.0,
            2019: 9900.0, 2020: 10100.0})
        self.assertEqual(resultat['sigma_source'], ORIGINE_MESUREE)
        self.assertEqual(resultat['sigma_annees'], 5)
        self.assertIsNotNone(resultat['p90_kwh'])
        self.assertLess(resultat['p90_kwh'], resultat['p50_kwh'])

    def test_une_seule_annee_ne_mesure_aucun_ecart_type(self):
        sigma, origine, annees = variabilite_interannuelle({2020: 13000.0})
        self.assertIsNone(sigma)
        self.assertEqual(origine, ORIGINE_ABSENTE)
        self.assertEqual(annees, 1)

    def test_la_mesure_prime_sur_la_saisie(self):
        """Deux années observées valent mieux qu'un chiffre arrêté au bureau."""
        resultat = bankable(PRODUCTION_ESSAI,
                            totaux_par_annee={2019: 9900.0, 2020: 10100.0},
                            reglages=_reglage(9.0))
        self.assertEqual(resultat['sigma_source'], ORIGINE_MESUREE)


class SigmaSaisiTest(unittest.TestCase):
    """La deuxième origine admise : la société, avec sa provenance."""

    def test_un_sigma_saisi_et_source_rend_les_quantiles(self):
        resultat = bankable(PRODUCTION_ESSAI,
                            totaux_par_annee={2020: PRODUCTION_ESSAI},
                            reglages=_reglage(4.8))
        self.assertEqual(resultat['sigma_source'], ORIGINE_SAISIE)
        self.assertAlmostEqual(resultat['annual_variability'], 0.048,
                               places=4)
        self.assertIsNotNone(resultat['p90_kwh'])
        self.assertLess(resultat['p90_kwh'], resultat['p75_kwh'])

    def test_le_sigma_saisi_n_est_pas_compte_comme_mesure(self):
        resultat = bankable(PRODUCTION_ESSAI, reglages=_reglage(4.8))
        self.assertIsNone(resultat['sigma_annees'],
                          'Un σ saisi n’a été mesuré sur AUCUNE année : '
                          'écrire 0 se lirait « mesuré sur zéro année ».')
        self.assertIn('Étude interne', resultat['commentaire'])

    def test_un_sigma_saisi_sans_source_est_refuse_en_nommant_le_champ(self):
        with self.assertRaises(IncertitudeInvalide) as capture:
            bankable(PRODUCTION_ESSAI, reglages=_reglage(4.8, source=''))
        self.assertEqual(capture.exception.champ, CLE_SIGMA_METEO_SAISI)
        self.assertIn('source', capture.exception.motif)

    def test_un_sigma_saisi_illisible_est_refuse_en_nommant_le_champ(self):
        for valeur in ('beaucoup', None, [1]):
            with self.subTest(valeur=valeur):
                with self.assertRaises(IncertitudeInvalide) as capture:
                    bankable(PRODUCTION_ESSAI, reglages=_reglage(valeur))
                self.assertEqual(capture.exception.champ,
                                 CLE_SIGMA_METEO_SAISI)

    def test_un_sigma_saisi_negatif_est_refuse(self):
        with self.assertRaises(IncertitudeInvalide) as capture:
            bankable(PRODUCTION_ESSAI, reglages=_reglage(-2.0))
        self.assertEqual(capture.exception.champ, CLE_SIGMA_METEO_SAISI)

    def test_une_section_de_reglages_vide_ne_change_rien(self):
        """Rien de saisi = comportement d'aujourd'hui (D-CALX 12)."""
        for vide in (None, {}, {'mode_meteo': {'valeur': 'tmy',
                                               'source': 'societe',
                                               'reference': ''}}):
            with self.subTest(reglages=vide):
                resultat = bankable(PRODUCTION_ESSAI, reglages=vide)
                self.assertEqual(resultat['sigma_source'], ORIGINE_ABSENTE)


if __name__ == '__main__':  # pragma: no cover
    unittest.main()
