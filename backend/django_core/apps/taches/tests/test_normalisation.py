"""TCH6 — normalisation de saisie et dates pures (unittest pur, sans base ni Django)."""
import unittest
from datetime import date

from apps.taches.saisie.dates_pures import (
    ajouter_mois_borne, fin_de_mois, prochain_jour_semaine)
from apps.taches.saisie.normalisation import cle_nom, normaliser


class NormaliserTests(unittest.TestCase):
    def test_apostrophes(self):
        self.assertEqual(
            normaliser('l’a ‘b’ ʼcʼ ′d'),
            "l'a 'b' 'c' 'd")

    def test_espaces(self):
        self.assertEqual(
            normaliser('a b c d e\tf'), 'a b c d e f')

    def test_traits_d_union(self):
        self.assertEqual(normaliser('après‑demain'), 'apres-demain')
        self.assertEqual(normaliser('a‐b'), 'a-b')

    def test_casse(self):
        self.assertEqual(normaliser('DEMAIN Matin'), 'demain matin')

    def test_casse_longueur_changee_laissee(self):
        # İ minuscule = 2 caractères : laissé tel quel ; ẞ garde la longueur.
        self.assertEqual(normaliser('İ'), 'İ')
        self.assertEqual(len(normaliser('ẞ')), 1)

    def test_accents(self):
        self.assertEqual(normaliser('Été à ça û'),
                         'ete a ca u')

    def test_ligatures_intactes(self):
        self.assertEqual(normaliser('œuvre æ'), 'œuvre æ')

    def test_longueur_egale(self):
        for texte in ('Réunion d’équipe !', 'İstanbul ẞ',
                      'après‑demain\tœ', ''):
            self.assertEqual(len(normaliser(texte)), len(texte), texte)

    def test_cle_nom(self):
        self.assertEqual(cle_nom('  Mon Projet-été_1 '), 'monprojetete1')
        self.assertEqual(cle_nom('Mon projet'), cle_nom('mon-projet'))
        self.assertEqual(cle_nom('A_B - C'), 'abc')


class DatesPuresTests(unittest.TestCase):
    def test_prochain_jour_semaine(self):
        mardi = date(2026, 11, 17)
        self.assertEqual(prochain_jour_semaine(mardi, 0), date(2026, 11, 23))
        self.assertEqual(prochain_jour_semaine(mardi, 1), date(2026, 11, 24))
        self.assertEqual(
            prochain_jour_semaine(mardi, 1, inclure=True), mardi)
        self.assertEqual(prochain_jour_semaine(mardi, 2), date(2026, 11, 18))

    def test_ajouter_mois_borne(self):
        self.assertEqual(ajouter_mois_borne(date(2026, 1, 31), 1),
                         date(2026, 2, 28))
        self.assertEqual(ajouter_mois_borne(date(2028, 1, 31), 1),
                         date(2028, 2, 29))
        self.assertEqual(ajouter_mois_borne(date(2026, 11, 30), 3),
                         date(2027, 2, 28))
        self.assertEqual(ajouter_mois_borne(date(2026, 3, 15), -3),
                         date(2025, 12, 15))
        self.assertEqual(ajouter_mois_borne(date(2026, 5, 5), 0),
                         date(2026, 5, 5))

    def test_fin_de_mois(self):
        self.assertEqual(fin_de_mois(date(2026, 2, 3)), date(2026, 2, 28))
        self.assertEqual(fin_de_mois(date(2028, 2, 3)), date(2028, 2, 29))
        self.assertEqual(fin_de_mois(date(2026, 12, 31)), date(2026, 12, 31))
