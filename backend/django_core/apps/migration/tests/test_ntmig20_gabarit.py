"""NTMIG20 — modèles de fichiers source téléchargeables (gabarits)."""
import csv
import io

from django.test import TestCase

from apps.migration import services

from ._base import auth, make_admin, make_company


class GabaritKitCsvTests(TestCase):

    def test_gabarit_sage_clients_colonnes_exactes(self):
        contenu = services.gabarit_kit_csv('sage', 'clients')
        lignes = list(csv.reader(io.StringIO(contenu.decode('utf-8'))))
        entetes = lignes[0]
        self.assertEqual(
            entetes,
            ['code tiers', 'compte', 'raison sociale', 'nom', 'e-mail',
             'email', 'telephone', 'téléphone', 'adresse', 'ice', 'n° ice'])
        # Une ligne d'exemple COMMENTÉE (jamais prise pour une vraie donnée).
        self.assertTrue(lignes[1][0].startswith('#'))

    def test_gabarit_indisponible_pour_source_generique(self):
        with self.assertRaises(services.GabaritIndisponible):
            services.gabarit_kit_csv('excel', 'clients')

    def test_gabarit_indisponible_entite_inconnue(self):
        with self.assertRaises(services.GabaritIndisponible):
            services.gabarit_kit_csv('odoo', 'bidon')


class GabaritKitEndpointTests(TestCase):

    def setUp(self):
        self.company = make_company('ntmig20', 'NTMIG20')
        self.admin = make_admin(self.company, 'ntmig20-admin')
        self.api = auth(self.admin)

    def test_telecharger_gabarit_sage_clients(self):
        resp = self.api.get(
            '/api/django/migration/kits/sage/clients/gabarit/')
        self.assertEqual(resp.status_code, 200, resp.content)
        self.assertEqual(resp['Content-Type'], 'text/csv; charset=utf-8')
        self.assertIn('gabarit-sage-clients.csv',
                      resp['Content-Disposition'])

    def test_gabarit_404_pour_source_sans_kit(self):
        resp = self.api.get(
            '/api/django/migration/kits/excel/clients/gabarit/')
        self.assertEqual(resp.status_code, 404)
