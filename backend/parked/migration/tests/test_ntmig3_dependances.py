"""NTMIG3 — ordre de chargement dépendance-aware (graphe d'entités).

Couvre le graphe déclaré (:mod:`apps.migration.dependances`), le tri
topologique + la pose de ``ordre`` (:func:`ordonner_lots`), le refus d'une
dépendance manquante AVANT tout chargement, et la garde NTMIG2 (« pas de
lot N+1 avant que le lot N soit réconcilié ») appliquée aux actions
interactives.
"""
from django.test import TestCase

from apps.migration import dependances, services
from apps.migration.models import LotMigration, ProjetMigration

from ._base import auth, make_admin, make_company
from ._stockage_factice import patcher_stockage

CSV_CLIENTS = b'nom,email,external_id\nAlpha,alpha@ex.ma,ODOO-1\n'
CSV_PRODUCTS = b'nom,sku,prix_vente,external_id\nPanneau,SKU-1,100,ODOO-P1\n'


class DependancesGrapheTests(TestCase):
    """Le DAG lui-même — pas de DB nécessaire."""

    def test_devis_depend_de_clients_et_products(self):
        self.assertEqual(
            set(dependances.dependances_de('devis')), {'clients', 'products'})

    def test_entite_inconnue_sans_dependance(self):
        self.assertEqual(dependances.dependances_de('inexistante'), ())

    def test_dependances_manquantes_signale_ce_qui_manque(self):
        manquantes = dependances.dependances_manquantes(
            'devis', {'products'})
        self.assertEqual(manquantes, ['clients'])

    def test_dependances_manquantes_vide_quand_tout_present(self):
        manquantes = dependances.dependances_manquantes(
            'devis', {'clients', 'products'})
        self.assertEqual(manquantes, [])

    def test_tri_topologique_ordonne_clients_avant_devis(self):
        graphe = {'clients': [], 'products': [], 'devis': ['clients', 'products']}
        ordre = dependances._tri_topologique(graphe)
        self.assertLess(ordre.index('clients'), ordre.index('devis'))
        self.assertLess(ordre.index('products'), ordre.index('devis'))

    def test_cycle_leve_cycledependances(self):
        graphe = {'a': ['b'], 'b': ['a']}
        with self.assertRaises(dependances.CycleDependances):
            dependances._tri_topologique(graphe)


class OrdonnerLotsTests(TestCase):

    def setUp(self):
        self.company = make_company('ntmig3-ord', 'NTMIG3 ordonner')
        self.projet = ProjetMigration.objects.create(
            company=self.company, nom='Bascule', source='odoo')

    def test_facture_sans_client_leve_dependance_manquante(self):
        LotMigration.objects.create(
            company=self.company, projet=self.projet, entite='factures')
        with self.assertRaises(dependances.DependanceManquante):
            dependances.ordonner_lots(self.projet)

    def test_ordonne_clients_produits_devis(self):
        lot_devis = LotMigration.objects.create(
            company=self.company, projet=self.projet, entite='devis',
            ordre=0)
        lot_clients = LotMigration.objects.create(
            company=self.company, projet=self.projet, entite='clients',
            ordre=0)
        lot_products = LotMigration.objects.create(
            company=self.company, projet=self.projet, entite='products',
            ordre=0)

        dependances.ordonner_lots(self.projet)

        lot_devis.refresh_from_db()
        lot_clients.refresh_from_db()
        lot_products.refresh_from_db()
        self.assertLess(lot_clients.ordre, lot_devis.ordre)
        self.assertLess(lot_products.ordre, lot_devis.ordre)


class OrdreGateApiTests(TestCase):
    """NTMIG2/3 — la garde au niveau des actions interactives."""

    def setUp(self):
        self.stockage = patcher_stockage(self)
        self.company = make_company('ntmig3-gate', 'NTMIG3 garde')
        self.admin = make_admin(self.company, 'ntmig3-admin')
        self.projet = ProjetMigration.objects.create(
            company=self.company, nom='Bascule', source='odoo')
        self.api = auth(self.admin)

    def test_creation_lot_factures_sans_clients_refusee(self):
        resp = self.api.post(
            '/api/django/migration/lots-migration/',
            {'projet': self.projet.pk, 'entite': 'factures'})
        self.assertEqual(resp.status_code, 400, resp.content)
        self.assertIn('entite', resp.json())

    def test_creation_lot_valide_ordonne_automatiquement(self):
        resp_clients = self.api.post(
            '/api/django/migration/lots-migration/',
            {'projet': self.projet.pk, 'entite': 'clients'})
        self.assertEqual(resp_clients.status_code, 201, resp_clients.content)
        resp_products = self.api.post(
            '/api/django/migration/lots-migration/',
            {'projet': self.projet.pk, 'entite': 'products'})
        self.assertEqual(resp_products.status_code, 201)
        resp_devis = self.api.post(
            '/api/django/migration/lots-migration/',
            {'projet': self.projet.pk, 'entite': 'devis'})
        self.assertEqual(resp_devis.status_code, 201, resp_devis.content)

        lot_clients = LotMigration.objects.get(pk=resp_clients.json()['id'])
        lot_devis = LotMigration.objects.get(pk=resp_devis.json()['id'])
        self.assertLess(lot_clients.ordre, lot_devis.ordre)

    def test_charger_lot_bloque_avant_lot_precedent_reconcilie(self):
        lot_clients = LotMigration.objects.create(
            company=self.company, projet=self.projet, entite='clients',
            ordre=0)
        lot_products = LotMigration.objects.create(
            company=self.company, projet=self.projet, entite='products',
            ordre=1)

        resp = self.api.post(
            f'/api/django/migration/lots-migration/{lot_products.pk}/charger/',
            {'fichier': _fichier(CSV_PRODUCTS, 'products.csv')})
        self.assertEqual(resp.status_code, 400, resp.content)
        self.assertIn('clients', resp.json()['detail'])

        # Charger + réconcilier + terminer le lot 0 lève le blocage.
        services.charger_lot(lot_clients, CSV_CLIENTS, 'clients.csv',
                             user=self.admin)
        lot_clients.refresh_from_db()
        services.reconcilier_lot(lot_clients)
        services.marquer_lot_termine(lot_clients)

        resp2 = self.api.post(
            f'/api/django/migration/lots-migration/{lot_products.pk}/charger/',
            {'fichier': _fichier(CSV_PRODUCTS, 'products.csv')})
        self.assertEqual(resp2.status_code, 200, resp2.content)


def _fichier(contenu, nom):
    from django.core.files.uploadedfile import SimpleUploadedFile
    return SimpleUploadedFile(nom, contenu, content_type='text/csv')
