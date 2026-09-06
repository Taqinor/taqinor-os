"""AUD602 — une seule chaîne d'arrondi sur les sous-totaux du bordereau AO.

Le cas qui coûte cher : un sous-total qui tombe EXACTEMENT sur ``,xx5``.

* ``SectionBordereau.total_ht`` quantifiait sans argument ``rounding`` — donc en
  arrondi BANCAIRE (HALF_EVEN, le défaut du contexte décimal) — alors que
  ``BordereauPrix.sous_total_ht`` quantifie en HALF_UP depuis 2026-08-18 : la
  section affichait 1 000,00 et le bordereau qui la contient 1 000,01, pour les
  MÊMES lignes ;
* la règle de contrôle ``AO_TOTAL_LIGNES`` recalculait cette même somme avec
  l'arrondi bancaire puis la comparait au ``sous_total_ht`` HALF_UP : elle
  déclarait donc BLOQUANT un bordereau parfaitement cohérent — un refus de
  dépôt à tort, sur un dossier dont l'heure limite ne se rattrape pas.

Run :
    python manage.py test apps.ao.tests.test_aud602_arrondi_bordereau -v2
"""
from decimal import ROUND_HALF_EVEN, ROUND_HALF_UP, Decimal

from django.test import TestCase

from apps.ao import controles
from apps.ao.models import (
    AppelOffre, BordereauPrix, LigneBordereau, SectionBordereau,
)
from authentication.models import Company

CLAUSE = 'Marché à prix unitaires — quantités prévisionnelles.'

#: La somme des deux lignes vaut EXACTEMENT 1 000,005 MAD HT.
TOTAL_EXACT = Decimal('1000.005')


class BaseDemiCentime(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='AUD602 Co',
                                              slug='aud602-co')
        self.ao = AppelOffre.objects.create(
            company=self.company, reference='AO-602-1', objet='Arrondi')
        self.bordereau = BordereauPrix.objects.create(
            company=self.company, appel_offre=self.ao, clause_reserve=CLAUSE)
        self.section = SectionBordereau.objects.create(
            company=self.company, bordereau=self.bordereau, numero=1,
            libelle='Lot unique')
        LigneBordereau.objects.create(
            company=self.company, bordereau=self.bordereau,
            section=self.section, numero=1, designation='Fourniture',
            quantite=Decimal('1.000'), prix_unitaire=Decimal('1000.00'))
        LigneBordereau.objects.create(
            company=self.company, bordereau=self.bordereau,
            section=self.section, numero=2, designation='Appoint',
            quantite=Decimal('0.005'), prix_unitaire=Decimal('1.00'))


class TestLeCasEstBienUnDemiCentime(BaseDemiCentime):
    """Sans ce garde-fou, le test passerait « vert » sur un cas hors sujet."""

    def test_la_somme_brute_tombe_sur_le_demi_centime(self):
        somme = sum((ligne.montant_ht
                     for ligne in self.bordereau.lignes.all()),
                    Decimal('0.00'))
        self.assertEqual(somme, TOTAL_EXACT)

    def test_les_deux_arrondis_donnaient_bien_deux_valeurs(self):
        self.assertNotEqual(
            TOTAL_EXACT.quantize(Decimal('0.01'), rounding=ROUND_HALF_EVEN),
            TOTAL_EXACT.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP))


class TestArrondiUnique(BaseDemiCentime):
    def test_la_section_arrondit_comme_le_bordereau(self):
        self.assertEqual(self.section.total_ht,
                         self.bordereau.sous_total_ht)

    def test_la_section_arrondit_en_half_up(self):
        self.assertEqual(self.section.total_ht, Decimal('1000.01'))


class TestRegleTotalLignes(BaseDemiCentime):
    def test_aucun_refus_de_depot_a_tort_sur_le_demi_centime(self):
        anomalies = controles.executer_regles(
            {'bordereau': self.bordereau}, codes={'AO_TOTAL_LIGNES'})
        self.assertEqual(
            anomalies, [],
            'AO_TOTAL_LIGNES refuse un bordereau cohérent (arrondi divergent)')

    def test_la_regle_voit_toujours_un_vrai_ecart(self):
        """Le correctif aligne l'arrondi — il ne désarme pas la règle."""
        class _Faux:
            """Bordereau dont le sous-total annoncé ment d'un dirham."""

            def __init__(self, vrai):
                self.lignes = vrai.lignes
                self.sous_total_ht = vrai.sous_total_ht + Decimal('1.00')

        anomalies = controles.executer_regles(
            {'bordereau': _Faux(self.bordereau)},
            codes={'AO_TOTAL_LIGNES'})
        self.assertEqual(len(anomalies), 1, anomalies)
        self.assertEqual(anomalies[0]['code_regle'], 'AO_TOTAL_LIGNES')
