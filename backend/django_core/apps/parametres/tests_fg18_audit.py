"""FG18 — complétude du journal d'audit des Paramètres.

Vérifie que les écritures de gestion d'utilisateurs (rôle / activation /
superviseur / création / suppression) et d'automatisations (création /
bascule / suppression) écrivent désormais une ligne ``SettingsAuditLog``, et
que l'endpoint ``audit/sections/`` expose les sections."""
from django.test import TestCase
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.parametres.models import SettingsAuditLog
from apps.roles.models import Role, ADMIN_PERMISSIONS, COMMERCIAL_PERMISSIONS

User = get_user_model()


def _company(slug='fg18-co', nom='FG18 Co'):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


class FG18UserAuditTest(TestCase):
    def setUp(self):
        self.company = _company()
        self.admin_role = Role.objects.create(
            company=self.company, nom='Administrateur',
            permissions=list(ADMIN_PERMISSIONS), est_systeme=True)
        self.commercial_role = Role.objects.create(
            company=self.company, nom='Commercial',
            permissions=list(COMMERCIAL_PERMISSIONS))
        self.admin = User.objects.create_user(
            username='fg18_admin', password='pw', role_legacy='admin',
            role=self.admin_role, company=self.company)
        self.target = User.objects.create_user(
            username='fg18_target', password='pw', role_legacy='utilisateur',
            role=self.commercial_role, company=self.company)
        self.api = APIClient()
        token = str(AccessToken.for_user(self.admin))
        self.api.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')

    def _user_rows(self):
        return SettingsAuditLog.objects.filter(
            company=self.company, section='utilisateurs')

    def test_role_change_is_audited(self):
        r = self.api.patch(
            f'/api/django/users/{self.target.id}/',
            {'role': self.admin_role.id}, format='json')
        self.assertEqual(r.status_code, 200, r.content)
        row = self._user_rows().filter(
            field=f'user:{self.target.username}:role').first()
        self.assertIsNotNone(row)
        self.assertEqual(row.new_value, 'Administrateur')
        self.assertEqual(row.user_id, self.admin.id)

    def test_deactivation_is_audited(self):
        r = self.api.patch(
            f'/api/django/users/{self.target.id}/',
            {'is_active': False}, format='json')
        self.assertEqual(r.status_code, 200, r.content)
        row = self._user_rows().filter(
            field=f'user:{self.target.username}:actif').first()
        self.assertIsNotNone(row)
        self.assertEqual(row.new_value, 'désactivé')

    def test_supervisor_change_is_audited(self):
        r = self.api.patch(
            f'/api/django/users/{self.target.id}/',
            {'supervisor': self.admin.id}, format='json')
        self.assertEqual(r.status_code, 200, r.content)
        row = self._user_rows().filter(
            field=f'user:{self.target.username}:superviseur').first()
        self.assertIsNotNone(row)
        self.assertEqual(row.new_value, str(self.admin.id))

    def test_user_delete_is_audited(self):
        uname = self.target.username
        r = self.api.delete(f'/api/django/users/{self.target.id}/')
        self.assertEqual(r.status_code, 204, r.content)
        row = self._user_rows().filter(field=f'user:{uname}').first()
        self.assertIsNotNone(row)
        self.assertEqual(row.field_label, 'Utilisateur supprimé')

    def test_unchanged_user_writes_nothing(self):
        self.api.patch(
            f'/api/django/users/{self.target.id}/',
            {'email': 'x@y.z'}, format='json')
        # Pas de changement rôle/actif/superviseur → aucune ligne d'audit.
        self.assertEqual(
            self._user_rows().exclude(field_label='Utilisateur créé').count(),
            0)

    def test_sections_endpoint_lists_known_sections(self):
        r = self.api.get('/api/django/parametres/audit/sections/')
        self.assertEqual(r.status_code, 200)
        values = {s['value'] for s in r.data['sections']}
        # VX233 — 'tarification' rejoint les sections connues (≥ 6 au total).
        for s in ('profil', 'roles', 'utilisateurs', 'automatisations',
                  'messages', 'tarification'):
            self.assertIn(s, values)
        self.assertGreaterEqual(len(values), 6)

    def test_sections_endpoint_admin_only(self):
        viewer = User.objects.create_user(
            username='fg18_viewer', password='pw', role_legacy='utilisateur',
            company=self.company)
        api = APIClient()
        token = str(AccessToken.for_user(viewer))
        api.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')
        r = api.get('/api/django/parametres/audit/sections/')
        self.assertEqual(r.status_code, 403)


class FG18AutomationAuditTest(TestCase):
    def setUp(self):
        self.company = _company(slug='fg18-auto', nom='FG18 Auto')
        self.admin_role = Role.objects.create(
            company=self.company, nom='Administrateur',
            permissions=list(ADMIN_PERMISSIONS), est_systeme=True)
        self.admin = User.objects.create_user(
            username='fg18_auto_admin', password='pw', role_legacy='admin',
            role=self.admin_role, company=self.company)
        self.api = APIClient()
        token = str(AccessToken.for_user(self.admin))
        self.api.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')

    def _rows(self):
        return SettingsAuditLog.objects.filter(
            company=self.company, section='automatisations')

    def _create_rule(self):
        return self.api.post('/api/django/automation/rules/', {
            'nom': 'Relance signée',
            'trigger_type': 'devis_accepted',
            'action_type': 'create_activity',
            'trigger_config': {},
            'action_config': {},
        }, format='json')

    def test_rule_create_toggle_delete_are_audited(self):
        r = self._create_rule()
        self.assertEqual(r.status_code, 201, r.content)
        rule_id = r.data['id']
        self.assertTrue(self._rows().filter(
            field='rule:Relance signée',
            field_label='Règle créée').exists())

        r = self.api.post(f'/api/django/automation/rules/{rule_id}/toggle/')
        self.assertEqual(r.status_code, 200, r.content)
        self.assertTrue(self._rows().filter(
            field_label='Règle (bascule)').exists())

        r = self.api.delete(f'/api/django/automation/rules/{rule_id}/')
        self.assertEqual(r.status_code, 204, r.content)
        self.assertTrue(self._rows().filter(
            field_label='Règle supprimée').exists())
