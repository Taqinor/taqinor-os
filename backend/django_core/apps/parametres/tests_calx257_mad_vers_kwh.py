"""CALX257 — l'inversion du barème société : facture MAD TTC → kWh du mois.

Ce qui est prouvé ici :

* l'ANCRE de la facture réelle SRM n° 643769639 (``models_tariff.py``) :
  359 kWh × 1,381704 = 496,03 MAD TTC d'énergie ⇒ l'inversion rend 359 kWh
  (± 1 kWh) ;
* les charges FIXES d'abonnement (``redevance_compteur_mad_mois``) sont
  retirées AVANT l'inversion — et un réglage VIDE rend ``kwh = None`` avec un
  motif qui NOMME le réglage (jamais la location du compteur comptée comme de
  l'énergie) ;
* sans société (``settings=None``) : ``kwh`` vaut ``None`` et le motif nomme
  le réglage manquant — jamais un prix moyen supposé ;
* la classe est SAISIE : absente ou inconnue ⇒ refus nommant ``classe`` ;
* c'est bien l'INVERSE de ``monthly_bill`` (aller-retour), y compris dans les
  sauts du barème sélectif (borne BASSE, côté prudent).

Aucune base : des ``TariffSettings`` NON enregistrés portent les défauts du
modèle (``SimpleTestCase``).
"""
from decimal import Decimal

from django.test import SimpleTestCase

from apps.parametres import tariff
from apps.parametres.models_tariff import TariffSettings

#: Les lignes fixes de la même facture réelle (location du compteur 18,28 HT
#: + entretien du branchement 15,00 HT, TVA 20 %) — ``models_tariff.py`` CJ2a.
CHARGES_FIXES_FACTURE_REELLE = Decimal('39.94')


def reglages(redevance=Decimal('0.00'), **champs):
    """Un réglage société NON enregistré, défauts du modèle sauf surcharge."""
    return TariffSettings(redevance_compteur_mad_mois=redevance, **champs)


class AncreFactureReelleTest(SimpleTestCase):

    def test_496_03_mad_ttc_donnent_359_kwh(self):
        # L'énergie de la facture réelle (charges fixes déclarées à 0 : le
        # montant est la ligne d'énergie seule).
        resultat = tariff.kwh_depuis_facture(
            reglages(), Decimal('496.03'), classe='residentiel')
        self.assertEqual(resultat['motif'], '')
        self.assertAlmostEqual(float(resultat['kwh']), 359.0, delta=1.0)

    def test_les_charges_fixes_sont_retirees_avant_inversion(self):
        s = reglages(CHARGES_FIXES_FACTURE_REELLE)
        total = Decimal('496.03') + CHARGES_FIXES_FACTURE_REELLE
        resultat = tariff.kwh_depuis_facture(s, total, classe='residentiel')
        self.assertAlmostEqual(float(resultat['kwh']), 359.0, delta=1.0)
        self.assertEqual(resultat['charges_fixes_mad'],
                         CHARGES_FIXES_FACTURE_REELLE)
        self.assertEqual(resultat['energie_mad'], Decimal('496.03'))

    def test_les_charges_fixes_ne_sont_pas_ignorees(self):
        # Le même montant, charges fixes déclarées : moins d'énergie ⇒ moins
        # de kWh (sinon la location du compteur deviendrait de l'énergie).
        sans = tariff.kwh_depuis_facture(
            reglages(), Decimal('496.03'), classe='residentiel')
        avec = tariff.kwh_depuis_facture(
            reglages(CHARGES_FIXES_FACTURE_REELLE), Decimal('496.03'),
            classe='residentiel')
        self.assertLess(avec['kwh'], sans['kwh'])

    def test_reglage_des_charges_fixes_vide_rend_none_et_le_nomme(self):
        resultat = tariff.kwh_depuis_facture(
            reglages(None), Decimal('496.03'), classe='residentiel')
        self.assertIsNone(resultat['kwh'])
        self.assertIn('redevance_compteur_mad_mois', resultat['motif'])
        self.assertIn('Tarification & ROI', resultat['motif'])


