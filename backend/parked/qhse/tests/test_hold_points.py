"""Tests QHSE6 — points d'arrêt bloquants (hold points) gating l'avancement.

DÉCISION (règle de blocage) — un point de contrôle marqué ``hold_point`` bloque
l'avancement au-delà de sa phase tant que son relevé est *non résolu* : relevé
absent OU ``conforme`` ≠ ``True`` (``None`` = pas encore relevé, ``False`` = non
conforme). Il débloque dès que son relevé existe avec ``conforme=True``. Les
non-conformités sur des points qui ne sont PAS des points d'arrêt n'entrent
jamais dans le calcul.

Couvre :

* le sélecteur ``hold_points_status`` (peut_avancer + liste/phases bloquantes) ;
* le gate par phase ``phase_peut_avancer`` ;
* qu'une non-conformité NON-hold-point ne bloque pas ;
* qu'un relevé conforme lève le blocage ;
* l'endpoint ``plans-chantier/<id>/hold-points/`` (scopé société : 404 ailleurs,
  403 pour un rôle normal) ;
* les champs ``peut_avancer`` / ``nb_hold_points_bloquants`` du sérialiseur.
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
from apps.qhse.selectors import hold_points_status, phase_peut_avancer
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


def make_plan(company):
    modele = PlanInspectionModele.objects.create(company=company, nom='ITP')
    plan = PlanInspectionChantier.objects.create(
        company=company, modele=modele, chantier_id=1)
    return modele, plan


def make_point(company, modele, **kwargs):
    defaults = {'intitule': 'P', 'phase': 'pose'}
    defaults.update(kwargs)
    return PointControleModele.objects.create(
        company=company, plan=modele, **defaults)


class HoldPointSelectorTests(TestCase):
    """Règle de gating au niveau du sélecteur ``hold_points_status``."""

    def setUp(self):
        self.co = make_company('qhse6-sel', 'Sel')
        self.modele, self.plan = make_plan(self.co)

    def _releve(self, point, conforme=None, valeur=''):
        return ReleveControle.objects.create(
            company=self.co, plan_chantier=self.plan, point=point,
            valeur=valeur, conforme=conforme)

    def test_no_hold_points_can_advance(self):
        # Un point normal (pas hold) ne bloque jamais, même non conforme.
        point = make_point(self.co, self.modele, hold_point=False)
        self._releve(point, conforme=False)
        status = hold_points_status(self.plan)
        self.assertTrue(status['peut_avancer'])
        self.assertEqual(status['nb_hold_points'], 0)
        self.assertEqual(status['nb_bloquants'], 0)
        self.assertEqual(status['points_bloquants'], [])

    def test_hold_point_without_releve_blocks(self):
        # Point d'arrêt sans relevé matérialisé → bloquant.
        point = make_point(
            self.co, self.modele, hold_point=True, ordre=1,
            intitule='Étanchéité', phase='pose')
        status = hold_points_status(self.plan)
        self.assertFalse(status['peut_avancer'])
        self.assertEqual(status['nb_hold_points'], 1)
        self.assertEqual(status['nb_bloquants'], 1)
        self.assertEqual(len(status['points_bloquants']), 1)
        bloc = status['points_bloquants'][0]
        self.assertEqual(bloc['point_id'], point.id)
        self.assertEqual(bloc['intitule'], 'Étanchéité')
        self.assertEqual(bloc['phase'], 'pose')
        self.assertFalse(bloc['releve_present'])
        self.assertIsNone(bloc['releve_id'])
        self.assertIsNone(bloc['conforme'])
        self.assertEqual(status['phases_bloquees'], ['pose'])

    def test_hold_point_releve_not_yet_checked_blocks(self):
        # Relevé présent mais conforme=None (pas encore relevé) → bloquant.
        point = make_point(self.co, self.modele, hold_point=True)
        rel = self._releve(point, conforme=None)
        status = hold_points_status(self.plan)
        self.assertFalse(status['peut_avancer'])
        self.assertEqual(status['nb_bloquants'], 1)
        bloc = status['points_bloquants'][0]
        self.assertTrue(bloc['releve_present'])
        self.assertEqual(bloc['releve_id'], rel.id)
        self.assertIsNone(bloc['conforme'])

    def test_hold_point_non_conforme_blocks(self):
        # Relevé conforme=False → bloquant.
        point = make_point(self.co, self.modele, hold_point=True)
        self._releve(point, conforme=False)
        status = hold_points_status(self.plan)
        self.assertFalse(status['peut_avancer'])
        self.assertEqual(status['nb_bloquants'], 1)
        self.assertFalse(status['points_bloquants'][0]['conforme'])

    def test_hold_point_conforme_unblocks(self):
        # Relevé conforme=True → débloque.
        point = make_point(self.co, self.modele, hold_point=True)
        self._releve(point, conforme=True)
        status = hold_points_status(self.plan)
        self.assertTrue(status['peut_avancer'])
        self.assertEqual(status['nb_hold_points'], 1)
        self.assertEqual(status['nb_bloquants'], 0)
        self.assertEqual(status['phases_bloquees'], [])

    def test_non_hold_point_non_conforme_does_not_block(self):
        # Une non-conformité sur un point NON-hold ne bloque pas l'avancement,
        # même quand un point d'arrêt voisin est conforme.
        normal = make_point(
            self.co, self.modele, hold_point=False, intitule='Visuel')
        hold = make_point(self.co, self.modele, hold_point=True)
        self._releve(normal, conforme=False)
        self._releve(hold, conforme=True)
        status = hold_points_status(self.plan)
        self.assertTrue(status['peut_avancer'])
        self.assertEqual(status['nb_bloquants'], 0)

    def test_mixed_only_unresolved_holds_listed(self):
        # Deux points d'arrêt : un levé, un non levé → seul le non levé bloque.
        leve = make_point(
            self.co, self.modele, hold_point=True, ordre=1,
            intitule='Mise à la terre', phase='raccordement')
        non_leve = make_point(
            self.co, self.modele, hold_point=True, ordre=2,
            intitule='Test de tension', phase='essais')
        self._releve(leve, conforme=True)
        self._releve(non_leve, conforme=False)
        status = hold_points_status(self.plan)
        self.assertFalse(status['peut_avancer'])
        self.assertEqual(status['nb_hold_points'], 2)
        self.assertEqual(status['nb_bloquants'], 1)
        ids = [b['point_id'] for b in status['points_bloquants']]
        self.assertEqual(ids, [non_leve.id])
        self.assertEqual(status['phases_bloquees'], ['essais'])

    def test_points_bloquants_ordered_by_ordre(self):
        p2 = make_point(
            self.co, self.modele, hold_point=True, ordre=2, intitule='B')
        p1 = make_point(
            self.co, self.modele, hold_point=True, ordre=1, intitule='A')
        status = hold_points_status(self.plan)
        ids = [b['point_id'] for b in status['points_bloquants']]
        self.assertEqual(ids, [p1.id, p2.id])

    def test_phase_peut_avancer(self):
        # 'pose' : point d'arrêt sans relevé → bloqué.
        make_point(
            self.co, self.modele, hold_point=True, phase='pose',
            intitule='Bloquant pose')
        # 'essais' : point d'arrêt levé (relevé conforme) → débloqué.
        point_essais = make_point(
            self.co, self.modele, hold_point=True, phase='essais',
            intitule='Essais OK')
        self._releve(point_essais, conforme=True)

        self.assertFalse(phase_peut_avancer(self.plan, 'pose'))
        self.assertTrue(phase_peut_avancer(self.plan, 'essais'))
        # Phase sans point d'arrêt : jamais bloquée.
        self.assertTrue(phase_peut_avancer(self.plan, 'inconnue'))

    def test_releves_via_instancier_block_until_conforme(self):
        # Flux réel : l'instanciation matérialise les relevés (conforme=None) →
        # un point d'arrêt bloque tant qu'on n'a pas posé conforme=True.
        make_point(
            self.co, self.modele, hold_point=True, intitule='Étanchéité')
        plan = instancier_plan_chantier(
            modele=self.modele, chantier_id=99, company=self.co)
        self.assertFalse(hold_points_status(plan)['peut_avancer'])
        rel = plan.releves.get(point__hold_point=True)
        rel.conforme = True
        rel.save()
        self.assertTrue(hold_points_status(plan)['peut_avancer'])


class HoldPointEndpointTests(TestCase):
    BASE = '/api/django/qhse/plans-chantier/'

    def setUp(self):
        self.co_a = make_company('qhse6-ep-a', 'A')
        self.co_b = make_company('qhse6-ep-b', 'B')
        self.user_a = make_user(self.co_a, 'qhse6-ep-a')
        self.user_b = make_user(self.co_b, 'qhse6-ep-b')
        self.modele_a, self.plan_a = make_plan(self.co_a)
        self.point = make_point(
            self.co_a, self.modele_a, hold_point=True, intitule='Étanchéité',
            phase='pose')

    def _url(self, plan):
        return f'{self.BASE}{plan.id}/hold-points/'

    def test_endpoint_reports_blocked(self):
        resp = auth(self.user_a).get(self._url(self.plan_a))
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertFalse(resp.data['peut_avancer'])
        self.assertEqual(resp.data['nb_bloquants'], 1)
        self.assertEqual(
            resp.data['points_bloquants'][0]['intitule'], 'Étanchéité')
        self.assertEqual(resp.data['phases_bloquees'], ['pose'])

    def test_endpoint_reports_unblocked_after_conforme(self):
        ReleveControle.objects.create(
            company=self.co_a, plan_chantier=self.plan_a, point=self.point,
            conforme=True)
        resp = auth(self.user_a).get(self._url(self.plan_a))
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertTrue(resp.data['peut_avancer'])
        self.assertEqual(resp.data['nb_bloquants'], 0)

    def test_endpoint_cross_company_404(self):
        # Plan de A consulté par B → 404 (scopé société).
        resp = auth(self.user_b).get(self._url(self.plan_a))
        self.assertEqual(resp.status_code, 404)

    def test_endpoint_role_normal_refuse(self):
        normal = make_user(self.co_a, 'qhse6-ep-normal', role='normal')
        resp = auth(normal).get(self._url(self.plan_a))
        self.assertEqual(resp.status_code, 403)

    def test_serializer_exposes_gate_fields(self):
        resp = auth(self.user_a).get(f'{self.BASE}{self.plan_a.id}/')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertIn('peut_avancer', resp.data)
        self.assertFalse(resp.data['peut_avancer'])
        self.assertEqual(resp.data['nb_hold_points_bloquants'], 1)
