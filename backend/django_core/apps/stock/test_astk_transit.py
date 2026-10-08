"""ASTK206 (C-ASTK-052, volet MVT-18) — la marchandise d'un transfert
EXPÉDIÉ et pas encore reçu est « en transit » : elle n'est plus comptée au
dépôt principal (dérivé), elle apparaît sur une ligne « En transit » de la
ventilation, et la réception la solde.

Sonde MVT-18 d'origine : pendant le transit camionnette → dépôt B de 10, la
ventilation lisait {principal 100, camionnette 0, B 0} — le principal
gonflait de 10 et ``transfer_stock`` pouvait en sortir 100.

Aucun mock : services de transfert en deux temps et ventilation réels.

Run :
    python manage.py test apps.stock.test_astk_transit -v 2
"""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase

from apps.stock.models import EmplacementStock, Produit, StockEmplacement
from apps.stock.services import (
    ensure_emplacements, quantite_en_transit, stock_breakdown,
    stock_breakdown_map, transfer_stock,
)
from apps.stock.services_transfert_deux_temps import (
    creer_demande_transfert, expedier_transfert, receptionner_transfert,
)

User = get_user_model()


def make_company(slug, nom):
    from authentication.models import Company
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


class TransitTests(TestCase):
    def setUp(self):
        self.co = make_company('astk206-co', 'ASTK206 Co')
        self.user = User.objects.create_user(
            username='astk206_admin', password='x', role_legacy='admin',
            company=self.co)
        ensure_emplacements(self.co)
        self.principal = EmplacementStock.objects.get(
            company=self.co, is_principal=True)
        self.camionnette = EmplacementStock.objects.create(
            company=self.co, nom='Camionnette ASTK206', ordre=50)
        self.depot_b = EmplacementStock.objects.create(
            company=self.co, nom='Dépôt B ASTK206', ordre=60)
        self.produit = Produit.objects.create(
            company=self.co, nom='Panneau ASTK206', sku='ASTK206-1',
            prix_achat=Decimal('10'), prix_vente=Decimal('20'),
            quantite_stock=100)
        StockEmplacement.objects.create(
            company=self.co, produit=self.produit,
            emplacement=self.camionnette, quantite=10)

    def _ventilation(self):
        self.produit.refresh_from_db()
        lignes = stock_breakdown(self.produit)
        par_nom = {}
        for ligne in lignes:
            nom = 'transit' if ligne.get('is_transit') else ligne[
                'emplacement_id']
            par_nom[nom] = ligne['quantite']
        return par_nom

    def _transfert(self, source, quantite):
        return creer_demande_transfert(
            company=self.co, user=self.user, produit_id=self.produit.id,
            source_id=source.id, destination_id=self.depot_b.id,
            quantite=quantite)

    def test_transit_non_compte_au_principal(self):
        transfert = self._transfert(self.camionnette, 10)
        expedier_transfert(transfert, self.user)
        v = self._ventilation()
        self.assertEqual(v[self.principal.id], 90)
        self.assertEqual(v[self.camionnette.id], 0)
        self.assertEqual(v[self.depot_b.id], 0)
        self.assertEqual(v['transit'], 10)
        self.assertEqual(sum(v.values()), 100)
        self.assertEqual(quantite_en_transit(self.co, self.produit), 10)
        # La ventilation en masse dérive le principal de la même façon.
        carte = {(r['emplacement_id'], bool(r.get('is_transit'))): r['quantite']
                 for r in stock_breakdown_map(self.co)[self.produit.id]}
        self.assertEqual(carte[(self.principal.id, False)], 90)
        self.assertEqual(carte[(None, True)], 10)
        # transfer_stock depuis le principal ne voit que 90.
        with self.assertRaises(ValueError):
            transfer_stock(
                company=self.co, user=self.user, produit_id=self.produit.id,
                source_id=self.principal.id, destination_id=self.depot_b.id,
                quantite=91)
        transfer_stock(
            company=self.co, user=self.user, produit_id=self.produit.id,
            source_id=self.principal.id, destination_id=self.depot_b.id,
            quantite=90)

    def test_reception_solde_le_transit(self):
        transfert = self._transfert(self.camionnette, 10)
        transfert = expedier_transfert(transfert, self.user)
        receptionner_transfert(transfert, self.user)
        v = self._ventilation()
        self.assertEqual(v[self.depot_b.id], 10)
        self.assertNotIn('transit', v)
        self.assertEqual(v[self.principal.id], 90)
        self.assertEqual(quantite_en_transit(self.co, self.produit), 0)

    def test_source_principal_baisse_a_l_expedition(self):
        transfert = self._transfert(self.principal, 30)
        avant = self._ventilation()
        self.assertEqual(avant[self.principal.id], 90)
        transfert = expedier_transfert(transfert, self.user)
        v = self._ventilation()
        self.assertEqual(v[self.principal.id], 60)
        self.assertEqual(v['transit'], 30)
        receptionner_transfert(transfert, self.user)
        v = self._ventilation()
        self.assertEqual(v[self.principal.id], 60)
        self.assertEqual(v[self.depot_b.id], 30)
        self.assertNotIn('transit', v)
