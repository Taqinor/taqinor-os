"""Tests FG66 / DC36 — Kit / nomenclature (BOM) vendable.

  - FG66 : un kit s'explose en lignes composant (un SKU par ligne) ;
  - DC36 : aucun prix / marque / TVA n'est stocké sur le kit — tout est dérivé
    des composants (Produit) au moment de l'explosion ; composants = FK→Produit.

Le prix d'ACHAT n'est jamais exposé par l'explosion (interne).

Run :
    python manage.py test apps.stock.test_kit -v 2
"""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase

from apps.stock.models import Produit, KitProduit, KitComposant
from apps.stock.services import exploser_kit, exploser_kit_par_id

User = get_user_model()


def make_company(slug='kit-co', nom='Kit Co'):
    from authentication.models import Company
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


class KitBase(TestCase):
    def setUp(self):
        self.company = make_company()
        self.other = make_company(slug='kit-co-2', nom='Autre Kit Co')
        self.panneau = Produit.objects.create(
            company=self.company, nom='Panneau 550W', sku='PV550',
            prix_achat=Decimal('400'), prix_vente=Decimal('600'),
            quantite_stock=20, tva=Decimal('10'), marque='JA Solar')
        self.onduleur = Produit.objects.create(
            company=self.company, nom='Onduleur 5kW', sku='OND5',
            prix_achat=Decimal('3000'), prix_vente=Decimal('4500'),
            quantite_stock=5, tva=Decimal('20'), marque='Huawei')
        self.kit = KitProduit.objects.create(
            company=self.company, nom='Kit résidentiel 5 kWc', sku='KIT5')
        KitComposant.objects.create(
            kit=self.kit, produit=self.panneau, quantite=Decimal('9'))
        KitComposant.objects.create(
            kit=self.kit, produit=self.onduleur, quantite=Decimal('1'))


class TestDC36KitSchema(KitBase):
    """DC36 — le kit ne porte AUCUN prix / marque / TVA propre (tout vient des
    composants) ; les composants sont des FK→Produit, explosés à l'insertion."""

    def test_kit_has_no_price_brand_tva_fields(self):
        field_names = {f.name for f in KitProduit._meta.get_fields()}
        for forbidden in ('prix_vente', 'prix_achat', 'marque', 'tva'):
            self.assertNotIn(forbidden, field_names,
                             f'Le kit ne doit pas stocker {forbidden} (DC36).')

    def test_composant_is_fk_to_produit(self):
        c = self.kit.composants.first()
        self.assertIsInstance(c.produit, Produit)

    def test_composant_has_no_inline_price_brand_tva(self):
        # DC36 — le composant ne recopie pas prix/marque/TVA : seuls le FK
        # produit (ou XMFG17 composant_kit), la quantité et le taux de perte
        # planifié (XMFG11) sont portés.
        field_names = {f.name for f in KitComposant._meta.get_fields()}
        for forbidden in ('prix_vente', 'prix_achat', 'marque', 'tva'):
            self.assertNotIn(forbidden, field_names)
        self.assertEqual(
            field_names,
            {'id', 'kit', 'produit', 'composant_kit', 'quantite',
             'taux_perte_pct'})


class TestKitExplosion(KitBase):
    """FG66 — l'explosion produit une ligne par composant, quantités × facteur,
    prix / TVA / marque LUS sur le Produit (DC36)."""

    def test_explode_single_unit(self):
        lignes = exploser_kit(self.kit, 1)
        self.assertEqual(len(lignes), 2)
        by_sku = {ligne['sku']: ligne for ligne in lignes}
        self.assertEqual(by_sku['PV550']['quantite'], Decimal('9'))
        self.assertEqual(by_sku['PV550']['prix_vente_unitaire'], Decimal('600'))
        self.assertEqual(by_sku['PV550']['tva'], Decimal('10'))
        self.assertEqual(by_sku['PV550']['marque'], 'JA Solar')
        self.assertEqual(by_sku['OND5']['quantite'], Decimal('1'))
        self.assertEqual(by_sku['OND5']['tva'], Decimal('20'))

    def test_explode_multiple_units_scales_quantities(self):
        lignes = exploser_kit(self.kit, 3)
        by_sku = {ligne['sku']: ligne for ligne in lignes}
        self.assertEqual(by_sku['PV550']['quantite'], Decimal('27'))
        self.assertEqual(by_sku['OND5']['quantite'], Decimal('3'))

    def test_explode_never_exposes_purchase_price(self):
        for ligne in exploser_kit(self.kit, 1):
            self.assertNotIn('prix_achat', ligne)

    def test_explode_by_id_scoped(self):
        lignes = exploser_kit_par_id(self.company, self.kit.id, 1)
        self.assertEqual(len(lignes), 2)
        # Hors société -> None.
        self.assertIsNone(exploser_kit_par_id(self.other, self.kit.id, 1))

    def test_explode_archived_kit_returns_none(self):
        self.kit.is_archived = True
        self.kit.save(update_fields=['is_archived'])
        self.assertIsNone(exploser_kit_par_id(self.company, self.kit.id, 1))
