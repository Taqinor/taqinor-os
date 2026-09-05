"""AUD808 — `config_import` doit écrire SettingsAuditLog pour chaque valeur
modifiée par un `_import_*` (profil, rôles, modèles de message, règles
d'automatisation, statuts, modèles de document).

Avant le fix, `_import_profile`/`_import_roles`/`_import_automation_rules`/
`_import_statuts`/`_import_message_templates`/`_import_document_templates`
faisaient un `setattr`+`save()` SANS jamais appeler `SettingsAuditLog.log_change`
— contrairement à `update_profile` (audite champ par champ) et
`RoleViewSet.perform_update` (journalise). Un Admin pouvait importer (mode
overwrite) un bundle d'une autre société avec `tva_standard=0` sans laisser
la moindre trace dans l'écran Journal d'audit des Paramètres."""
from django.test import TestCase
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.roles.models import Role, ADMIN_PERMISSIONS
from apps.parametres.models import CompanyProfile, MessageTemplate, SettingsAuditLog

User = get_user_model()


def _company(slug, nom):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


def _admin_api(company):
    role = Role.objects.create(
        company=company, nom='Administrateur',
        permissions=list(ADMIN_PERMISSIONS), est_systeme=True)
    u = User.objects.create_user(
        username=f'aud808_admin_{company.slug}', password='pw',
        role_legacy='admin', role=role, company=company)
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(u)}')
    return api


class Aud808ConfigImportProfileAuditTest(TestCase):
    """Test ROUGE d'abord : POST config_import avec tva_standard modifié
    produisait zéro ligne SettingsAuditLog."""

    def setUp(self):
        self.company = _company('aud808-co', 'AUD808 Co')
        CompanyProfile.objects.create(company=self.company, tva_standard=20)
        self.api = _admin_api(self.company)

    def test_overwrite_import_of_tva_standard_writes_audit_row(self):
        r = self.api.post(
            '/api/django/parametres/config-import/?mode=overwrite',
            {'profile': {'tva_standard': 0}}, format='json')
        self.assertEqual(r.status_code, 200, r.content)
        row = SettingsAuditLog.objects.filter(
            company=self.company, section='config_import',
            field='tva_standard').first()
        self.assertIsNotNone(row)
        self.assertEqual(row.new_value, '0')
        self.assertIsNotNone(row.user_id)

    def test_merge_mode_never_touches_profile_so_no_audit_row(self):
        r = self.api.post(
            '/api/django/parametres/config-import/',
            {'profile': {'tva_standard': 0}}, format='json')
        self.assertEqual(r.status_code, 200, r.content)
        self.assertFalse(SettingsAuditLog.objects.filter(
            company=self.company, section='config_import',
            field='tva_standard').exists())

    def test_unchanged_value_writes_nothing(self):
        self.api.post(
            '/api/django/parametres/config-import/?mode=overwrite',
            {'profile': {'tva_standard': 20}}, format='json')
        self.assertFalse(SettingsAuditLog.objects.filter(
            company=self.company, section='config_import',
            field='tva_standard').exists())


class Aud808ConfigImportRolesAuditTest(TestCase):
    """`_import_roles` en overwrite réécrivait les permissions sans logger —
    même trou que le profil, cité explicitement par AUD808."""

    def setUp(self):
        self.company = _company('aud808-roles-co', 'AUD808 Roles Co')
        Role.objects.create(
            company=self.company, nom='Rôle perso',
            permissions=['crm_voir'], est_systeme=False)
        self.api = _admin_api(self.company)

    def test_overwrite_role_permissions_writes_audit_row(self):
        r = self.api.post(
            '/api/django/parametres/config-import/?mode=overwrite',
            {'roles': [{'nom': 'Rôle perso',
                        'permissions': ['crm_voir', 'crm_modifier'],
                        'est_systeme': False}]},
            format='json')
        self.assertEqual(r.status_code, 200, r.content)
        row = SettingsAuditLog.objects.filter(
            company=self.company, section='config_import',
            field='role.Rôle perso.permissions').first()
        self.assertIsNotNone(row)


class Aud808ConfigImportMessageTemplateAuditTest(TestCase):
    def setUp(self):
        self.company = _company('aud808-msg-co', 'AUD808 Msg Co')
        MessageTemplate.objects.create(
            company=self.company, cle='facture', corps_fr='Ancien texte')
        self.api = _admin_api(self.company)

    def test_overwrite_message_template_writes_audit_row(self):
        r = self.api.post(
            '/api/django/parametres/config-import/?mode=overwrite',
            {'message_templates': [
                {'cle': 'facture', 'corps_fr': 'Nouveau texte'}]},
            format='json')
        self.assertEqual(r.status_code, 200, r.content)
        row = SettingsAuditLog.objects.filter(
            company=self.company, section='config_import',
            field='message_template.facture.corps_fr').first()
        self.assertIsNotNone(row)
        self.assertEqual(row.new_value, 'Nouveau texte')
