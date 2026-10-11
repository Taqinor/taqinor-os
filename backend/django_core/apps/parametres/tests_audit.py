"""Tests du journal d'audit des paramètres (N55) — qui change quoi, quand."""
from django.test import SimpleTestCase, TestCase
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.parametres.models import SettingsAuditLog
from apps.parametres.serializers_audit import SettingsAuditLogSerializer

User = get_user_model()


def _company(slug='audit-co', nom='Audit Co'):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


class SettingsAuditTest(TestCase):
    def setUp(self):
        self.company = _company()
        self.admin = User.objects.create_user(
            username='audit_admin', password='pw',
            role_legacy='admin', company=self.company)
        self.api = APIClient()
        token = str(AccessToken.for_user(self.admin))
        self.api.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')

    def test_profile_update_writes_audit_rows(self):
        r = self.api.patch(
            '/api/django/parametres/update/',
            {'nom': 'Nouvelle Raison Sociale', 'telephone': '0522000000'},
            format='json')
        self.assertEqual(r.status_code, 200)
        rows = SettingsAuditLog.objects.filter(
            company=self.company, section='profil')
        fields = {row.field for row in rows}
        self.assertIn('nom', fields)
        self.assertIn('telephone', fields)
        nom_row = rows.get(field='nom')
        self.assertEqual(nom_row.new_value, 'Nouvelle Raison Sociale')
        self.assertEqual(nom_row.user_id, self.admin.id)

    def test_unchanged_field_writes_nothing(self):
        # Premier passage : pose une valeur.
        self.api.patch('/api/django/parametres/update/',
                       {'nom': 'ACME'}, format='json')
        SettingsAuditLog.objects.all().delete()
        # Même valeur → aucun nouvel enregistrement.
        self.api.patch('/api/django/parametres/update/',
                       {'nom': 'ACME'}, format='json')
        self.assertEqual(
            SettingsAuditLog.objects.filter(field='nom').count(), 0)

    def test_audit_endpoint_lists_changes(self):
        self.api.patch('/api/django/parametres/update/',
                       {'nom': 'Lecture'}, format='json')
        r = self.api.get('/api/django/parametres/audit/')
        self.assertEqual(r.status_code, 200)
        self.assertGreaterEqual(r.data['count'], 1)
        self.assertTrue(
            any(row['field'] == 'nom' for row in r.data['results']))

    def test_audit_endpoint_admin_only(self):
        viewer = User.objects.create_user(
            username='audit_viewer', password='pw',
            role_legacy='utilisateur', company=self.company)
        api = APIClient()
        token = str(AccessToken.for_user(viewer))
        api.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')
        r = api.get('/api/django/parametres/audit/')
        self.assertEqual(r.status_code, 403)

    def test_audit_is_company_scoped(self):
        self.api.patch('/api/django/parametres/update/',
                       {'nom': 'Scopé'}, format='json')
        other = _company(slug='audit-other', nom='Other')
        other_admin = User.objects.create_user(
            username='other_admin', password='pw',
            role_legacy='admin', company=other)
        api = APIClient()
        token = str(AccessToken.for_user(other_admin))
        api.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')
        r = api.get('/api/django/parametres/audit/')
        self.assertEqual(r.data['count'], 0)


# ── ENF17 — la FK ``user`` du journal n'est pas inscriptible ───────────
# Sérialiseur de SORTIE (aucune écriture API) : ``user`` en lecture seule,
# un ``user`` fourni dans un corps est ignoré.

class SettingsAuditLogUserLectureSeuleTests(SimpleTestCase):
    def test_user_en_lecture_seule(self):
        champ = SettingsAuditLogSerializer().fields['user']
        self.assertTrue(champ.read_only)

    def test_user_ignore_en_entree(self):
        ser = SettingsAuditLogSerializer(
            data={'section': 's', 'field': 'f', 'user': 99999999},
            partial=True)
        self.assertTrue(ser.is_valid(), ser.errors)
        self.assertNotIn('user', ser.validated_data)
