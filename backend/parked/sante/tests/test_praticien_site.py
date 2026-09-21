"""NTSAN32 — Multi-cabinet / multi-salle pour un praticien itinérant :
l'agenda d'un praticien multi-site affiche ses RDV consolidés tous sites
confondus, avec filtre par site.
"""
import datetime as dt

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company

from apps.sante.models import Patient, Praticien, PraticienSite, RendezVous, Salle

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


class PraticienSiteModelTests(TestCase):
    def setUp(self):
        self.company = make_company('sante-multisite-co', 'Clinique Multisite')
        self.praticien = Praticien.objects.create(
            company=self.company, nom='Dr. Itinérant')
        self.site_a = Salle.objects.create(company=self.company, nom='Site A')
        self.site_b = Salle.objects.create(company=self.company, nom='Site B')

    def test_praticien_can_be_attached_to_multiple_sites(self):
        PraticienSite.objects.create(
            company=self.company, praticien=self.praticien, salle=self.site_a)
        PraticienSite.objects.create(
            company=self.company, praticien=self.praticien, salle=self.site_b)

        self.assertEqual(self.praticien.sites.count(), 2)


class PraticienSiteApiTests(TestCase):
    BASE = '/api/django/sante/sites-praticien/'
    RDV_BASE = '/api/django/sante/rendezvous/'

    def setUp(self):
        self.company = make_company('sante-multisite-api-co', 'Clinique API')
        self.user = make_user(self.company, 'sante-multisite-api')
        self.praticien = Praticien.objects.create(
            company=self.company, nom='Dr. Multisite')
        self.site_a = Salle.objects.create(company=self.company, nom='Clinique Nord')
        self.site_b = Salle.objects.create(company=self.company, nom='Clinique Sud')
        self.patient = Patient.objects.create(company=self.company, nom='X')

        PraticienSite.objects.create(
            company=self.company, praticien=self.praticien, salle=self.site_a)
        PraticienSite.objects.create(
            company=self.company, praticien=self.praticien, salle=self.site_b)

        RendezVous.objects.create(
            company=self.company, patient=self.patient, praticien=self.praticien,
            salle=self.site_a,
            date_heure_debut=timezone.make_aware(dt.datetime(2026, 8, 3, 9, 0)),
            duree_min=30)
        RendezVous.objects.create(
            company=self.company, patient=self.patient, praticien=self.praticien,
            salle=self.site_b,
            date_heure_debut=timezone.make_aware(dt.datetime(2026, 8, 3, 11, 0)),
            duree_min=30)

    def test_create_praticien_site_scoped_by_tenant(self):
        site_c = Salle.objects.create(company=self.company, nom='Clinique Est')
        api = auth(self.user)
        resp = api.post(
            self.BASE,
            {'praticien': self.praticien.id, 'salle': site_c.id},
            format='json')
        self.assertEqual(resp.status_code, 201, resp.data)

        resp2 = api.get(self.BASE)
        self.assertEqual(resp2.status_code, 200)
        rows = resp2.data.get('results', resp2.data) if isinstance(resp2.data, dict) else resp2.data
        self.assertEqual(len(rows), 3)

    def test_agenda_consolidated_across_all_sites_without_salle_filter(self):
        api = auth(self.user)
        resp = api.get(
            self.RDV_BASE,
            {'praticien': self.praticien.id, 'date_debut': '2026-08-03',
             'date_fin': '2026-08-03'})

        self.assertEqual(resp.status_code, 200)
        rows = resp.data.get('results', resp.data) if isinstance(resp.data, dict) else resp.data
        self.assertEqual(len(rows), 2)

    def test_agenda_filtered_by_single_site(self):
        api = auth(self.user)
        resp = api.get(
            self.RDV_BASE,
            {'praticien': self.praticien.id, 'salle': self.site_a.id,
             'date_debut': '2026-08-03', 'date_fin': '2026-08-03'})

        self.assertEqual(resp.status_code, 200)
        rows = resp.data.get('results', resp.data) if isinstance(resp.data, dict) else resp.data
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]['salle'], self.site_a.id)
