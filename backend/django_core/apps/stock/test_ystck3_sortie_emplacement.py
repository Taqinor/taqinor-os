"""YSTCK3 — Les SORTIE ne décrémentent JAMAIS `StockEmplacement` (avant ce
correctif) : grand livre aveugle à l'emplacement, stock camionnette fictif.

Couvre :
  * `record_stock_movement(emplacement_source=...)` décrémente le
    `StockEmplacement` fourni pour un mouvement SORTIE ;
  * défaut (`emplacement_source=None`) reste octet-identique au comportement
    historique (aucun `StockEmplacement` touché) ;
  * un emplacement PRINCIPAL passé en source est un no-op (le principal est
    dérivé, jamais stocké) ;
  * `stock_breakdown` reste cohérent (le principal absorbe la différence) ;
  * le décrément est plafonné à 0 (jamais négatif) ;
  * un mouvement ENTREE ignore `emplacement_source` (pas de double-compte
    avec `credit_emplacement_destination`).

Run:
    python manage.py test apps.stock.test_ystck3_sortie_emplacement -v 2
"""
from decimal import Decimal

from django.test import TestCase

from authentication.models import Company
from apps.stock.models import (
    EmplacementStock, MouvementStock, Produit, StockEmplacement,
)
from apps.stock.services import (
    record_stock_movement, mouvement_type_sortie, mouvement_type_entree,
    stock_breakdown, ensure_emplacements,
)


def _company(slug):
    return Company.objects.create(nom=slug, slug=slug)


class Ystck3Base(TestCase):
    def setUp(self):
        self.company = _company('ystck3-co')
        ensure_emplacements(self.company)
        self.principal = EmplacementStock.objects.get(
            company=self.company, is_principal=True)
        self.camionnette = EmplacementStock.objects.create(
            company=self.company, nom='Camionnette Y3', is_principal=False)
        self.produit = Produit.objects.create(
            company=self.company, nom='Câble YSTCK3', sku='CAB-YSTCK3',
            prix_vente=Decimal('50'), quantite_stock=20)
        StockEmplacement.objects.create(
            company=self.company, produit=self.produit,
            emplacement=self.camionnette, quantite=8)


class TestDecrementEmplacementSource(Ystck3Base):
    def test_sortie_avec_emplacement_source_decremente_camionnette(self):
        record_stock_movement(
            company=self.company, produit=self.produit,
            type_mouvement=mouvement_type_sortie(),
            quantite=3, quantite_avant=20, quantite_apres=17,
            reference='TEST-Y3-1', note='Consommation van',
            created_by=None, emplacement_source=self.camionnette)
        se = StockEmplacement.objects.get(
            produit=self.produit, emplacement=self.camionnette)
        self.assertEqual(se.quantite, 5)
        self.produit.refresh_from_db()
        self.assertEqual(self.produit.quantite_stock, 17)

    def test_stock_breakdown_reste_coherent_apres_sortie_van(self):
        record_stock_movement(
            company=self.company, produit=self.produit,
            type_mouvement=mouvement_type_sortie(),
            quantite=3, quantite_avant=20, quantite_apres=17,
            reference='TEST-Y3-2', note='Consommation van',
            created_by=None, emplacement_source=self.camionnette)
        self.produit.refresh_from_db()
        breakdown = {b['emplacement_id']: b['quantite']
                     for b in stock_breakdown(self.produit)}
        self.assertEqual(breakdown[self.camionnette.id], 5)
        # Le principal = total(17) - camionnette(5) = 12.
        self.assertEqual(breakdown[self.principal.id], 12)

    def test_plafonne_a_zero_jamais_negatif(self):
        record_stock_movement(
            company=self.company, produit=self.produit,
            type_mouvement=mouvement_type_sortie(),
            quantite=50, quantite_avant=20, quantite_apres=0,
            reference='TEST-Y3-3', note='Sortie massive',
            created_by=None, emplacement_source=self.camionnette)
        se = StockEmplacement.objects.get(
            produit=self.produit, emplacement=self.camionnette)
        self.assertEqual(se.quantite, 0)

    def test_emplacement_principal_en_source_est_no_op(self):
        record_stock_movement(
            company=self.company, produit=self.produit,
            type_mouvement=mouvement_type_sortie(),
            quantite=3, quantite_avant=20, quantite_apres=17,
            reference='TEST-Y3-4', note='Sortie principal',
            created_by=None, emplacement_source=self.principal)
        # Aucun StockEmplacement créé/modifié pour le principal (dérivé).
        self.assertFalse(
            StockEmplacement.objects.filter(
                produit=self.produit, emplacement=self.principal).exists())
        se_camion = StockEmplacement.objects.get(
            produit=self.produit, emplacement=self.camionnette)
        self.assertEqual(se_camion.quantite, 8)


class TestDefautInchange(Ystck3Base):
    def test_sans_emplacement_source_comportement_historique(self):
        record_stock_movement(
            company=self.company, produit=self.produit,
            type_mouvement=mouvement_type_sortie(),
            quantite=3, quantite_avant=20, quantite_apres=17,
            reference='TEST-Y3-5', note='Sortie sans emplacement',
            created_by=None)
        se = StockEmplacement.objects.get(
            produit=self.produit, emplacement=self.camionnette)
        # Inchangé — la camionnette n'a jamais bougé sans emplacement_source.
        self.assertEqual(se.quantite, 8)
        self.produit.refresh_from_db()
        self.assertEqual(self.produit.quantite_stock, 17)


class TestEntreeIgnoreEmplacementSource(Ystck3Base):
    def test_entree_avec_emplacement_source_ne_touche_pas_stockemplacement(self):
        record_stock_movement(
            company=self.company, produit=self.produit,
            type_mouvement=mouvement_type_entree(),
            quantite=5, quantite_avant=20, quantite_apres=25,
            reference='TEST-Y3-6', note='Entrée (pas de van)',
            created_by=None, emplacement_source=self.camionnette)
        se = StockEmplacement.objects.get(
            produit=self.produit, emplacement=self.camionnette)
        self.assertEqual(se.quantite, 8)
        self.assertEqual(
            MouvementStock.objects.filter(
                produit=self.produit,
                type_mouvement=MouvementStock.TypeMouvement.ENTREE).count(),
            1)
