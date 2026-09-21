"""NTMIG10 — cibles d'import étendues : devis & factures (en-têtes).
NTMIG11 — import des lignes de document (devis/factures) rattachées à
l'en-tête déjà importé, via un second fichier « lignes ».
"""
from decimal import Decimal

from django.test import TestCase

from apps.crm.models import Client
from apps.migration import services
from apps.migration.models import LotMigration, ProjetMigration
from apps.stock.models import Produit
from apps.ventes.models import Devis, Facture

from ._base import make_admin, make_company
from ._stockage_factice import patcher_stockage

CSV_CLIENTS = (
    b'nom,email,external_id\n'
    b'Alpha SARL,alpha@ex.ma,ODOO-C1\n'
)
CSV_DEVIS = (
    b'reference,client_email,statut,external_id\n'
    b'SO001,alpha@ex.ma,envoye,ODOO-SO1\n'
    b'SO002,alpha@ex.ma,brouillon,ODOO-SO2\n'
)
CSV_LIGNES_DEVIS = (
    b'document_external_id,designation,quantite,prix_unitaire_ht\n'
    b'ODOO-SO1,Panneau 550W,10,1500\n'
    b'ODOO-SO1,Onduleur 5kW,1,4500\n'
    b'ODOO-INCONNU,Ligne orpheline,1,100\n'
)
CSV_FACTURES = (
    b'reference,client_email,statut,external_id\n'
    b'INV001,alpha@ex.ma,emise,ODOO-INV1\n'
)
CSV_LIGNES_FACTURES = (
    b'document_external_id,designation,quantite,prix_unitaire_ht\n'
    b'ODOO-INV1,Panneau 550W,5,1500\n'
    b'ODOO-INV1,Produit Inconnu,1,999\n'
)


