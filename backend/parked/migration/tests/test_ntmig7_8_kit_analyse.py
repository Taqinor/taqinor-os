"""NTMIG7 — analyse de fichier source & aperçu réconciliable (avec kit).
NTMIG8 — kit Odoo : mappings prédéfinis par entité (en-têtes techniques
Odoo/FR mappés SANS mapping manuel, résolu automatiquement de
``(projet.source, lot.entite)``).
"""
from decimal import Decimal

from django.test import TestCase

from apps.crm.models import Client
from apps.migration import services
from apps.migration.kits import KIT_REGISTRY, cle_kit
from apps.migration.kits.odoo import KIT_REGISTRY as ODOO_KIT_REGISTRY
from apps.migration.models import LotMigration, ProjetMigration

from ._base import make_admin, make_company
from ._stockage_factice import patcher_stockage

# En-têtes TECHNIQUES Odoo (``res.partner``) : aucune de ces colonnes n'est
# reconnue par ``dataimport.FIELD_MAPS['clients']`` sans le kit.
CSV_ODOO_CLIENTS = (
    'name,email,phone,vat,id,list_price\n'
    'Alpha SARL,alpha@ex.ma,0612345678,001234567000012,ODOO-1,\n'
).encode('utf-8')

CSV_ODOO_PRODUCTS = (
    'name,default_code,list_price,id\n'
    'Panneau 550W,SKU-1,1500,ODOO-P1\n'
    'Onduleur 5kW,SKU-2,4500,ODOO-P2\n'
).encode('utf-8')


class KitRegistryTests(TestCase):
    """Le registre lui-même — pas de DB nécessaire."""

    def test_cle_kit_forme_source_deux_points_entite(self):
        self.assertEqual(cle_kit('odoo', 'clients'), 'odoo:clients')

    def test_registre_fusionne_odoo_sage_generique(self):
        self.assertIn('odoo:clients', KIT_REGISTRY)
        self.assertIn('sage:clients', KIT_REGISTRY)
        self.assertIn('csv_generique:clients', KIT_REGISTRY)

    def test_kit_odoo_clients_mappe_champs_techniques(self):
        kit = ODOO_KIT_REGISTRY[cle_kit('odoo', 'clients')]
        self.assertEqual(kit.mapping['phone'], 'telephone')
        self.assertEqual(kit.mapping['vat'], 'ice')
        self.assertEqual(kit.mapping['id'], 'external_id')

    def test_kit_odoo_leads_reutilise_odoo_field_map(self):
        kit = ODOO_KIT_REGISTRY[cle_kit('odoo', 'leads')]
        self.assertEqual(kit.mapping.get('email_from'), 'email')


class AnalyserLotAvecKitTests(TestCase):

    def setUp(self):
        self.stockage = patcher_stockage(self)
        self.company = make_company('ntmig7-odoo', 'NTMIG7 Odoo')
        self.admin = make_admin(self.company, 'ntmig7-admin')
        self.projet = ProjetMigration.objects.create(
            company=self.company, nom='Bascule Odoo', source='odoo')

    def test_kit_resolu_automatiquement_pour_le_lot(self):
        lot = LotMigration.objects.create(
            company=self.company, projet=self.projet, entite='clients')
        kit = services._kit_pour_lot(lot)
        self.assertIsNotNone(kit)
        self.assertEqual(kit.mapping['phone'], 'telephone')

    def test_analyse_traduit_les_en_tetes_techniques_odoo(self):
        """NTMIG8 : sans mapping manuel, `phone`/`vat`/`id` sont reconnus."""
        lot = LotMigration.objects.create(
            company=self.company, projet=self.projet, entite='clients')

        apercu = services.analyser_lot(lot, CSV_ODOO_CLIENTS, 'export.csv')

        self.assertEqual(apercu['total_lignes'], 1)
        # Rien n'a été écrit en cible (dry-run strict).
        self.assertEqual(Client.objects.filter(company=self.company).count(), 0)
        lot.refresh_from_db()
        self.assertEqual(lot.source_lignes, 1)

    def test_analyse_pose_source_montant_depuis_colonnes_montant_kit(self):
        """NTMIG7 : le total HT source est posé AVANT tout chargement."""
        lot = LotMigration.objects.create(
            company=self.company, projet=self.projet, entite='products')

        services.analyser_lot(lot, CSV_ODOO_PRODUCTS, 'produits.csv')

        lot.refresh_from_db()
        self.assertEqual(lot.source_montant, Decimal('6000'))

    def test_chargement_traduit_aussi_les_en_tetes(self):
        """Le même kit s'applique au CHARGEMENT réel, pas seulement à
        l'analyse — sinon l'aperçu mentirait sur ce qui serait importé."""
        lot = LotMigration.objects.create(
            company=self.company, projet=self.projet, entite='clients')

        result = services.charger_lot(
            lot, CSV_ODOO_CLIENTS, 'export.csv', user=self.admin)

        self.assertEqual(result['created'], 1)
        client = Client.objects.get(company=self.company)
        self.assertEqual(client.nom, 'Alpha SARL')
        self.assertEqual(client.telephone, '0612345678')
        self.assertEqual(client.ice, '001234567000012')

    def test_sans_kit_analyse_reste_inchangee(self):
        """Une source SANS kit (aucune entrée pour ce couple) ne change rien
        au comportement historique (mapping automatique du moteur seul)."""
        lot = LotMigration.objects.create(
            company=self.company, projet=self.projet, entite='fournisseurs')
        csv = b'nom,email\nFournisseur X,x@ex.ma\n'

        apercu = services.analyser_lot(lot, csv, 'fournisseurs.csv')

        self.assertEqual(apercu['total_lignes'], 1)
        lot.refresh_from_db()
        self.assertIsNone(lot.source_montant)
