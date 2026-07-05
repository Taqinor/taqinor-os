"""
XFSM10 — Astreinte / rotation après-heures.

Couvre :
  * CRUD scopé société de l'astreinte (`AstreinteViewSet`), écriture
    responsable/admin, lecture tout rôle ;
  * garde de chevauchement de périodes (même société) → 400 ;
  * sélecteur `technicien_astreinte(company, dt)` renvoie le bon technicien
    (ou None hors de toute période) — consommable en lecture seule par la paie ;
  * `astreintes_periode` filtre correctement une fenêtre.

NOTE : le routage effectif des tickets SAV urgents hors-heures vers le
technicien d'astreinte (au lieu du seul responsable) nécessite un hook dans
`apps/sav` — HORS PÉRIMÈTRE de ce lot (cette lane ne modifie que
`apps/installations`) ; le sélecteur ci-dessous est le point d'intégration
prêt à consommer côté SAV/paie dans une session ultérieure.

Run :
    python manage.py test apps.installations.tests_xfsm10_astreinte -v2
"""
import itertools

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.installations.models import Astreinte
from apps.installations import selectors

User = get_user_model()
_seq = itertools.count(1)
BASE = '/api/django/installations'


def make_company(slug=None, nom=None):
    from authentication.models import Company
    n = next(_seq)
    company, _ = Company.objects.get_or_create(
        slug=slug or f'xfsm10-co-{n}', defaults={'nom': nom or f'XFSM10 Co {n}'})
    return company


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


def make_user(company, role='responsable', username=None):
    return User.objects.create_user(
        username=username or f'xfsm10-{next(_seq)}', password='x',
        role_legacy=role, company=company)


class TestAstreinteCrud(TestCase):
    def setUp(self):
        self.company = make_company()
        self.resp = make_user(self.company, role='responsable')
        self.tech = make_user(self.company, role='technicien')
        self.api = auth(self.resp)
        self.now = timezone.now()

    def test_create_astreinte(self):
        r = self.api.post(f'{BASE}/astreintes/', {
            'technicien': self.tech.id,
            'date_debut': (self.now).isoformat(),
            'date_fin': (self.now + timezone.timedelta(days=7)).isoformat(),
            'telephone_astreinte': '0600000000',
        }, format='json')
        self.assertEqual(r.status_code, 201, r.content)
        self.assertEqual(r.data['technicien'], self.tech.id)

    def test_overlap_rejected(self):
        Astreinte.objects.create(
            company=self.company, technicien=self.tech,
            date_debut=self.now, date_fin=self.now + timezone.timedelta(days=7))
        r = self.api.post(f'{BASE}/astreintes/', {
            'technicien': self.tech.id,
            'date_debut': (self.now + timezone.timedelta(days=3)).isoformat(),
            'date_fin': (self.now + timezone.timedelta(days=10)).isoformat(),
        }, format='json')
        self.assertEqual(r.status_code, 400, r.content)

    def test_other_company_technicien_rejected(self):
        other_co = make_company()
        other_tech = make_user(other_co, role='technicien')
        r = self.api.post(f'{BASE}/astreintes/', {
            'technicien': other_tech.id,
            'date_debut': self.now.isoformat(),
            'date_fin': (self.now + timezone.timedelta(days=1)).isoformat(),
        }, format='json')
        self.assertEqual(r.status_code, 400, r.content)

    def test_technicien_cannot_write(self):
        tech_api = auth(self.tech)
        r = tech_api.post(f'{BASE}/astreintes/', {
            'technicien': self.tech.id,
            'date_debut': self.now.isoformat(),
            'date_fin': (self.now + timezone.timedelta(days=1)).isoformat(),
        }, format='json')
        self.assertEqual(r.status_code, 403)

    def test_list_scoped_to_company(self):
        Astreinte.objects.create(
            company=self.company, technicien=self.tech,
            date_debut=self.now, date_fin=self.now + timezone.timedelta(days=1))
        other_co = make_company()
        other_tech = make_user(other_co)
        Astreinte.objects.create(
            company=other_co, technicien=other_tech,
            date_debut=self.now, date_fin=self.now + timezone.timedelta(days=1))
        r = self.api.get(f'{BASE}/astreintes/')
        self.assertEqual(r.status_code, 200)
        ids = [a['id'] for a in r.data['results']] if isinstance(r.data, dict) and 'results' in r.data else [a['id'] for a in r.data]
        self.assertEqual(len(ids), 1)


class TestTechnicienAstreinteSelector(TestCase):
    def setUp(self):
        self.company = make_company()
        self.tech = make_user(self.company, role='technicien')
        self.now = timezone.now()

    def test_returns_technicien_within_period(self):
        Astreinte.objects.create(
            company=self.company, technicien=self.tech,
            date_debut=self.now - timezone.timedelta(hours=1),
            date_fin=self.now + timezone.timedelta(hours=8))
        result = selectors.technicien_astreinte(self.company, self.now)
        self.assertEqual(result, self.tech)

    def test_returns_none_outside_period(self):
        Astreinte.objects.create(
            company=self.company, technicien=self.tech,
            date_debut=self.now + timezone.timedelta(days=5),
            date_fin=self.now + timezone.timedelta(days=6))
        result = selectors.technicien_astreinte(self.company, self.now)
        self.assertIsNone(result)

    def test_returns_none_without_company_or_dt(self):
        self.assertIsNone(selectors.technicien_astreinte(None, self.now))
        self.assertIsNone(selectors.technicien_astreinte(self.company, None))

    def test_astreintes_periode_filters_window(self):
        Astreinte.objects.create(
            company=self.company, technicien=self.tech,
            date_debut=self.now, date_fin=self.now + timezone.timedelta(days=1))
        Astreinte.objects.create(
            company=self.company, technicien=self.tech,
            date_debut=self.now + timezone.timedelta(days=30),
            date_fin=self.now + timezone.timedelta(days=31))
        qs = selectors.astreintes_periode(
            self.company, self.now, self.now + timezone.timedelta(days=2))
        self.assertEqual(qs.count(), 1)
