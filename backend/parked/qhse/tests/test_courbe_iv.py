"""Tests QHSE7 — relevé courbe I-V par string (mise en service PV).

Couvre :

* le facteur de forme ``fill_factor`` calculé côté modèle (FF = Pmpp/(Voc·Isc))
  et ``None`` quand une grandeur manque ou que le dénominateur est nul ;
* la création d'un relevé via l'API : ``company`` + ``releve_par`` posés côté
  serveur, points de courbe JSON ``[{v, i}]`` persistés, FF exposé ;
* le rattachement lâche optionnel ``plan_chantier`` (même société → ok, autre
  société → 400) ;
* le sélecteur ``courbes_iv_for_chantier`` (filtré société + chantier) ;
* l'isolation multi-société (A ne voit pas les courbes de B) et le filtre
  ``?chantier_id=`` ;
* l'action ``par-chantier`` (chantier_id requis, scopée société) ;
* l'accès réservé au palier Administrateur/Responsable (rôle « normal » → 403).
"""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company

from apps.qhse.models import (
    PlanInspectionChantier, PlanInspectionModele, ReleveCourbeIV,
)
from apps.qhse.selectors import courbes_iv_for_chantier

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


class FillFactorModelTests(TestCase):
    def setUp(self):
        self.co = make_company('qhse7-ff', 'FF')

    def test_fill_factor_computed_when_values_present(self):
        rec = ReleveCourbeIV.objects.create(
            company=self.co, chantier_id=1, string_id='S1',
            voc=Decimal('40.000'), isc=Decimal('10.000'),
            pmpp=Decimal('320.000'))
        # FF = 320 / (40 * 10) = 0.8
        self.assertEqual(rec.fill_factor(), Decimal('0.8000'))

    def test_fill_factor_none_when_value_missing(self):
        rec = ReleveCourbeIV.objects.create(
            company=self.co, chantier_id=1, string_id='S2',
            voc=Decimal('40.000'), isc=Decimal('10.000'))
        self.assertIsNone(rec.fill_factor())

    def test_fill_factor_none_when_denominator_zero(self):
        rec = ReleveCourbeIV.objects.create(
            company=self.co, chantier_id=1, string_id='S3',
            voc=Decimal('0.000'), isc=Decimal('10.000'),
            pmpp=Decimal('320.000'))
        self.assertIsNone(rec.fill_factor())


