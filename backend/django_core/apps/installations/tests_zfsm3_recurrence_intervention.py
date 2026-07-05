"""
ZFSM3 — Interventions récurrentes autonomes (sans contrat de maintenance).

Couvre :
  * CRUD `recurrences-intervention/` (company-scopé, installation validée
    tenant) ;
  * `manage.py generer_interventions_recurrentes` (service direct) crée UNE
    intervention par échéance passée, jamais deux pour la même échéance
    (idempotent, re-run le même jour) ;
  * la récurrence avance `prochaine_echeance` d'un pas de la règle
    (trimestrielle testée explicitement) ;
  * la fin de récurrence (`date_fin` / `nb_occurrences`) désactive la
    récurrence sans générer au-delà ;
  * un chantier annulé (YSERV6) désactive la récurrence sans créer de
    nouvelle intervention ;
  * isolation multi-société.

Run :
    python manage.py test apps.installations.tests_zfsm3_recurrence_intervention -v2
"""
import itertools
from datetime import date, timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.crm.models import Client
from apps.installations.models import (
    Installation, Intervention, RecurrenceIntervention,
)
from apps.installations.services import generer_interventions_recurrentes

User = get_user_model()
_seq = itertools.count(1)
BASE = '/api/django/installations'


def make_company(slug=None, nom=None):
    from authentication.models import Company
    n = next(_seq)
    company, _ = Company.objects.get_or_create(
        slug=slug or f'zfsm3-co-{n}', defaults={'nom': nom or f'ZFSM3 Co {n}'})
    return company


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


def make_user(company, role='responsable'):
    return User.objects.create_user(
        username=f'zfsm3-{next(_seq)}', password='x',
        role_legacy=role, company=company)


def make_installation(company):
    n = next(_seq)
    client = Client.objects.create(
        company=company, nom='Client', prenom='ZFSM3',
        email=f'zfsm3-{company.id}-{n}@example.invalid')
    return Installation.objects.create(
        company=company, reference=f'CHT-ZFSM3-{n}', client=client)


class TestRecurrenceInterventionCRUD(TestCase):
    def setUp(self):
        self.company = make_company()
        self.user = make_user(self.company)
        self.api = auth(self.user)
        self.inst = make_installation(self.company)

    def test_create_recurrence(self):
        r = self.api.post(
            f'{BASE}/recurrences-intervention/',
            {'installation': self.inst.id, 'type_intervention': 'controle',
             'regle': 'trimestrielle', 'intervalle': 1,
             'prochaine_echeance': str(date.today())}, format='json')
        self.assertEqual(r.status_code, 201, r.content)
        self.assertTrue(
            RecurrenceIntervention.objects.filter(
                company=self.company, installation=self.inst).exists())

    def test_rejects_foreign_company_installation(self):
        other = make_company()
        other_inst = make_installation(other)
        r = self.api.post(
            f'{BASE}/recurrences-intervention/',
            {'installation': other_inst.id, 'type_intervention': 'controle',
             'regle': 'annuelle', 'prochaine_echeance': str(date.today())},
            format='json')
        self.assertEqual(r.status_code, 400)

    def test_multi_tenant_isolation(self):
        RecurrenceIntervention.objects.create(
            company=self.company, installation=self.inst,
            type_intervention='controle', regle='annuelle',
            prochaine_echeance=date.today())
        other = make_company()
        other_inst = make_installation(other)
        RecurrenceIntervention.objects.create(
            company=other, installation=other_inst,
            type_intervention='controle', regle='annuelle',
            prochaine_echeance=date.today())
        r = self.api.get(f'{BASE}/recurrences-intervention/')
        self.assertEqual(len(r.data), 1)


