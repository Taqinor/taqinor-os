"""Tests API QHSE2 — ITP (modèles de plan d'inspection + points de contrôle).

Couvre : société posée côté serveur (jamais du corps), isolation entre sociétés
(A ne voit pas les plans/points de B), rattachement d'un point à un plan de la
MÊME société (un plan d'une autre société est refusé en 400), persistance de
``hold_point`` et ``type_releve``, et accès réservé au palier
Administrateur/Responsable (un rôle « normal » est refusé).
"""
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company

from apps.qhse.models import PlanInspectionModele, PointControleModele

User = get_user_model()


def make_company(slug, nom):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


def make_user(company, username, role='responsable'):
    return User.objects.create_user(
        username=username, password='x', company=company, role_legacy=role)


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


def rows(resp):
    data = resp.data
    return data['results'] if isinstance(data, dict) and 'results' in data else data


class PlanInspectionApiTests(TestCase):
    BASE = '/api/django/qhse/plans-inspection/'

    def setUp(self):
        self.co_a = make_company('itp-a', 'A')
        self.co_b = make_company('itp-b', 'B')
        self.user_a = make_user(self.co_a, 'itp-a')
        self.user_b = make_user(self.co_b, 'itp-b')

    def test_create_forces_company_server_side(self):
        api = auth(self.user_a)
        resp = api.post(
            self.BASE,
            {'nom': 'ITP Toiture', 'code': 'ITP-001'},
            format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        obj = PlanInspectionModele.objects.get(id=resp.data['id'])
        self.assertEqual(obj.company, self.co_a)

    def test_create_ignores_company_from_body(self):
        api = auth(self.user_a)
        resp = api.post(
            self.BASE,
            {'nom': 'ITP', 'company': self.co_b.id},
            format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        obj = PlanInspectionModele.objects.get(id=resp.data['id'])
        self.assertEqual(obj.company, self.co_a)

    def test_list_isolation(self):
        PlanInspectionModele.objects.create(company=self.co_a, nom='ITP A')
        resp = auth(self.user_b).get(self.BASE)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(rows(resp)), 0)

    def test_cross_tenant_detail_404(self):
        plan = PlanInspectionModele.objects.create(company=self.co_a, nom='ITP A')
        resp = auth(self.user_b).get(f'{self.BASE}{plan.id}/')
        self.assertEqual(resp.status_code, 404)

    def test_role_normal_refuse(self):
        normal = make_user(self.co_a, 'itp-normal', role='normal')
        resp = auth(normal).get(self.BASE)
        self.assertEqual(resp.status_code, 403)


class PointControleApiTests(TestCase):
    BASE = '/api/django/qhse/points-controle/'

    def setUp(self):
        self.co_a = make_company('itp-pc-a', 'A')
        self.co_b = make_company('itp-pc-b', 'B')
        self.user_a = make_user(self.co_a, 'itp-pc-a')
        self.user_b = make_user(self.co_b, 'itp-pc-b')
        self.plan_a = PlanInspectionModele.objects.create(
            company=self.co_a, nom='ITP A')
        self.plan_b = PlanInspectionModele.objects.create(
            company=self.co_b, nom='ITP B')

    def test_create_forces_company_and_persists_fields(self):
        api = auth(self.user_a)
        resp = api.post(
            self.BASE,
            {
                'plan': self.plan_a.id,
                'ordre': 2,
                'intitule': 'Serrage couple panneaux',
                'phase': 'Pose',
                'type_releve': 'mesure',
                'hold_point': True,
            },
            format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        obj = PointControleModele.objects.get(id=resp.data['id'])
        self.assertEqual(obj.company, self.co_a)
        self.assertEqual(obj.plan, self.plan_a)
        self.assertEqual(obj.type_releve, 'mesure')
        self.assertTrue(obj.hold_point)
        self.assertEqual(obj.ordre, 2)

    def test_point_must_belong_to_same_company_plan(self):
        # Plan de la société B rejeté pour un utilisateur de A (400).
        api = auth(self.user_a)
        resp = api.post(
            self.BASE,
            {
                'plan': self.plan_b.id,
                'intitule': 'Contrôle',
                'type_releve': 'visuel',
            },
            format='json')
        self.assertEqual(resp.status_code, 400)
        self.assertIn('plan', resp.data)

    def test_list_isolation(self):
        PointControleModele.objects.create(
            company=self.co_a, plan=self.plan_a, intitule='PC A')
        resp = auth(self.user_b).get(self.BASE)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(rows(resp)), 0)

    def test_cross_tenant_detail_404(self):
        pc = PointControleModele.objects.create(
            company=self.co_a, plan=self.plan_a, intitule='PC A')
        resp = auth(self.user_b).get(f'{self.BASE}{pc.id}/')
        self.assertEqual(resp.status_code, 404)

    def test_role_normal_refuse(self):
        normal = make_user(self.co_a, 'itp-pc-normal', role='normal')
        resp = auth(normal).get(self.BASE)
        self.assertEqual(resp.status_code, 403)
