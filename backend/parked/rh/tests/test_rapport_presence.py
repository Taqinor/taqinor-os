"""Tests ZRH18 — rapport de présence & heures supp. par employé/département.

Couvre : agrégat jours pointés/heures/HS/absences par employé, totaux par
département, filtres employé/département, isolation tenant, gate admin.
"""
from datetime import date, datetime

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.rh.models import (
    Departement, DossierEmploye, HeuresSupp, IncidentPresence, Pointage,
)

User = get_user_model()

URL = '/api/django/rh/pointages/rapport/'


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


def aware(d, hour):
    return timezone.make_aware(datetime(d.year, d.month, d.day, hour))


class RapportPresenceTests(TestCase):
    def setUp(self):
        self.co_a = make_company('rp-a', 'A')
        self.co_b = make_company('rp-b', 'B')
        self.user_a = make_user(self.co_a, 'rp-user-a')
        self.user_b = make_user(self.co_b, 'rp-user-b')
        self.dep = Departement.objects.create(company=self.co_a, nom='Terrain')
        self.emp = DossierEmploye.objects.create(
            company=self.co_a, matricule='E1', nom='N', prenom='P',
            departement=self.dep)
        self.debut = date(2026, 1, 1)
        self.fin = date(2026, 1, 31)

    def _params(self, **extra):
        params = {
            'debut': self.debut.isoformat(), 'fin': self.fin.isoformat(),
        }
        params.update(extra)
        return params

    def test_manque_dates_requises(self):
        resp = auth(self.user_a).get(URL)
        self.assertEqual(resp.status_code, 400)

    def test_agrege_jours_et_heures(self):
        Pointage.objects.create(
            company=self.co_a, employe=self.emp,
            heure_arrivee=aware(date(2026, 1, 5), 8),
            heure_depart=aware(date(2026, 1, 5), 17))
        Pointage.objects.create(
            company=self.co_a, employe=self.emp,
            heure_arrivee=aware(date(2026, 1, 6), 8),
            heure_depart=aware(date(2026, 1, 6), 16))
        resp = auth(self.user_a).get(URL, self._params())
        self.assertEqual(resp.status_code, 200, resp.data)
        par_employe = resp.data['par_employe']
        self.assertEqual(len(par_employe), 1)
        entry = par_employe[0]
        self.assertEqual(entry['jours_pointes'], 2)
        self.assertEqual(entry['heures_totales'], 17.0)

    def test_heures_supp_agregees(self):
        HeuresSupp.objects.create(
            company=self.co_a, employe=self.emp, date=date(2026, 1, 10),
            heures_travaillees=10, hs_25=2)
        resp = auth(self.user_a).get(URL, self._params())
        entry = resp.data['par_employe'][0]
        self.assertEqual(entry['heures_supp'], 2.0)

    def test_jours_absence_comptes(self):
        IncidentPresence.objects.create(
            company=self.co_a, employe=self.emp,
            type_incident=IncidentPresence.TypeIncident.ABSENCE_INJUSTIFIEE,
            date=date(2026, 1, 12), justifie=False)
        # Justifiée -> ne compte pas.
        IncidentPresence.objects.create(
            company=self.co_a, employe=self.emp,
            type_incident=IncidentPresence.TypeIncident.ABSENCE_INJUSTIFIEE,
            date=date(2026, 1, 13), justifie=True)
        resp = auth(self.user_a).get(URL, self._params())
        entry = resp.data['par_employe'][0]
        self.assertEqual(entry['jours_absence'], 1)

    def test_totaux_departement(self):
        Pointage.objects.create(
            company=self.co_a, employe=self.emp,
            heure_arrivee=aware(date(2026, 1, 5), 8),
            heure_depart=aware(date(2026, 1, 5), 17))
        resp = auth(self.user_a).get(URL, self._params())
        totaux = resp.data['totaux_departement']
        terrain = [t for t in totaux if t['departement_nom'] == 'Terrain']
        self.assertEqual(len(terrain), 1)
        self.assertEqual(terrain[0]['jours_pointes'], 1)

    def test_filtre_employe(self):
        autre = DossierEmploye.objects.create(
            company=self.co_a, matricule='E2', nom='N2', prenom='P2')
        Pointage.objects.create(
            company=self.co_a, employe=self.emp,
            heure_arrivee=aware(date(2026, 1, 5), 8),
            heure_depart=aware(date(2026, 1, 5), 17))
        Pointage.objects.create(
            company=self.co_a, employe=autre,
            heure_arrivee=aware(date(2026, 1, 6), 8),
            heure_depart=aware(date(2026, 1, 6), 17))
        resp = auth(self.user_a).get(
            URL, self._params(employe=self.emp.id))
        ids = [e['employe_id'] for e in resp.data['par_employe']]
        self.assertEqual(ids, [self.emp.id])

    def test_isolation_tenant(self):
        Pointage.objects.create(
            company=self.co_a, employe=self.emp,
            heure_arrivee=aware(date(2026, 1, 5), 8),
            heure_depart=aware(date(2026, 1, 5), 17))
        resp = auth(self.user_b).get(URL, self._params())
        self.assertEqual(resp.data['par_employe'], [])

    def test_role_normal_refuse(self):
        normal = make_user(self.co_a, 'rp-normal', role='normal')
        resp = auth(normal).get(URL, self._params())
        self.assertEqual(resp.status_code, 403)
