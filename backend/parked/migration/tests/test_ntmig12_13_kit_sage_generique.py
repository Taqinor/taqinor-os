"""NTMIG12 — kit Sage : mappings prédéfinis par export CSV (séparateur `;`,
décimale virgule, encodage CP1252 en repli — géré par ``dataimport.parse_rows``,
pas par le kit).
NTMIG13 — kit Excel/CSV générique : pas de mapping prédéfini, réutilise le
mapping SAUVEGARDÉ (``dataimport.ImportMapping``) — analyser un fichier à
en-têtes non standard une fois, l'ajuster, le sauver, le rejouer.
"""
from decimal import Decimal

from django.test import TestCase

from apps.crm.models import Client
from apps.migration import services
from apps.migration.kits import cle_kit
from apps.migration.kits.sage import KIT_REGISTRY as SAGE_KIT_REGISTRY
from apps.migration.models import LotMigration, ProjetMigration

from ._base import make_admin, make_company
from ._stockage_factice import patcher_stockage

# Export Sage 100 typique : en-têtes FR, décimale virgule.
CSV_SAGE_CLIENTS = (
    'Code Tiers;Raison Sociale;E-mail;Telephone\n'
    'C001;Beta Solutions;beta@ex.ma;0612345678\n'
).encode('cp1252')

CSV_SAGE_PRODUCTS = (
    'Reference;Libelle;Prix de vente\n'
    'REF-1;Onduleur;4 500,50\n'
    'REF-2;Panneau;1 200,00\n'
).encode('utf-8')


class KitSageTests(TestCase):

    def test_kit_sage_clients_mappe_entetes_fr(self):
        kit = SAGE_KIT_REGISTRY[cle_kit('sage', 'clients')]
        self.assertEqual(kit.mapping['raison sociale'], 'nom')
        self.assertEqual(kit.mapping['code tiers'], 'external_id')

    def test_kit_sage_fournisseurs_distinct_de_clients(self):
        cles = SAGE_KIT_REGISTRY.keys()
        self.assertIn(cle_kit('sage', 'fournisseurs'), cles)
        self.assertIn(cle_kit('sage', 'clients'), cles)


class AnalyserAvecKitSageTests(TestCase):

    def setUp(self):
        self.stockage = patcher_stockage(self)
        self.company = make_company('ntmig12-sage', 'NTMIG12 Sage')
        self.admin = make_admin(self.company, 'ntmig12-admin')
        self.projet = ProjetMigration.objects.create(
            company=self.company, nom='Reprise Sage', source='sage')

    def test_export_cp1252_decimale_virgule_mappe_et_parse(self):
        """Un export Articles Sage en CP1252 avec décimale virgule mappe et
        parse les prix correctement."""
        lot = LotMigration.objects.create(
            company=self.company, projet=self.projet, entite='products')

        services.analyser_lot(lot, CSV_SAGE_PRODUCTS, 'articles.csv')

        lot.refresh_from_db()
        self.assertEqual(lot.source_lignes, 2)
        # 4500,50 + 1200,00 = 5700,50 (décimale virgule normalisée en point).
        self.assertEqual(lot.source_montant, Decimal('5700.50'))

    def test_chargement_client_sage_cp1252(self):
        lot = LotMigration.objects.create(
            company=self.company, projet=self.projet, entite='clients')

        result = services.charger_lot(
            lot, CSV_SAGE_CLIENTS, 'tiers.csv', user=self.admin)

        self.assertEqual(result['created'], 1)
        client = Client.objects.get(company=self.company)
        self.assertEqual(client.nom, 'Beta Solutions')
        self.assertEqual(client.email, 'beta@ex.ma')


class KitGeneriqueMappingSauvegardeTests(TestCase):
    """NTMIG13 — pas de mapping prédéfini : le mapping SAUVEGARDÉ
    (``dataimport.ImportMapping``, XPLT2) est proposé, ajusté, sauvé, puis
    rejoué sur d'autres fichiers identiques."""

    def setUp(self):
        self.stockage = patcher_stockage(self)
        self.company = make_company('ntmig13-generique', 'NTMIG13')
        self.admin = make_admin(self.company, 'ntmig13-admin')
        self.projet = ProjetMigration.objects.create(
            company=self.company, nom='Excel maison', source='excel')
        self.lot = LotMigration.objects.create(
            company=self.company, projet=self.projet, entite='clients')

    def test_kit_generique_sans_mapping_predefini(self):
        from apps.migration.services import kit_pour

        kit = kit_pour('excel', 'clients')
        self.assertIsNotNone(kit)
        self.assertEqual(kit.mapping, {})

    def test_mapping_sauvegarde_rejouable_sur_fichiers_identiques(self):
        from apps.dataimport.services import save_mapping

        # En-têtes NON standard, propres à l'export maison de ce client.
        csv_1 = b'Nom Complet,Courriel\nGamma SARL,gamma@ex.ma\n'
        csv_2 = b'Nom Complet,Courriel\nDelta SARL,delta@ex.ma\n'

        save_mapping(
            self.company, 'clients', 'export-maison',
            {'Nom Complet': 'nom', 'Courriel': 'email'})

        r1 = services.charger_lot(
            self.lot, csv_1, 'fichier1.csv',
            mapping_name='export-maison', user=self.admin)
        r2 = services.charger_lot(
            self.lot, csv_2, 'fichier2.csv',
            mapping_name='export-maison', user=self.admin)

        self.assertEqual(r1['created'], 1)
        self.assertEqual(r2['created'], 1)
        self.assertEqual(
            set(Client.objects.filter(company=self.company)
                .values_list('nom', flat=True)),
            {'Gamma SARL', 'Delta SARL'})
