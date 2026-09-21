"""NTMIG6 — journal & rollback d'un lot de migration.

``leads`` est la SEULE entité qui cumule aujourd'hui (a) une trace
``ExternalRef`` posée par ``dataimport`` ET (b) un mécanisme d'archivage
EXISTANT (``crm.Lead`` étend ``core.models.SoftDeleteModel``) — voir la
docstring de ``apps.migration.services`` au-dessus d'``annuler_lot``. Ce
fichier couvre donc le rollback réel sur ``leads``, l'isolation multi-lot, la
garde temporelle anti-upsert-sur-préexistant, et le refus explicite pour une
entité sans mécanisme d'archivage (``clients``).
"""
from django.test import TestCase

from apps.crm.models import Client, Lead
from apps.dataimport.models import ExternalRef
from apps.migration import services
from apps.migration.models import LotMigration, ProjetMigration

from ._base import auth, make_admin, make_company
from ._stockage_factice import patcher_stockage

CSV_LEADS = (
    b'nom,email,external_id\n'
    b'Lead A,a@ex.ma,ODOO-1\n'
    b'Lead B,b@ex.ma,ODOO-2\n'
)
CSV_CLIENTS = b'nom,email,external_id\nClient A,a@ex.ma,ODOO-1\n'


class AnnulerLotLeadsTests(TestCase):

    def setUp(self):
        self.stockage = patcher_stockage(self)
        self.company = make_company('ntmig6-leads', 'NTMIG6 leads')
        self.admin = make_admin(self.company, 'ntmig6-admin')
        self.projet = ProjetMigration.objects.create(
            company=self.company, nom='Bascule', source='odoo')
        self.lot = LotMigration.objects.create(
            company=self.company, projet=self.projet, entite='leads')

    def test_rien_a_annuler_sur_lot_vierge(self):
        with self.assertRaises(services.RollbackImpossible):
            services.annuler_lot(self.lot)

    def test_annule_exactement_les_leads_crees(self):
        services.charger_lot(self.lot, CSV_LEADS, 'leads.csv', user=self.admin)
        self.lot.refresh_from_db()
        self.assertEqual(self.lot.crees, 2)
        self.assertEqual(Lead.objects.filter(company=self.company).count(), 2)

        resultat = services.annuler_lot(self.lot, user=self.admin)

        self.assertEqual(resultat['archives'], 2)
        self.lot.refresh_from_db()
        self.assertEqual(self.lot.statut, LotMigration.Statut.EN_ATTENTE)
        self.assertEqual(self.lot.crees, 0)
        # SOFT-delete : les leads existent toujours, mais archivés.
        self.assertEqual(
            Lead.all_objects.filter(company=self.company).count(), 2)
        self.assertEqual(
            Lead.objects.filter(company=self.company).count(), 0)
        for lead in Lead.all_objects.filter(company=self.company):
            self.assertTrue(lead.is_deleted)
        # Les ExternalRef posées par ce lot disparaissent (rejeu propre).
        self.assertEqual(
            ExternalRef.objects.filter(
                company=self.company,
                external_system=services.external_system_pour(self.projet),
            ).count(), 0)

    def test_isolation_ne_touche_pas_un_autre_projet(self):
        autre_projet = ProjetMigration.objects.create(
            company=self.company, nom='Autre', source='odoo')
        autre_lot = LotMigration.objects.create(
            company=self.company, projet=autre_projet, entite='leads')
        services.charger_lot(autre_lot, CSV_LEADS, 'leads.csv', user=self.admin)

        # Rien n'a jamais été chargé dans self.lot : annuler refuse.
        with self.assertRaises(services.RollbackImpossible):
            services.annuler_lot(self.lot)

        autre_lot.refresh_from_db()
        self.assertEqual(
            Lead.objects.filter(company=self.company).count(), 2)

    def test_ne_touche_pas_un_lead_preexistant_rapproche_par_upsert(self):
        """Garde temporelle : un lead créé AVANT ce chargement, rapproché par
        upsert (même email), n'est jamais archivé par le rollback."""
        preexistant = Lead.objects.create(
            company=self.company, nom='Ancien', email='a@ex.ma')
        # Le rapprochement upsert se fait par contact normalisé : le fichier
        # rejoint ce lead existant (même email) au lieu d'en créer un nouveau.
        services.charger_lot(self.lot, CSV_LEADS, 'leads.csv', user=self.admin)
        self.lot.refresh_from_db()
        self.assertEqual(self.lot.maj, 1)  # "Lead A" a été RAPPROCHÉ, pas créé
        self.assertEqual(self.lot.crees, 1)  # seul "Lead B" est neuf

        services.annuler_lot(self.lot, user=self.admin)

        preexistant.refresh_from_db()
        self.assertFalse(preexistant.is_deleted)
        nouveau = Lead.all_objects.get(email='b@ex.ma')
        self.assertTrue(nouveau.is_deleted)

    def test_endpoint_annuler(self):
        services.charger_lot(self.lot, CSV_LEADS, 'leads.csv', user=self.admin)
        api = auth(self.admin)
        resp = api.post(
            f'/api/django/migration/lots-migration/{self.lot.pk}/annuler/')
        self.assertEqual(resp.status_code, 200, resp.content)
        self.assertEqual(resp.json()['annulation']['archives'], 2)
        self.assertEqual(
            resp.json()['lot']['statut'], LotMigration.Statut.EN_ATTENTE)

    def test_endpoint_annuler_refuse_lot_vierge(self):
        api = auth(self.admin)
        resp = api.post(
            f'/api/django/migration/lots-migration/{self.lot.pk}/annuler/')
        self.assertEqual(resp.status_code, 400, resp.content)


class AnnulerLotClientsNonPriseEnChargeTests(TestCase):
    """``crm.Client`` n'a aucun mécanisme d'archivage existant — refus
    explicite, jamais un hard-delete de repli (voir la docstring du module)."""

    def setUp(self):
        self.stockage = patcher_stockage(self)
        self.company = make_company('ntmig6-clients', 'NTMIG6 clients')
        self.admin = make_admin(self.company, 'ntmig6-admin')
        self.projet = ProjetMigration.objects.create(
            company=self.company, nom='Bascule', source='odoo')
        self.lot = LotMigration.objects.create(
            company=self.company, projet=self.projet, entite='clients')
        services.charger_lot(self.lot, CSV_CLIENTS, 'clients.csv',
                             user=self.admin)
        self.lot.refresh_from_db()

    def test_refuse_annulation_client(self):
        with self.assertRaises(services.RollbackImpossible):
            services.annuler_lot(self.lot, user=self.admin)
        # Rien n'est supprimé : le refus est total, pas partiel.
        self.assertEqual(Client.objects.filter(company=self.company).count(), 1)
        self.lot.refresh_from_db()
        self.assertNotEqual(self.lot.statut, LotMigration.Statut.EN_ATTENTE)
