"""Tests XCTR9 — Valeur vie client (CLV) sur revenu récurrent (fondation pure).

Couvre la fonction pure :func:`core.clv.clv` :
  * formule ARPC/churn nominale ;
  * bords : churn nul/négatif/inconnu -> repli propre (clv=None) ;
  * ARPC nul -> CLV = 0 (cas valide, pas un repli) ;
  * ARPC négatif -> repli propre ;
  * plafonnage du multiple CLV/ARPC pour un churn minuscule.

Aucune dépendance à Django/DB — fonction pure (``SimpleTestCase``).
"""
from decimal import Decimal

from django.test import SimpleTestCase

from core.clv import DEFAULT_MAX_MULTIPLE, ClvResult, clv


class ClvNominalTests(SimpleTestCase):
    def test_formule_nominale(self):
        # ARPC 1000 MAD/mois, churn 5%/mois -> CLV = 1000 / 0.05 = 20000.
        resultat = clv(Decimal('1000'), Decimal('0.05'))
        self.assertIsInstance(resultat, ClvResult)
        self.assertEqual(resultat.clv, Decimal('20000.00'))
        self.assertEqual(resultat.duree_vie_mois, Decimal('20.00'))
        self.assertFalse(resultat.used_fallback)
        self.assertFalse(resultat.plafonnee)

    def test_accepte_floats_et_strings(self):
        resultat = clv(1000.0, 0.10)
        self.assertEqual(resultat.clv, Decimal('10000.00'))


class ClvBordsTests(SimpleTestCase):
    def test_churn_nul_repli_propre(self):
        resultat = clv(Decimal('1000'), Decimal('0'))
        self.assertIsNone(resultat.clv)
        self.assertIsNone(resultat.duree_vie_mois)
        self.assertTrue(resultat.used_fallback)

    def test_churn_negatif_repli_propre(self):
        resultat = clv(Decimal('1000'), Decimal('-0.05'))
        self.assertIsNone(resultat.clv)
        self.assertTrue(resultat.used_fallback)

    def test_churn_inconnu_none_repli_propre(self):
        resultat = clv(Decimal('1000'), None)
        self.assertIsNone(resultat.clv)
        self.assertTrue(resultat.used_fallback)

    def test_churn_non_numerique_repli_propre(self):
        resultat = clv(Decimal('1000'), 'abc')
        self.assertIsNone(resultat.clv)
        self.assertTrue(resultat.used_fallback)

    def test_arpc_nul_est_un_clv_zero_valide(self):
        """Un ARPC de 0 (client sans contrat facturable) N'EST PAS un repli."""
        resultat = clv(Decimal('0'), Decimal('0.05'))
        self.assertEqual(resultat.clv, Decimal('0.00'))
        self.assertFalse(resultat.used_fallback)

    def test_arpc_negatif_repli_propre(self):
        resultat = clv(Decimal('-100'), Decimal('0.05'))
        self.assertIsNone(resultat.clv)
        self.assertTrue(resultat.used_fallback)

    def test_arpc_none_repli_propre(self):
        resultat = clv(None, Decimal('0.05'))
        self.assertIsNone(resultat.clv)
        self.assertTrue(resultat.used_fallback)

    def test_client_sans_contrat_et_sans_churn_calculable(self):
        """Le cas décrit par XCTR9 : client sans contrat (ARPC=0) ET aucun
        taux de churn calculable (None) -> repli propre, PAS un 0 trompeur."""
        resultat = clv(Decimal('0'), None)
        self.assertIsNone(resultat.clv)
        self.assertTrue(resultat.used_fallback)


class ClvPlafondTests(SimpleTestCase):
    def test_churn_minuscule_plafonne(self):
        # Churn 0.01%/mois -> multiple brut = 10000x, plafonné à
        # DEFAULT_MAX_MULTIPLE (120x).
        resultat = clv(Decimal('100'), Decimal('0.0001'))
        self.assertTrue(resultat.plafonnee)
        self.assertEqual(
            resultat.clv, (Decimal('100') * DEFAULT_MAX_MULTIPLE))
        self.assertEqual(resultat.duree_vie_mois, DEFAULT_MAX_MULTIPLE)

    def test_max_multiple_personnalise(self):
        resultat = clv(Decimal('100'), Decimal('0.0001'), max_multiple=10)
        self.assertTrue(resultat.plafonnee)
        self.assertEqual(resultat.clv, Decimal('1000.00'))

    def test_pas_de_plafond_si_dans_la_limite(self):
        resultat = clv(Decimal('100'), Decimal('0.10'))  # multiple = 10x
        self.assertFalse(resultat.plafonnee)
