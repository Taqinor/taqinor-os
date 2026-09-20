"""CAL163 — la feuille de lestage est PARAMÉTRÉE, jamais devinée.

Quatre garanties, et ce sont exactement celles du « Done » de la tâche :

1. un paramètre NON saisi ⇒ le résultat qui en dépend n'est PAS calculé (et la
   ligne NOMME ce qui manque) — jamais une valeur par défaut ;
2. chaque résultat imprimable porte « paramètres saisis par <société>,
   référence <texte> » ;
3. AUCUNE constante normative dans le code (test de SURFACE : on relit le
   fichier du service et on refuse tout littéral numérique hors des nombres de
   FORME des formules) ;
4. sur un jeu entièrement saisi, le calcul est celui des formules publiées —
   vérifié à la main, chiffre par chiffre.

Tests PURS : aucune base de données, aucun réseau.
"""
from __future__ import annotations

import ast
import pathlib
import unittest

from apps.calepinage.services.lestage import (
    NOMBRES_DE_FORME,
    PARAMETRES,
    feuille_de_lestage,
    normaliser_section_lestage,
)
from apps.calepinage.services.parametres import ReglageInvalide


def _saisie(valeur, source='Texte de référence saisi par la société'):
    return {'valeur': valeur, 'source': source}


#: Un jeu COMPLET, entièrement saisi — des valeurs d'essai, aucune n'étant
#: présentée comme un fait normatif (c'est bien tout le propos de la tâche).
JEU_COMPLET = {
    'masse_volumique_air_kg_m3': _saisie(1.25),
    'vitesse_vent_reference_m_s': _saisie(20.0),
    'categorie_terrain': _saisie('rase campagne'),
    'coefficient_terrain': _saisie(1.0),
    'coefficient_pression_soulevement': _saisie(1.6),
    'coefficient_pression_horizontal': _saisie(0.8),
    'coefficient_frottement': _saisie(0.4),
    'charge_neige_kn_m2': _saisie(0.2),
    'acceleration_pesanteur_m_s2': _saisie(10.0),
    'masse_structure_kg_par_module': _saisie(5.0),
}


def _ligne(feuille, code):
    return next(ligne for ligne in feuille['lignes'] if ligne['code'] == code)


class SectionLestageTest(unittest.TestCase):
    """La saisie : refusée sans source, refusée hors vocabulaire."""

    def test_section_vide_reste_vide(self):
        self.assertEqual(normaliser_section_lestage({}), {})
        self.assertEqual(normaliser_section_lestage(None), {})

    def test_valeur_sans_source_refusee_en_nommant_le_champ(self):
        with self.assertRaises(ReglageInvalide) as capture:
            normaliser_section_lestage(
                {'vitesse_vent_reference_m_s': {'valeur': 26.0}})
        self.assertEqual(capture.exception.champ, 'vitesse_vent_reference_m_s')
        self.assertIn('RÉFÉRENCE', str(capture.exception))

    def test_parametre_inconnu_refuse(self):
        with self.assertRaises(ReglageInvalide) as capture:
            normaliser_section_lestage({'coefficient_magique': _saisie(1.0)})
        self.assertEqual(capture.exception.champ, 'coefficient_magique')

    def test_valeur_non_numerique_refusee(self):
        with self.assertRaises(ReglageInvalide) as capture:
            normaliser_section_lestage(
                {'coefficient_terrain': _saisie('beaucoup')})
        self.assertEqual(capture.exception.champ, 'coefficient_terrain')

    def test_categorie_terrain_est_un_texte(self):
        section = normaliser_section_lestage(
            {'categorie_terrain': _saisie('zone urbaine dense')})
        self.assertEqual(section['categorie_terrain']['valeur'],
                         'zone urbaine dense')


class FeuilleNonCalculeeTest(unittest.TestCase):
    """RIEN de saisi ⇒ RIEN de calculé, et la feuille le dit."""

    def test_aucun_parametre_aucun_resultat(self):
        feuille = feuille_de_lestage({}, surface_module_m2=2.0,
                                     masse_module_kg=22.0, societe='Taqinor')
        self.assertFalse(feuille['calculable'])
        for ligne in feuille['lignes']:
            self.assertIsNone(ligne['valeur'], ligne['code'])
            self.assertTrue(ligne['manquants'], ligne['code'])
            self.assertIn('à saisir', ligne['mention'])
        self.assertEqual(sorted(feuille['manquants']),
                         sorted(PARAMETRES))
        self.assertIn("Aucun paramètre de lestage n'a été saisi",
                      feuille['mention'])

    def test_un_parametre_manquant_ne_calcule_pas_sa_ligne(self):
        section = dict(JEU_COMPLET)
        section.pop('coefficient_pression_soulevement')
        feuille = feuille_de_lestage(normaliser_section_lestage(section),
                                     surface_module_m2=2.0,
                                     masse_module_kg=22.0, societe='Taqinor')
        # La pression dynamique, elle, ne dépend pas du coefficient absent.
        self.assertIsNotNone(_ligne(feuille, 'pression_dynamique')['valeur'])
        manquante = _ligne(feuille, 'pression_soulevement')
        self.assertIsNone(manquante['valeur'])
        self.assertEqual(manquante['manquants'],
                         ['coefficient_pression_soulevement'])
        self.assertIn('Coefficient de pression (soulèvement)',
                      manquante['mention'])

    def test_sans_surface_de_module_aucun_effort(self):
        feuille = feuille_de_lestage(normaliser_section_lestage(JEU_COMPLET),
                                     masse_module_kg=22.0, societe='Taqinor')
        ligne = _ligne(feuille, 'effort_soulevement_module')
        self.assertIsNone(ligne['valeur'])
        self.assertIn('surface_module_m2', ligne['manquants'])


