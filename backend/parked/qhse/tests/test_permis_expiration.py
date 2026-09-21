"""Tests QHSE25 — Alerte d'expiration des permis de travail.

Couvre le sélecteur ``permis_travail_expirant`` et l'action
``GET .../permis-travail/expirant/`` :

* un permis dont la ``date_fin`` tombe dans la fenêtre est signalé ;
* un permis dont la ``date_fin`` est hors fenêtre ne l'est pas ;
* un permis déjà expiré est inclus par défaut, exclu avec ``inclure_expires=0`` ;
* un permis clôturé (soldé) et un permis sans ``date_fin`` sont exclus ;
* isolation entre sociétés (jamais les permis d'une autre société) ;
* tri par échéance la plus proche d'abord.
"""
from datetime import date, timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company

from apps.qhse.models import PermisTravail
from apps.qhse.selectors import permis_travail_expirant

User = get_user_model()

EXPIRANT_URL = '/api/django/qhse/permis-travail/expirant/'


# ── Helpers ──────────────────────────────────────────────────────────────────

def make_company(slug, nom):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


def make_user(company, username, role='responsable'):
    return User.objects.create_user(
        username=username, password='x', company=company, role_legacy=role)


def auth_client(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


def rows(resp):
    data = resp.data
    return (data['results']
            if isinstance(data, dict) and 'results' in data else data)


def make_permis(company, reference, date_fin, statut='valide'):
    return PermisTravail.objects.create(
        company=company, titre=f'Permis {reference}', type_permis='hauteur',
        statut=statut, reference=reference,
        date_debut=date(2026, 1, 1), date_fin=date_fin)


# ── Sélecteur ────────────────────────────────────────────────────────────────

class PermisTravailExpirantSelectorTests(TestCase):
    def setUp(self):
        self.company = make_company('co-pt-exp', 'CoPtExp')
        self.other = make_company('co-pt-exp-2', 'CoPtExp2')
        self.today = timezone.localdate()

    def test_dans_la_fenetre_est_signale(self):
        p = make_permis(self.company, 'PT-202606-0001',
                        self.today + timedelta(days=10))
        ids = list(permis_travail_expirant(
            self.company, within_days=30).values_list('id', flat=True))
        self.assertIn(p.id, ids)

    def test_hors_fenetre_exclu(self):
        p = make_permis(self.company, 'PT-202606-0002',
                        self.today + timedelta(days=60))
        ids = list(permis_travail_expirant(
            self.company, within_days=30).values_list('id', flat=True))
        self.assertNotIn(p.id, ids)

    def test_expire_inclus_par_defaut(self):
        p = make_permis(self.company, 'PT-202606-0003',
                        self.today - timedelta(days=5))
        ids = list(permis_travail_expirant(
            self.company, within_days=30).values_list('id', flat=True))
        self.assertIn(p.id, ids)

    def test_expire_exclu_si_inclure_expires_false(self):
        p = make_permis(self.company, 'PT-202606-0004',
                        self.today - timedelta(days=5))
        ids = list(permis_travail_expirant(
            self.company, within_days=30, inclure_expires=False
        ).values_list('id', flat=True))
        self.assertNotIn(p.id, ids)

    def test_cloture_exclu(self):
        p = make_permis(self.company, 'PT-202606-0005',
                        self.today + timedelta(days=5), statut='cloture')
        ids = list(permis_travail_expirant(
            self.company, within_days=30).values_list('id', flat=True))
        self.assertNotIn(p.id, ids)

    def test_sans_date_fin_exclu(self):
        p = PermisTravail.objects.create(
            company=self.company, titre='Sans échéance', type_permis='autre',
            statut='valide', reference='PT-202606-0006',
            date_debut=self.today, date_fin=None)
        ids = list(permis_travail_expirant(
            self.company, within_days=30).values_list('id', flat=True))
        self.assertNotIn(p.id, ids)

    def test_isolation_societe(self):
        autre = make_permis(self.other, 'PT-202606-0001',
                            self.today + timedelta(days=5))
        ids = list(permis_travail_expirant(
            self.company, within_days=30).values_list('id', flat=True))
        self.assertNotIn(autre.id, ids)

    def test_tri_echeance_la_plus_proche_dabord(self):
        loin = make_permis(self.company, 'PT-202606-0007',
                           self.today + timedelta(days=20))
        proche = make_permis(self.company, 'PT-202606-0008',
                             self.today + timedelta(days=2))
        ids = list(permis_travail_expirant(
            self.company, within_days=30).values_list('id', flat=True))
        self.assertEqual(ids, [proche.id, loin.id])

    def test_societe_absente_renvoie_vide(self):
        self.assertEqual(
            list(permis_travail_expirant(None)), [])


# ── Action API ───────────────────────────────────────────────────────────────

class PermisTravailExpirantApiTests(TestCase):
    def setUp(self):
        self.company = make_company('co-pt-exp-api', 'CoPtExpApi')
        self.other = make_company('co-pt-exp-api-2', 'CoPtExpApi2')
        self.user = make_user(self.company, 'pt-exp-resp')
        self.client_api = auth_client(self.user)
        self.today = timezone.localdate()

    def test_action_liste_les_expirants(self):
        dedans = make_permis(self.company, 'PT-202606-0001',
                             self.today + timedelta(days=10))
        make_permis(self.company, 'PT-202606-0002',
                    self.today + timedelta(days=90))
        resp = self.client_api.get(EXPIRANT_URL)
        self.assertEqual(resp.status_code, 200, resp.data)
        ids = {r['id'] for r in rows(resp)}
        self.assertEqual(ids, {dedans.id})

    def test_action_inclure_expires_false(self):
        avenir = make_permis(self.company, 'PT-202606-0003',
                             self.today + timedelta(days=5))
        make_permis(self.company, 'PT-202606-0004',
                    self.today - timedelta(days=5))
        resp = self.client_api.get(
            EXPIRANT_URL, {'inclure_expires': '0'})
        self.assertEqual(resp.status_code, 200, resp.data)
        ids = {r['id'] for r in rows(resp)}
        self.assertEqual(ids, {avenir.id})

    def test_action_expire_within_param(self):
        proche = make_permis(self.company, 'PT-202606-0005',
                             self.today + timedelta(days=5))
        make_permis(self.company, 'PT-202606-0006',
                    self.today + timedelta(days=40))
        resp = self.client_api.get(EXPIRANT_URL, {'expire_within': '7'})
        self.assertEqual(resp.status_code, 200, resp.data)
        ids = {r['id'] for r in rows(resp)}
        self.assertEqual(ids, {proche.id})

    def test_action_isolation_societe(self):
        make_permis(self.other, 'PT-202606-0001',
                    self.today + timedelta(days=5))
        resp = self.client_api.get(EXPIRANT_URL)
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(rows(resp), [])

    def test_action_role_normal_refuse(self):
        normal = make_user(self.company, 'pt-exp-normal', role='normal')
        resp = auth_client(normal).get(EXPIRANT_URL)
        self.assertEqual(resp.status_code, 403)
