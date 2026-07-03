"""XPUR5 — Fiche fournisseur enrichie : contacts multiples, catégorie/tags,
devise/incoterm par défaut, validation ICE.

Couvre :
  * CRUD contacts (N par fournisseur) ;
  * catégorie + filtre liste ;
  * validation format ICE (15 chiffres) ;
  * détection de doublon ICE (warning non bloquant) ;
  * devise_defaut/incoterm préremplissage (champs exposés).

Run:
    python manage.py test apps.stock.test_xpur5_fiche_fournisseur -v 2
"""
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.roles.models import Role
from apps.stock.models import CategorieFournisseur, ContactFournisseur, Fournisseur
from apps.stock.services import find_duplicate_ice, validate_ice_format

User = get_user_model()


def _company(slug):
    return Company.objects.create(nom=slug, slug=slug)


def _user(company, username, permissions=None):
    role = Role.objects.create(
        company=company, nom=f'r-{username}', permissions=permissions or [])
    return User.objects.create_user(
        username=username, password='x', company=company, role=role,
        role_legacy='responsable')


def _api(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


class Xpur5Base(TestCase):
    def setUp(self):
        self.company = _company('xpur5-co')
        self.user = _user(
            self.company, 'xpur5-user',
            permissions=['stock_modifier', 'stock_voir'])
        self.api = _api(self.user)
        self.fournisseur = Fournisseur.objects.create(
            company=self.company, nom='Grossiste Solaire')


class TestValidateIceFormat(TestCase):
    def test_valid_15_digits(self):
        self.assertTrue(validate_ice_format('001234567000012'[:15]))

    def test_empty_is_ok(self):
        self.assertTrue(validate_ice_format(''))
        self.assertTrue(validate_ice_format(None))

    def test_too_short_invalid(self):
        self.assertFalse(validate_ice_format('12345'))

    def test_non_digits_invalid(self):
        self.assertFalse(validate_ice_format('12345ABCDE12345'))


class TestIceValidationEndpoint(Xpur5Base):
    def test_malformed_ice_rejected(self):
        resp = self.api.post('/api/django/stock/fournisseurs/', {
            'nom': 'Mauvais ICE', 'ice': '12345',
        }, format='json')
        self.assertEqual(resp.status_code, 400, resp.data)
        self.assertIn('ice', resp.data)

    def test_valid_ice_accepted(self):
        resp = self.api.post('/api/django/stock/fournisseurs/', {
            'nom': 'Bon ICE', 'ice': '001234567000099',
        }, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)


class TestDuplicateIce(Xpur5Base):
    def test_duplicate_ice_detected(self):
        Fournisseur.objects.create(
            company=self.company, nom='Premier', ice='001234567000012')
        dup = find_duplicate_ice(self.company, '001234567000012')
        self.assertIsNotNone(dup)
        self.assertEqual(dup.nom, 'Premier')

    def test_duplicate_ice_warning_on_create_endpoint(self):
        Fournisseur.objects.create(
            company=self.company, nom='Original', ice='001234567000012')
        resp = self.api.post('/api/django/stock/fournisseurs/', {
            'nom': 'Doublon', 'ice': '001234567000012',
        }, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        self.assertIn('ice_duplicate_warning', resp.data)

    def test_no_warning_without_duplicate(self):
        resp = self.api.post('/api/django/stock/fournisseurs/', {
            'nom': 'Unique', 'ice': '001234567000099',
        }, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        self.assertNotIn('ice_duplicate_warning', resp.data)

    def test_exclude_self_on_update(self):
        f = Fournisseur.objects.create(
            company=self.company, nom='Moi-même', ice='001234567000012')
        dup = find_duplicate_ice(
            self.company, '001234567000012', exclude_id=f.id)
        self.assertIsNone(dup)


class TestContactsFournisseur(Xpur5Base):
    def test_create_multiple_contacts(self):
        for nom in ('Contact A', 'Contact B', 'Contact C'):
            resp = self.api.post('/api/django/stock/contacts-fournisseur/', {
                'fournisseur': self.fournisseur.id, 'nom': nom,
                'fonction': 'Achats',
            }, format='json')
            self.assertEqual(resp.status_code, 201, resp.data)
        self.assertEqual(
            ContactFournisseur.objects.filter(
                fournisseur=self.fournisseur).count(), 3)

    def test_contacts_listed_on_fournisseur_detail(self):
        ContactFournisseur.objects.create(
            company=self.company, fournisseur=self.fournisseur,
            nom='Contact Principal', fonction='Directeur')
        resp = self.api.get(
            f'/api/django/stock/fournisseurs/{self.fournisseur.id}/')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(resp.data['contacts']), 1)
        self.assertEqual(resp.data['contacts'][0]['nom'], 'Contact Principal')

    def test_cross_company_fournisseur_rejected(self):
        other_company = _company('xpur5-co-2')
        other_fournisseur = Fournisseur.objects.create(
            company=other_company, nom='Autre Société')
        resp = self.api.post('/api/django/stock/contacts-fournisseur/', {
            'fournisseur': other_fournisseur.id, 'nom': 'Intrus',
        }, format='json')
        self.assertEqual(resp.status_code, 400, resp.data)


class TestCategorieFournisseur(Xpur5Base):
    def test_create_and_assign_categorie(self):
        resp = self.api.post('/api/django/stock/categories-fournisseur/', {
            'nom': 'Grossiste panneaux',
        }, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        cat_id = resp.data['id']
        resp2 = self.api.patch(
            f'/api/django/stock/fournisseurs/{self.fournisseur.id}/',
            {'categorie': cat_id}, format='json')
        self.assertEqual(resp2.status_code, 200, resp2.data)
        self.assertEqual(resp2.data['categorie_nom'], 'Grossiste panneaux')

    def test_filter_fournisseurs_by_categorie(self):
        cat = CategorieFournisseur.objects.create(
            company=self.company, nom='Import')
        f2 = Fournisseur.objects.create(
            company=self.company, nom='Import Co', categorie=cat)
        resp = self.api.get(
            f'/api/django/stock/fournisseurs/?categorie={cat.id}')
        self.assertEqual(resp.status_code, 200)
        ids = [f['id'] for f in resp.data.get(
            'results', resp.data if isinstance(resp.data, list) else [])]
        self.assertIn(f2.id, ids)
        self.assertNotIn(self.fournisseur.id, ids)


class TestDeviseIncotermDefaults(Xpur5Base):
    def test_fields_exposed_and_default_empty(self):
        resp = self.api.get(
            f'/api/django/stock/fournisseurs/{self.fournisseur.id}/')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['devise_defaut'], '')
        self.assertEqual(resp.data['incoterm'], '')

    def test_set_devise_and_incoterm(self):
        resp = self.api.patch(
            f'/api/django/stock/fournisseurs/{self.fournisseur.id}/',
            {'devise_defaut': 'EUR', 'incoterm': 'FOB'}, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(resp.data['devise_defaut'], 'EUR')
        self.assertEqual(resp.data['incoterm'], 'FOB')
