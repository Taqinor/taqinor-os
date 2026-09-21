"""Tests XQHS4 — Catalogue de codes de défauts + Pareto qualité.

Couvre :

* le référentiel ``CodeDefaut`` (company-scoped, unique par code) ;
* le rattachement (FK nullable) sur ``NonConformite``, ``ReleveControle``
  (échec), ``Incident`` ;
* le seed idempotent ``seed_codes_defaut_solaire`` ;
* le Pareto (comptes + % cumulé) et le taux de conformité premier-passage ;
* l'isolation entre sociétés.
"""
from io import StringIO

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company

from apps.qhse.models import (
    CodeDefaut, Incident, NonConformite, PlanInspectionChantier,
    PlanInspectionModele, PointControleModele, ReleveControle,
)
from apps.qhse.selectors import (
    pareto_defauts, taux_conformite_premier_passage,
)

User = get_user_model()

PARETO_URL = '/api/django/qhse/pareto-defauts/'
CODES_URL = '/api/django/qhse/codes-defaut/'


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


def make_code(company, code, famille='produit'):
    return CodeDefaut.objects.create(
        company=company, code=code, libelle=f'Défaut {code}', famille=famille)


def make_releve_echec(company, code_defaut=None):
    modele = PlanInspectionModele.objects.create(company=company, nom='ITP')
    point = PointControleModele.objects.create(
        company=company, plan=modele, intitule='Point 1')
    plan_chantier = PlanInspectionChantier.objects.create(
        company=company, modele=modele, chantier_id=1)
    return ReleveControle.objects.create(
        company=company, plan_chantier=plan_chantier, point=point,
        conforme=False, code_defaut=code_defaut)


# ── Modèle CodeDefaut ────────────────────────────────────────────────────────

class CodeDefautModelTests(TestCase):
    def test_unique_par_societe(self):
        company = make_company('co-xqhs4-uniq', 'CoXqhs4Uniq')
        make_code(company, 'PRD-CASSE')
        with self.assertRaises(Exception):
            make_code(company, 'PRD-CASSE')

    def test_meme_code_differentes_societes_ok(self):
        c1 = make_company('co-xqhs4-a', 'CoXqhs4A')
        c2 = make_company('co-xqhs4-b', 'CoXqhs4B')
        make_code(c1, 'PRD-CASSE')
        make_code(c2, 'PRD-CASSE')  # ne lève pas


# ── Seed idempotent ──────────────────────────────────────────────────────────

class SeedCodesDefautSolaireTests(TestCase):
    def test_seed_cree_des_codes(self):
        company = make_company('co-xqhs4-seed', 'CoXqhs4Seed')
        out = StringIO()
        call_command(
            'seed_codes_defaut_solaire', '--company', company.slug,
            stdout=out)
        self.assertGreater(
            CodeDefaut.objects.filter(company=company).count(), 0)

    def test_seed_idempotent(self):
        company = make_company('co-xqhs4-seed2', 'CoXqhs4Seed2')
        call_command(
            'seed_codes_defaut_solaire', '--company', company.slug,
            stdout=StringIO())
        nb_avant = CodeDefaut.objects.filter(company=company).count()
        call_command(
            'seed_codes_defaut_solaire', '--company', company.slug,
            stdout=StringIO())
        self.assertEqual(
            CodeDefaut.objects.filter(company=company).count(), nb_avant)


# ── Pareto ───────────────────────────────────────────────────────────────────

