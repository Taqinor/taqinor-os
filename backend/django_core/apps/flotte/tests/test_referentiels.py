"""Tests FLOTTE6 — référentiels listes éditables du parc (ReferentielFlotte).

Couvre : CRUD complet, isolation par société (A ne voit/touche pas B), société
posée côté serveur (jamais lue du corps de requête), filtre ``?domaine=``, 404
cross-tenant, 403 pour un rôle sans droit d'écriture, et le seeder idempotent
(valeurs standard, re-jeu sans doublon, n'écrase aucune ligne éditée).
"""
from io import StringIO

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company

from apps.flotte.models import ReferentielFlotte
from apps.flotte.management.commands.seed_referentiels_flotte import (
    DEFAULTS,
    seed_referentiels_flotte_for_company,
)

User = get_user_model()

EXPECTED_TOTAL = sum(len(v) for v in DEFAULTS.values())


def make_company(slug, nom):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


def make_user(company, username, role='admin'):
    return User.objects.create_user(
        username=username, password='x', company=company, role_legacy=role)


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


def rows(resp):
    data = resp.data
    if isinstance(data, dict) and 'results' in data:
        return data['results']
    return data


class ReferentielFlotteApiTests(TestCase):
    def setUp(self):
        self.co_a = make_company('flotte-ref-a', 'Flotte Ref A')
        self.co_b = make_company('flotte-ref-b', 'Flotte Ref B')
        self.admin_a = make_user(self.co_a, 'flotte-ref-admin-a', 'admin')
        self.admin_b = make_user(self.co_b, 'flotte-ref-admin-b', 'admin')
        # Utilisateur "normal" sans rôle fin -> non-responsable -> écriture 403.
        self.user_a = make_user(self.co_a, 'flotte-ref-user-a', 'normal')

    def test_create_force_company_server_side(self):
        api = auth(self.admin_a)
        resp = api.post('/api/django/flotte/referentiels/', {
            'domaine': 'energie', 'code': 'gpl', 'libelle': 'GPL',
            'ordre': 50, 'actif': True,
            'company': self.co_b.id,  # tentative d'injection — doit être ignorée
        }, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        ref = ReferentielFlotte.objects.get(id=resp.data['id'])
        self.assertEqual(ref.company_id, self.co_a.id)
        self.assertEqual(resp.data['domaine_display'], 'Énergie')

    def test_full_crud(self):
        api = auth(self.admin_a)
        # CREATE
        resp = api.post('/api/django/flotte/referentiels/', {
            'domaine': 'categorie_permis', 'code': 'B', 'libelle': 'B',
        }, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        ref_id = resp.data['id']
        # RETRIEVE
        resp = api.get(f'/api/django/flotte/referentiels/{ref_id}/')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['code'], 'B')
        # UPDATE (PATCH le libellé)
        resp = api.patch(
            f'/api/django/flotte/referentiels/{ref_id}/',
            {'libelle': 'B — Véhicules légers'}, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(resp.data['libelle'], 'B — Véhicules légers')
        # DELETE
        resp = api.delete(f'/api/django/flotte/referentiels/{ref_id}/')
        self.assertEqual(resp.status_code, 204)
        self.assertFalse(ReferentielFlotte.objects.filter(id=ref_id).exists())

    def test_tenant_isolation_list(self):
        ReferentielFlotte.objects.create(
            company=self.co_a, domaine='energie', code='diesel',
            libelle='Diesel A')
        ReferentielFlotte.objects.create(
            company=self.co_b, domaine='energie', code='diesel',
            libelle='Diesel B')
        resp = auth(self.admin_a).get('/api/django/flotte/referentiels/')
        libelles = [r['libelle'] for r in rows(resp)]
        self.assertIn('Diesel A', libelles)
        self.assertNotIn('Diesel B', libelles)

    def test_cannot_retrieve_other_company_entry(self):
        b_ref = ReferentielFlotte.objects.create(
            company=self.co_b, domaine='energie', code='essence',
            libelle='Essence B')
        resp = auth(self.admin_a).get(
            f'/api/django/flotte/referentiels/{b_ref.id}/')
        self.assertEqual(resp.status_code, 404)

    def test_filter_by_domaine(self):
        ReferentielFlotte.objects.create(
            company=self.co_a, domaine='energie', code='diesel',
            libelle='Diesel')
        ReferentielFlotte.objects.create(
            company=self.co_a, domaine='categorie_permis', code='B',
            libelle='B')
        api = auth(self.admin_a)
        r1 = api.get('/api/django/flotte/referentiels/?domaine=energie')
        self.assertEqual([x['libelle'] for x in rows(r1)], ['Diesel'])
        r2 = api.get(
            '/api/django/flotte/referentiels/?domaine=categorie_permis')
        self.assertEqual([x['code'] for x in rows(r2)], ['B'])

    def test_filter_by_actif(self):
        ReferentielFlotte.objects.create(
            company=self.co_a, domaine='energie', code='diesel',
            libelle='Diesel', actif=True)
        ReferentielFlotte.objects.create(
            company=self.co_a, domaine='energie', code='vieux',
            libelle='Obsolète', actif=False)
        resp = auth(self.admin_a).get(
            '/api/django/flotte/referentiels/?actif=false')
        self.assertEqual([x['code'] for x in rows(resp)], ['vieux'])

    def test_duplicate_code_same_domaine_rejected(self):
        ReferentielFlotte.objects.create(
            company=self.co_a, domaine='energie', code='diesel',
            libelle='Diesel')
        resp = auth(self.admin_a).post('/api/django/flotte/referentiels/', {
            'domaine': 'energie', 'code': 'diesel', 'libelle': 'Doublon',
        }, format='json')
        self.assertEqual(resp.status_code, 400, resp.data)
        self.assertEqual(
            ReferentielFlotte.objects.filter(
                company=self.co_a, domaine='energie', code='diesel').count(),
            1)

    def test_same_code_different_domaine_allowed(self):
        api = auth(self.admin_a)
        r1 = api.post('/api/django/flotte/referentiels/', {
            'domaine': 'type_vehicule', 'code': 'B', 'libelle': 'Berline',
        }, format='json')
        r2 = api.post('/api/django/flotte/referentiels/', {
            'domaine': 'categorie_permis', 'code': 'B', 'libelle': 'Permis B',
        }, format='json')
        self.assertEqual(r1.status_code, 201, r1.data)
        self.assertEqual(r2.status_code, 201, r2.data)

    def test_role_without_write_gets_403(self):
        resp = auth(self.user_a).post('/api/django/flotte/referentiels/', {
            'domaine': 'energie', 'code': 'diesel', 'libelle': 'Diesel',
        }, format='json')
        self.assertEqual(resp.status_code, 403, resp.data)

    def test_read_allowed_for_any_role(self):
        ReferentielFlotte.objects.create(
            company=self.co_a, domaine='energie', code='diesel',
            libelle='Diesel')
        resp = auth(self.user_a).get('/api/django/flotte/referentiels/')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual([x['code'] for x in rows(resp)], ['diesel'])


class SeedReferentielsFlotteTests(TestCase):
    def setUp(self):
        self.co_a = make_company('seed-ref-a', 'A')
        self.co_b = make_company('seed-ref-b', 'B')

    def run_cmd(self, **kwargs):
        out = StringIO()
        call_command('seed_referentiels_flotte', stdout=out, **kwargs)
        return out.getvalue()

    def test_seeds_standard_values_for_a_company(self):
        self.run_cmd(company='seed-ref-a')
        qs = ReferentielFlotte.objects.filter(company=self.co_a)
        self.assertEqual(qs.count(), EXPECTED_TOTAL)
        # Une valeur standard de chaque domaine est bien présente.
        self.assertTrue(qs.filter(domaine='energie', code='diesel').exists())
        self.assertTrue(
            qs.filter(domaine='categorie_permis', code='B').exists())
        self.assertTrue(
            qs.filter(domaine='type_engin', code='nacelle').exists())
        self.assertTrue(
            qs.filter(domaine='type_vehicule').exists())

    def test_idempotent_rerun_creates_nothing(self):
        self.run_cmd(company='seed-ref-a')
        before = ReferentielFlotte.objects.count()
        self.run_cmd(company='seed-ref-a')  # second run
        self.assertEqual(ReferentielFlotte.objects.count(), before)

    def test_idempotent_rerun_does_not_overwrite_edited_rows(self):
        self.run_cmd(company='seed-ref-a')
        ref = ReferentielFlotte.objects.filter(
            company=self.co_a, domaine='energie', code='diesel').first()
        ref.libelle = 'Diesel (édité par le fondateur)'
        ref.actif = False
        ref.save()
        self.run_cmd(company='seed-ref-a')  # re-run must not clobber the edit
        ref.refresh_from_db()
        self.assertEqual(ref.libelle, 'Diesel (édité par le fondateur)')
        self.assertFalse(ref.actif)

    def test_all_companies_seeded_when_no_arg(self):
        self.run_cmd()  # no --company → every company
        self.assertEqual(
            ReferentielFlotte.objects.filter(company=self.co_a).count(),
            EXPECTED_TOTAL)
        self.assertEqual(
            ReferentielFlotte.objects.filter(company=self.co_b).count(),
            EXPECTED_TOTAL)

    def test_company_arg_scopes_to_one_company(self):
        self.run_cmd(company='seed-ref-a')
        self.assertEqual(
            ReferentielFlotte.objects.filter(company=self.co_a).count(),
            EXPECTED_TOTAL)
        self.assertEqual(
            ReferentielFlotte.objects.filter(company=self.co_b).count(), 0)

    def test_unknown_company_slug_raises(self):
        with self.assertRaises(CommandError):
            self.run_cmd(company='does-not-exist')

    def test_helper_returns_created_count(self):
        created = seed_referentiels_flotte_for_company(self.co_a)
        self.assertEqual(created, EXPECTED_TOTAL)
        # Deuxième appel : rien de neuf.
        self.assertEqual(
            seed_referentiels_flotte_for_company(self.co_a), 0)
