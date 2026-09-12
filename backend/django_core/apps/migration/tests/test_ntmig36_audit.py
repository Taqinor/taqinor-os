"""NTMIG36 — piste d'audit complète de la migration.

Chaque action (analyse, chargement, réconciliation, dérogation, annulation,
purge) journalise via la primitive plateforme UNIQUE
(``apps.audit.recorder.record``) — jamais un second journal maison. Le
``content_type`` de l'instance journalisée (``migration.LotMigration``/
``ProjetMigration``/``RapportReconciliation``) suffit à retracer une
migration complète dans ``/journal``.
"""
from django.contrib.contenttypes.models import ContentType
from django.test import TestCase

from apps.audit.models import AuditLog
from apps.migration import services
from apps.migration.models import LotMigration, ProjetMigration, \
    RapportReconciliation

from ._base import make_admin, make_company
from ._stockage_factice import patcher_stockage

CSV = b'nom,email,external_id\nClient A,a@ex.ma,ODOO-1\n'


def _logs_pour(instance):
    ct = ContentType.objects.get_for_model(type(instance))
    return AuditLog.objects.filter(
        content_type=ct, object_id=str(instance.pk)).order_by('timestamp')


class PisteAuditMigrationTests(TestCase):

    def setUp(self):
        self.stockage = patcher_stockage(self)
        self.company = make_company('ntmig36', 'NTMIG36')
        self.admin = make_admin(self.company, 'ntmig36-admin')
        self.projet = ProjetMigration.objects.create(
            company=self.company, nom='Bascule', source='odoo')
        self.lot = LotMigration.objects.create(
            company=self.company, projet=self.projet, entite='clients')

    def test_analyse_journalisee(self):
        services.analyser_lot(self.lot, CSV, 'clients.csv', user=self.admin)
        logs = _logs_pour(self.lot)
        self.assertTrue(
            any('Analyse' in log.detail for log in logs), logs)

    def test_chargement_journalise(self):
        services.charger_lot(self.lot, CSV, 'clients.csv', user=self.admin)
        logs = _logs_pour(self.lot)
        self.assertTrue(
            any('Chargement' in log.detail for log in logs), logs)
        self.assertEqual(logs.first().user_id, self.admin.pk)

    def test_reconciliation_journalisee(self):
        services.charger_lot(self.lot, CSV, 'clients.csv', user=self.admin)
        self.lot.refresh_from_db()
        rapport = services.reconcilier_lot(self.lot)
        logs = _logs_pour(rapport)
        self.assertTrue(any('conciliation' in log.detail for log in logs))

    def test_derogation_journalisee(self):
        services.deroger_reconcile(self.lot, 'Écart accepté', self.admin)
        logs = _logs_pour(self.lot)
        self.assertTrue(
            any('rogation' in log.detail and 'Écart accepté' in log.detail
                for log in logs))

    def test_piste_complete_dans_l_ordre(self):
        """Dérouler analyse → charger → réconcilier → déroger produit une
        piste d'audit ORDONNÉE retraçant qui a fait quoi et quand."""
        services.analyser_lot(self.lot, CSV, 'clients.csv', user=self.admin)
        services.charger_lot(self.lot, CSV, 'clients.csv', user=self.admin)
        self.lot.refresh_from_db()
        services.reconcilier_lot(self.lot)
        services.deroger_reconcile(self.lot, 'Motif test', self.admin)

        ct_lot = ContentType.objects.get_for_model(LotMigration)
        ct_rapport = ContentType.objects.get_for_model(RapportReconciliation)
        toutes = AuditLog.objects.filter(
            content_type__in=[ct_lot, ct_rapport]).order_by('timestamp')
        actions = [(log.content_type_id, log.detail[:20]) for log in toutes]
        self.assertGreaterEqual(len(actions), 4)
        libelles = ' | '.join(log.detail for log in toutes)
        self.assertIn('Analyse', libelles)
        self.assertIn('Chargement', libelles)
