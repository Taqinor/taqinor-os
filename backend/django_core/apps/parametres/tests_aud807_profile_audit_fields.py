"""AUD807 — TOUS les champs concrets de `CompanyProfile` doivent être audités.

Avant le fix, `_PROFILE_AUDIT_FIELDS` était une liste tenue à la main
(47/102 champs) : 55 champs — dont TOUTE la politique de sécurité et
`audit_retention_days` (le levier de purge du journal lui-même) — étaient
PATCH-ables sans une seule ligne SettingsAuditLog. Le fix dérive la liste par
introspection du modèle (tous les champs concrets moins `read_only_fields`)."""
from django.test import TestCase
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.parametres.models import CompanyProfile, SettingsAuditLog
from apps.parametres.serializers import CompanyProfileSerializer

User = get_user_model()


def _company(slug='aud807-co', nom='AUD807 Co'):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


class Aud807ProfileAuditFieldsCoverageTest(TestCase):
    """Test ROUGE d'abord : le set des champs audités doit être EXACTEMENT
    l'ensemble des champs concrets du modèle moins les champs read-only du
    serializer et `id` — jamais une liste manuelle divergente."""

    def test_all_writable_concrete_fields_are_audited(self):
        from apps.parametres.views_profile import _PROFILE_AUDIT_FIELDS

        read_only = set(CompanyProfileSerializer.Meta.read_only_fields)
        expected = {
            f.name for f in CompanyProfile._meta.concrete_fields
        } - read_only - {'id'}
        self.assertEqual(set(_PROFILE_AUDIT_FIELDS), expected)


class Aud807SecurityFieldsAuditedTest(TestCase):
    """Scénario concret du founder : PATCH `audit_retention_days` (et le
    reste de la politique de sécurité) doit maintenant écrire une ligne
    SettingsAuditLog — sinon la purge planifiée efface l'historique
    d'audit sans laisser de trace du changement lui-même."""

    def setUp(self):
        self.company = _company()
        self.admin = User.objects.create_user(
            username='aud807_admin', password='pw',
            role_legacy='admin', company=self.company)
        self.api = APIClient()
        token = str(AccessToken.for_user(self.admin))
        self.api.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')

    def test_audit_retention_days_change_is_logged(self):
        r = self.api.patch(
            '/api/django/parametres/update/',
            {'audit_retention_days': 1}, format='json')
        self.assertEqual(r.status_code, 200, r.content)
        row = SettingsAuditLog.objects.filter(
            company=self.company, section='profil',
            field='audit_retention_days').first()
        self.assertIsNotNone(row)
        self.assertEqual(row.new_value, '1')

    def test_previously_unaudited_security_policy_fields_are_logged(self):
        r = self.api.patch(
            '/api/django/parametres/update/',
            {
                'password_min_length': 12,
                'lockout_max_attempts': 3,
                'lockout_duration_minutes': 30,
                'session_absolute_hours': 8,
                'allow_device_trust': False,
            }, format='json')
        self.assertEqual(r.status_code, 200, r.content)
        fields = set(SettingsAuditLog.objects.filter(
            company=self.company, section='profil').values_list(
            'field', flat=True))
        self.assertIn('password_min_length', fields)
        self.assertIn('lockout_max_attempts', fields)
        self.assertIn('lockout_duration_minutes', fields)
        self.assertIn('session_absolute_hours', fields)
        self.assertIn('allow_device_trust', fields)
