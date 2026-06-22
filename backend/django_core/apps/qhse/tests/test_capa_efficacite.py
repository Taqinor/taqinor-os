"""Tests QHSE13 — Vérification d'efficacité CAPA (clôture conditionnée).

Couvre :

* ``verifier_efficacite_capa`` exige une CAPA RÉALISÉE ; ``efficace=True`` →
  statut VÉRIFIÉE, ``efficace=False`` → repasse EN COURS ; trace
  date/utilisateur/commentaire ;
* ``cloturer_ncr`` n'autorise la clôture que si TOUTES les CAPA sont vérifiées
  efficaces ; idempotent si déjà clôturée ;
* endpoints ``…/capa/<id>/verifier-efficacite/`` et
  ``…/non-conformites/<id>/cloturer/`` (palier Responsable/Admin, scopés société).
"""
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company

from apps.qhse.models import ActionCorrectivePreventive, NonConformite
from apps.qhse.services import (
    cloturer_ncr, ncr_capa_bloquantes, verifier_efficacite_capa,
)

User = get_user_model()
S = ActionCorrectivePreventive.Statut


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


def make_ncr(company):
    return NonConformite.objects.create(company=company, titre='NCR')


def make_capa(company, ncr, statut=S.A_FAIRE):
    return ActionCorrectivePreventive.objects.create(
        company=company, non_conformite=ncr, description='Reprise',
        statut=statut)


class VerifEfficaciteServiceTests(TestCase):
    def setUp(self):
        self.co = make_company('qhse13-svc', 'Svc')
        self.user = make_user(self.co, 'qhse13-svc')
        self.ncr = make_ncr(self.co)

    def test_requires_realisee(self):
        capa = make_capa(self.co, self.ncr, statut=S.EN_COURS)
        with self.assertRaises(ValueError):
            verifier_efficacite_capa(capa, efficace=True)

    def test_effective_moves_to_verifiee(self):
        capa = make_capa(self.co, self.ncr, statut=S.REALISEE)
        verifier_efficacite_capa(
            capa, efficace=True, verifiee_par=self.user, commentaire='OK')
        capa.refresh_from_db()
        self.assertEqual(capa.statut, S.VERIFIEE)
        self.assertTrue(capa.efficace)
        self.assertEqual(capa.verifiee_par, self.user)
        self.assertIsNotNone(capa.date_verification)
        self.assertEqual(capa.commentaire_verification, 'OK')

    def test_ineffective_reopens(self):
        capa = make_capa(self.co, self.ncr, statut=S.REALISEE)
        verifier_efficacite_capa(capa, efficace=False)
        capa.refresh_from_db()
        self.assertEqual(capa.statut, S.EN_COURS)
        self.assertFalse(capa.efficace)


class CloturerNcrServiceTests(TestCase):
    def setUp(self):
        self.co = make_company('qhse13-cls', 'Cls')
        self.ncr = make_ncr(self.co)

    def test_blocked_until_all_verified_effective(self):
        capa = make_capa(self.co, self.ncr, statut=S.REALISEE)
        self.assertEqual(len(ncr_capa_bloquantes(self.ncr)), 1)
        with self.assertRaises(ValueError):
            cloturer_ncr(self.ncr)
        verifier_efficacite_capa(capa, efficace=True)
        self.assertEqual(ncr_capa_bloquantes(self.ncr), [])
        cloturer_ncr(self.ncr)
        self.ncr.refresh_from_db()
        self.assertEqual(self.ncr.statut, NonConformite.Statut.CLOTUREE)

    def test_ncr_without_capa_can_close(self):
        cloturer_ncr(self.ncr)
        self.ncr.refresh_from_db()
        self.assertEqual(self.ncr.statut, NonConformite.Statut.CLOTUREE)

    def test_close_idempotent(self):
        cloturer_ncr(self.ncr)
        # Pas d'erreur même ré-appelée.
        cloturer_ncr(self.ncr)
        self.ncr.refresh_from_db()
        self.assertEqual(self.ncr.statut, NonConformite.Statut.CLOTUREE)


class CapaEfficaciteApiTests(TestCase):
    def setUp(self):
        self.co = make_company('qhse13-api', 'Api')
        self.user = make_user(self.co, 'qhse13-api')
        self.ncr = make_ncr(self.co)
        self.capa = make_capa(self.co, self.ncr, statut=S.REALISEE)

    def test_verifier_efficacite_endpoint(self):
        resp = auth(self.user).post(
            f'/api/django/qhse/capa/{self.capa.id}/verifier-efficacite/',
            {'efficace': True, 'commentaire': 'concluant'}, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.capa.refresh_from_db()
        self.assertEqual(self.capa.statut, S.VERIFIEE)
        self.assertEqual(self.capa.verifiee_par, self.user)

    def test_cloturer_blocked_then_ok(self):
        blocked = auth(self.user).post(
            f'/api/django/qhse/non-conformites/{self.ncr.id}/cloturer/',
            {}, format='json')
        self.assertEqual(blocked.status_code, 400)
        verifier_efficacite_capa(self.capa, efficace=True)
        ok = auth(self.user).post(
            f'/api/django/qhse/non-conformites/{self.ncr.id}/cloturer/',
            {}, format='json')
        self.assertEqual(ok.status_code, 200, ok.data)
        self.assertEqual(ok.data['statut'], NonConformite.Statut.CLOTUREE)

    def test_verifier_requires_efficace(self):
        resp = auth(self.user).post(
            f'/api/django/qhse/capa/{self.capa.id}/verifier-efficacite/',
            {}, format='json')
        self.assertEqual(resp.status_code, 400)

    def test_role_normal_refuse(self):
        normal = make_user(self.co, 'qhse13-normal', role='normal')
        resp = auth(normal).post(
            f'/api/django/qhse/capa/{self.capa.id}/verifier-efficacite/',
            {'efficace': True}, format='json')
        self.assertEqual(resp.status_code, 403)
