"""
XFSM5 — Fenêtres de RDV promises + taux de ponctualité.

Couvre :
  * `fenetre_debut`/`fenetre_fin` saisissables (nullable, additif) ;
  * `arrivee_dans_fenetre` calculé au check-in GPS F6 (True dans la fenêtre,
    False hors fenêtre, None sans fenêtre promise) ;
  * KPI « taux d'arrivée à l'heure » correct sur des données de test.

Run :
    python manage.py test apps.installations.tests_xfsm5_fenetre_rdv -v2
"""
import itertools
from datetime import date, timedelta
from decimal import Decimal
from unittest import mock

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.crm.models import Client, Lead
from apps.ventes.models import Devis
from apps.installations.models import Intervention
from apps.installations.services import create_installation_from_devis

User = get_user_model()
_seq = itertools.count(1)
BASE = '/api/django/installations'


def make_company(slug=None, nom=None):
    from authentication.models import Company
    n = next(_seq)
    company, _ = Company.objects.get_or_create(
        slug=slug or f'xfsm5-co-{n}', defaults={'nom': nom or f'XFSM5 Co {n}'})
    return company


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


def make_user(company, role='responsable', username=None):
    return User.objects.create_user(
        username=username or f'xfsm5-{next(_seq)}', password='x',
        role_legacy=role, company=company)


def make_chantier(company, user):
    n = next(_seq)
    client = Client.objects.create(
        company=company, nom='Site', prenom='Client',
        email=f'xfsm5-{company.id}-{n}@example.invalid')
    lead = Lead.objects.create(
        company=company, nom='Site', prenom='Client', stage='SIGNED',
        type_installation='residentiel')
    devis = Devis.objects.create(
        company=company, reference=f'DEV-XFSM5-{company.id}-{n}', client=client,
        lead=lead, statut=Devis.Statut.ACCEPTE, taux_tva=Decimal('20'),
        mode_installation='residentiel')
    inst, _ = create_installation_from_devis(devis, user, company)
    return inst


class TestFenetreRdvChamp(TestCase):
    def setUp(self):
        self.company = make_company()
        self.user = make_user(self.company)
        self.api = auth(self.user)
        self.inst = make_chantier(self.company, self.user)

    def test_fenetre_saisissable(self):
        resp = self.api.post(f'{BASE}/interventions/', {
            'installation': self.inst.id, 'type_intervention': 'pose',
            'fenetre_debut': '08:00', 'fenetre_fin': '10:00',
        }, format='json')
        self.assertEqual(resp.status_code, 201, resp.content)
        self.assertEqual(resp.data['fenetre_debut'], '08:00:00')
        self.assertEqual(resp.data['fenetre_fin'], '10:00:00')

    def test_sans_fenetre_arrivee_dans_fenetre_reste_none(self):
        interv = Intervention.objects.create(
            company=self.company, installation=self.inst,
            type_intervention='pose', created_by=self.user)
        resp = self.api.post(
            f'{BASE}/interventions/{interv.id}/checkin/',
            {'lat': 33.5, 'lng': -7.5}, format='json')
        self.assertEqual(resp.status_code, 200, resp.content)
        self.assertIsNone(resp.data['arrivee_dans_fenetre'])


