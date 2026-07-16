"""NTEXT2 — générateur de vue LISTE pour objets custom.

Endpoint ``GET custom-fields/custom-objects/<code>/vue-liste/`` renvoie le
schéma des colonnes (uniquement les CustomFieldDef ``visible_liste=True``,
ordonnées) + les données paginées de CustomRecord, strictement scopées à la
société de l'appelant (jamais un paramètre du corps/de l'URL)."""
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.customfields.models import CustomFieldDef, CustomObjectDef, CustomRecord
from apps.roles.models import Role
from authentication.models import Company

User = get_user_model()


class NTEXT2Base(TestCase):
    def setUp(self):
        self.company = Company.objects.get_or_create(
            slug='ntext2-co', defaults={'nom': 'NTEXT2 Co'})[0]
        self.admin = User.objects.create_user(
            username='ntext2_admin', password='x', role_legacy='admin',
            company=self.company)
        self.api = APIClient()
        self.api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.admin)}')
        self.objet = CustomObjectDef.objects.create(
            company=self.company, code='cles', libelle='Clés')
        # 3 champs visibles en liste, 1 champ NON visible en liste.
        CustomFieldDef.objects.create(
            company=self.company, module='custom:cles', code='numero',
            libelle='Numéro', type='text', visible_liste=True, ordre=1)
        CustomFieldDef.objects.create(
            company=self.company, module='custom:cles', code='emprunteur',
            libelle='Emprunteur', type='text', visible_liste=True, ordre=2)
        CustomFieldDef.objects.create(
            company=self.company, module='custom:cles', code='date_pret',
            libelle='Date de prêt', type='date', visible_liste=True, ordre=3)
        CustomFieldDef.objects.create(
            company=self.company, module='custom:cles', code='notes_internes',
            libelle='Notes internes', type='text', visible_liste=False)


class TestVueListeSchema(NTEXT2Base):
    def test_creating_object_with_3_visible_fields_yields_3_typed_columns(self):
        resp = self.api.get(
            '/api/django/custom-fields/custom-objects/cles/vue-liste/')
        self.assertEqual(resp.status_code, 200, resp.data)
        colonnes = resp.data['colonnes']
        self.assertEqual(len(colonnes), 3)
        self.assertEqual(
            [c['code'] for c in colonnes], ['numero', 'emprunteur', 'date_pret'])
        self.assertEqual(colonnes[2]['type'], 'date')
        self.assertIn('largeur', colonnes[0])
        self.assertIn('formatage', colonnes[0])

    def test_hidden_field_excluded_from_columns(self):
        resp = self.api.get(
            '/api/django/custom-fields/custom-objects/cles/vue-liste/')
        codes = [c['code'] for c in resp.data['colonnes']]
        self.assertNotIn('notes_internes', codes)

    def test_paginated_data_included(self):
        CustomRecord.objects.create(
            company=self.company, objet=self.objet,
            data={'numero': 'A1', 'emprunteur': 'Reda'})
        CustomRecord.objects.create(
            company=self.company, objet=self.objet,
            data={'numero': 'A2', 'emprunteur': 'Sami'})
        resp = self.api.get(
            '/api/django/custom-fields/custom-objects/cles/vue-liste/')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(resp.data['count'], 2)
        self.assertEqual(len(resp.data['results']), 2)

    def test_unknown_object_404(self):
        resp = self.api.get(
            '/api/django/custom-fields/custom-objects/inexistant/vue-liste/')
        self.assertEqual(resp.status_code, 404)


class TestVueListeTenantAndPermission(NTEXT2Base):
    def test_other_company_data_not_leaked(self):
        other = Company.objects.create(slug='ntext2-other', nom='Autre')
        other_objet = CustomObjectDef.objects.create(
            company=other, code='cles', libelle='Clés')
        CustomRecord.objects.create(
            company=other, objet=other_objet, data={'numero': 'X1'})
        resp = self.api.get(
            '/api/django/custom-fields/custom-objects/cles/vue-liste/')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(resp.data['count'], 0)

    def test_role_without_permission_denied(self):
        role = Role.objects.create(
            company=self.company, nom='SansAccesCles', permissions=[])
        user = User.objects.create_user(
            username='ntext2_sans_acces', password='x',
            company=self.company, role=role)
        api = APIClient()
        api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
        resp = api.get(
            '/api/django/custom-fields/custom-objects/cles/vue-liste/')
        self.assertEqual(resp.status_code, 403, resp.data)
