"""NTSAN30 — Horaires praticien & indisponibilités : un RDV hors horaire
d'ouverture ou pendant une indisponibilité est rejeté à la création. Un
praticien SANS horaire configuré n'est PAS restreint (additif, jamais de
régression pour un praticien déjà en service).
"""
import datetime as dt

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company

from apps.sante.models import (
    HoraireOuverturePraticien, IndisponibilitePraticien, Patient, Praticien)
from apps.sante.services import verifier_horaires_praticien

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


# Lundi 2026-08-03.
LUNDI = dt.date(2026, 8, 3)


class VerifierHorairesPraticienServiceTests(TestCase):
    def setUp(self):
        self.company = make_company('sante-horaires-co', 'Clinique Horaires')
        self.praticien = Praticien.objects.create(
            company=self.company, nom='Dr. Alami')

    def test_no_horaire_configured_never_restricts(self):
        debut = timezone.make_aware(dt.datetime(2026, 8, 3, 23, 0))
        message = verifier_horaires_praticien(
            praticien=self.praticien, date_heure_debut=debut, duree_min=30)
        self.assertIsNone(message)

    def test_rdv_within_configured_horaire_allowed(self):
        HoraireOuverturePraticien.objects.create(
            company=self.company, praticien=self.praticien,
            jour_semaine=LUNDI.weekday(),
            heure_debut=dt.time(9, 0), heure_fin=dt.time(12, 0))

        debut = timezone.make_aware(dt.datetime(2026, 8, 3, 10, 0))
        message = verifier_horaires_praticien(
            praticien=self.praticien, date_heure_debut=debut, duree_min=30)
        self.assertIsNone(message)

    def test_rdv_outside_configured_horaire_rejected(self):
        HoraireOuverturePraticien.objects.create(
            company=self.company, praticien=self.praticien,
            jour_semaine=LUNDI.weekday(),
            heure_debut=dt.time(9, 0), heure_fin=dt.time(12, 0))

        debut = timezone.make_aware(dt.datetime(2026, 8, 3, 14, 0))
        message = verifier_horaires_praticien(
            praticien=self.praticien, date_heure_debut=debut, duree_min=30)
        self.assertIsNotNone(message)

    def test_rdv_during_indisponibilite_rejected(self):
        IndisponibilitePraticien.objects.create(
            company=self.company, praticien=self.praticien,
            date_debut=timezone.make_aware(dt.datetime(2026, 8, 3, 8, 0)),
            date_fin=timezone.make_aware(dt.datetime(2026, 8, 3, 18, 0)),
            motif='Formation')

        debut = timezone.make_aware(dt.datetime(2026, 8, 3, 10, 0))
        message = verifier_horaires_praticien(
            praticien=self.praticien, date_heure_debut=debut, duree_min=30)
        self.assertIsNotNone(message)


class RendezVousApiHorairesTests(TestCase):
    BASE = '/api/django/sante/rendezvous/'

    def setUp(self):
        self.company = make_company('sante-horaires-api-co', 'Clinique Horaires API')
        self.user = make_user(self.company, 'sante-horaires-api')
        self.praticien = Praticien.objects.create(
            company=self.company, nom='Dr. Bennani')
        self.patient = Patient.objects.create(company=self.company, nom='X')
        HoraireOuverturePraticien.objects.create(
            company=self.company, praticien=self.praticien,
            jour_semaine=LUNDI.weekday(),
            heure_debut=dt.time(9, 0), heure_fin=dt.time(12, 0))

    def test_create_rejects_rdv_outside_horaire(self):
        api = auth(self.user)
        resp = api.post(
            self.BASE,
            {
                'patient': self.patient.id, 'praticien': self.praticien.id,
                'date_heure_debut': dt.datetime(2026, 8, 3, 14, 0).isoformat(),
                'duree_min': 30,
            },
            format='json')
        self.assertEqual(resp.status_code, 400)

    def test_create_accepts_rdv_within_horaire(self):
        api = auth(self.user)
        resp = api.post(
            self.BASE,
            {
                'patient': self.patient.id, 'praticien': self.praticien.id,
                'date_heure_debut': dt.datetime(2026, 8, 3, 9, 30).isoformat(),
                'duree_min': 30,
            },
            format='json')
        self.assertEqual(resp.status_code, 201, resp.data)

    def test_praticien_without_horaire_unrestricted(self):
        autre_praticien = Praticien.objects.create(
            company=self.company, nom='Dr. Sans horaire')
        api = auth(self.user)
        resp = api.post(
            self.BASE,
            {
                'patient': self.patient.id, 'praticien': autre_praticien.id,
                'date_heure_debut': dt.datetime(2026, 8, 3, 23, 0).isoformat(),
                'duree_min': 30,
            },
            format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