class SansSocieteTest(SimpleTestCase):

    def test_sans_reglage_kwh_none_et_le_motif_nomme_le_reglage(self):
        resultat = tariff.kwh_depuis_facture(
            None, Decimal('496.03'), classe='residentiel')
        self.assertIsNone(resultat['kwh'])
        self.assertIn('Tarification & ROI', resultat['motif'])
        self.assertIn('TariffSettings', resultat['motif'])

    def test_aucun_montant_rien_a_convertir(self):
        resultat = tariff.kwh_depuis_facture(
            reglages(), None, classe='residentiel')
        self.assertIsNone(resultat['kwh'])
        self.assertTrue(resultat['motif'])


class ClasseSaisieTest(SimpleTestCase):

    def test_classe_absente_refusee_en_la_nommant(self):
        with self.assertRaises(tariff.FactureInvalide) as capture:
            tariff.kwh_depuis_facture(reglages(), 300, classe=None)
        self.assertEqual(capture.exception.champ, 'classe')

    def test_classe_inconnue_refusee_en_la_nommant(self):
        with self.assertRaises(tariff.FactureInvalide) as capture:
            tariff.kwh_depuis_facture(reglages(), 300, classe='industriel')
        self.assertEqual(capture.exception.champ, 'classe')

    def test_force_motrice_au_tarif_unique(self):
        s = reglages(force_motrice_prix_kwh_ttc=Decimal('0.9500'))
        resultat = tariff.kwh_depuis_facture(s, Decimal('950.00'),
                                             classe='force_motrice')
        self.assertEqual(resultat['kwh'], Decimal('1000.0'))

    def test_montant_illisible_ou_negatif_refuse_en_le_nommant(self):
        for montant in ('beaucoup', Decimal('-1'), float('nan')):
            with self.assertRaises(tariff.FactureInvalide) as capture:
                tariff.kwh_depuis_facture(reglages(), montant,
                                          classe='residentiel')
            self.assertEqual(capture.exception.champ, 'mad_ttc')


class InverseDeMonthlyBillTest(SimpleTestCase):

    def test_aller_retour_sur_le_bareme(self):
        s = reglages(CHARGES_FIXES_FACTURE_REELLE)
        for kwh in (40, 100, 120, 149, 180, 250, 359, 450, 700):
            facture = (tariff.monthly_bill(s, kwh, 'residentiel')
                       + CHARGES_FIXES_FACTURE_REELLE)
            resultat = tariff.kwh_depuis_facture(s, facture,
                                                 classe='residentiel')
            self.assertAlmostEqual(float(resultat['kwh']), kwh, delta=0.1,
                                   msg=f'{kwh} kWh → {facture} MAD')

    def test_un_montant_tombe_dans_un_saut_rend_la_borne_basse(self):
        # 210 kWh coûtent 229,19 MAD, 210,1 kWh passent à la tranche
        # suivante (≈ 249 MAD) : 240 MAD ne décrit aucune consommation — la
        # borne BASSE (210) est rendue, jamais plus.
        s = reglages()
        resultat = tariff.kwh_depuis_facture(s, Decimal('240'),
                                             classe='residentiel')
        self.assertEqual(resultat['kwh'], Decimal('210.0'))

    def test_montant_egal_aux_charges_fixes_zero_kwh(self):
        s = reglages(CHARGES_FIXES_FACTURE_REELLE)
        resultat = tariff.kwh_depuis_facture(
            s, CHARGES_FIXES_FACTURE_REELLE, classe='residentiel')
        self.assertEqual(resultat['kwh'], Decimal('0.0'))

    def test_montant_sous_les_charges_fixes_ne_fabrique_rien(self):
        s = reglages(CHARGES_FIXES_FACTURE_REELLE)
        resultat = tariff.kwh_depuis_facture(s, Decimal('10'),
                                             classe='residentiel')
        self.assertIsNone(resultat['kwh'])
        self.assertIn('charges fixes', resultat['motif'])

    def test_montant_hors_bareme_dit_plutot_que_rendre_la_borne(self):
        s = reglages()
        resultat = tariff.kwh_depuis_facture(s, Decimal('1e9'),
                                             classe='residentiel')
        self.assertIsNone(resultat['kwh'])
        self.assertTrue(resultat['motif'])
