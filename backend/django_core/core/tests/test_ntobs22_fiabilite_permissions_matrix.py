"""NTOBS22-câblage — permissions fines (``fiabilite_voir``/``fiabilite_
administration``) sur les 6 vues Fiabilité concrètes, au lieu des gardes
``IsDirecteurOrAdmin``/``IsAdminOrResponsableTier`` codés en dur.

Le catalogue lui-même (``ALL_PERMISSIONS``, héritage Directeur/Administrateur,
exclusion de ``PERMISSION_MODULE``) est déjà testé par
``apps/roles/tests_ntobs22_fiabilite_permissions.py`` (autre lane) — ce
module teste le CÂBLAGE réel sur les vues :

  1. ``MaintenanceWindowListCreateView`` GET (liste)
  2. ``MaintenanceWindowListCreateView`` POST (création)
  3. ``annuler_fenetre`` POST
  4. ``SlaCreditsDusListView`` GET (bornée à sa société pour un non-admin)
  5. ``sla_credit_statut`` POST
  6. ``BackupRunViewSet`` (GET liste / POST création)

Aucun rôle système « Comptable » n'existe dans ce dépôt (cf. la docstring de
``apps/roles/tests_ntobs22_fiabilite_permissions.py``) : les rôles
``fiabilite_voir``/``fiabilite_administration`` ci-dessous sont des rôles
CUSTOM créés pour le test, exactement comme un Directeur les octroierait
depuis l'éditeur de rôles."""
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from apps.roles.models import Role
from authentication.models import Company
from core.maintenance_windows import MaintenanceWindow
from core.models import BackupRun
from core.sla import SlaSnapshot, generer_snapshot_societe

User = get_user_model()


