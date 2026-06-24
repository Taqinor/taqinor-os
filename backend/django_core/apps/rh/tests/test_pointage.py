"""Tests FG166 — Pointage / clock-in–out (arrivée/départ avec géoloc).

Couvre :
* Création d'un pointage arrivée via l'action pointager-arrivee (company +
  heure_arrivee posées côté serveur).
* Fermeture d'un pointage via l'action pointager-depart (heure_depart
  posée côté serveur, type COMPLET, duree_minutes calculée).
* Isolation multi-société : un utilisateur de la société B ne voit pas les
  pointages de A, et ne peut pas pointer un employé de A.
* Refus du départ doublon (pointage déjà fermé).
* Filtre ?employe= et ?date=.
* Propriété duree_minutes sur le modèle.
"""
from datetime import timezone as dt_timezone
from datetime import datetime, timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.rh.models import DossierEmploye, Pointage

User = get_user_model()

BASE = '/api/django/rh/pointages/'
ARRIVEE_URL = BASE + 'pointager-arrivee/'


def make_company(slug, nom):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


def make_user(company, username, role='responsable'):
    return User.objects.create_user(
        username=username, password='x', company=company, role_legacy=role)


def make_employe(company, matricule):
    return DossierEmploye.objects.create(
        company=company, matricule=matricule, nom='Test', prenom='E')


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


def rows(resp):
    data = resp.data
    return data['results'] if isinstance(data, dict) and 'results' in data \
        else data


class PointageModelTests(TestCase):
    """Tests unitaires sur le modèle Pointage (propriétés, logique pure)."""

    def setUp(self):
        self.co = make_company('pt-model', 'ModelCo')
        self.emp = make_employe(self.co, 'PM1')

    def test_duree_minutes_computed(self):
        now = datetime(2026, 6, 24, 8, 0, 0, tzinfo=dt_timezone.utc)
        later = now + timedelta(hours=8, minutes=30)
        p = Pointage(
            company=self.co, employe=self.emp,
            heure_arrivee=now, heure_depart=later)
        self.assertEqual(p.duree_minutes, 510)

    def test_duree_minutes_none_without_depart(self):
        now = datetime(2026, 6, 24, 8, 0, 0, tzinfo=dt_timezone.utc)
        p = Pointage(company=self.co, employe=self.emp, heure_arrivee=now)
        self.assertIsNone(p.duree_minutes)

    def test_duree_minutes_none_without_arrivee(self):
        p = Pointage(company=self.co, employe=self.emp)
        self.assertIsNone(p.duree_minutes)

    def test_duree_minutes_zero_if_negative(self):
        # Si départ < arrivée (erreur de saisie), duree_minutes = 0.
        now = datetime(2026, 6, 24, 9, 0, 0, tzinfo=dt_timezone.utc)
        earlier = now - timedelta(hours=1)
        p = Pointage(
            company=self.co, employe=self.emp,
            heure_arrivee=now, heure_depart=earlier)
        self.assertEqual(p.duree_minutes, 0)


