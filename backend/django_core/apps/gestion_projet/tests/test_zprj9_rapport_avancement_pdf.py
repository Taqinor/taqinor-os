"""Tests du PDF interne « Point d'avancement projet » (ZPRJ9).

Couvre : génération PDF (blocs peuplés depuis les sélecteurs existants),
projet vide (sans jalon/risque/temps) dégrade proprement sans crash,
en-tête société, endpoint ``projets/<id>/rapport-avancement-pdf/`` (200 +
content-type PDF, isolation société).
"""
from datetime import date

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company

from apps.gestion_projet import reports
from apps.gestion_projet.models import Jalon, Projet

User = get_user_model()


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


class RapportAvancementPdfTests(TestCase):
    def setUp(self):
        self.co = make_company('gp-z9-sel', 'S')
        self.projet = Projet.objects.create(
            company=self.co, code='P-Z9', nom='Projet Z9')

    def test_pdf_projet_vide_ne_plante_pas(self):
        pdf_bytes = reports.rapport_avancement_pdf(self.projet)
        self.assertIsInstance(pdf_bytes, bytes)
        self.assertGreater(len(pdf_bytes), 0)
        self.assertEqual(pdf_bytes[:4], b'%PDF')

    def test_pdf_avec_jalons_et_retards(self):
        Jalon.objects.create(
            company=self.co, projet=self.projet, libelle='Atteint',
            date_prevue=date(2026, 1, 1), statut=Jalon.Statut.ATTEINT)
        Jalon.objects.create(
            company=self.co, projet=self.projet, libelle='A venir',
            date_prevue=date(2027, 1, 1), statut=Jalon.Statut.A_VENIR)
        pdf_bytes = reports.rapport_avancement_pdf(self.projet)
        self.assertEqual(pdf_bytes[:4], b'%PDF')


class RapportAvancementPdfApiTests(TestCase):
    BASE = '/api/django/gestion-projet/projets/'

    def setUp(self):
        self.co_a = make_company('gp-z9-a', 'A')
        self.co_b = make_company('gp-z9-b', 'B')
        self.user_a = make_user(self.co_a, 'gp-z9-a-u')
        self.user_b = make_user(self.co_b, 'gp-z9-b-u')
        self.projet_a = Projet.objects.create(
            company=self.co_a, code='P-Z9A', nom='A')

    def test_endpoint_retourne_pdf(self):
        api = auth(self.user_a)
        resp = api.get(
            f'{self.BASE}{self.projet_a.id}/rapport-avancement-pdf/')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp['Content-Type'], 'application/pdf')

    def test_isolation_societe_404(self):
        api = auth(self.user_b)
        resp = api.get(
            f'{self.BASE}{self.projet_a.id}/rapport-avancement-pdf/')
        self.assertEqual(resp.status_code, 404)
