"""Tests QHSE4 — ITP appliqué (plan chantier + relevés de contrôle).

Couvre :

* ``instancier_plan_chantier`` copie un relevé par point du modèle et est
  IDEMPOTENT (un 2ᵉ appel ne duplique rien, complète seulement les manquants) ;
* l'endpoint ``POST instancier`` pose la société côté serveur et renvoie 404
  pour un modèle d'une autre société ;
* persistance de ``valeur`` / ``conforme`` / ``photo_key`` et pose de
  ``releve_par`` côté serveur à la création d'un relevé ;
* isolation entre sociétés (A ne voit pas les plans/relevés de B) ;
* rattachement d'un relevé à un plan/point de la MÊME société (parent d'une
  autre société → 400) ;
* accès réservé au palier Administrateur/Responsable (rôle « normal » → 403).
"""
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company

from apps.qhse.models import (
    PlanInspectionChantier, PlanInspectionModele, PointControleModele,
    ReleveControle,
)
from apps.qhse.services import instancier_plan_chantier

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


def make_modele_with_points(company, nb_points):
    modele = PlanInspectionModele.objects.create(company=company, nom='ITP')
    for i in range(nb_points):
        PointControleModele.objects.create(
            company=company, plan=modele, ordre=i, intitule=f'Point {i}')
    return modele


class InstancierServiceTests(TestCase):
    def setUp(self):
        self.co = make_company('qhse4-svc', 'Svc')
        self.modele = make_modele_with_points(self.co, 3)

    def test_instancier_copies_one_releve_per_point(self):
        plan = instancier_plan_chantier(
            modele=self.modele, chantier_id=42, company=self.co)
        self.assertEqual(plan.company, self.co)
        self.assertEqual(plan.chantier_id, 42)
        self.assertEqual(plan.releves.count(), 3)
        # Chaque relevé pointe vers un point distinct du modèle.
        point_ids = set(plan.releves.values_list('point_id', flat=True))
        self.assertEqual(
            point_ids,
            set(self.modele.points.values_list('id', flat=True)))

    def test_instancier_is_idempotent(self):
        plan1 = instancier_plan_chantier(
            modele=self.modele, chantier_id=42, company=self.co)
        plan2 = instancier_plan_chantier(
            modele=self.modele, chantier_id=42, company=self.co)
        self.assertEqual(plan1.id, plan2.id)
        self.assertEqual(PlanInspectionChantier.objects.count(), 1)
        self.assertEqual(ReleveControle.objects.count(), 3)

    def test_instancier_backfills_new_points(self):
        plan = instancier_plan_chantier(
            modele=self.modele, chantier_id=42, company=self.co)
        self.assertEqual(plan.releves.count(), 3)
        # Le modèle gagne un point ; un 2ᵉ appel ne crée que le manquant.
        PointControleModele.objects.create(
            company=self.co, plan=self.modele, ordre=99, intitule='Nouveau')
        instancier_plan_chantier(
            modele=self.modele, chantier_id=42, company=self.co)
        self.assertEqual(plan.releves.count(), 4)

    def test_instancier_rejects_cross_company_modele(self):
        other = make_company('qhse4-svc-other', 'Other')
        with self.assertRaises(ValueError):
            instancier_plan_chantier(
                modele=self.modele, chantier_id=1, company=other)