class PointageApiArriveeTests(TestCase):
    """Tests de l'action pointager-arrivee et du CRUD standard."""

    def setUp(self):
        self.co_a = make_company('pt-a', 'A')
        self.co_b = make_company('pt-b', 'B')
        self.user_a = make_user(self.co_a, 'pt-user-a')
        self.user_b = make_user(self.co_b, 'pt-user-b')
        self.emp_a = make_employe(self.co_a, 'EA1')
        self.emp_b = make_employe(self.co_b, 'EB1')

    def test_arrivee_company_posee_cote_serveur(self):
        """La société est forcée côté serveur, jamais lue du corps."""
        resp = auth(self.user_a).post(
            ARRIVEE_URL, {'employe': self.emp_a.id}, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        pt = Pointage.objects.get(id=resp.data['id'])
        self.assertEqual(pt.company, self.co_a)
        self.assertEqual(pt.type_pointage, Pointage.TypePointage.ARRIVEE)
        self.assertIsNotNone(pt.heure_arrivee)

    def test_arrivee_avec_gps(self):
        resp = auth(self.user_a).post(ARRIVEE_URL, {
            'employe': self.emp_a.id,
            'arrivee_gps_lat': '33.589886',
            'arrivee_gps_lng': '-7.603869',
        }, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        pt = Pointage.objects.get(id=resp.data['id'])
        self.assertIsNotNone(pt.arrivee_gps_lat)
        self.assertIsNotNone(pt.arrivee_gps_lng)

    def test_arrivee_employe_autre_societe_refuse(self):
        """Un utilisateur de A ne peut pas pointer un employé de B."""
        resp = auth(self.user_a).post(
            ARRIVEE_URL, {'employe': self.emp_b.id}, format='json')
        self.assertEqual(resp.status_code, 400)

    def test_isolation_list(self):
        """La liste des pointages de A n'est pas visible par B."""
        Pointage.objects.create(
            company=self.co_a, employe=self.emp_a,
            type_pointage=Pointage.TypePointage.ARRIVEE)
        resp = auth(self.user_b).get(BASE)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(rows(resp)), 0)

    def test_create_standard_company_forcee(self):
        """Création via POST standard : company forcée côté serveur."""
        resp = auth(self.user_a).post(BASE, {
            'employe': self.emp_a.id,
            'type_pointage': 'arrivee',
        }, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        pt = Pointage.objects.get(id=resp.data['id'])
        self.assertEqual(pt.company, self.co_a)

    def test_filtre_employe(self):
        emp2 = make_employe(self.co_a, 'EA2')
        Pointage.objects.create(
            company=self.co_a, employe=self.emp_a,
            type_pointage=Pointage.TypePointage.ARRIVEE)
        Pointage.objects.create(
            company=self.co_a, employe=emp2,
            type_pointage=Pointage.TypePointage.ARRIVEE)
        resp = auth(self.user_a).get(BASE + f'?employe={self.emp_a.id}')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(rows(resp)), 1)

    def test_role_normal_refuse(self):
        normal = make_user(self.co_a, 'pt-normal', role='normal')
        resp = auth(normal).get(BASE)
        self.assertEqual(resp.status_code, 403)


class PointageDepartTests(TestCase):
    """Tests de l'action pointager-depart."""

    def setUp(self):
        self.co = make_company('pt-dep', 'Dep')
        self.user = make_user(self.co, 'pt-dep-user')
        self.emp = make_employe(self.co, 'ED1')

    def _create_arrivee(self):
        return Pointage.objects.create(
            company=self.co, employe=self.emp,
            type_pointage=Pointage.TypePointage.ARRIVEE)

    def test_depart_ferme_pointage(self):
        pt = self._create_arrivee()
        resp = auth(self.user).post(
            f'{BASE}{pt.id}/pointager-depart/', {}, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        pt.refresh_from_db()
        self.assertIsNotNone(pt.heure_depart)
        self.assertEqual(pt.type_pointage, Pointage.TypePointage.COMPLET)

    def test_depart_calcule_duree(self):
        pt = self._create_arrivee()
        resp = auth(self.user).post(
            f'{BASE}{pt.id}/pointager-depart/', {}, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        # duree_minutes doit être un entier >= 0 (proche de 0 en test).
        self.assertIsNotNone(resp.data['duree_minutes'])
        self.assertGreaterEqual(resp.data['duree_minutes'], 0)

    def test_depart_doublon_refuse(self):
        pt = self._create_arrivee()
        # Premier départ.
        auth(self.user).post(
            f'{BASE}{pt.id}/pointager-depart/', {}, format='json')
        # Deuxième départ → 400.
        resp = auth(self.user).post(
            f'{BASE}{pt.id}/pointager-depart/', {}, format='json')
        self.assertEqual(resp.status_code, 400)

    def test_depart_avec_gps(self):
        pt = self._create_arrivee()
        resp = auth(self.user).post(
            f'{BASE}{pt.id}/pointager-depart/', {
                'depart_gps_lat': '33.589886',
                'depart_gps_lng': '-7.603869',
            }, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        pt.refresh_from_db()
        self.assertIsNotNone(pt.depart_gps_lat)

    def test_depart_autre_societe_refuse(self):
        """Un utilisateur d'une autre société ne peut pas fermer ce pointage."""
        co_b = make_company('pt-dep-b', 'B')
        user_b = make_user(co_b, 'pt-dep-b-user')
        pt = self._create_arrivee()
        resp = auth(user_b).post(
            f'{BASE}{pt.id}/pointager-depart/', {}, format='json')
        # 404 car le TenantMixin filtre hors société.
        self.assertIn(resp.status_code, [403, 404])


class PointageSerializerValidationTests(TestCase):
    """Tests de validation du sérialiseur Pointage (heure_depart < heure_arrivee)."""

    def setUp(self):
        self.co = make_company('pt-ser', 'Ser')
        self.user = make_user(self.co, 'pt-ser-user')
        self.emp = make_employe(self.co, 'ES1')

    def test_depart_avant_arrivee_refuse(self):
        """heure_depart < heure_arrivee doit être rejeté à la création."""
        resp = auth(self.user).post(BASE, {
            'employe': self.emp.id,
            'type_pointage': 'complet',
            'heure_arrivee': '2026-06-24T09:00:00Z',
            'heure_depart': '2026-06-24T08:00:00Z',
        }, format='json')
        self.assertEqual(resp.status_code, 400)