class Ntobs22PermissionsMatrixTest(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='Acme', slug='ntobs22-acme')
        self.autre = Company.objects.create(nom='Autre', slug='ntobs22-autre')

        self.role_voir = Role.objects.create(
            company=self.company, nom='Lecture Fiabilité',
            permissions=['fiabilite_voir'])
        self.role_admin_fiabilite = Role.objects.create(
            company=self.company, nom='Administration Fiabilité',
            permissions=['fiabilite_administration'])
        self.role_aucun = Role.objects.create(
            company=self.company, nom='Sans droit Fiabilité', permissions=[])
        self.role_directeur = Role.objects.create(
            company=self.company, nom='Directeur')

        self.u_voir = User.objects.create_user(
            'voir22', password='x', company=self.company, role=self.role_voir)
        self.u_admin_fiab = User.objects.create_user(
            'admfiab22', password='x', company=self.company,
            role=self.role_admin_fiabilite)
        self.u_aucun = User.objects.create_user(
            'aucun22', password='x', company=self.company,
            role=self.role_aucun)
        self.u_directeur = User.objects.create_user(
            'directeur22', password='x', company=self.company,
            role=self.role_directeur)

    def _client(self, user):
        c = APIClient()
        c.force_authenticate(user)
        return c

    # ── 1/2/3 — fenêtres de maintenance ─────────────────────────────────

    def test_maintenance_list_readable_by_fiabilite_voir(self):
        resp = self._client(self.u_voir).get(
            '/api/django/core/maintenance-windows/')
        self.assertEqual(resp.status_code, 200)

    def test_maintenance_list_forbidden_without_any_grant(self):
        resp = self._client(self.u_aucun).get(
            '/api/django/core/maintenance-windows/')
        self.assertEqual(resp.status_code, 403)

    def test_maintenance_create_forbidden_for_fiabilite_voir_only(self):
        resp = self._client(self.u_voir).post(
            '/api/django/core/maintenance-windows/', {})
        self.assertEqual(resp.status_code, 403)

    def test_maintenance_create_allowed_for_fiabilite_administration(self):
        now = timezone.now()
        payload = {
            'debute_le': (now + timezone.timedelta(days=1)).isoformat(),
            'termine_le': (now + timezone.timedelta(days=1, hours=1)).isoformat(),
            'description': 'Test NTOBS22',
        }
        resp = self._client(self.u_admin_fiab).post(
            '/api/django/core/maintenance-windows/', payload)
        self.assertEqual(resp.status_code, 201, resp.data)

    def test_directeur_never_regresses(self):
        now = timezone.now()
        payload = {
            'debute_le': (now + timezone.timedelta(days=1)).isoformat(),
            'termine_le': (now + timezone.timedelta(days=1, hours=1)).isoformat(),
            'description': 'Test NTOBS22 Directeur',
        }
        resp = self._client(self.u_directeur).post(
            '/api/django/core/maintenance-windows/', payload)
        self.assertEqual(resp.status_code, 201, resp.data)
        resp = self._client(self.u_directeur).get(
            '/api/django/core/maintenance-windows/')
        self.assertEqual(resp.status_code, 200)

    def test_annuler_fenetre_forbidden_for_fiabilite_voir_only(self):
        fenetre = MaintenanceWindow.objects.create(
            company=self.company,
            debute_le=timezone.now() + timezone.timedelta(hours=1),
            termine_le=timezone.now() + timezone.timedelta(hours=2),
            description='X')
        resp = self._client(self.u_voir).post(
            f'/api/django/core/maintenance-windows/{fenetre.pk}/annuler/')
        self.assertEqual(resp.status_code, 403)

    def test_annuler_fenetre_allowed_for_fiabilite_administration(self):
        fenetre = MaintenanceWindow.objects.create(
            company=self.company,
            debute_le=timezone.now() + timezone.timedelta(hours=1),
            termine_le=timezone.now() + timezone.timedelta(hours=2),
            description='X')
        resp = self._client(self.u_admin_fiab).post(
            f'/api/django/core/maintenance-windows/{fenetre.pk}/annuler/')
        self.assertEqual(resp.status_code, 200)

    # ── 4/5 — SLA (crédits cross-tenant + statut de crédit) ─────────────

    def test_sla_credits_forbidden_without_any_grant(self):
        resp = self._client(self.u_aucun).get('/api/django/core/sla/credits/')
        self.assertEqual(resp.status_code, 403)

    def test_sla_credits_fiabilite_voir_sees_only_own_company(self):
        snap_mine = generer_snapshot_societe(
            self.company, timezone.now().date().replace(day=1))
        snap_mine.credit_statut = SlaSnapshot.CreditStatut.A_EMETTRE
        snap_mine.save(update_fields=['credit_statut'])
        snap_autre = generer_snapshot_societe(
            self.autre, timezone.now().date().replace(day=1))
        snap_autre.credit_statut = SlaSnapshot.CreditStatut.A_EMETTRE
        snap_autre.save(update_fields=['credit_statut'])

        resp = self._client(self.u_voir).get('/api/django/core/sla/credits/')
        self.assertEqual(resp.status_code, 200)
        ids = [row['id'] for row in resp.data]
        self.assertIn(snap_mine.id, ids)
        self.assertNotIn(snap_autre.id, ids)

    def test_sla_credits_directeur_sees_all_companies(self):
        snap_mine = generer_snapshot_societe(
            self.company, timezone.now().date().replace(day=1))
        snap_mine.credit_statut = SlaSnapshot.CreditStatut.A_EMETTRE
        snap_mine.save(update_fields=['credit_statut'])
        snap_autre = generer_snapshot_societe(
            self.autre, timezone.now().date().replace(day=1))
        snap_autre.credit_statut = SlaSnapshot.CreditStatut.A_EMETTRE
        snap_autre.save(update_fields=['credit_statut'])

        resp = self._client(self.u_directeur).get(
            '/api/django/core/sla/credits/')
        self.assertEqual(resp.status_code, 200)
        ids = [row['id'] for row in resp.data]
        self.assertIn(snap_mine.id, ids)
        self.assertIn(snap_autre.id, ids)

    def test_sla_credit_statut_forbidden_for_fiabilite_voir_only(self):
        snapshot = generer_snapshot_societe(
            self.company, timezone.now().date().replace(day=1))
        resp = self._client(self.u_voir).post(
            f'/api/django/core/sla/credits/{snapshot.pk}/statut/',
            {'statut': 'emis'})
        self.assertEqual(resp.status_code, 403)

    def test_sla_credit_statut_allowed_for_fiabilite_administration(self):
        snapshot = generer_snapshot_societe(
            self.company, timezone.now().date().replace(day=1))
        resp = self._client(self.u_admin_fiab).post(
            f'/api/django/core/sla/credits/{snapshot.pk}/statut/',
            {'statut': 'emis'})
        self.assertEqual(resp.status_code, 200, resp.data)

    # ── 6 — Sauvegardes (BackupRunViewSet) ───────────────────────────────

    def test_backups_list_readable_by_fiabilite_voir(self):
        resp = self._client(self.u_voir).get('/api/django/core/sauvegardes/')
        self.assertEqual(resp.status_code, 200)

    def test_backups_list_forbidden_without_any_grant(self):
        resp = self._client(self.u_aucun).get('/api/django/core/sauvegardes/')
        self.assertEqual(resp.status_code, 403)

    def test_backups_create_forbidden_for_fiabilite_voir_only(self):
        resp = self._client(self.u_voir).post(
            '/api/django/core/sauvegardes/', {'kind': BackupRun.KIND_EXPORT})
        self.assertEqual(resp.status_code, 403)

    def test_backups_create_allowed_for_fiabilite_administration(self):
        resp = self._client(self.u_admin_fiab).post(
            '/api/django/core/sauvegardes/', {'kind': BackupRun.KIND_EXPORT})
        self.assertEqual(resp.status_code, 201, resp.data)
