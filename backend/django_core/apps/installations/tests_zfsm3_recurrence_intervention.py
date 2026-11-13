"""
ZFSM3 — Interventions récurrentes autonomes (sans contrat de maintenance).

Couvre :
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

from apps.crm.models import Client
from apps.installations.models import (
    Installation, Intervention, RecurrenceIntervention,
)
from apps.installations.services import generer_interventions_recurrentes

User = get_user_model()
_seq = itertools.count(1)


def make_company(slug=None, nom=None):
    from authentication.models import Company
    n = next(_seq)
    company, _ = Company.objects.get_or_create(
        slug=slug or f'zfsm3-co-{n}', defaults={'nom': nom or f'ZFSM3 Co {n}'})
    return company


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

    def test_societe_en_echec_consignee_et_suivantes_generees(self):
        # ACEL45 — l'échec d'une société est consigné, les autres générées.
        from unittest import mock

        from apps.installations import services
        from apps.installations.tasks import generer_interventions_recurrentes_task
        autre = make_company()
        inst_b = make_installation(autre)
        RecurrenceIntervention.objects.create(
            company=autre, installation=inst_b, type_intervention='controle',
            regle='mensuelle', prochaine_echeance=date.today())
        reel = services.generer_interventions_recurrentes

        def generer(company, *args, **kwargs):
            if company.id == self.company.id:
                raise RuntimeError('panne société A')
            return reel(company, *args, **kwargs)

        with mock.patch.object(services, 'generer_interventions_recurrentes', side_effect=generer):
            with mock.patch('apps.reporting.journal_problemes.consigner_echec_tache') as consigner:
                self.assertEqual(generer_interventions_recurrentes_task(), 1)
        consigner.assert_called_once()
        self.assertEqual(consigner.call_args.args[0],
                         'installations.generer_interventions_recurrentes')
        self.assertEqual(Intervention.objects.filter(installation=inst_b).count(), 1)

    def test_recurrence_creee_par_api_garde_le_31(self):
        # ACEL46 — créée depuis la fiche chantier, la récurrence du 31 revient
        # au 31 après février (avant : route 404 ; 31/01, 28/02, 28/03).
        import json
        from pathlib import Path

        def lignes(rep):
            return rep.data['results'] if isinstance(rep.data, dict) else rep.data

        api = APIClient()
        api.force_authenticate(self.user)
        url = '/api/django/installations/recurrences-intervention/'
        corps = {'installation': self.inst.id, 'regle': 'mensuelle', 'intervalle': 1,
                 'prochaine_echeance': '2026-01-31', 'type_intervention': 'nettoyage'}
        rep = api.post(url, corps, format='json')
        self.assertEqual(rep.status_code, 201, rep.content)
        self.assertEqual(rep.data['jour_ancrage'], 31)
        generer_interventions_recurrentes(self.company, aujourd_hui=date(2026, 3, 31))
        dates = sorted(Intervention.objects.filter(
            installation=self.inst).values_list('date_prevue', flat=True))
        self.assertEqual(dates, [date(2026, 1, 31), date(2026, 2, 28), date(2026, 3, 31)])
        recs = lignes(api.get(url, {'installation': self.inst.id}))
        self.assertEqual([r['prochaine_echeance'] for r in recs], ['2026-04-30'])
        # Contrat partagé (PACT10) : la réponse porte exactement les clés de l'exemple.
        contrat = json.loads((Path(__file__).parent / 'contract_samples'
                              / 'recurrences_intervention.json').read_text(encoding='utf-8'))
        self.assertEqual(set(contrat['exemple']), set(recs[0]))
        # Autre chantier / autre société : rien ne fuit (404).
        autre_inst = make_installation(self.company)
        self.assertEqual(lignes(api.get(url, {'installation': autre_inst.id})), [])
        api_b = APIClient()
        api_b.force_authenticate(make_user(make_company()))
        self.assertEqual(api_b.get(f"{url}{recs[0]['id']}/").status_code, 404)
        self.assertEqual(api_b.post(url, corps, format='json').status_code, 404)