class TestPonctualiteCheckin(TestCase):
    def setUp(self):
        self.company = make_company()
        self.user = make_user(self.company)
        self.api = auth(self.user)
        self.inst = make_chantier(self.company, self.user)

    def _checkin_at(self, interv, hour, minute):
        fixed = timezone.make_aware(
            timezone.datetime(2026, 8, 1, hour, minute))
        with mock.patch(
                'apps.installations.views.intervention.timezone.now',
                return_value=fixed):
            return self.api.post(
                f'{BASE}/interventions/{interv.id}/checkin/',
                {'lat': 33.5, 'lng': -7.5}, format='json')

    def test_arrivee_dans_fenetre_true(self):
        interv = Intervention.objects.create(
            company=self.company, installation=self.inst,
            type_intervention='pose', created_by=self.user, technicien=self.user,
            fenetre_debut='08:00', fenetre_fin='10:00')
        resp = self._checkin_at(interv, 9, 0)
        self.assertEqual(resp.status_code, 200, resp.content)
        self.assertTrue(resp.data['arrivee_dans_fenetre'])

    def test_arrivee_hors_fenetre_false(self):
        interv = Intervention.objects.create(
            company=self.company, installation=self.inst,
            type_intervention='pose', created_by=self.user, technicien=self.user,
            fenetre_debut='08:00', fenetre_fin='10:00')
        resp = self._checkin_at(interv, 11, 30)
        self.assertEqual(resp.status_code, 200, resp.content)
        self.assertFalse(resp.data['arrivee_dans_fenetre'])


class TestKpiTauxPonctualite(TestCase):
    def setUp(self):
        self.company = make_company()
        self.user = make_user(self.company)
        self.api = auth(self.user)
        self.inst = make_chantier(self.company, self.user)

    def test_taux_correct_sur_donnees_de_test(self):
        today = date.today()
        Intervention.objects.create(
            company=self.company, installation=self.inst,
            type_intervention='pose', created_by=self.user, technicien=self.user,
            fenetre_debut='08:00', fenetre_fin='10:00',
            arrivee_site_le=timezone.now(), arrivee_dans_fenetre=True)
        Intervention.objects.create(
            company=self.company, installation=self.inst,
            type_intervention='pose', created_by=self.user, technicien=self.user,
            fenetre_debut='08:00', fenetre_fin='10:00',
            arrivee_site_le=timezone.now(), arrivee_dans_fenetre=False)
        # non mesurable (pas de fenêtre) — exclu du calcul.
        Intervention.objects.create(
            company=self.company, installation=self.inst,
            type_intervention='pose', created_by=self.user, technicien=self.user,
            arrivee_site_le=timezone.now())

        resp = self.api.get(
            f'{BASE}/interventions/taux-ponctualite/'
            f'?debut={today.isoformat()}&fin={today.isoformat()}')
        self.assertEqual(resp.status_code, 200, resp.content)
        self.assertEqual(resp.data['nb_mesurees'], 2)
        self.assertEqual(resp.data['nb_a_lheure'], 1)
        self.assertEqual(resp.data['taux_pct'], 50.0)

    def test_taux_none_sans_donnees(self):
        futur = date.today() + timedelta(days=30)
        resp = self.api.get(
            f'{BASE}/interventions/taux-ponctualite/'
            f'?debut={futur.isoformat()}&fin={futur.isoformat()}')
        self.assertEqual(resp.status_code, 200, resp.content)
        self.assertEqual(resp.data['nb_mesurees'], 0)
        self.assertIsNone(resp.data['taux_pct'])

    def test_filtre_par_technicien(self):
        autre = make_user(self.company, username='xfsm5-autre-tech')
        today = date.today()
        Intervention.objects.create(
            company=self.company, installation=self.inst,
            type_intervention='pose', created_by=self.user, technicien=self.user,
            fenetre_debut='08:00', fenetre_fin='10:00',
            arrivee_site_le=timezone.now(), arrivee_dans_fenetre=True)
        Intervention.objects.create(
            company=self.company, installation=self.inst,
            type_intervention='pose', created_by=self.user, technicien=autre,
            fenetre_debut='08:00', fenetre_fin='10:00',
            arrivee_site_le=timezone.now(), arrivee_dans_fenetre=False)
        resp = self.api.get(
            f'{BASE}/interventions/taux-ponctualite/'
            f'?debut={today.isoformat()}&fin={today.isoformat()}'
            f'&technicien={self.user.id}')
        self.assertEqual(resp.status_code, 200, resp.content)
        self.assertEqual(resp.data['nb_mesurees'], 1)
        self.assertEqual(resp.data['taux_pct'], 100.0)
