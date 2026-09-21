"""Tests du workflow d'approbation des feuilles de temps (XPRJ1).

Couvre : cycle brouillon→soumise→approuvee/rejetee (transitions illégales
→ 400), ``saisi_par``/``approuve_par``/``date_approbation`` posés côté serveur,
isolation tenant, verrouillage de période (création/édition/suppression
refusées dans un mois verrouillé, sauf admin), édition/suppression d'une
timesheet approuvée refusée.
"""
from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company

from apps.gestion_projet import services
from apps.gestion_projet.models import (
    PeriodeVerrouilleeTemps,
    Projet,
    RessourceProfil,
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


class TimesheetTransitionServiceTests(TestCase):
    def setUp(self):
        self.co = make_company('gp-wf-svc', 'S')
        self.projet = Projet.objects.create(company=self.co, code='P', nom='P')
        self.res = RessourceProfil.objects.create(company=self.co, nom='R')
        self.ts = Timesheet.objects.create(
            company=self.co, projet=self.projet, ressource=self.res,
            date=date(2026, 2, 1), heures=Decimal('5'))

    def test_soumettre_depuis_brouillon(self):
        services.soumettre_timesheet(self.ts)
        self.assertEqual(self.ts.statut, Timesheet.Statut.SOUMISE)

    def test_soumettre_deux_fois_refuse(self):
        services.soumettre_timesheet(self.ts)
        with self.assertRaises(services.TimesheetTransitionError):
            services.soumettre_timesheet(self.ts)

    def test_approuver_depuis_soumise(self):
        approbateur = make_user(self.co, 'appro')
        services.soumettre_timesheet(self.ts)
        services.approuver_timesheet(self.ts, approbateur)
        self.assertEqual(self.ts.statut, Timesheet.Statut.APPROUVEE)
        self.assertEqual(self.ts.approuve_par_id, approbateur.id)
        self.assertIsNotNone(self.ts.date_approbation)

    def test_approuver_depuis_brouillon_refuse(self):
        approbateur = make_user(self.co, 'appro2')
        with self.assertRaises(services.TimesheetTransitionError):
            services.approuver_timesheet(self.ts, approbateur)

    def test_rejeter_depuis_soumise(self):
        approbateur = make_user(self.co, 'appro3')
        services.soumettre_timesheet(self.ts)
        services.rejeter_timesheet(self.ts, approbateur, motif='incomplet')
        self.assertEqual(self.ts.statut, Timesheet.Statut.REJETEE)
        self.assertEqual(self.ts.motif_rejet, 'incomplet')

    def test_periode_verrouillee_bloque(self):
        PeriodeVerrouilleeTemps.objects.create(
            company=self.co, mois=date(2026, 2, 1))
        with self.assertRaises(services.PeriodeVerrouilleeError):
            services.verifier_periode_ouverte(self.co, date(2026, 2, 15))

    def test_periode_verrouillee_admin_contourne(self):
        PeriodeVerrouilleeTemps.objects.create(
            company=self.co, mois=date(2026, 2, 1))
        # Ne lève pas.
        services.verifier_periode_ouverte(
            self.co, date(2026, 2, 15), admin=True)


class TimesheetWorkflowApiTests(TestCase):
    BASE = '/api/django/gestion-projet/timesheets/'

    def setUp(self):
        self.co_a = make_company('gp-wf-a', 'A')
        self.co_b = make_company('gp-wf-b', 'B')
        self.user_a = make_user(self.co_a, 'wf-a')
        self.admin_a = make_user(self.co_a, 'wf-admin', role='admin')
        self.projet = Projet.objects.create(
            company=self.co_a, code='P-WF', nom='A')
        self.res = RessourceProfil.objects.create(company=self.co_a, nom='R')

    def _create_ts(self, api, date_str='2026-03-10'):
        resp = api.post(self.BASE, {
            'projet': self.projet.id,
            'ressource': self.res.id,
            'date': date_str,
            'heures': '4',
        }, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        return resp.data

    def test_creation_pose_saisi_par(self):
        api = auth(self.user_a)
        data = self._create_ts(api)
        ts = Timesheet.objects.get(id=data['id'])
        self.assertEqual(ts.saisi_par_id, self.user_a.id)
        self.assertEqual(ts.statut, Timesheet.Statut.BROUILLON)

    def test_cycle_soumission_approbation(self):
        api = auth(self.user_a)
        data = self._create_ts(api)
        ts_id = data['id']

        resp = api.post(f'{self.BASE}{ts_id}/soumettre/')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(resp.data['statut'], 'soumise')

        resp = api.post(f'{self.BASE}{ts_id}/approuver/')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(resp.data['statut'], 'approuvee')
        self.assertEqual(resp.data['approuve_par'], self.user_a.id)

    def test_transition_illegale_400(self):
        api = auth(self.user_a)
        data = self._create_ts(api)
        ts_id = data['id']
        # Approuver directement depuis brouillon (sans soumettre) → 400.
        resp = api.post(f'{self.BASE}{ts_id}/approuver/')
        self.assertEqual(resp.status_code, 400)

    def test_rejet_avec_motif(self):
        api = auth(self.user_a)
        data = self._create_ts(api)
        ts_id = data['id']
        api.post(f'{self.BASE}{ts_id}/soumettre/')
        resp = api.post(
            f'{self.BASE}{ts_id}/rejeter/', {'motif': 'heures fausses'},
            format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(resp.data['statut'], 'rejetee')
        self.assertEqual(resp.data['motif_rejet'], 'heures fausses')

    def test_edition_timesheet_approuvee_refusee(self):
        api = auth(self.user_a)
        data = self._create_ts(api)
        ts_id = data['id']
        api.post(f'{self.BASE}{ts_id}/soumettre/')
        api.post(f'{self.BASE}{ts_id}/approuver/')
        resp = api.patch(f'{self.BASE}{ts_id}/', {'heures': '99'},
                         format='json')
        self.assertEqual(resp.status_code, 400)

    def test_creation_dans_periode_verrouillee_refusee(self):
        PeriodeVerrouilleeTemps.objects.create(
            company=self.co_a, mois=date(2026, 3, 1))
        api = auth(self.user_a)
        resp = api.post(self.BASE, {
            'projet': self.projet.id,
            'ressource': self.res.id,
            'date': '2026-03-15',
            'heures': '4',
        }, format='json')
        self.assertEqual(resp.status_code, 400)

    def test_creation_dans_periode_verrouillee_admin_autorisee(self):
        PeriodeVerrouilleeTemps.objects.create(
            company=self.co_a, mois=date(2026, 3, 1))
        api = auth(self.admin_a)
        resp = api.post(self.BASE, {
            'projet': self.projet.id,
            'ressource': self.res.id,
            'date': '2026-03-15',
            'heures': '4',
        }, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)

    def test_suppression_dans_periode_verrouillee_refusee(self):
        api = auth(self.user_a)
        data = self._create_ts(api, date_str='2026-04-05')
        ts_id = data['id']
        PeriodeVerrouilleeTemps.objects.create(
            company=self.co_a, mois=date(2026, 4, 1))
        resp = api.delete(f'{self.BASE}{ts_id}/')
        self.assertEqual(resp.status_code, 400)

    def test_isolation_tenant_transitions(self):
        user_b = make_user(self.co_b, 'wf-b')
        api_a = auth(self.user_a)
        data = self._create_ts(api_a)
        ts_id = data['id']
        api_b = auth(user_b)
        resp = api_b.post(f'{self.BASE}{ts_id}/soumettre/')
        self.assertEqual(resp.status_code, 404)


class PeriodeVerrouilleeTempsApiTests(TestCase):
    BASE = '/api/django/gestion-projet/periodes-verrouillees-temps/'

    def setUp(self):
        self.co = make_company('gp-wf-lock', 'L')
        self.user = make_user(self.co, 'lock-user')

    def test_creation_pose_verrouille_par(self):
        api = auth(self.user)
        resp = api.post(self.BASE, {'mois': '2026-05-01'}, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        self.assertEqual(resp.data['verrouille_par'], self.user.id)
