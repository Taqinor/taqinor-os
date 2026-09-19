"""NTOBS30-reste — 3 des 4 signaux ``core.events`` listés par la lane NTOBS30
d'origine (voir la docstring de ``apps/statuspage/tests/
test_ntobs30_postmortem_audit_log.py``) : ``maintenance_window_created``,
``export_reversibilite_declenche``, ``sla_credit_statut_change``, émis
depuis les vues ``core`` concernées et journalisés par
``apps/audit/receivers.py`` (``core`` ne peut jamais importer ``apps.audit``
— contrat import-linter ``core-foundation-is-a-base-layer``).

La 4ᵉ action listée par le plan (« édition SlaCreditPolicy ») N'A AUCUNE vue
d'écriture dans ce dépôt (``core.sla.SlaCreditPolicy`` n'est exposée par
aucun viewset ni admin) : aucun signal ``sla_credit_policy_edited`` n'est
donc déclaré — un signal jamais émis serait un seam creux, pas un contrat
(voir la docstring de ``core/events.py``, section NTOBS30-reste)."""
from unittest import mock

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from apps.audit.models import AuditLog
from apps.roles.models import Role
from authentication.models import Company
from core.export_registry import ExportReversibiliteRun
from core.maintenance_windows import MaintenanceWindow
from core.sla import SlaSnapshot, generer_snapshot_societe

User = get_user_model()


def make_company(slug, nom):
    return Company.objects.get_or_create(slug=slug, defaults={'nom': nom})[0]


def make_directeur(company, username):
    role = Role.objects.create(company=company, nom='Directeur')
    return User.objects.create_user(
        username, password='x', company=company, role=role)


class MaintenanceWindowCreatedAuditTests(TestCase):
    def setUp(self):
        self.company = make_company('ntobs30r-mw', 'NTOBS30r MW')
        self.directeur = make_directeur(self.company, 'ntobs30r-mw-dir')
        self.api = APIClient()
        self.api.force_authenticate(self.directeur)

    def test_creation_via_api_journalise_un_audit_log(self):
        now = timezone.now()
        resp = self.api.post('/api/django/core/maintenance-windows/', {
            'debute_le': (now + timezone.timedelta(days=1)).isoformat(),
            'termine_le': (now + timezone.timedelta(days=1, hours=1)).isoformat(),
            'description': 'Bascule infra planifiée.',
        })
        self.assertEqual(resp.status_code, 201, resp.data)

        from django.contrib.contenttypes.models import ContentType
        ct = ContentType.objects.get_for_model(MaintenanceWindow)
        entries = AuditLog.objects.filter(
            content_type=ct, object_id=str(resp.data['id']),
            action=AuditLog.Action.CREATE)
        self.assertEqual(entries.count(), 1)
        entry = entries.first()
        self.assertEqual(entry.user_id, self.directeur.id)
        self.assertEqual(entry.company_id, self.company.id)
        self.assertIn('Fenêtre de maintenance créée', entry.detail)


class ExportReversibiliteDeclencheAuditTests(TestCase):
    def setUp(self):
        self.company = make_company('ntobs30r-exp', 'NTOBS30r Export')
        self.directeur = make_directeur(self.company, 'ntobs30r-exp-dir')
        self.api = APIClient()
        self.api.force_authenticate(self.directeur)

    def test_declenchement_via_api_journalise_un_audit_log(self):
        with mock.patch('core.tasks.export_reversibilite_tenant.delay'):
            resp = self.api.post('/api/django/core/export-reversibilite/')
        self.assertEqual(resp.status_code, 202, resp.data)

        run = ExportReversibiliteRun.objects.get(id=resp.data['id'])
        from django.contrib.contenttypes.models import ContentType
        ct = ContentType.objects.get_for_model(ExportReversibiliteRun)
        entries = AuditLog.objects.filter(
            content_type=ct, object_id=str(run.id),
            action=AuditLog.Action.EXPORT)
        self.assertEqual(entries.count(), 1)
        entry = entries.first()
        self.assertEqual(entry.user_id, self.directeur.id)
        self.assertEqual(entry.company_id, self.company.id)


class SlaCreditStatutChangeAuditTests(TestCase):
    def setUp(self):
        self.company = make_company('ntobs30r-sla', 'NTOBS30r SLA')
        self.role_admin_fiabilite = Role.objects.create(
            company=self.company, nom='Administration Fiabilité',
            permissions=['fiabilite_administration'])
        self.admin = User.objects.create_user(
            'ntobs30r-sla-adm', password='x', company=self.company,
            role=self.role_admin_fiabilite)
        self.api = APIClient()
        self.api.force_authenticate(self.admin)
        self.snapshot = generer_snapshot_societe(
            self.company, timezone.now().date().replace(day=1))

    def test_decision_via_api_journalise_un_diff_structure(self):
        ancien = self.snapshot.credit_statut
        resp = self.api.post(
            f'/api/django/core/sla/credits/{self.snapshot.pk}/statut/',
            {'statut': 'emis'})
        self.assertEqual(resp.status_code, 200, resp.data)

        from django.contrib.contenttypes.models import ContentType
        ct = ContentType.objects.get_for_model(SlaSnapshot)
        entries = AuditLog.objects.filter(
            content_type=ct, object_id=str(self.snapshot.pk),
            action=AuditLog.Action.STATUS)
        self.assertEqual(entries.count(), 1)
        entry = entries.first()
        self.assertEqual(entry.user_id, self.admin.id)
        self.assertEqual(entry.company_id, self.company.id)
        self.assertEqual(entry.changes, [
            {'field': 'credit_statut', 'old': ancien or '', 'new': 'emis'}])
