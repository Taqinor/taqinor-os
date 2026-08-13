"""NTMIG33 — migration à blanc sur le tenant sandbox (jamais la production)."""
import tempfile

from django.test import TestCase, override_settings
from django.utils import timezone

from apps.adminops.models import SandboxEnvironment
from apps.crm.models import Client
from apps.migration import services
from apps.migration.models import LotMigration, ProjetMigration

from ._base import auth, make_admin, make_company

CSV = (
    'Nom,Email\n'
    'Client A,a@exemple.ma\n'
    'Client B,b@exemple.ma\n'
).encode('utf-8')

_MEDIA = tempfile.mkdtemp(prefix='ntmig33-')


@override_settings(MEDIA_ROOT=_MEDIA)
class MigrationABlancTests(TestCase):

    def setUp(self):
        self.company = make_company('ntmig33', 'NTMIG33')
        self.admin = make_admin(self.company, 'ntmig33-admin')
        self.projet = ProjetMigration.objects.create(
            company=self.company, nom='Bascule Odoo', source='odoo')
        self.lot = LotMigration.objects.create(
            company=self.company, projet=self.projet, entite='clients')
        services.memoriser_fichier_source(self.lot, CSV, 'clients.csv')
        self.lot.save(update_fields=[
            'fichier_source', 'fichier_source_nom', 'updated_at'])

    def _provisionner_sandbox(self):
        self.sandbox_company = make_company(
            'ntmig33-sandbox', 'NTMIG33 sandbox')
        return SandboxEnvironment.objects.create(
            company=self.company, sandbox_company=self.sandbox_company,
            statut=SandboxEnvironment.Statut.PRET,
            date_expiration=timezone.now() + timezone.timedelta(days=14))

    def test_sans_sandbox_no_op_propre(self):
        with self.assertRaises(services.SandboxIndisponible):
            services.migrer_a_blanc(self.projet, user=self.admin)
        # Rien n'a été créé : ni projet miroir, ni donnée.
        self.assertEqual(ProjetMigration.objects.count(), 1)
        self.assertEqual(Client.objects.count(), 0)

    def test_sandbox_en_creation_ne_suffit_pas(self):
        sandbox_company = make_company('ntmig33-sbx2', 'NTMIG33 sbx2')
        SandboxEnvironment.objects.create(
            company=self.company, sandbox_company=sandbox_company,
            statut=SandboxEnvironment.Statut.EN_CREATION,
            date_expiration=timezone.now() + timezone.timedelta(days=14))
        with self.assertRaises(services.SandboxIndisponible):
            services.migrer_a_blanc(self.projet, user=self.admin)

    def test_charge_dans_le_sandbox_et_jamais_en_production(self):
        self._provisionner_sandbox()

        rapport = services.migrer_a_blanc(self.projet, user=self.admin)

        self.assertEqual(rapport['societe_sandbox'], self.sandbox_company.pk)
        self.assertTrue(rapport['conforme'])
        # Les clients sont créés DANS le sandbox, jamais dans la production.
        self.assertEqual(Client.objects.filter(
            company=self.sandbox_company).count(), 2)
        self.assertEqual(Client.objects.filter(
            company=self.company).count(), 0)
        # Le projet d'origine est intact.
        self.projet.refresh_from_db()
        self.lot.refresh_from_db()
        self.assertEqual(
            self.projet.statut, ProjetMigration.Statut.BROUILLON)
        self.assertEqual(self.lot.statut, LotMigration.Statut.EN_ATTENTE)
        self.assertEqual(self.lot.crees, 0)

    def test_rapport_de_reconciliation_produit_dans_le_sandbox(self):
        self._provisionner_sandbox()
        rapport = services.migrer_a_blanc(self.projet, user=self.admin)
        lot_blanc = LotMigration.objects.get(pk=rapport['lots'][0]['lot_blanc'])
        self.assertEqual(lot_blanc.company, self.sandbox_company)
        self.assertEqual(lot_blanc.rapports.count(), 1)
        self.assertTrue(lot_blanc.rapports.first().conforme)

    def test_lot_sans_fichier_est_saute_avec_motif(self):
        self._provisionner_sandbox()
        LotMigration.objects.create(
            company=self.company, projet=self.projet, entite='products',
            ordre=2)

        rapport = services.migrer_a_blanc(self.projet, user=self.admin)

        saute = [r for r in rapport['lots'] if r['saute']]
        self.assertEqual(len(saute), 1)
        self.assertEqual(saute[0]['entite'], 'products')
        self.assertIn('Fichier source', saute[0]['motif'])

    def test_sandbox_pointant_sur_la_production_est_refuse(self):
        """Garde-fou : un sandbox mal provisionné ne devient pas un import réel."""
        SandboxEnvironment.objects.create(
            company=self.company, sandbox_company=self.company,
            statut=SandboxEnvironment.Statut.PRET,
            date_expiration=timezone.now() + timezone.timedelta(days=14))
        with self.assertRaises(services.SandboxIndisponible):
            services.migrer_a_blanc(self.projet, user=self.admin)
        self.assertEqual(Client.objects.filter(
            company=self.company).count(), 0)

    def test_endpoint_sans_sandbox_renvoie_400(self):
        api = auth(self.admin)
        resp = api.post(
            f'/api/django/migration/projets-migration/{self.projet.pk}/'
            'migrer-a-blanc/')
        self.assertEqual(resp.status_code, 400)
        self.assertIn('sandbox', resp.json()['detail'].lower())

    def test_endpoint_avec_sandbox(self):
        self._provisionner_sandbox()
        api = auth(self.admin)
        resp = api.post(
            f'/api/django/migration/projets-migration/{self.projet.pk}/'
            'migrer-a-blanc/')
        self.assertEqual(resp.status_code, 200, resp.content)
        self.assertTrue(resp.json()['conforme'])
