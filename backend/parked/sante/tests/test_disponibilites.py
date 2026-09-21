"""NTSAN29 — `GET /api/django/sante/disponibilites/?praticien=&date=` :
créneaux libres d'un praticien pour un jour donné, calculés à partir des
``RendezVous`` existants (fondation d'un futur module de prise de RDV en
ligne, NTCOL, hors périmètre de ce lot — pas d'exposition publique ici).
"""
import datetime as dt

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company

from apps.sante.models import Patient, Praticien, RendezVous
from apps.sante.selectors import creneaux_disponibles

User = get_user_model()


def make_company(slug, nom):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


def make_user(company, username):
    return User.objects.create_user(
        username=username, password='x', company=company)


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


class CreneauxDisponiblesSelectorTests(TestCase):
    def setUp(self):
        self.company = make_company('sante-dispo-co', 'Clinique Dispo')
        self.praticien = Praticien.objects.create(
            company=self.company, nom='Dr. Alami')
        self.patient = Patient.objects.create(company=self.company, nom='X')
        self.date = dt.date(2026, 8, 3)

    def test_returns_default_slots_when_no_rdv(self):
        creneaux = creneaux_disponibles(
            company=self.company, praticien=self.praticien, date=self.date,
            duree_min=30)
        # Défaut 08:00-18:00, créneaux de 30 min = 20 créneaux.
        self.assertEqual(len(creneaux), 20)
        self.assertEqual(creneaux[0].strftime('%H:%M'), '08:00')

    def test_existing_rdv_blocks_its_slot(self):
        debut = timezone.make_aware(dt.datetime(2026, 8, 3, 9, 0))
        RendezVous.objects.create(
            company=self.company, patient=self.patient,
            praticien=self.praticien, date_heure_debut=debut, duree_min=30)

        creneaux = creneaux_disponibles(
            company=self.company, praticien=self.praticien, date=self.date,
            duree_min=30)

        heures = {c.strftime('%H:%M') for c in creneaux}
        self.assertNotIn('09:00', heures)
        self.assertIn('08:00', heures)
        self.assertIn('09:30', heures)

    def test_cancelled_rdv_does_not_block(self):
        debut = timezone.make_aware(dt.datetime(2026, 8, 3, 9, 0))
        RendezVous.objects.create(
            company=self.company, patient=self.patient,
            praticien=self.praticien, date_heure_debut=debut, duree_min=30,
            statut=RendezVous.Statut.ANNULE)

        creneaux = creneaux_disponibles(
            company=self.company, praticien=self.praticien, date=self.date,
            duree_min=30)

        heures = {c.strftime('%H:%M') for c in creneaux}
        self.assertIn('09:00', heures)


class DisponibilitesApiTests(TestCase):
    BASE = '/api/django/sante/disponibilites/'

    def setUp(self):
        self.company = make_company('sante-dispo-api-co', 'Clinique Dispo API')
        self.user = make_user(self.company, 'sante-dispo-api')
        self.praticien = Praticien.objects.create(
            company=self.company, nom='Dr. Bennani')
        self.patient = Patient.objects.create(company=self.company, nom='Y')

    def test_endpoint_returns_free_slots_excluding_existing_rdv(self):
        debut = timezone.make_aware(dt.datetime(2026, 8, 3, 10, 0))
        RendezVous.objects.create(
            company=self.company, patient=self.patient,
            praticien=self.praticien, date_heure_debut=debut, duree_min=30)

        api = auth(self.user)
        resp = api.get(
            self.BASE, {'praticien': self.praticien.id, 'date': '2026-08-03'})

        self.assertEqual(resp.status_code, 200, resp.data)
        creneaux = resp.data['creneaux']
        self.assertTrue(any('T10:00' in c for c in creneaux) is False)
        self.assertTrue(any('T08:00' in c for c in creneaux))

    def test_missing_params_rejected(self):
        api = auth(self.user)
        resp = api.get(self.BASE, {'praticien': self.praticien.id})
        self.assertEqual(resp.status_code, 400)

    def test_unknown_praticien_rejected(self):
        api = auth(self.user)
        resp = api.get(self.BASE, {'praticien': 999999, 'date': '2026-08-03'})
        self.assertEqual(resp.status_code, 400)
