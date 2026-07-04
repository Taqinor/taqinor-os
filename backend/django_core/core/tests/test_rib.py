"""Tests XACC24 — Validateur RIB marocain (core.rib, fondation partagée).

Couvre : un RIB à clé fausse est signalé (jamais d'exception), un RIB valide
passe le contrôle mod 97, la normalisation tolère espaces/tirets, et le
diagnostic renvoie des erreurs explicites sans jamais bloquer.
"""
from django.test import SimpleTestCase

from core.rib import cle_rib_valide, normaliser_rib, valider_rib

RIB_VALIDE_1 = '123456789012345678901213'
RIB_VALIDE_2 = '070001234598765432109842'


class RibValidatorTests(SimpleTestCase):
    def test_rib_valide_cle_correcte(self):
        self.assertTrue(cle_rib_valide(RIB_VALIDE_1))
        self.assertTrue(cle_rib_valide(RIB_VALIDE_2))

    def test_rib_cle_fausse_signale(self):
        rib_faux = RIB_VALIDE_1[:-2] + '99'
        self.assertFalse(cle_rib_valide(rib_faux))
        diagnostic = valider_rib(rib_faux)
        self.assertFalse(diagnostic['valide'])
        self.assertTrue(diagnostic['erreurs'])

    def test_longueur_incorrecte_jamais_exception(self):
        self.assertFalse(cle_rib_valide('12345'))
        diagnostic = valider_rib('12345')
        self.assertFalse(diagnostic['valide'])
        self.assertIn('24 chiffres', diagnostic['erreurs'][0])

    def test_rib_vide_jamais_exception(self):
        diagnostic = valider_rib('')
        self.assertFalse(diagnostic['valide'])
        diagnostic_none = valider_rib(None)
        self.assertFalse(diagnostic_none['valide'])

    def test_normalisation_espaces_tirets(self):
        rib_espace = '1234 5678 9012 3456 7890 1213'
        self.assertEqual(normaliser_rib(rib_espace), RIB_VALIDE_1)
        self.assertTrue(cle_rib_valide(rib_espace))

    def test_rib_non_numerique_jamais_exception(self):
        self.assertFalse(cle_rib_valide('ABCDEFGHIJKLMNOPQRSTUVWX'))
        diagnostic = valider_rib('not-a-rib-at-all')
        self.assertFalse(diagnostic['valide'])

    def test_diagnostic_rib_valide_aucune_erreur(self):
        diagnostic = valider_rib(RIB_VALIDE_1)
        self.assertTrue(diagnostic['valide'])
        self.assertEqual(diagnostic['erreurs'], [])
