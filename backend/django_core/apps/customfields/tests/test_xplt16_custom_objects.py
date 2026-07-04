"""XPLT16 — objets personnalisés no-code (CustomObjectDef + CustomRecord)."""
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.customfields.models import CustomFieldDef, CustomObjectDef, CustomRecord
from apps.roles.models import Role
from authentication.models import Company

User = get_user_model()


class CF16Base(TestCase):
    def setUp(self):
        self.company = Company.objects.get_or_create(
            slug='cf16-co', defaults={'nom': 'CF16 Co'})[0]
        self.admin = User.objects.create_user(
            username='cf16_admin', password='x', role_legacy='admin',
            company=self.company)
        self.api = APIClient()
        self.api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.admin)}')


class TestCustomObjectDefCRUD(CF16Base):
    def test_admin_creates_object(self):
        resp = self.api.post('/api/django/custom-fields/objects/', {
            'code': 'registre_cles', 'libelle': 'Registre des clés',
            'icone': '🔑',
        }, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        self.assertTrue(CustomObjectDef.objects.filter(
            company=self.company, code='registre_cles').exists())

    def test_object_scoped_to_company(self):
        other = Company.objects.create(slug='cf16-other', nom='Autre')
        CustomObjectDef.objects.create(
            company=other, code='visiteurs', libelle='Visiteurs')
        resp = self.api.get('/api/django/custom-fields/objects/')
        self.assertEqual(resp.status_code, 200)
        rows = resp.data['results'] if isinstance(resp.data, dict) else resp.data
        self.assertEqual(len(rows), 0)


class TestCustomRecordCRUD(CF16Base):
    def _create_object_with_fields(self):
        objet = CustomObjectDef.objects.create(
            company=self.company, code='registre_cles',
            libelle='Registre des clés')
        CustomFieldDef.objects.create(
            company=self.company, module='custom:registre_cles',
            code='numero_cle', libelle='Numéro de clé', type='text',
            obligatoire=True)
        CustomFieldDef.objects.create(
            company=self.company, module='custom:registre_cles',
            code='emprunteur', libelle='Emprunteur', type='text')
        return objet

    def test_create_record_validated_and_stored(self):
        self._create_object_with_fields()
        resp = self.api.post(
            '/api/django/custom-fields/custom-objects/registre_cles/records/',
            {'data': {'numero_cle': 'A12', 'emprunteur': 'Reda'}},
            format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        rec = CustomRecord.objects.get(id=resp.data['id'])
        self.assertEqual(rec.data['numero_cle'], 'A12')
        self.assertEqual(rec.company, self.company)
        self.assertEqual(rec.created_by, self.admin)

    def test_required_field_enforced(self):
        self._create_object_with_fields()
        resp = self.api.post(
            '/api/django/custom-fields/custom-objects/registre_cles/records/',
            {'data': {'emprunteur': 'Reda'}}, format='json')
        self.assertEqual(resp.status_code, 400, resp.data)

    def test_list_and_filter_records(self):
        objet = self._create_object_with_fields()
        CustomRecord.objects.create(
            company=self.company, objet=objet,
            data={'numero_cle': 'A1', 'emprunteur': 'X'})
        CustomRecord.objects.create(
            company=self.company, objet=objet,
            data={'numero_cle': 'A2', 'emprunteur': 'Y'})
        resp = self.api.get(
            '/api/django/custom-fields/custom-objects/registre_cles/records/')
        self.assertEqual(resp.status_code, 200)
        rows = resp.data['results'] if isinstance(resp.data, dict) else resp.data
        self.assertEqual(len(rows), 2)

    def test_records_tenant_isolated(self):
        objet = self._create_object_with_fields()
        CustomRecord.objects.create(
            company=self.company, objet=objet, data={'numero_cle': 'A1'})
        other = Company.objects.create(slug='cf16-other2', nom='Autre2')
        other_objet = CustomObjectDef.objects.create(
            company=other, code='registre_cles', libelle='Registre')
        CustomRecord.objects.create(
            company=other, objet=other_objet, data={'numero_cle': 'B1'})
        resp = self.api.get(
            '/api/django/custom-fields/custom-objects/registre_cles/records/')
        rows = resp.data['results'] if isinstance(resp.data, dict) else resp.data
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]['data']['numero_cle'], 'A1')

    def test_unknown_object_code_404(self):
        resp = self.api.get(
            '/api/django/custom-fields/custom-objects/inexistant/records/')
        self.assertEqual(resp.status_code, 404)


class TestCustomObjectRolePermission(CF16Base):
    """Un rôle SANS la permission dédiée ne voit pas l'objet ; avec, oui."""

    def setUp(self):
        super().setUp()
        self.objet = CustomObjectDef.objects.create(
            company=self.company, code='registre_cles',
            libelle='Registre des clés')
        CustomFieldDef.objects.create(
            company=self.company, module='custom:registre_cles',
            code='numero_cle', libelle='Numéro', type='text')
        CustomRecord.objects.create(
            company=self.company, objet=self.objet,
            data={'numero_cle': 'A1'})

        self.role_sans_acces = Role.objects.create(
            company=self.company, nom='SansAccesClefs', permissions=[])
        self.user_sans_acces = User.objects.create_user(
            username='cf16_sans_acces', password='x',
            company=self.company, role=self.role_sans_acces)
        self.api_sans_acces = APIClient()
        self.api_sans_acces.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.user_sans_acces)}')

        self.role_avec_acces = Role.objects.create(
            company=self.company, nom='AvecAccesClefs',
            permissions=['custom_object.registre_cles.voir'])
        self.user_avec_acces = User.objects.create_user(
            username='cf16_avec_acces', password='x',
            company=self.company, role=self.role_avec_acces)
        self.api_avec_acces = APIClient()
        self.api_avec_acces.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.user_avec_acces)}')

    def test_role_without_permission_denied(self):
        resp = self.api_sans_acces.get(
            '/api/django/custom-fields/custom-objects/registre_cles/records/')
        self.assertEqual(resp.status_code, 403, resp.data)

    def test_role_with_permission_allowed(self):
        resp = self.api_avec_acces.get(
            '/api/django/custom-fields/custom-objects/registre_cles/records/')
        self.assertEqual(resp.status_code, 200, resp.data)

    def test_voir_permission_insufficient_to_create(self):
        # 'voir' ne donne pas 'gerer' -> création refusée.
        resp = self.api_avec_acces.post(
            '/api/django/custom-fields/custom-objects/registre_cles/records/',
            {'data': {'numero_cle': 'B1'}}, format='json')
        self.assertEqual(resp.status_code, 403, resp.data)

    def test_admin_legacy_account_unaffected(self):
        # Le compte de test setUp() de CF16Base n'a pas de rôle fin (legacy) —
        # comportement historique préservé, jamais bloqué par la permission
        # par-objet (raffinement OPT-IN, pas une régression pour les comptes
        # hérités).
        resp = self.api.get(
            '/api/django/custom-fields/custom-objects/registre_cles/records/')
        self.assertEqual(resp.status_code, 200, resp.data)
