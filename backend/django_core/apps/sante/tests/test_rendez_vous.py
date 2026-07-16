"""NTSAN4 — Agenda multi-praticiens `RendezVous` : chevauchement praticien ET
salle refusé (complète aussi le critère d'acceptation NTSAN2 sur `Salle`,
dont la garde de non-double-réservation n'est exerçable qu'une fois ce
modèle posé), filtres calendrier.
"""
import datetime as dt

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company

from apps.sante.models import Patient, Praticien, RendezVous, Salle
from apps.sante.services import verifier_chevauchement_rdv

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


# Horodatage figé (jamais timezone.now() dans un test dépendant de la date).
DEBUT = timezone.make_aware(dt.datetime(2026, 8, 3, 9, 0))


class ChevauchementServiceTests(TestCase):
    def setUp(self):
        self.company = make_company('sante-rdv-svc-co', 'Clinique RDV')
        self.praticien = Praticien.objects.create(
            company=self.company, nom='Dr. Alami')
        self.praticien_2 = Praticien.objects.create(
            company=self.company, nom='Dr. Bennani')
        self.salle = Salle.objects.create(company=self.company, nom='Salle 1')
        self.patient = Patient.objects.create(company=self.company, nom='X')

    def test_praticien_double_booking_refused(self):
        RendezVous.objects.create(
            company=self.company, patient=self.patient,
            praticien=self.praticien, date_heure_debut=DEBUT, duree_min=30)

        message = verifier_chevauchement_rdv(
            company=self.company, praticien=self.praticien, salle=None,
            date_heure_debut=DEBUT + dt.timedelta(minutes=15), duree_min=30)

        self.assertIsNotNone(message)

    def test_non_overlapping_slot_allowed(self):
        RendezVous.objects.create(
            company=self.company, patient=self.patient,
            praticien=self.praticien, date_heure_debut=DEBUT, duree_min=30)

        message = verifier_chevauchement_rdv(
            company=self.company, praticien=self.praticien, salle=None,
            date_heure_debut=DEBUT + dt.timedelta(minutes=30), duree_min=30)

        self.assertIsNone(message)

    def test_salle_double_booking_refused_even_different_praticiens(self):
        """NTSAN2 — une salle ne peut pas être double-réservée sur le même
        créneau, même pour deux praticiens différents."""
        RendezVous.objects.create(
            company=self.company, patient=self.patient,
            praticien=self.praticien, salle=self.salle,
            date_heure_debut=DEBUT, duree_min=30)

        message = verifier_chevauchement_rdv(
            company=self.company, praticien=self.praticien_2, salle=self.salle,
            date_heure_debut=DEBUT + dt.timedelta(minutes=10), duree_min=30)

        self.assertIsNotNone(message)

    def test_cancelled_rdv_frees_the_slot(self):
        rdv = RendezVous.objects.create(
            company=self.company, patient=self.patient,
            praticien=self.praticien, date_heure_debut=DEBUT, duree_min=30,
            statut=RendezVous.Statut.ANNULE)

        message = verifier_chevauchement_rdv(
            company=self.company, praticien=self.praticien, salle=None,
            date_heure_debut=DEBUT, duree_min=30, exclude_id=None)

        self.assertIsNone(message)
        self.assertEqual(rdv.statut, RendezVous.Statut.ANNULE)


class RendezVousApiTests(TestCase):
    BASE = '/api/django/sante/rendezvous/'

    def setUp(self):
        self.company = make_company('sante-rdv-api-co', 'Clinique RDV API')
        self.user = make_user(self.company, 'sante-rdv-api')
        self.praticien = Praticien.objects.create(
            company=self.company, nom='Dr. Chraibi')
        self.patient = Patient.objects.create(company=self.company, nom='Y')

    def _payload(self, **overrides):
        payload = {
            'patient': self.patient.id,
            'praticien': self.praticien.id,
            'date_heure_debut': DEBUT.isoformat(),
            'duree_min': 30,
        }
        payload.update(overrides)
        return payload

    def test_create_rejects_overlap_with_clear_message(self):
        api = auth(self.user)
        resp1 = api.post(self.BASE, self._payload(), format='json')
        self.assertEqual(resp1.status_code, 201, resp1.data)

        resp2 = api.post(
            self.BASE,
            self._payload(
                date_heure_debut=(DEBUT + dt.timedelta(minutes=10)).isoformat()),
            format='json')
        self.assertEqual(resp2.status_code, 400)
        self.assertIn('detail', resp2.data)

    def test_calendar_filters_by_praticien_and_date(self):
        RendezVous.objects.create(
            company=self.company, patient=self.patient,
            praticien=self.praticien, date_heure_debut=DEBUT, duree_min=30)
        autre_praticien = Praticien.objects.create(
            company=self.company, nom='Dr. Idrissi')
        RendezVous.objects.create(
            company=self.company, patient=self.patient,
            praticien=autre_praticien,
            date_heure_debut=DEBUT + dt.timedelta(days=1), duree_min=30)

        api = auth(self.user)
        resp = api.get(
            self.BASE,
            {'praticien': self.praticien.id, 'date_debut': '2026-08-03',
             'date_fin': '2026-08-03'})

        self.assertEqual(resp.status_code, 200)
        data = resp.data
        rows = data['results'] if isinstance(data, dict) and 'results' in data else data
        self.assertEqual(len(rows), 1)
