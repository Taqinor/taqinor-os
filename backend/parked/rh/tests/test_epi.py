"""Tests FG178 — Catalogue & dotation EPI nominative par employé.

Équipement de protection individuelle (EPI). Couvre :
* Catalogue : création (company posée côté serveur, jamais lue du corps), rôle
  normal refusé (403), isolation multi-société, filtre type_epi, max_length.
* Dotation nominative : création avec taille + date_dotation +
  date_renouvellement ; company posée côté serveur ; employe/epi validés.
* Cross-société : employe d'une autre société refusé (400) ; epi d'une autre
  société refusé (400).
* Cohérence des dates : renouvellement avant dotation refusé (400).
* Liste par employé : ``?employe=`` et action ``employe/``.
* Endpoint a-renouveler : renouvellements proches + dépassés ; ``expire_within``
  borne la fenêtre ; ``inclure_expirees=0`` exclut les échus ; isolation.
* Moteur d'échéances RH (FG175) : la dotation à renouveler apparaît bien dans
  ``echeances_rh`` (sans casser les autres familles).
"""
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.rh import selectors
from apps.rh.models import DossierEmploye, DotationEpi, EpiCatalogue

User = get_user_model()

CAT = '/api/django/rh/epi-catalogue/'
DOT = '/api/django/rh/dotations-epi/'


def make_company(slug, nom):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


def make_user(company, username, role='responsable'):
    return User.objects.create_user(
        username=username, password='x', company=company, role_legacy=role)


def make_employe(company, matricule):
    return DossierEmploye.objects.create(
        company=company, matricule=matricule, nom='Test', prenom='E')


def make_epi(company, type_epi='casque', designation='Casque MSA V-Gard',
             actif=True):
    return EpiCatalogue.objects.create(
        company=company, type_epi=type_epi, designation=designation,
        actif=actif)


def make_dotation(company, employe, epi, taille='M', date_dotation=None,
                  date_renouvellement=None, quantite=1):
    return DotationEpi.objects.create(
        company=company, employe=employe, epi=epi, taille=taille,
        date_dotation=date_dotation, date_renouvellement=date_renouvellement,
        quantite=quantite)


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


def rows(resp):
    data = resp.data
    return data['results'] if isinstance(data, dict) and 'results' in data \
        else data


class EpiCatalogueTests(TestCase):
    def setUp(self):
        self.co_a = make_company('epi-a', 'A')
        self.co_b = make_company('epi-b', 'B')
        self.user_a = make_user(self.co_a, 'epi-user-a')
        self.user_b = make_user(self.co_b, 'epi-user-b')

    def test_create_company_posee_cote_serveur(self):
        resp = auth(self.user_a).post(CAT, {
            'type_epi': 'harnais',
            'designation': 'Harnais Petzl Avao Bod',
            'company': self.co_b.id,  # ignoré
        }, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        epi = EpiCatalogue.objects.get(id=resp.data['id'])
        self.assertEqual(epi.company, self.co_a)
        self.assertEqual(epi.type_epi, 'harnais')

    def test_role_normal_refuse(self):
        normal = make_user(self.co_a, 'epi-normal', role='normal')
        resp = auth(normal).get(CAT)
        self.assertEqual(resp.status_code, 403)

    def test_isolation_list(self):
        make_epi(self.co_a, 'casque', 'Casque A')
        resp = auth(self.user_b).get(CAT)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(rows(resp)), 0)

    def test_filtre_type_epi(self):
        make_epi(self.co_a, 'casque', 'Casque')
        make_epi(self.co_a, 'gants_isolants', 'Gants 1000V')
        resp = auth(self.user_a).get(CAT + '?type_epi=gants_isolants')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(
            [e['type_epi'] for e in rows(resp)], ['gants_isolants'])

    def test_tous_les_codes_tiennent_dans_max_length(self):
        field = EpiCatalogue._meta.get_field('type_epi')
        for value, _label in EpiCatalogue.TypeEpi.choices:
            self.assertLessEqual(
                len(value), field.max_length,
                f'Le code {value!r} dépasse max_length={field.max_length}')


