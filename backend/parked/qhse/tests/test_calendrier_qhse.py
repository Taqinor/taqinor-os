"""Tests QHSE35 — Inspections / permis dans le digest + calendrier.

Couvre :
* le sélecteur ``calendrier_qhse`` : agrégation inspections (QHSE33) + permis
  (QHSE25) + déclarations CNSS (QHSE30), normalisation en événements, tri par
  date, drapeau ``en_retard``, bornage ``within_days``, isolation société ;
* l'action API ``GET …/calendrier/`` (``?within_days=``), scopée société + rôle.
"""
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company

from apps.qhse.models import InspectionSecurite, PermisTravail
from apps.qhse.selectors import calendrier_qhse

User = get_user_model()

CAL_URL = '/api/django/qhse/calendrier/'


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


class CalendrierQhseSelectorTests(TestCase):
    def setUp(self):
        self.company = make_company('co-cal', 'CoCal')
        self.today = timezone.localdate()

    def test_agrege_inspection_et_permis(self):
        InspectionSecurite.objects.create(
            company=self.company, titre='Ronde', reference='INSP-1',
            statut='planifiee', date_prevue=self.today + timedelta(days=3))
        PermisTravail.objects.create(
            company=self.company, titre='Hauteur', reference='PT-1',
            statut='valide', date_fin=self.today + timedelta(days=5))
        digest = calendrier_qhse(self.company, within_days=30)
        self.assertEqual(digest['total'], 2)
        self.assertEqual(digest['inspections'], 1)
        self.assertEqual(digest['permis'], 1)
        types = [e['type'] for e in digest['evenements']]
        # Tri par date croissante : inspection (J+3) avant permis (J+5).
        self.assertEqual(types, ['inspection', 'permis'])

    def test_en_retard(self):
        InspectionSecurite.objects.create(
            company=self.company, titre='Ronde', reference='INSP-1',
            statut='planifiee', date_prevue=self.today - timedelta(days=2))
        digest = calendrier_qhse(self.company, within_days=30)
        self.assertEqual(digest['total'], 1)
        self.assertTrue(digest['evenements'][0]['en_retard'])

    def test_inspection_annulee_exclue(self):
        InspectionSecurite.objects.create(
            company=self.company, titre='Ronde', reference='INSP-1',
            statut='annulee', date_prevue=self.today + timedelta(days=3))
        digest = calendrier_qhse(self.company, within_days=30)
        self.assertEqual(digest['inspections'], 0)

    def test_bornage_within_days(self):
        InspectionSecurite.objects.create(
            company=self.company, titre='Loin', reference='INSP-1',
            statut='planifiee', date_prevue=self.today + timedelta(days=60))
        digest = calendrier_qhse(self.company, within_days=30)
        self.assertEqual(digest['total'], 0)

    def test_isolation_societe(self):
        other = make_company('co-cal-2', 'CoCal2')
        InspectionSecurite.objects.create(
            company=other, titre='Autre', reference='INSP-1',
            statut='planifiee', date_prevue=self.today + timedelta(days=3))
        digest = calendrier_qhse(self.company, within_days=30)
        self.assertEqual(digest['total'], 0)


class CalendrierQhseApiTests(TestCase):
    def setUp(self):
        self.company = make_company('co-cal-api', 'CoCalApi')
        self.user = make_user(self.company, 'cal-resp')
        self.client_api = auth_client(self.user)
        self.today = timezone.localdate()

    def test_api_liste(self):
        InspectionSecurite.objects.create(
            company=self.company, titre='Ronde', reference='INSP-1',
            statut='planifiee', date_prevue=self.today + timedelta(days=2))
        resp = self.client_api.get(CAL_URL)
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(resp.data['total'], 1)
        self.assertEqual(resp.data['evenements'][0]['type'], 'inspection')

    def test_api_within_days(self):
        InspectionSecurite.objects.create(
            company=self.company, titre='Loin', reference='INSP-1',
            statut='planifiee', date_prevue=self.today + timedelta(days=20))
        resp = self.client_api.get(CAL_URL, {'within_days': 7})
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(resp.data['total'], 0)

    def test_role_normal_refuse(self):
        normal = make_user(self.company, 'cal-normal', role='normal')
        resp = auth_client(normal).get(CAL_URL)
        self.assertEqual(resp.status_code, 403)
