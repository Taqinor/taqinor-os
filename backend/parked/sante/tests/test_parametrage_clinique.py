"""NTSAN35 — Paramétrage clinique : créer un RDV pré-remplit la durée
depuis la spécialité du praticien sélectionné (duree_consultation_defaut_min),
modifiable manuellement. Motifs de consultation paramétrables par société.
"""
import datetime as dt

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company

from apps.sante.models import MotifConsultation, Patient, Praticien, RendezVous

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


class DureeConsultationDefautTests(TestCase):
    BASE = '/api/django/sante/rendezvous/'

    def setUp(self):
        self.company = make_company('sante-param-co', 'Clinique Param')
        self.user = make_user(self.company, 'sante-param-user')
        self.patient = Patient.objects.create(company=self.company, nom='X')

    def test_create_without_duree_prefills_from_praticien_default(self):
        praticien = Praticien.objects.create(
            company=self.company, nom='Dr. Cardio', specialite='Cardiologie',
            duree_consultation_defaut_min=45)

        api = auth(self.user)
        resp = api.post(
            self.BASE,
            {
                'patient': self.patient.id, 'praticien': praticien.id,
                'date_heure_debut': dt.datetime(2026, 8, 3, 9, 0).isoformat(),
            },
            format='json')

        self.assertEqual(resp.status_code, 201, resp.data)
        rdv = RendezVous.objects.get(id=resp.data['id'])
        self.assertEqual(rdv.duree_min, 45)

    def test_explicit_duree_overrides_praticien_default(self):
        """« modifiable manuellement » : un duree_min explicite gagne
        toujours sur la valeur par défaut du praticien."""
        praticien = Praticien.objects.create(
            company=self.company, nom='Dr. Généraliste',
            duree_consultation_defaut_min=20)

        api = auth(self.user)
        resp = api.post(
            self.BASE,
            {
                'patient': self.patient.id, 'praticien': praticien.id,
                'date_heure_debut': dt.datetime(2026, 8, 3, 9, 0).isoformat(),
                'duree_min': 15,
            },
            format='json')

        self.assertEqual(resp.status_code, 201, resp.data)
        rdv = RendezVous.objects.get(id=resp.data['id'])
        self.assertEqual(rdv.duree_min, 15)

    def test_no_default_configured_falls_back_to_model_default(self):
        praticien = Praticien.objects.create(company=self.company, nom='Dr. Sans défaut')

        api = auth(self.user)
        resp = api.post(
            self.BASE,
            {
                'patient': self.patient.id, 'praticien': praticien.id,
                'date_heure_debut': dt.datetime(2026, 8, 3, 9, 0).isoformat(),
            },
            format='json')

        self.assertEqual(resp.status_code, 201, resp.data)
        rdv = RendezVous.objects.get(id=resp.data['id'])
        self.assertEqual(rdv.duree_min, 30)


class MotifConsultationApiTests(TestCase):
    BASE = '/api/django/sante/motifs-consultation/'

    def setUp(self):
        self.company = make_company('sante-motif-co', 'Clinique Motif')
        self.user = make_user(self.company, 'sante-motif-user')

    def test_motifs_scoped_by_tenant(self):
        other = make_company('sante-motif-co-b', 'Clinique B')
        MotifConsultation.objects.create(company=self.company, libelle='Contrôle')
        MotifConsultation.objects.create(company=other, libelle='Autre société')

        api = auth(self.user)
        resp = api.get(self.BASE)

        self.assertEqual(resp.status_code, 200)
        rows = resp.data.get('results', resp.data) if isinstance(resp.data, dict) else resp.data
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]['libelle'], 'Contrôle')

    def test_create_motif(self):
        api = auth(self.user)
        resp = api.post(self.BASE, {'libelle': 'Suivi post-opératoire'}, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
