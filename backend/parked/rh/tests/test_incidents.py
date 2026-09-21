"""Tests FG171 — Retards & absences injustifiées (marquage + compteur).

Couvre :
* Création d'un incident (company posée côté serveur, jamais lue du corps).
* Justification via l'action justifier/ (justifie=True, justifie_par/le posés
  côté serveur ; sort du décompte par défaut).
* Isolation multi-société : B ne voit pas / ne crée pas / ne justifie pas les
  incidents de A.
* Filtres ?employe=, ?type_incident=, ?justifie=, plage.
* Action compteur/ + sélecteur compteur_incidents (agrégation par type, les
  justifiés exclus par défaut, inclure_justifies rétablit le total).
* Permission : un rôle normal est refusé (403).
"""
from datetime import date

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.rh import selectors
from apps.rh.models import DossierEmploye, IncidentPresence

User = get_user_model()

BASE = '/api/django/rh/incidents-presence/'
JOUR = date(2026, 6, 24)
RETARD = IncidentPresence.TypeIncident.RETARD
ABSENCE = IncidentPresence.TypeIncident.ABSENCE_INJUSTIFIEE


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


class IncidentApiTests(TestCase):
    def setUp(self):
        self.co_a = make_company('inc-a', 'A')
        self.co_b = make_company('inc-b', 'B')
        self.user_a = make_user(self.co_a, 'inc-user-a')
        self.user_b = make_user(self.co_b, 'inc-user-b')
        self.emp_a = make_employe(self.co_a, 'IA1')
        self.emp_b = make_employe(self.co_b, 'IB1')

    def test_create_company_posee_cote_serveur(self):
        resp = auth(self.user_a).post(BASE, {
            'employe': self.emp_a.id, 'type_incident': 'retard',
            'date': JOUR.isoformat(), 'minutes_retard': 15,
        }, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        inc = IncidentPresence.objects.get(id=resp.data['id'])
        self.assertEqual(inc.company, self.co_a)
        self.assertEqual(inc.minutes_retard, 15)
        self.assertFalse(inc.justifie)

    def test_create_employe_autre_societe_refuse(self):
        resp = auth(self.user_a).post(BASE, {
            'employe': self.emp_b.id, 'type_incident': 'retard',
            'date': JOUR.isoformat(),
        }, format='json')
        self.assertEqual(resp.status_code, 400)

    def test_isolation_list(self):
        IncidentPresence.objects.create(
            company=self.co_a, employe=self.emp_a, type_incident=RETARD,
            date=JOUR)
        resp = auth(self.user_b).get(BASE)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(rows(resp)), 0)

    def test_filtre_type_et_justifie(self):
        IncidentPresence.objects.create(
            company=self.co_a, employe=self.emp_a, type_incident=RETARD,
            date=JOUR)
        IncidentPresence.objects.create(
            company=self.co_a, employe=self.emp_a, type_incident=ABSENCE,
            date=JOUR, justifie=True)
        r1 = auth(self.user_a).get(BASE + '?type_incident=retard')
        self.assertEqual(len(rows(r1)), 1)
        r2 = auth(self.user_a).get(BASE + '?justifie=1')
        self.assertEqual(len(rows(r2)), 1)

    def test_role_normal_refuse(self):
        normal = make_user(self.co_a, 'inc-normal', role='normal')
        resp = auth(normal).get(BASE)
        self.assertEqual(resp.status_code, 403)


class IncidentJustifierTests(TestCase):
    def setUp(self):
        self.co = make_company('inc-just', 'Just')
        self.user = make_user(self.co, 'inc-just-user')
        self.emp = make_employe(self.co, 'IJ1')

    def test_justifier_pose_regularisation_cote_serveur(self):
        inc = IncidentPresence.objects.create(
            company=self.co, employe=self.emp, type_incident=RETARD, date=JOUR)
        resp = auth(self.user).post(
            f'{BASE}{inc.id}/justifier/', {'motif': 'Certificat médical'},
            format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        inc.refresh_from_db()
        self.assertTrue(inc.justifie)
        self.assertEqual(inc.motif, 'Certificat médical')
        self.assertEqual(inc.justifie_par, self.user)
        self.assertIsNotNone(inc.justifie_le)

    def test_justifier_autre_societe_refuse(self):
        co_b = make_company('inc-just-b', 'B')
        user_b = make_user(co_b, 'inc-just-b-user')
        inc = IncidentPresence.objects.create(
            company=self.co, employe=self.emp, type_incident=RETARD, date=JOUR)
        resp = auth(user_b).post(f'{BASE}{inc.id}/justifier/', {}, format='json')
        self.assertIn(resp.status_code, [403, 404])


class IncidentCompteurTests(TestCase):
    def setUp(self):
        self.co = make_company('inc-cpt', 'Cpt')
        self.user = make_user(self.co, 'inc-cpt-user')
        self.emp = make_employe(self.co, 'IC1')

    def _seed(self):
        IncidentPresence.objects.create(
            company=self.co, employe=self.emp, type_incident=RETARD,
            date=JOUR, minutes_retard=10)
        IncidentPresence.objects.create(
            company=self.co, employe=self.emp, type_incident=RETARD,
            date=JOUR, minutes_retard=20)
        IncidentPresence.objects.create(
            company=self.co, employe=self.emp, type_incident=ABSENCE,
            date=JOUR)
        # Un incident JUSTIFIÉ — exclu du décompte par défaut.
        IncidentPresence.objects.create(
            company=self.co, employe=self.emp, type_incident=ABSENCE,
            date=JOUR, justifie=True)

    def test_selector_compteur_exclut_justifies(self):
        self._seed()
        res = selectors.compteur_incidents(self.co)
        self.assertEqual(len(res), 1)
        row = res[0]
        self.assertEqual(row['retards'], 2)
        self.assertEqual(row['absences'], 1)  # le justifié est exclu
        self.assertEqual(row['total'], 3)
        self.assertEqual(row['minutes_retard_total'], 30)

    def test_selector_compteur_inclure_justifies(self):
        self._seed()
        res = selectors.compteur_incidents(self.co, inclure_justifies=True)
        self.assertEqual(res[0]['absences'], 2)  # justifié inclus
        self.assertEqual(res[0]['total'], 4)

    def test_selector_compteur_sans_company(self):
        self.assertEqual(selectors.compteur_incidents(None), [])

    def test_action_compteur(self):
        self._seed()
        resp = auth(self.user).get(
            f'{BASE}compteur/?debut={JOUR.isoformat()}&fin={JOUR.isoformat()}')
        self.assertEqual(resp.status_code, 200, resp.data)
        data = resp.data
        self.assertEqual(len(data), 1)
        self.assertEqual(data[0]['employe_id'], self.emp.id)
        self.assertEqual(data[0]['total'], 3)
