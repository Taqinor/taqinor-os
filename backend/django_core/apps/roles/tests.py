"""Tests RBAC : sérialisation des utilisateurs d'un rôle + audit des rôles.

Couvre :
- l'API /roles/ renvoie la liste légère des utilisateurs portant chaque rôle
  (tâche RBAC « afficher les utilisateurs assignés »),
- create/update/delete d'un rôle écrit une ligne SettingsAuditLog
  section='roles' (tâche RBAC « journaliser à l'audit »),
- la société reste forcée côté serveur (multi-tenant),
- les protections existantes (rôle système / rôle assigné) ne sont pas
  affaiblies.
"""
from django.test import TestCase
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.parametres.models import SettingsAuditLog
from apps.roles.models import Role, ALL_PERMISSIONS

User = get_user_model()


class RolesRbacTest(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='RBAC Co', slug='rbac-co')
        self.admin_role = Role.objects.create(
            company=self.company, nom='Administrateur',
            permissions=ALL_PERMISSIONS, est_systeme=True,
        )
        self.admin = User.objects.create_user(
            username='rbac_admin', password='x', role=self.admin_role,
            role_legacy='admin', company=self.company,
        )
        self.api = APIClient()
        token = str(AccessToken.for_user(self.admin))
        self.api.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')

    # ── Liste des utilisateurs assignés ──────────────────────────────────
    def test_role_serializer_lists_assigned_users(self):
        role = Role.objects.create(
            company=self.company, nom='Comptable', permissions=['stock_voir'])
        User.objects.create_user(
            username='clara', password='x', role=role, company=self.company)
        User.objects.create_user(
            username='omar', password='x', role=role, company=self.company)
        resp = self.api.get(f'/api/django/roles/{role.id}/')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['users_count'], 2)
        usernames = sorted(u['username'] for u in resp.data['users'])
        self.assertEqual(usernames, ['clara', 'omar'])
        for u in resp.data['users']:
            self.assertIn('id', u)

    # ── Audit create / update / delete ───────────────────────────────────
    def test_create_role_writes_audit_row(self):
        resp = self.api.post(
            '/api/django/roles/',
            {'nom': 'Magasinier', 'permissions': ['stock_voir', 'stock_creer']},
            format='json')
        self.assertEqual(resp.status_code, 201)
        rows = SettingsAuditLog.objects.filter(
            company=self.company, section='roles')
        self.assertEqual(rows.count(), 1)
        row = rows.first()
        self.assertEqual(row.field_label, 'Rôle créé')
        self.assertEqual(row.user, self.admin)
        self.assertIn('Magasinier', row.new_value)

    def test_update_role_permissions_writes_audit_row(self):
        role = Role.objects.create(
            company=self.company, nom='Vendeur', permissions=['ventes_voir'])
        resp = self.api.patch(
            f'/api/django/roles/{role.id}/',
            {'permissions': ['ventes_voir', 'ventes_creer']},
            format='json')
        self.assertEqual(resp.status_code, 200)
        rows = SettingsAuditLog.objects.filter(
            company=self.company, section='roles', field_label='Rôle modifié')
        self.assertEqual(rows.count(), 1)

    def test_update_without_change_writes_no_audit_row(self):
        role = Role.objects.create(
            company=self.company, nom='Vendeur', permissions=['ventes_voir'])
        resp = self.api.patch(
            f'/api/django/roles/{role.id}/',
            {'permissions': ['ventes_voir']}, format='json')
        self.assertEqual(resp.status_code, 200)
        self.assertFalse(SettingsAuditLog.objects.filter(
            section='roles', field_label='Rôle modifié').exists())

    def test_delete_role_writes_audit_row(self):
        role = Role.objects.create(
            company=self.company, nom='Temp', permissions=['stock_voir'])
        resp = self.api.delete(f'/api/django/roles/{role.id}/')
        self.assertEqual(resp.status_code, 204)
        rows = SettingsAuditLog.objects.filter(
            company=self.company, section='roles', field_label='Rôle supprimé')
        self.assertEqual(rows.count(), 1)

    # ── Protections existantes préservées ────────────────────────────────
    def test_cannot_delete_system_role(self):
        resp = self.api.delete(f'/api/django/roles/{self.admin_role.id}/')
        self.assertEqual(resp.status_code, 403)
        self.assertTrue(Role.objects.filter(id=self.admin_role.id).exists())

    def test_cannot_delete_assigned_role(self):
        role = Role.objects.create(
            company=self.company, nom='Assigné', permissions=['stock_voir'])
        User.objects.create_user(
            username='ria', password='x', role=role, company=self.company)
        resp = self.api.delete(f'/api/django/roles/{role.id}/')
        self.assertEqual(resp.status_code, 403)
        self.assertTrue(Role.objects.filter(id=role.id).exists())

    def test_company_is_forced_server_side_on_create(self):
        other = Company.objects.create(nom='Autre', slug='autre-co')
        resp = self.api.post(
            '/api/django/roles/',
            {'nom': 'Pirate', 'permissions': ['stock_voir'],
             'company': other.id},
            format='json')
        self.assertEqual(resp.status_code, 201)
        role = Role.objects.get(nom='Pirate')
        self.assertEqual(role.company, self.company)
