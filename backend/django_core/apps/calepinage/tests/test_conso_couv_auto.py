"""CAL150 — couverture = part AUTOCONSOMMÉE, jamais production ÷ consommation.

Ce que ces tests tiennent :

* le test ÉCHOUE si une sortie du module expose un taux calculé comme
  production ÷ consommation (cas construit exprès : production = 2 ×
  consommation, et pourtant couverture < 100 %) ;
* sans courbe horaire, AUCUN taux n'est publié (pas de forfait) ;
* aucun ratio forfaitaire d'autoconsommation n'existe dans le module (test de
  surface sur les sources).

Tests PURS : aucune base, aucun réseau.
"""
from __future__ import annotations

import ast
import pathlib
import unittest

from apps.calepinage.services.autoconsommation import (
    MOTIF_SANS_COURBE, BilanInvalide, bilan_autoconsommation,
)

RACINE_MODULE = pathlib.Path(__file__).resolve().parent.parent

#: Une journée : consommation à plat, production en cloche diurne.
CONSO_PLATE = [1.0] * 24
PROD_CLOCHE = ([0.0] * 6 + [1.0, 2.0, 3.0, 4.0, 5.0, 6.0]
               + [6.0, 5.0, 4.0, 3.0, 2.0, 1.0] + [0.0] * 6)


class CouvAutoTest(unittest.TestCase):

    def test_la_couverture_n_est_PAS_production_sur_consommation(self):
        """Production BIEN SUPÉRIEURE à la consommation, couverture < 100 %."""
        bilan = bilan_autoconsommation(CONSO_PLATE, PROD_CLOCHE)
        ratio_interdit = bilan['production_kwh'] / bilan['consommation_kwh']
        # Le cas qui piège : le ratio interdit dépasse 1 (il se lirait
        # « 175 % des besoins couverts »)…
        self.assertGreater(ratio_interdit, 1.0)
        # …alors que la couverture RÉELLE, elle, reste sous 100 %.
        self.assertLess(bilan['taux_couverture'], 1.0)
        self.assertNotEqual(bilan['taux_couverture'], ratio_interdit)

    def test_la_couverture_est_l_autoconsomme_sur_la_consommation(self):
        bilan = bilan_autoconsommation(CONSO_PLATE, PROD_CLOCHE)
        self.assertAlmostEqual(
            bilan['taux_couverture'],
            round(bilan['autoconsomme_kwh'] / bilan['consommation_kwh'], 4),
            places=4)

    def test_le_taux_d_autoconsommation_est_l_autoconsomme_sur_la_production(self):
        bilan = bilan_autoconsommation(CONSO_PLATE, PROD_CLOCHE)
        self.assertAlmostEqual(
            bilan['taux_autoconsommation'],
            round(bilan['autoconsomme_kwh'] / bilan['production_kwh'], 4),
            places=4)

    def test_un_champ_geant_ne_couvre_jamais_plus_de_100_pour_cent(self):
        enorme = [valeur * 50 for valeur in PROD_CLOCHE]
        bilan = bilan_autoconsommation(CONSO_PLATE, enorme)
        self.assertLessEqual(bilan['taux_couverture'], 1.0)

    def test_les_totaux_se_referment(self):
        bilan = bilan_autoconsommation(CONSO_PLATE, PROD_CLOCHE)
        self.assertAlmostEqual(
            bilan['autoconsomme_kwh'] + bilan['import_reseau_kwh'],
            bilan['consommation_kwh'], places=3)
        self.assertAlmostEqual(
            bilan['autoconsomme_kwh'] + bilan['surplus_kwh'],
            bilan['production_kwh'], places=3)

    def test_la_definition_publiee_dit_la_regle(self):
        bilan = bilan_autoconsommation(CONSO_PLATE, PROD_CLOCHE)
        self.assertIn('COUV-AUTO', bilan['definition'])


class SansCourbeTest(unittest.TestCase):

    def test_sans_courbe_aucun_taux_n_est_publie(self):
        for charge, production in ((None, PROD_CLOCHE),
                                   (CONSO_PLATE, None),
                                   ([], []), (None, None)):
            with self.subTest(charge=bool(charge), prod=bool(production)):
                bilan = bilan_autoconsommation(charge, production)
                self.assertFalse(bilan['publiable'])
                self.assertIsNone(bilan['taux_couverture'])
                self.assertIsNone(bilan['taux_autoconsommation'])
                self.assertEqual(bilan['motif'], MOTIF_SANS_COURBE)

    def test_deux_periodes_differentes_sont_refusees(self):
        with self.assertRaises(BilanInvalide) as refus:
            bilan_autoconsommation(CONSO_PLATE, PROD_CLOCHE * 12)
        self.assertIn('même période', str(refus.exception))

    def test_une_heure_illisible_nomme_son_rang(self):
        mauvaise = list(CONSO_PLATE)
        mauvaise[5] = 'beaucoup'
        with self.assertRaises(BilanInvalide) as refus:
            bilan_autoconsommation(mauvaise, PROD_CLOCHE)
        self.assertEqual(refus.exception.champ, 'consommation[5]')


class SurfaceAucunForfaitTest(unittest.TestCase):
    """Aucun ratio d'autoconsommation forfaitaire dans le module."""

    #: Les noms des ratios forfaitaires de l'écran devis. Ils n'ont RIEN à
    #: faire ici : le module calcule, il ne recopie pas un pourcentage.
    NOMS_INTERDITS = ('AUTOCONSO_SANS', 'AUTOCONSO_AVEC',
                      'TAUX_AUTOCONSO_DEFAUT')

    def test_aucun_ratio_forfaitaire_n_est_employe(self):
        fautifs = []
        for chemin in RACINE_MODULE.rglob('*.py'):
            if 'tests' in chemin.parts or 'migrations' in chemin.parts:
                continue
            arbre = ast.parse(chemin.read_text(encoding='utf-8'),
                              filename=str(chemin))
            identifiants = set()
            for noeud in ast.walk(arbre):
                if isinstance(noeud, ast.Name):
                    identifiants.add(noeud.id)
                elif isinstance(noeud, ast.Attribute):
                    identifiants.add(noeud.attr)
                elif isinstance(noeud, ast.alias):
                    identifiants.add(noeud.name.split('.')[-1])
            for nom in self.NOMS_INTERDITS:
                if nom in identifiants:
                    fautifs.append(f'{chemin.name} : {nom}')
        self.assertEqual(fautifs, [], '; '.join(fautifs))

    def test_le_croisement_vient_du_moteur_unique(self):
        """Une seconde arithmétique d'autoconsommation finirait par diverger."""
        from apps.calepinage.services import autoconsommation

        self.assertIs(
            autoconsommation.hourly_self_consumption.__module__.endswith(
                'solar_design'), True)


if __name__ == '__main__':  # pragma: no cover
    unittest.main()