class FeuilleCalculeeTest(unittest.TestCase):
    """Sur un jeu SAISI, le calcul est celui des formules publiées."""

    def setUp(self):
        self.feuille = feuille_de_lestage(
            normaliser_section_lestage(JEU_COMPLET),
            surface_module_m2=2.0, masse_module_kg=22.0,
            societe='Taqinor SARL')

    def test_pression_dynamique(self):
        # q = ½ · 1,25 · (1,0 · 20)² = 250 Pa
        self.assertAlmostEqual(
            _ligne(self.feuille, 'pression_dynamique')['valeur'], 250.0)

    def test_pression_et_effort_de_soulevement(self):
        # p = 250 · 1,6 = 400 Pa ; F = 400 · 2 = 800 N
        self.assertAlmostEqual(
            _ligne(self.feuille, 'pression_soulevement')['valeur'], 400.0)
        self.assertAlmostEqual(
            _ligne(self.feuille, 'effort_soulevement_module')['valeur'], 800.0)

    def test_lest_anti_soulevement(self):
        # m = 800 / 10 − (22 + 5) = 53 kg
        self.assertAlmostEqual(
            _ligne(self.feuille, 'lest_anti_soulevement')['valeur'], 53.0)

    def test_lest_anti_glissement(self):
        # F_h = 250 · 0,8 · 2 = 400 N ; m = 400 / (0,4 · 10) − 27 = 73 kg
        self.assertAlmostEqual(
            _ligne(self.feuille, 'effort_horizontal_module')['valeur'], 400.0)
        self.assertAlmostEqual(
            _ligne(self.feuille, 'lest_anti_glissement')['valeur'], 73.0)

    def test_charge_de_neige(self):
        # F = 0,2 kN/m² · 1000 · 2 m² = 400 N
        self.assertAlmostEqual(
            _ligne(self.feuille, 'charge_neige_module')['valeur'], 400.0)

    def test_lest_jamais_negatif(self):
        section = dict(JEU_COMPLET)
        section['coefficient_pression_soulevement'] = _saisie(0.01)
        feuille = feuille_de_lestage(normaliser_section_lestage(section),
                                     surface_module_m2=2.0,
                                     masse_module_kg=22.0)
        self.assertEqual(
            _ligne(feuille, 'lest_anti_soulevement')['valeur'], 0)

    def test_mention_imprimable_nomme_la_societe_et_la_source(self):
        self.assertIn('paramètres saisis par Taqinor SARL',
                      self.feuille['mention'])
        self.assertIn('Texte de référence saisi par la société',
                      self.feuille['mention'])

    def test_chaque_parametre_publie_sa_source(self):
        publies = {entree['cle']: entree for entree in
                   self.feuille['parametres']}
        self.assertEqual(sorted(publies), sorted(JEU_COMPLET))
        for entree in publies.values():
            self.assertTrue(entree['source'].strip(), entree['cle'])


class AucuneConstanteNormativeTest(unittest.TestCase):
    """Test de SURFACE : le service ne contient AUCUN coefficient écrit."""

    def test_aucun_litteral_numerique_hors_formes(self):
        chemin = (pathlib.Path(__file__).resolve().parent.parent
                  / 'services' / 'lestage.py')
        arbre = ast.parse(chemin.read_text(encoding='utf-8'))
        intrus = []
        for noeud in ast.walk(arbre):
            if isinstance(noeud, ast.Constant) and isinstance(
                    noeud.value, (int, float)) and not isinstance(
                    noeud.value, bool):
                if noeud.value not in NOMBRES_DE_FORME:
                    intrus.append((noeud.lineno, noeud.value))
        self.assertEqual(
            intrus, [],
            "Constante numérique dans services/lestage.py : un coefficient de "
            "vent, de neige ou de terrain se SAISIT avec sa source, il ne "
            "s'écrit jamais dans le code (CAL163).")