class CourbeIVApiTests(TestCase):
    BASE = '/api/django/qhse/courbes-iv/'

    def setUp(self):
        self.co_a = make_company('qhse7-a', 'A')
        self.co_b = make_company('qhse7-b', 'B')
        self.user_a = make_user(self.co_a, 'qhse7-a')
        self.user_b = make_user(self.co_b, 'qhse7-b')
        # ITP appliqué côté A et côté B pour tester le rattachement lâche.
        self.modele_a = PlanInspectionModele.objects.create(
            company=self.co_a, nom='ITP A')
        self.plan_a = PlanInspectionChantier.objects.create(
            company=self.co_a, modele=self.modele_a, chantier_id=7)
        self.modele_b = PlanInspectionModele.objects.create(
            company=self.co_b, nom='ITP B')
        self.plan_b = PlanInspectionChantier.objects.create(
            company=self.co_b, modele=self.modele_b, chantier_id=9)

    def test_create_persists_fields_and_sets_releve_par(self):
        resp = auth(self.user_a).post(
            self.BASE,
            {
                'chantier_id': 7,
                'plan_chantier': self.plan_a.id,
                'string_id': 'String-A1',
                'voc': '40.0',
                'isc': '10.0',
                'vmpp': '32.0',
                'impp': '9.5',
                'pmpp': '320.0',
                'irradiance': '950.5',
                'temperature_module': '45.2',
                'courbe_points': [
                    {'v': 0, 'i': 10.0},
                    {'v': 32.0, 'i': 9.5},
                    {'v': 40.0, 'i': 0},
                ],
                'notes': 'string sain',
            },
            format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        obj = ReleveCourbeIV.objects.get(id=resp.data['id'])
        # company + releve_par posés côté serveur.
        self.assertEqual(obj.company, self.co_a)
        self.assertEqual(obj.releve_par, self.user_a)
        self.assertEqual(obj.string_id, 'String-A1')
        self.assertEqual(obj.plan_chantier_id, self.plan_a.id)
        # Points de courbe JSON persistés tels quels.
        self.assertEqual(len(obj.courbe_points), 3)
        self.assertEqual(obj.courbe_points[0], {'v': 0, 'i': 10.0})
        # FF exposé : 320 / (40 * 10) = 0.8
        self.assertEqual(resp.data['fill_factor'], '0.8000')

    def test_create_without_pmpp_returns_null_fill_factor(self):
        resp = auth(self.user_a).post(
            self.BASE,
            {'chantier_id': 7, 'string_id': 'S2', 'voc': '40', 'isc': '10'},
            format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        self.assertIsNone(resp.data['fill_factor'])

    def test_company_not_accepted_from_body(self):
        resp = auth(self.user_a).post(
            self.BASE,
            {'chantier_id': 7, 'string_id': 'S3', 'company': self.co_b.id},
            format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        obj = ReleveCourbeIV.objects.get(id=resp.data['id'])
        self.assertEqual(obj.company, self.co_a)

    def test_cross_company_plan_chantier_400(self):
        resp = auth(self.user_a).post(
            self.BASE,
            {'chantier_id': 7, 'string_id': 'S4',
             'plan_chantier': self.plan_b.id},
            format='json')
        self.assertEqual(resp.status_code, 400)
        self.assertIn('plan_chantier', resp.data)

    def test_list_isolation(self):
        ReleveCourbeIV.objects.create(
            company=self.co_a, chantier_id=7, string_id='A1')
        ReleveCourbeIV.objects.create(
            company=self.co_b, chantier_id=9, string_id='B1')
        resp = auth(self.user_b).get(self.BASE)
        self.assertEqual(resp.status_code, 200)
        out = rows(resp)
        self.assertEqual(len(out), 1)
        self.assertEqual(out[0]['string_id'], 'B1')

    def test_list_filter_by_chantier_id(self):
        ReleveCourbeIV.objects.create(
            company=self.co_a, chantier_id=7, string_id='A1')
        ReleveCourbeIV.objects.create(
            company=self.co_a, chantier_id=8, string_id='A2')
        resp = auth(self.user_a).get(f'{self.BASE}?chantier_id=7')
        self.assertEqual(resp.status_code, 200)
        out = rows(resp)
        self.assertEqual(len(out), 1)
        self.assertEqual(out[0]['string_id'], 'A1')

    def test_par_chantier_requires_chantier_id(self):
        resp = auth(self.user_a).get(f'{self.BASE}par-chantier/')
        self.assertEqual(resp.status_code, 400)

    def test_par_chantier_scoped_company(self):
        ReleveCourbeIV.objects.create(
            company=self.co_a, chantier_id=7, string_id='A1')
        ReleveCourbeIV.objects.create(
            company=self.co_b, chantier_id=7, string_id='B-on-same-chantier')
        resp = auth(self.user_a).get(f'{self.BASE}par-chantier/?chantier_id=7')
        self.assertEqual(resp.status_code, 200)
        out = resp.data
        self.assertEqual(len(out), 1)
        self.assertEqual(out[0]['string_id'], 'A1')

    def test_role_normal_refuse(self):
        normal = make_user(self.co_a, 'qhse7-normal', role='normal')
        resp = auth(normal).get(self.BASE)
        self.assertEqual(resp.status_code, 403)


class CourbeIVSelectorTests(TestCase):
    def setUp(self):
        self.co_a = make_company('qhse7-sel-a', 'A')
        self.co_b = make_company('qhse7-sel-b', 'B')

    def test_selector_scopes_company_and_chantier(self):
        ReleveCourbeIV.objects.create(
            company=self.co_a, chantier_id=7, string_id='A1')
        ReleveCourbeIV.objects.create(
            company=self.co_a, chantier_id=8, string_id='A2')
        ReleveCourbeIV.objects.create(
            company=self.co_b, chantier_id=7, string_id='B1')
        out = courbes_iv_for_chantier(self.co_a, 7)
        self.assertEqual([r.string_id for r in out], ['A1'])