class DotationEpiCreateTests(TestCase):
    def setUp(self):
        self.co_a = make_company('dot-a', 'A')
        self.co_b = make_company('dot-b', 'B')
        self.user_a = make_user(self.co_a, 'dot-user-a')
        self.user_b = make_user(self.co_b, 'dot-user-b')
        self.emp_a = make_employe(self.co_a, 'EA1')
        self.emp_b = make_employe(self.co_b, 'EB1')
        self.epi_a = make_epi(self.co_a, 'chaussures', 'Chaussures S3')
        self.epi_b = make_epi(self.co_b, 'chaussures', 'Chaussures S3 B')

    def test_create_nominative_taille_date(self):
        today = timezone.localdate()
        renouv = today + timedelta(days=365)
        resp = auth(self.user_a).post(DOT, {
            'employe': self.emp_a.id,
            'epi': self.epi_a.id,
            'taille': '42',
            'date_dotation': today.isoformat(),
            'date_renouvellement': renouv.isoformat(),
            'quantite': 1,
            'company': self.co_b.id,  # ignoré
        }, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        dot = DotationEpi.objects.get(id=resp.data['id'])
        self.assertEqual(dot.company, self.co_a)
        self.assertEqual(dot.employe, self.emp_a)
        self.assertEqual(dot.taille, '42')
        self.assertEqual(dot.date_renouvellement, renouv)
        # Champs dérivés de l'EPI exposés en lecture.
        self.assertEqual(resp.data['type_epi'], 'chaussures')
        self.assertEqual(resp.data['epi_designation'], 'Chaussures S3')

    def test_employe_autre_societe_refuse(self):
        resp = auth(self.user_a).post(DOT, {
            'employe': self.emp_b.id, 'epi': self.epi_a.id,
        }, format='json')
        self.assertEqual(resp.status_code, 400, resp.data)

    def test_epi_autre_societe_refuse(self):
        resp = auth(self.user_a).post(DOT, {
            'employe': self.emp_a.id, 'epi': self.epi_b.id,
        }, format='json')
        self.assertEqual(resp.status_code, 400, resp.data)

    def test_renouvellement_avant_dotation_refuse(self):
        today = timezone.localdate()
        resp = auth(self.user_a).post(DOT, {
            'employe': self.emp_a.id, 'epi': self.epi_a.id,
            'date_dotation': today.isoformat(),
            'date_renouvellement': (today - timedelta(days=5)).isoformat(),
        }, format='json')
        self.assertEqual(resp.status_code, 400, resp.data)

    def test_isolation_list(self):
        make_dotation(self.co_a, self.emp_a, self.epi_a)
        resp = auth(self.user_b).get(DOT)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(rows(resp)), 0)

    def test_taille_tient_dans_max_length(self):
        field = DotationEpi._meta.get_field('taille')
        self.assertGreaterEqual(field.max_length, 4)


class DotationEpiListeParEmployeTests(TestCase):
    def setUp(self):
        self.co_a = make_company('dote-a', 'A')
        self.user_a = make_user(self.co_a, 'dote-user-a')
        self.emp1 = make_employe(self.co_a, 'EA1')
        self.emp2 = make_employe(self.co_a, 'EA2')
        self.epi = make_epi(self.co_a, 'lunettes', 'Lunettes 3M')
        self.d1 = make_dotation(self.co_a, self.emp1, self.epi, taille='U')
        self.d2 = make_dotation(self.co_a, self.emp2, self.epi, taille='U')

    def test_filtre_employe(self):
        resp = auth(self.user_a).get(DOT + f'?employe={self.emp1.id}')
        self.assertEqual(resp.status_code, 200)
        ids = {d['id'] for d in rows(resp)}
        self.assertEqual(ids, {self.d1.id})

    def test_action_employe(self):
        resp = auth(self.user_a).get(DOT + f'employe/?employe={self.emp2.id}')
        self.assertEqual(resp.status_code, 200, resp.data)
        ids = {d['id'] for d in rows(resp)}
        self.assertEqual(ids, {self.d2.id})


