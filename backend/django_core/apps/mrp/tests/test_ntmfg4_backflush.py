"""NTMFG4 — Consommation & production de stock sur l'Ordre de Fabrication
(backflush industriel).

Critère : clôturer un OF sans OrdreAssemblage lié décrémente
composants/incrémente le composite exactement une fois ; un OF AVEC lien ne
mouvemente rien en double (délégué à XMFG1)."""
from decimal import Decimal

from django.test import TestCase

from apps.installations.models_kitting import OrdreAssemblage
from apps.mrp.models import Gamme, OrdreFabrication
from apps.mrp.services import cloturer_of
from apps.stock.models import KitComposant, KitProduit, MouvementStock, Produit

from ._fixtures import make_company


def make_produit(company, nom, quantite_stock=0):
    return Produit.objects.create(
        company=company, nom=nom, prix_vente=0, tva=20,
        quantite_stock=quantite_stock)


class BackflushSansLienTests(TestCase):
    def setUp(self):
        self.company = make_company('mrp-bf-1', 'MRP Backflush 1')
        self.composant = make_produit(self.company, 'Vis M6', quantite_stock=1000)
        self.composite = make_produit(self.company, 'Coffret assemblé', quantite_stock=0)
        self.kit = KitProduit.objects.create(company=self.company, nom='Kit coffret')
        KitComposant.objects.create(
            kit=self.kit, produit=self.composant, quantite=Decimal('4'))
        self.gamme = Gamme.objects.create(
            company=self.company, nom='Gamme coffret', produit=self.composite,
            kit_source=self.kit)

    def test_cloturer_consomme_composants_et_produit_composite_une_fois(self):
        of = OrdreFabrication.objects.create(
            company=self.company, produit=self.composite, quantite=10,
            gamme=self.gamme)
        cloturer_of(of)
        of.refresh_from_db()
        self.composant.refresh_from_db()
        self.composite.refresh_from_db()

        self.assertTrue(of.stock_mouvemente)
        self.assertEqual(of.statut, OrdreFabrication.Statut.TERMINE)
        # 10 composites x 4 vis = 40 vis consommées.
        self.assertEqual(self.composant.quantite_stock, 1000 - 40)
        self.assertEqual(self.composite.quantite_stock, 10)

    def test_cloturer_est_idempotent_pas_de_double_mouvement(self):
        of = OrdreFabrication.objects.create(
            company=self.company, produit=self.composite, quantite=10,
            gamme=self.gamme)
        cloturer_of(of)
        cloturer_of(of)  # Rejoué -> ne doit RIEN mouvementer de plus.
        self.composant.refresh_from_db()
        self.composite.refresh_from_db()
        self.assertEqual(self.composant.quantite_stock, 1000 - 40)
        self.assertEqual(self.composite.quantite_stock, 10)
        self.assertEqual(
            MouvementStock.objects.filter(
                company=self.company, reference=f'OF-{of.id}').count(), 2)

    def test_of_sans_nomenclature_ne_mouvemente_rien(self):
        composite_libre = make_produit(self.company, 'Article de suivi seul')
        gamme_libre = Gamme.objects.create(
            company=self.company, nom='Gamme sans BOM', produit=composite_libre)
        of = OrdreFabrication.objects.create(
            company=self.company, produit=composite_libre, quantite=3,
            gamme=gamme_libre)
        cloturer_of(of)
        of.refresh_from_db()
        self.assertEqual(of.statut, OrdreFabrication.Statut.TERMINE)
        self.assertFalse(
            MouvementStock.objects.filter(
                company=self.company, reference=f'OF-{of.id}').exists())


class BackflushAvecLienKittingTests(TestCase):
    def setUp(self):
        self.company = make_company('mrp-bf-2', 'MRP Backflush 2')
        self.composant = make_produit(self.company, 'Vis M8', quantite_stock=500)
        self.composite = make_produit(self.company, 'Kit boutique assemblé')

    def test_of_avec_kit_ordre_assemblage_ne_mouvemente_rien(self):
        from apps.installations.models_kitting import Kit as InstallationsKit

        kit_boutique = InstallationsKit.objects.create(
            company=self.company, nom='Kit boutique',
            produit_compose=self.composite)
        ordre_assemblage = OrdreAssemblage.objects.create(
            company=self.company, kit=kit_boutique, quantite=1,
            reference='ASM-TEST-0001')
        of = OrdreFabrication.objects.create(
            company=self.company, produit=self.composite, quantite=1,
            kit_ordre_assemblage=ordre_assemblage)
        cloturer_of(of)
        of.refresh_from_db()
        self.assertEqual(of.statut, OrdreFabrication.Statut.TERMINE)
        self.assertFalse(of.stock_mouvemente)
        self.assertFalse(
            MouvementStock.objects.filter(
                company=self.company, reference=f'OF-{of.id}').exists())