class ParetoDefautsTests(TestCase):
    def setUp(self):
        self.company = make_company('co-xqhs4-pareto', 'CoXqhs4Pareto')
        self.autre = make_company('co-xqhs4-pareto-autre', 'CoXqhs4ParetoAutre')
        self.code_a = make_code(self.company, 'PRD-CASSE', famille='produit')
        self.code_b = make_code(self.company, 'DC-SERRAGE', famille='pose_dc')

    def test_agrege_ncr_et_releves_et_incidents(self):
        NonConformite.objects.create(
            company=self.company, titre='NCR 1', code_defaut=self.code_a)
        NonConformite.objects.create(
            company=self.company, titre='NCR 2', code_defaut=self.code_a)
        make_releve_echec(self.company, code_defaut=self.code_b)
        Incident.objects.create(
            company=self.company, titre='Inc 1', code_defaut=self.code_a)

        result = pareto_defauts(self.company)
        codes = {ligne['code']: ligne['nb'] for ligne in result}
        self.assertEqual(codes.get('PRD-CASSE'), 3)
        self.assertEqual(codes.get('DC-SERRAGE'), 1)

    def test_pct_cumule_somme_a_100(self):
        NonConformite.objects.create(
            company=self.company, titre='NCR 1', code_defaut=self.code_a)
        NonConformite.objects.create(
            company=self.company, titre='NCR 2', code_defaut=self.code_b)
        result = pareto_defauts(self.company)
        self.assertEqual(result[-1]['pct_cumule'], 100.0)

    def test_filtre_famille(self):
        NonConformite.objects.create(
            company=self.company, titre='NCR 1', code_defaut=self.code_a)
        NonConformite.objects.create(
            company=self.company, titre='NCR 2', code_defaut=self.code_b)
        result = pareto_defauts(self.company, famille='pose_dc')
        codes = {ligne['code'] for ligne in result}
        self.assertEqual(codes, {'DC-SERRAGE'})

    def test_isolation_societe(self):
        NonConformite.objects.create(
            company=self.company, titre='NCR 1', code_defaut=self.code_a)
        result = pareto_defauts(self.autre)
        self.assertEqual(result, [])

    def test_ncr_sans_code_defaut_exclue(self):
        NonConformite.objects.create(company=self.company, titre='NCR sans code')
        result = pareto_defauts(self.company)
        self.assertEqual(result, [])


# ── Taux de conformité premier passage ──────────────────────────────────────

class TauxConformitePremierPassageTests(TestCase):
    def setUp(self):
        self.company = make_company('co-xqhs4-tf', 'CoXqhs4Tf')

    def test_calcule_taux(self):
        modele = PlanInspectionModele.objects.create(
            company=self.company, nom='ITP')
        pt1 = PointControleModele.objects.create(
            company=self.company, plan=modele, intitule='P1')
        pt2 = PointControleModele.objects.create(
            company=self.company, plan=modele, intitule='P2')
        plan_chantier = PlanInspectionChantier.objects.create(
            company=self.company, modele=modele, chantier_id=5)
        ReleveControle.objects.create(
            company=self.company, plan_chantier=plan_chantier, point=pt1,
            conforme=True)
        ReleveControle.objects.create(
            company=self.company, plan_chantier=plan_chantier, point=pt2,
            conforme=False)
        result = taux_conformite_premier_passage(self.company)
        self.assertEqual(result['total_statues'], 2)
        self.assertEqual(result['conformes'], 1)
        self.assertEqual(result['taux'], 50.0)

    def test_exclut_non_statues(self):
        modele = PlanInspectionModele.objects.create(
            company=self.company, nom='ITP2')
        pt1 = PointControleModele.objects.create(
            company=self.company, plan=modele, intitule='P1')
        plan_chantier = PlanInspectionChantier.objects.create(
            company=self.company, modele=modele, chantier_id=6)
        ReleveControle.objects.create(
            company=self.company, plan_chantier=plan_chantier, point=pt1,
            conforme=None)
        result = taux_conformite_premier_passage(self.company)
        self.assertEqual(result['total_statues'], 0)
        self.assertIsNone(result['taux'])


# ── API ──────────────────────────────────────────────────────────────────────

class ParetoDefautsApiTests(TestCase):
    def setUp(self):
        self.company = make_company('co-xqhs4-api', 'CoXqhs4Api')
        self.user = make_user(self.company, 'resp-xqhs4-api')
        self.client = auth_client(self.user)
        self.code = make_code(self.company, 'PRD-CASSE')

    def test_pareto_endpoint(self):
        NonConformite.objects.create(
            company=self.company, titre='NCR 1', code_defaut=self.code)
        resp = self.client.get(PARETO_URL)
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertIn('pareto', resp.data)
        self.assertIn('premier_passage', resp.data)

    def test_creation_code_defaut_scoped_company(self):
        resp = self.client.post(CODES_URL, {
            'code': 'AC-TERRE', 'libelle': 'Terre AC', 'famille': 'pose_ac',
        }, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        code = CodeDefaut.objects.get(pk=resp.data['id'])
        self.assertEqual(code.company, self.company)