class DotationEpiARenouvelerTests(TestCase):
    def setUp(self):
        self.co_a = make_company('dotr-a', 'A')
        self.co_b = make_company('dotr-b', 'B')
        self.user_a = make_user(self.co_a, 'dotr-user-a')
        self.user_b = make_user(self.co_b, 'dotr-user-b')
        self.emp_a = make_employe(self.co_a, 'EA1')
        self.emp_b = make_employe(self.co_b, 'EB1')
        self.epi_a = make_epi(self.co_a, 'harnais', 'Harnais antichute')
        self.epi_b = make_epi(self.co_b, 'harnais', 'Harnais B')
        today = timezone.localdate()
        self.bientot = make_dotation(
            self.co_a, self.emp_a, self.epi_a,
            date_renouvellement=today + timedelta(days=10))
        self.expiree = make_dotation(
            self.co_a, self.emp_a, self.epi_a,
            date_renouvellement=today - timedelta(days=1))
        self.lointaine = make_dotation(
            self.co_a, self.emp_a, self.epi_a,
            date_renouvellement=today + timedelta(days=200))
        self.sans_echeance = make_dotation(
            self.co_a, self.emp_a, self.epi_a, date_renouvellement=None)

    def test_a_renouveler_inclut_bientot_et_expirees(self):
        resp = auth(self.user_a).get(DOT + 'a-renouveler/')
        self.assertEqual(resp.status_code, 200, resp.data)
        ids = {d['id'] for d in rows(resp)}
        self.assertIn(self.bientot.id, ids)
        self.assertIn(self.expiree.id, ids)
        self.assertNotIn(self.lointaine.id, ids)
        self.assertNotIn(self.sans_echeance.id, ids)

    def test_expire_within_elargit_la_fenetre(self):
        resp = auth(self.user_a).get(DOT + 'a-renouveler/?expire_within=365')
        ids = {d['id'] for d in rows(resp)}
        self.assertIn(self.lointaine.id, ids)

    def test_inclure_expirees_0_exclut_les_echues(self):
        resp = auth(self.user_a).get(DOT + 'a-renouveler/?inclure_expirees=0')
        ids = {d['id'] for d in rows(resp)}
        self.assertIn(self.bientot.id, ids)
        self.assertNotIn(self.expiree.id, ids)

    def test_isolation_societe(self):
        make_dotation(
            self.co_b, self.emp_b, self.epi_b,
            date_renouvellement=timezone.localdate() + timedelta(days=5))
        resp = auth(self.user_b).get(DOT + 'a-renouveler/')
        self.assertEqual(resp.status_code, 200)
        ids = {d['id'] for d in rows(resp)}
        self.assertNotIn(self.bientot.id, ids)
        self.assertNotIn(self.expiree.id, ids)


class EcheancesRhDotationEpiTests(TestCase):
    """La dotation EPI à renouveler alimente le moteur d'échéances RH (FG175)."""

    def setUp(self):
        self.co_a = make_company('eche-a', 'A')
        self.emp_a = make_employe(self.co_a, 'EA1')
        self.epi = make_epi(self.co_a, 'harnais', 'Harnais Petzl')

    def test_echeances_rh_inclut_dotation_a_renouveler(self):
        today = timezone.localdate()
        make_dotation(
            self.co_a, self.emp_a, self.epi,
            date_renouvellement=today + timedelta(days=10))
        rows_ = selectors.echeances_rh(self.co_a, within_days=30, today=today)
        types = {r['type'] for r in rows_}
        self.assertIn('dotation_epi', types)
        row = next(r for r in rows_ if r['type'] == 'dotation_epi')
        self.assertEqual(row['employe_id'], self.emp_a.id)
        self.assertEqual(row['jours_restants'], 10)
        self.assertIn('Harnais Petzl', row['libelle'])

    def test_echeances_rh_ignore_dotation_sans_echeance(self):
        make_dotation(
            self.co_a, self.emp_a, self.epi, date_renouvellement=None)
        rows_ = selectors.echeances_rh(self.co_a, within_days=30)
        self.assertEqual(
            [r for r in rows_ if r['type'] == 'dotation_epi'], [])
