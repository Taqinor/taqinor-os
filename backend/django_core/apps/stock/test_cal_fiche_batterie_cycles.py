"""CAL118 — fiche batterie : nombre de cycles publié et vieillissement.

ROUGE avant CAL118 : le bloc batterie portait capacité/DoD/tension/
puissances/rendement aller-retour mais AUCUN nombre de cycles ni courbe de
vieillissement. VERT : trois champs optionnels
(``bat_cycles_publies``/``bat_retention_fin_de_vie_pct``/
``bat_garantie_annees``), exposés par ``specs_for_produit``.

Run :
    docker compose exec django_core python manage.py test \
        apps.stock.tests.test_fiche_batterie_cycles -v 2
"""
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.test import TestCase

from apps.stock.models import FicheTechnique, Produit
from apps.stock.selectors import specs_for_produit
from authentication.models import Company


class FicheBatterieCyclesTests(TestCase):
    def setUp(self):
        self.co = Company.objects.get_or_create(
            slug='cal118-stock-co', defaults={'nom': 'CAL118 Stock'})[0]
        self.produit = Produit.objects.create(
            company=self.co, nom='Batterie CAL118', sku='CAL118-BAT',
            prix_achat=Decimal('4000'), prix_vente=Decimal('6000'),
            quantite_stock=1)

    def test_champs_vides_par_defaut(self):
        fiche = FicheTechnique.objects.create(
            company=self.co, produit=self.produit, type_fiche='batterie')
        self.assertIsNone(fiche.bat_cycles_publies)
        self.assertIsNone(fiche.bat_retention_fin_de_vie_pct)
        self.assertIsNone(fiche.bat_garantie_annees)

    def test_saisie_des_trois_champs(self):
        fiche = FicheTechnique.objects.create(
            company=self.co, produit=self.produit, type_fiche='batterie',
            bat_cycles_publies=6000,
            bat_retention_fin_de_vie_pct=Decimal('80.0'),
            bat_garantie_annees=10)
        fiche.refresh_from_db()
        self.assertEqual(fiche.bat_cycles_publies, 6000)
        self.assertEqual(fiche.bat_retention_fin_de_vie_pct, Decimal('80.0'))
        self.assertEqual(fiche.bat_garantie_annees, 10)

    def test_retention_hors_bornes_rejetee(self):
        """0 % ou > 100 % rendraient une rétention absurde — jamais admis
        à la saisie (même discipline que bat_rendement_ar_pct, QJR137)."""
        fiche = FicheTechnique(
            company=self.co, produit=self.produit, type_fiche='batterie',
            bat_retention_fin_de_vie_pct=Decimal('0'))
        with self.assertRaises(ValidationError):
            fiche.full_clean()

    def test_specs_for_produit_omet_les_cles_non_saisies(self):
        FicheTechnique.objects.create(
            company=self.co, produit=self.produit, type_fiche='batterie',
            bat_kwh_nominal=Decimal('5.12'))
        self.produit.refresh_from_db()
        specs = specs_for_produit(self.produit)
        self.assertEqual(specs['kwh_nominal'], Decimal('5.12'))
        for key in ('cycles_publies', 'retention_fin_de_vie_pct',
                    'garantie_annees'):
            self.assertNotIn(key, specs)

    def test_specs_for_produit_expose_les_cles_saisies(self):
        FicheTechnique.objects.create(
            company=self.co, produit=self.produit, type_fiche='batterie',
            bat_cycles_publies=6000,
            bat_retention_fin_de_vie_pct=Decimal('80.0'),
            bat_garantie_annees=10)
        self.produit.refresh_from_db()
        specs = specs_for_produit(self.produit)
        self.assertEqual(specs['cycles_publies'], 6000)
        self.assertEqual(specs['retention_fin_de_vie_pct'], Decimal('80.0'))
        self.assertEqual(specs['garantie_annees'], 10)