class InstancierEndpointTests(TestCase):
    BASE = '/api/django/qhse/plans-chantier/'

    def setUp(self):
        self.co_a = make_company('qhse4-ep-a', 'A')
        self.co_b = make_company('qhse4-ep-b', 'B')
        self.user_a = make_user(self.co_a, 'qhse4-ep-a')
        self.user_b = make_user(self.co_b, 'qhse4-ep-b')
        self.modele_a = make_modele_with_points(self.co_a, 2)
        self.modele_b = make_modele_with_points(self.co_b, 2)

    def test_instancier_forces_company_and_creates_releves(self):
        resp = auth(self.user_a).post(
            f'{self.BASE}instancier/',
            {'modele': self.modele_a.id, 'chantier_id': 7},
            format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        plan = PlanInspectionChantier.objects.get(id=resp.data['id'])
        self.assertEqual(plan.company, self.co_a)
        self.assertEqual(plan.releves.count(), 2)

    def test_instancier_cross_company_modele_404(self):
        # Modèle de B instancié par A → 404 (scopé société).
        resp = auth(self.user_a).post(
            f'{self.BASE}instancier/',
            {'modele': self.modele_b.id, 'chantier_id': 7},
            format='json')
        self.assertEqual(resp.status_code, 404)

    def test_instancier_requires_fields(self):
        resp = auth(self.user_a).post(
            f'{self.BASE}instancier/', {'chantier_id': 7}, format='json')
        self.assertEqual(resp.status_code, 400)

    def test_list_isolation(self):
        instancier_plan_chantier(
            modele=self.modele_a, chantier_id=1, company=self.co_a)
        resp = auth(self.user_b).get(self.BASE)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(rows(resp)), 0)

    def test_role_normal_refuse(self):
        normal = make_user(self.co_a, 'qhse4-ep-normal', role='normal')
        resp = auth(normal).get(self.BASE)
        self.assertEqual(resp.status_code, 403)


class ReleveControleApiTests(TestCase):
    BASE = '/api/django/qhse/releves/'

    def setUp(self):
        self.co_a = make_company('qhse4-rel-a', 'A')
        self.co_b = make_company('qhse4-rel-b', 'B')
        self.user_a = make_user(self.co_a, 'qhse4-rel-a')
        self.user_b = make_user(self.co_b, 'qhse4-rel-b')
        self.modele_a = make_modele_with_points(self.co_a, 1)
        self.point_a = self.modele_a.points.first()
        self.plan_a = instancier_plan_chantier(
            modele=self.modele_a, chantier_id=1, company=self.co_a)
        # Côté B.
        self.modele_b = make_modele_with_points(self.co_b, 1)
        self.point_b = self.modele_b.points.first()
        self.plan_b = instancier_plan_chantier(
            modele=self.modele_b, chantier_id=2, company=self.co_b)

    def test_create_persists_fields_and_sets_releve_par(self):
        resp = auth(self.user_a).post(
            self.BASE,
            {
                'plan_chantier': self.plan_a.id,
                'point': self.point_a.id,
                'valeur': '24.5 N.m',
                'conforme': True,
                'photo_key': 'erp-uploads/qhse/abc.jpg',
            },
            format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        obj = ReleveControle.objects.get(id=resp.data['id'])
        self.assertEqual(obj.company, self.co_a)
        self.assertEqual(obj.valeur, '24.5 N.m')
        self.assertTrue(obj.conforme)
        self.assertEqual(obj.photo_key, 'erp-uploads/qhse/abc.jpg')
        # releve_par posé côté serveur (jamais du corps).
        self.assertEqual(obj.releve_par, self.user_a)

    def test_conforme_null_by_default_via_instancier(self):
        # Les relevés nés de l'instanciation ne sont pas encore relevés.
        releve = self.plan_a.releves.first()
        self.assertIsNone(releve.conforme)
        self.assertEqual(releve.valeur, '')
        self.assertEqual(releve.photo_key, '')

    def test_cross_company_plan_chantier_400(self):
        # Plan de B rejeté pour un utilisateur de A.
        resp = auth(self.user_a).post(
            self.BASE,
            {'plan_chantier': self.plan_b.id, 'point': self.point_a.id},
            format='json')
        self.assertEqual(resp.status_code, 400)
        self.assertIn('plan_chantier', resp.data)

    def test_cross_company_point_400(self):
        # Point de B rejeté pour un utilisateur de A.
        resp = auth(self.user_a).post(
            self.BASE,
            {'plan_chantier': self.plan_a.id, 'point': self.point_b.id},
            format='json')
        self.assertEqual(resp.status_code, 400)
        self.assertIn('point', resp.data)

    def test_list_isolation(self):
        resp = auth(self.user_b).get(self.BASE)
        self.assertEqual(resp.status_code, 200)
        # B ne voit que ses propres relevés (issus de plan_b).
        for r in rows(resp):
            self.assertEqual(
                ReleveControle.objects.get(id=r['id']).company, self.co_b)

    def test_role_normal_refuse(self):
        normal = make_user(self.co_a, 'qhse4-rel-normal', role='normal')
        resp = auth(normal).get(self.BASE)
        self.assertEqual(resp.status_code, 403)
