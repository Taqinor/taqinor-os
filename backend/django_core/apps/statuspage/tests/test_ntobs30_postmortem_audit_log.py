"""NTOBS30 — publication d'un post-mortem journalisée dans audit.AuditLog.

LIMITE ASSUMÉE DE CE LOT (lane isolée) : sur les 5 actions Fiabilité listées
par le plan (création/annulation MaintenanceWindow, lancement export de
réversibilité, publication post-mortem, émission crédit SLA, édition
SlaCreditPolicy), SEULE la publication de post-mortem (celle-ci) est
implémentée ici. Les 4 autres vivent dans ``core`` (``core.maintenance_
windows``/``core.export_registry``/``core.sla``), qui NE PEUT JAMAIS
importer ``apps.audit`` (contrat import-linter
``core-foundation-is-a-base-layer`` — ``.importlinter``, ``type = forbidden``,
``source_modules = core`` / ``forbidden_modules = apps``, AUCUNE exception
pour ``apps.audit``). Les journaliser correctement demande un NOUVEAU signal
``core.events`` (ex. ``maintenance_window_created``,
``export_reversibilite_declenche``, ``sla_credit_statut_change``,
``sla_credit_policy_edited``) + un abonné dans ``apps/audit/receivers.py`` —
deux fichiers HORS PÉRIMÈTRE de cette lane (``core/events.py`` appartient à
une autre lane en ce moment ; ``apps/audit`` n'est pas dans le périmètre
accordé). ``apps.statuspage`` n'est PAS ``core`` : elle peut importer
``apps.audit.recorder`` directement, comme de nombreuses autres apps
satellites (crm, compta, contrats…)."""
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from apps.audit.models import AuditLog
from apps.roles.models import Role
from authentication.models import Company

from ..models import IncidentPublic

User = get_user_model()


class PublierPostmortemAuditLogTest(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='Acme', slug='acme-nt30')
        self.role_directeur = Role.objects.create(
            company=self.company, nom='Directeur')
        self.directeur = User.objects.create_user(
            'directeur30', password='x', company=self.company,
            role=self.role_directeur)
        self.incident = IncidentPublic.objects.create(
            titre='Panne stockage', statut=IncidentPublic.Statut.RESOLVED,
            debute_le=timezone.now(), resolu_le=timezone.now(), company=None,
            postmortem_markdown='Cause : disque plein. Correctif : purge.',
        )

    def _client(self, user):
        c = APIClient()
        c.force_authenticate(user)
        return c

    def test_publishing_postmortem_creates_audit_log_entry(self):
        url = (
            f'/api/django/statuspage/incidents/{self.incident.pk}/'
            'publier-postmortem/')
        avant = AuditLog.objects.count()
        resp = self._client(self.directeur).post(url)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(AuditLog.objects.count(), avant + 1)

        entry = AuditLog.objects.latest('id')
        self.assertEqual(entry.action, AuditLog.Action.STATUS)
        self.assertEqual(entry.user_id, self.directeur.id)
        self.assertIn('Panne stockage', entry.detail)
        # Jamais le contenu du post-mortem en clair dans le journal.
        self.assertNotIn('disque plein', entry.detail)

    def test_republishing_creates_another_entry(self):
        """Idempotent côté métier (``postmortem_publie_le`` réactualisé), mais
        chaque republication reste une action tracée séparément."""
        url = (
            f'/api/django/statuspage/incidents/{self.incident.pk}/'
            'publier-postmortem/')
        client = self._client(self.directeur)
        client.post(url)
        avant = AuditLog.objects.count()
        client.post(url)
        self.assertEqual(AuditLog.objects.count(), avant + 1)