class TestGenererInterventionsRecurrentes(TestCase):
    def setUp(self):
        self.company = make_company()
        self.user = make_user(self.company)
        self.inst = make_installation(self.company)

    def test_generates_one_intervention_at_echeance(self):
        rec = RecurrenceIntervention.objects.create(
            company=self.company, installation=self.inst,
            type_intervention='controle', regle='trimestrielle',
            intervalle=1, prochaine_echeance=date.today())
        crees = generer_interventions_recurrentes(self.company)
        self.assertEqual(len(crees), 1)
        self.assertEqual(crees[0].installation_id, self.inst.id)
        self.assertEqual(crees[0].type_intervention, 'controle')
        rec.refresh_from_db()
        self.assertEqual(rec.nb_generees, 1)
        self.assertGreater(rec.prochaine_echeance, date.today())

    def test_idempotent_rerun_same_day_creates_no_duplicate(self):
        RecurrenceIntervention.objects.create(
            company=self.company, installation=self.inst,
            type_intervention='controle', regle='mensuelle',
            prochaine_echeance=date.today())
        crees1 = generer_interventions_recurrentes(self.company)
        crees2 = generer_interventions_recurrentes(self.company)
        self.assertEqual(len(crees1), 1)
        self.assertEqual(len(crees2), 0)
        self.assertEqual(
            Intervention.objects.filter(installation=self.inst).count(), 1)

    def test_trimestrielle_advances_three_months(self):
        start = date(2026, 1, 15)
        rec = RecurrenceIntervention.objects.create(
            company=self.company, installation=self.inst,
            type_intervention='controle', regle='trimestrielle',
            prochaine_echeance=start)
        generer_interventions_recurrentes(self.company, aujourd_hui=start)
        rec.refresh_from_db()
        self.assertEqual(rec.prochaine_echeance, date(2026, 4, 15))

    def test_date_fin_stops_recurrence(self):
        rec = RecurrenceIntervention.objects.create(
            company=self.company, installation=self.inst,
            type_intervention='controle', regle='mensuelle',
            prochaine_echeance=date(2026, 1, 1),
            date_fin=date(2026, 1, 31))
        generer_interventions_recurrentes(self.company, aujourd_hui=date(2026, 1, 1))
        rec.refresh_from_db()
        self.assertEqual(rec.nb_generees, 1)
        crees = generer_interventions_recurrentes(
            self.company, aujourd_hui=date(2026, 2, 1))
        self.assertEqual(len(crees), 0)
        rec.refresh_from_db()
        self.assertFalse(rec.actif)

    def test_nb_occurrences_stops_recurrence(self):
        rec = RecurrenceIntervention.objects.create(
            company=self.company, installation=self.inst,
            type_intervention='controle', regle='mensuelle',
            prochaine_echeance=date(2026, 1, 1), nb_occurrences=2)
        generer_interventions_recurrentes(self.company, aujourd_hui=date(2026, 3, 1))
        rec.refresh_from_db()
        self.assertEqual(rec.nb_generees, 2)
        self.assertFalse(rec.actif)
        self.assertEqual(
            Intervention.objects.filter(installation=self.inst).count(), 2)

    def test_cancelled_chantier_stops_recurrence(self):
        self.inst.annule = True
        self.inst.save(update_fields=['annule'])
        rec = RecurrenceIntervention.objects.create(
            company=self.company, installation=self.inst,
            type_intervention='controle', regle='mensuelle',
            prochaine_echeance=date.today())
        crees = generer_interventions_recurrentes(self.company)
        self.assertEqual(len(crees), 0)
        rec.refresh_from_db()
        self.assertFalse(rec.actif)

    def test_catches_up_multiple_missed_echeances(self):
        rec = RecurrenceIntervention.objects.create(
            company=self.company, installation=self.inst,
            type_intervention='controle', regle='mensuelle',
            prochaine_echeance=date(2026, 1, 1))
        crees = generer_interventions_recurrentes(
            self.company, aujourd_hui=date(2026, 4, 1))
        # Janvier, février, mars, avril = 4 échéances rattrapées.
        self.assertEqual(len(crees), 4)
        rec.refresh_from_db()
        self.assertEqual(rec.nb_generees, 4)
        self.assertEqual(rec.prochaine_echeance, date(2026, 5, 1))

    def test_inactive_recurrence_untouched(self):
        RecurrenceIntervention.objects.create(
            company=self.company, installation=self.inst,
            type_intervention='controle', regle='mensuelle',
            prochaine_echeance=date.today() - timedelta(days=30),
            actif=False)
        crees = generer_interventions_recurrentes(self.company)
        self.assertEqual(len(crees), 0)
