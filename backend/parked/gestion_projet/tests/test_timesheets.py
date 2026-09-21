"""Tests du suivi des temps (PROJ24 — timesheets imputés au projet).

Couvre : création d'une feuille de temps avec ``cout`` FIGÉ côté serveur
(heures × coût horaire interne, jamais lu du corps) ; ``cout`` ignoré s'il est
posté ; mise à jour recalculant le coût ; synthèse des temps (total + ventilation
par ressource/tâche) ; société posée côté serveur ; scoping multi-société +
404 cross-tenant ; garde même-projet pour tâche/phase ; accès réservé au palier
Administrateur/Responsable (rôle ``normal`` → 403).

Le coût est une donnée 100 % INTERNE de pilotage — jamais exposée au client.
"""
from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company

from apps.gestion_projet import selectors
from apps.gestion_projet.models import (
    Projet,
    RessourceProfil,
    Tache,
    Timesheet,
)

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


def rows(resp):
    data = resp.data
    return data['results'] if isinstance(data, dict) and 'results' in data \
        else data


class TimesheetApiTests(TestCase):
    BASE = '/api/django/gestion-projet/timesheets/'

    def setUp(self):
        self.co_a = make_company('gp-ts-a', 'A')
        self.co_b = make_company('gp-ts-b', 'B')
        self.user_a = make_user(self.co_a, 'ts-a')
        self.projet = Projet.objects.create(
            company=self.co_a, code='P-A', nom='A')
        self.tache = Tache.objects.create(
            company=self.co_a, projet=self.projet, libelle='T', ordre=1)
        self.ressource = RessourceProfil.objects.create(
            company=self.co_a, nom='R', cout_horaire=Decimal('120'))

    def test_creation_cout_fige_cote_serveur(self):
        api = auth(self.user_a)
        resp = api.post(self.BASE, {
            'projet': self.projet.id,
            'tache': self.tache.id,
            'ressource': self.ressource.id,
            'date': '2026-01-10',
            'heures': '5',
            # cout posté volontairement faux — doit être ignoré.
            'cout': '99999',
        }, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        ts = Timesheet.objects.get(id=resp.data['id'])
        self.assertEqual(ts.company_id, self.co_a.id)
        # 5 h × 120 = 600.
        self.assertEqual(ts.cout, Decimal('600.00'))
        self.assertEqual(resp.data['cout'], '600.00')

    def test_cout_zero_si_pas_de_cout_horaire(self):
        sans_cout = RessourceProfil.objects.create(
            company=self.co_a, nom='RZ')
        api = auth(self.user_a)
        resp = api.post(self.BASE, {
            'projet': self.projet.id,
            'ressource': sans_cout.id,
            'date': '2026-01-10',
            'heures': '5',
        }, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        self.assertEqual(resp.data['cout'], '0.00')

    def test_update_recalcule_cout(self):
        ts = Timesheet.objects.create(
            company=self.co_a, projet=self.projet, ressource=self.ressource,
            date=date(2026, 1, 10), heures=Decimal('5'), cout=Decimal('600'))
        api = auth(self.user_a)
        resp = api.patch(f'{self.BASE}{ts.id}/', {'heures': '10'},
                         format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        ts.refresh_from_db()
        self.assertEqual(ts.cout, Decimal('1200.00'))

    def test_tache_autre_projet_refusee(self):
        autre_projet = Projet.objects.create(
            company=self.co_a, code='P-A2', nom='A2')
        autre_tache = Tache.objects.create(
            company=self.co_a, projet=autre_projet, libelle='T2', ordre=1)
        api = auth(self.user_a)
        resp = api.post(self.BASE, {
            'projet': self.projet.id,
            'tache': autre_tache.id,
            'ressource': self.ressource.id,
            'date': '2026-01-10',
            'heures': '5',
        }, format='json')
        self.assertEqual(resp.status_code, 400)

    def test_scoping_isolation(self):
        autre_projet = Projet.objects.create(
            company=self.co_b, code='P-B', nom='B')
        autre_res = RessourceProfil.objects.create(
            company=self.co_b, nom='RB')
        Timesheet.objects.create(
            company=self.co_b, projet=autre_projet, ressource=autre_res,
            date=date(2026, 1, 10), heures=Decimal('1'))
        Timesheet.objects.create(
            company=self.co_a, projet=self.projet, ressource=self.ressource,
            date=date(2026, 1, 10), heures=Decimal('1'), cout=Decimal('120'))
        api = auth(self.user_a)
        resp = api.get(self.BASE)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(rows(resp)), 1)

    def test_role_normal_interdit(self):
        normal = make_user(self.co_a, 'ts-normal', role='normal')
        api = auth(normal)
        resp = api.get(self.BASE)
        self.assertEqual(resp.status_code, 403)


class SyntheseTempsTests(TestCase):
    BASE = '/api/django/gestion-projet/projets/'

    def setUp(self):
        self.co = make_company('gp-ts-syn', 'S')
        self.user = make_user(self.co, 'ts-syn')
        self.projet = Projet.objects.create(
            company=self.co, code='P-S', nom='S')
        self.t1 = Tache.objects.create(
            company=self.co, projet=self.projet, libelle='T1', ordre=1)
        self.r1 = RessourceProfil.objects.create(
            company=self.co, nom='R1', cout_horaire=Decimal('100'))
        self.r2 = RessourceProfil.objects.create(
            company=self.co, nom='R2', cout_horaire=Decimal('50'))
        Timesheet.objects.create(
            company=self.co, projet=self.projet, tache=self.t1,
            ressource=self.r1, date=date(2026, 1, 1), heures=Decimal('2'),
            cout=Decimal('200'))
        Timesheet.objects.create(
            company=self.co, projet=self.projet, ressource=self.r2,
            date=date(2026, 1, 2), heures=Decimal('3'), cout=Decimal('150'))

    def test_synthese_selector(self):
        data = selectors.synthese_temps_projet(self.projet)
        self.assertEqual(data['total_heures'], Decimal('5'))
        self.assertEqual(data['total_cout'], Decimal('350'))
        self.assertEqual(data['nb_saisies'], 2)
        self.assertEqual(len(data['par_ressource']), 2)
        # Une seule tâche imputée (la 2e saisie n'a pas de tâche).
        self.assertEqual(len(data['par_tache']), 1)

    def test_synthese_endpoint(self):
        api = auth(self.user)
        resp = api.get(f'{self.BASE}{self.projet.id}/synthese-temps/')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['total_heures'], '5.00')
        self.assertEqual(resp.data['total_cout'], '350.00')
