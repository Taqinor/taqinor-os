"""
XFSM10 — Astreinte / rotation après-heures.

Couvre :
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

from apps.installations.models import Astreinte
from apps.installations import selectors

User = get_user_model()
_seq = itertools.count(1)


def make_company(slug=None, nom=None):
    from authentication.models import Company
    n = next(_seq)
    company, _ = Company.objects.get_or_create(
        slug=slug or f'xfsm10-co-{n}', defaults={'nom': nom or f'XFSM10 Co {n}'})
    return company


def make_user(company, role='responsable', username=None):
    return User.objects.create_user(
        username=username or f'xfsm10-{next(_seq)}', password='x',
        role_legacy=role, company=company)


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
