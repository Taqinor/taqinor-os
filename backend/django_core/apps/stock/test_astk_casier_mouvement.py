"""ASTK195 (C-ASTK-046, volet WMS-7) — `record_stock_movement` fait suivre la
quantité PAR CASIER (BinAffectation) via le service installations
`appliquer_mouvement_casier` (ASTK194) dès qu'un mouvement porte
`bin_source` / `bin_destination`.

Sonde WMS-7 : S=10, C=0 inchangés après un transfert scanné ; C toujours dû
(quantite_a_transferer 20) avant et après.

Source réelle : `enregistrer_mouvement_scanne` → `record_stock_movement` →
`installations.services.appliquer_mouvement_casier`, sélecteur réel
`casiers_picking_a_reapprovisionner` — aucun mock.

Run :
    python manage.py test apps.stock.test_astk_casier_mouvement -v 2
"""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase

from apps.installations.models import BinAffectation, BinLocation
from apps.stock.models import EmplacementStock, Produit, SeuilReapproCasier
from apps.stock.services_reappro_casier import (
    casiers_picking_a_reapprovisionner,
)
from apps.stock.services_wms import enregistrer_mouvement_scanne
from authentication.models import Company

User = get_user_model()


class CasierMouvementTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(
            nom='ASTK195', slug='astk195-co')
        self.user = User.objects.create_user(
            username='astk195-resp', password='x', company=self.company,
            role_legacy='responsable')
        emplacement = EmplacementStock.objects.create(
            company=self.company, nom='Dépôt ASTK195', is_principal=True)
        self.source = BinLocation.objects.create(
            company=self.company, emplacement=emplacement,
            code='S-01-01', zone='S', allee='01', casier='01', ordre=120)
        self.cible = BinLocation.objects.create(
            company=self.company, emplacement=emplacement,
            code='P-01-01', zone='P', allee='01', casier='01', ordre=100)
        self.produit = Produit.objects.create(
            company=self.company, nom='Connecteur ASTK195', sku='MC4-ASTK195',
            prix_achat=Decimal('10'), prix_vente=Decimal('18'),
            quantite_stock=50)
        BinAffectation.objects.create(
            company=self.company, bin=self.source, produit=self.produit,
            quantite=10)
        SeuilReapproCasier.objects.create(
            company=self.company, bin=self.cible, produit=self.produit,
            seuil=5, quantite_cible=20)

    def _qte(self, casier):
        aff = BinAffectation.objects.filter(
            bin=casier, produit=self.produit).first()
        return aff.quantite if aff else 0

    def _scan(self, type_mouvement, quantite, **casiers):
        return enregistrer_mouvement_scanne(
            company=self.company, user=self.user,
            produit_id=self.produit.id, type_mouvement=type_mouvement,
            quantite=quantite, **casiers)

    def test_transfert_scanne_met_a_jour_les_casiers(self):
        self._scan('transfert', 8, bin_source_id=self.source.id,
                   bin_destination_id=self.cible.id)
        self.assertEqual((self._qte(self.source), self._qte(self.cible)),
                         (2, 8))
        self._scan('entree', 3, bin_destination_id=self.cible.id)
        self.assertEqual(self._qte(self.cible), 11)
        self._scan('sortie', 2, bin_source_id=self.source.id)
        # Persistance : BinAffectation relues.
        self.assertEqual((self._qte(self.source), self._qte(self.cible)),
                         (0, 11))
        # Le total produit suit les seules entrée/sortie (transfert neutre).
        self.produit.refresh_from_db()
        self.assertEqual(self.produit.quantite_stock, 51)

    def test_sortie_au_dela_du_casier_plafonnee(self):
        # Règle ASTK194 : la source est plafonnée à 0, jamais négative.
        self._scan('sortie', 12, bin_source_id=self.source.id)
        self.assertEqual(self._qte(self.source), 0)

    def test_reappro_ne_liste_plus_le_casier_servi(self):
        avant = [d['bin'] for d in
                 casiers_picking_a_reapprovisionner(self.company)]
        self.assertIn(self.cible.id, avant)
        self._scan('transfert', 8, bin_source_id=self.source.id,
                   bin_destination_id=self.cible.id)
        apres = [d['bin'] for d in
                 casiers_picking_a_reapprovisionner(self.company)]
        self.assertNotIn(self.cible.id, apres)