class DevisFacturesImportTests(TestCase):

    def setUp(self):
        self.stockage = patcher_stockage(self)
        self.company = make_company('ntmig10-devis', 'NTMIG10')
        self.admin = make_admin(self.company, 'ntmig10-admin')
        self.projet = ProjetMigration.objects.create(
            company=self.company, nom='Bascule Odoo', source='odoo')

        lot_clients = LotMigration.objects.create(
            company=self.company, projet=self.projet, entite='clients',
            ordre=0)
        services.charger_lot(
            lot_clients, CSV_CLIENTS, 'clients.csv', user=self.admin)

        Produit.objects.create(
            company=self.company, nom='Panneau 550W', sku='SKU-1',
            prix_vente=Decimal('1500'))
        Produit.objects.create(
            company=self.company, nom='Onduleur 5kW', sku='SKU-2',
            prix_vente=Decimal('4500'))

    def test_devis_est_une_cible_import_valide(self):
        from apps.dataimport.services import TARGETS
        self.assertIn('devis', TARGETS)
        self.assertIn('factures', TARGETS)

    def test_import_devis_cree_avec_client_et_statut_mappe(self):
        lot = LotMigration.objects.create(
            company=self.company, projet=self.projet, entite='devis',
            ordre=1)

        result = services.charger_lot(
            lot, CSV_DEVIS, 'devis.csv', user=self.admin)

        self.assertEqual(result['created'], 2)
        devis_list = Devis.objects.filter(company=self.company).order_by('id')
        self.assertEqual(devis_list.count(), 2)
        client = Client.objects.get(company=self.company)
        for d in devis_list:
            self.assertEqual(d.client_id, client.pk)
            self.assertTrue(d.reference.startswith('DEV-'))
        self.assertEqual(devis_list[0].statut, Devis.Statut.ENVOYE)
        self.assertEqual(devis_list[1].statut, Devis.Statut.BROUILLON)

    def test_references_gap_free(self):
        """Numérotation via core.numbering — jamais count()+1."""
        lot = LotMigration.objects.create(
            company=self.company, projet=self.projet, entite='devis',
            ordre=1)
        services.charger_lot(lot, CSV_DEVIS, 'devis.csv', user=self.admin)

        refs = sorted(
            Devis.objects.filter(company=self.company)
            .values_list('reference', flat=True))
        suffixes = sorted(int(r.rsplit('-', 1)[1]) for r in refs)
        self.assertEqual(suffixes, [1, 2])

    def test_client_introuvable_part_en_erreur_ligne(self):
        lot = LotMigration.objects.create(
            company=self.company, projet=self.projet, entite='devis',
            ordre=1)
        csv = b'reference,client_email,statut\nSO099,inconnu@ex.ma,brouillon\n'

        result = services.charger_lot(lot, csv, 'devis.csv', user=self.admin)

        self.assertEqual(result['created'], 0)
        self.assertEqual(len(result['skipped']), 1)
        self.assertIn('client introuvable', result['skipped'][0]['raison'])

    def test_import_lignes_devis_reconstitue_les_totaux(self):
        """NTMIG11 : 40 lignes / 10 devis → totaux HT reconstitués (ici 2
        lignes / 1 devis) — une ligne orpheline part en erreur, jamais un
        crash de tout le fichier."""
        lot = LotMigration.objects.create(
            company=self.company, projet=self.projet, entite='devis',
            ordre=1)
        services.charger_lot(lot, CSV_DEVIS, 'devis.csv', user=self.admin)

        resultat = services.charger_lignes_document(
            lot, CSV_LIGNES_DEVIS, 'lignes.csv', user=self.admin)

        self.assertEqual(resultat['crees'], 2)
        self.assertEqual(len(resultat['erreurs']), 1)
        self.assertIn('orpheline', resultat['erreurs'][0]['raison'])

        devis = Devis.objects.filter(company=self.company).order_by('id').first()
        lignes = devis.lignes.all()
        total_ht = sum(ligne.quantite * ligne.prix_unitaire for ligne in lignes)
        self.assertEqual(
            total_ht,
            Decimal('10') * Decimal('1500') + Decimal('1') * Decimal('4500'))

    def test_import_factures_et_lignes(self):
        lot_factures = LotMigration.objects.create(
            company=self.company, projet=self.projet, entite='factures',
            ordre=1)
        result = services.charger_lot(
            lot_factures, CSV_FACTURES, 'factures.csv', user=self.admin)
        self.assertEqual(result['created'], 1)
        facture = Facture.objects.get(company=self.company)
        self.assertEqual(facture.statut, Facture.Statut.EMISE)
        self.assertEqual(facture.type_facture, Facture.TypeFacture.COMPLETE)

        resultat = services.charger_lignes_document(
            lot_factures, CSV_LIGNES_FACTURES, 'lignes.csv', user=self.admin)

        # 1 ligne créée (produit connu) ; 1 en erreur (produit introuvable).
        self.assertEqual(resultat['crees'], 1)
        self.assertEqual(len(resultat['erreurs']), 1)
        self.assertIn('produit introuvable', resultat['erreurs'][0]['raison'])
        ligne = facture.lignes.get()
        self.assertEqual(ligne.produit.sku, 'SKU-1')

    def test_ajouter_lignes_refuse_pour_entite_non_document(self):
        lot_clients = LotMigration.objects.filter(
            company=self.company, entite='clients').first()
        with self.assertRaises(ValueError):
            services.charger_lignes_document(
                lot_clients, CSV_LIGNES_DEVIS, 'lignes.csv')

    def test_endpoint_ajouter_lignes(self):
        from django.core.files.uploadedfile import SimpleUploadedFile

        from ._base import auth

        lot = LotMigration.objects.create(
            company=self.company, projet=self.projet, entite='devis',
            ordre=1)
        services.charger_lot(lot, CSV_DEVIS, 'devis.csv', user=self.admin)
        api = auth(self.admin)

        resp = api.post(
            f'/api/django/migration/lots-migration/{lot.pk}/ajouter-lignes/',
            {'fichier': SimpleUploadedFile(
                'lignes.csv', CSV_LIGNES_DEVIS, content_type='text/csv')})

        self.assertEqual(resp.status_code, 200, resp.content)
        self.assertEqual(resp.json()['crees'], 2)
