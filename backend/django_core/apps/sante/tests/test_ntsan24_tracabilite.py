"""NTSAN24 — traçabilité instrument -> patient (M2M léger ActeRealise <->
InstrumentSterilise).

Critère d'acceptation : une requête de traçabilité PAR CYCLE renvoie la
liste des patients concernés en UNE SEULE requête indexée
(``selectors.patients_par_cycle_sterilisation``)."""
import datetime as dt

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.test.utils import CaptureQueriesContext
from django.db import connection
from django.utils import timezone
from rest_framework.test import APIClient

from authentication.models import Company

from apps.sante.models import (
    ActeMedical, Admission, CycleSterilisation, InstrumentSterilise, Patient,
    Praticien,
)
from apps.sante.selectors import patients_par_cycle_sterilisation
from apps.sante.services import realiser_acte

User = get_user_model()
DATE_REALISATION = timezone.make_aware(dt.datetime(2026, 8, 12, 9, 0))
DATE_CYCLE = timezone.make_aware(dt.datetime(2026, 8, 12, 7, 30))


class NTSAN24FixtureMixin:
    def setUp(self):
        super().setUp()
        self.company, _ = Company.objects.get_or_create(
            slug='sante-tracabilite-co', defaults={'nom': 'Clinique Traçabilité'})
        self.user = User.objects.create_user(
            username='admin@sante-tracabilite.ma', password='x',
            company=self.company)
        self.client = APIClient()
        self.client.force_authenticate(self.user)

        self.praticien = Praticien.objects.create(
            company=self.company, nom='Dr. Naciri')
        self.acte_medical = ActeMedical.objects.create(
            company=self.company, libelle='Détartrage', code_ngap='D1',
            tarif_base_ttc='150.00')

        self.cycle = CycleSterilisation.objects.create(
            company=self.company, numero_cycle='CY-100', date_cycle=DATE_CYCLE)
        self.instrument1 = InstrumentSterilise.objects.create(
            company=self.company, cycle=self.cycle, instrument_ref='DAV-1')
        self.instrument2 = InstrumentSterilise.objects.create(
            company=self.company, cycle=self.cycle, instrument_ref='DAV-2')

        autre_cycle = CycleSterilisation.objects.create(
            company=self.company, numero_cycle='CY-101', date_cycle=DATE_CYCLE)
        self.instrument_autre_cycle = InstrumentSterilise.objects.create(
            company=self.company, cycle=autre_cycle, instrument_ref='DAV-9')

        self.patient1 = Patient.objects.create(
            company=self.company, nom='Bennani', prenom='Yasmine')
        self.patient2 = Patient.objects.create(
            company=self.company, nom='Alaoui', prenom='Karim')
        self.patient_sans_instrument = Patient.objects.create(
            company=self.company, nom='Fassi', prenom='Sara')

        self.admission1 = Admission.objects.create(
            company=self.company, patient=self.patient1,
            praticien=self.praticien, date_admission=DATE_REALISATION)
        self.admission2 = Admission.objects.create(
            company=self.company, patient=self.patient2,
            praticien=self.praticien, date_admission=DATE_REALISATION)


class NTSAN24ModeleTests(NTSAN24FixtureMixin, TestCase):
    def test_acte_peut_referencer_plusieurs_instruments(self):
        acte = realiser_acte(
            admission=self.admission1, patient=self.patient1,
            praticien=self.praticien, acte=self.acte_medical,
            date_realisation=DATE_REALISATION)
        acte.instruments_utilises.set([self.instrument1, self.instrument2])
        self.assertEqual(acte.instruments_utilises.count(), 2)
        self.assertEqual(self.instrument1.actes_realises.count(), 1)

    def test_api_pose_les_instruments_a_la_creation(self):
        resp = self.client.post(
            '/api/django/sante/actes-realises/',
            {'admission': self.admission1.id, 'patient': self.patient1.id,
             'praticien': self.praticien.id, 'acte': self.acte_medical.id,
             'date_realisation': DATE_REALISATION.isoformat(),
             'instruments_utilises': [self.instrument1.id]}, format='json')
        self.assertEqual(resp.status_code, 201)
        from apps.sante.models import ActeRealise

        acte = ActeRealise.objects.get(pk=resp.data['id'])
        self.assertEqual(
            list(acte.instruments_utilises.all()), [self.instrument1])

    def test_instrument_dune_autre_societe_refuse(self):
        autre, _ = Company.objects.get_or_create(
            slug='sante-tracabilite-autre',
            defaults={'nom': 'Clinique Traçabilité Autre'})
        cycle_autre = CycleSterilisation.objects.create(
            company=autre, numero_cycle='CY-200', date_cycle=DATE_CYCLE)
        instrument_autre = InstrumentSterilise.objects.create(
            company=autre, cycle=cycle_autre, instrument_ref='EXT-1')

        resp = self.client.post(
            '/api/django/sante/actes-realises/',
            {'admission': self.admission1.id, 'patient': self.patient1.id,
             'praticien': self.praticien.id, 'acte': self.acte_medical.id,
             'date_realisation': DATE_REALISATION.isoformat(),
             'instruments_utilises': [instrument_autre.id]}, format='json')
        self.assertEqual(resp.status_code, 400)


class NTSAN24TracabiliteSelecteurTests(NTSAN24FixtureMixin, TestCase):
    def _rattacher(self, patient, admission, instruments):
        acte = realiser_acte(
            admission=admission, patient=patient, praticien=self.praticien,
            acte=self.acte_medical, date_realisation=DATE_REALISATION)
        acte.instruments_utilises.set(instruments)
        return acte

    def test_rappel_sanitaire_retrouve_tous_les_patients_du_cycle(self):
        self._rattacher(self.patient1, self.admission1, [self.instrument1])
        self._rattacher(self.patient2, self.admission2, [self.instrument2])

        patients = patients_par_cycle_sterilisation(self.company, self.cycle)
        ids = {p.id for p in patients}
        self.assertEqual(ids, {self.patient1.id, self.patient2.id})
        self.assertNotIn(self.patient_sans_instrument.id, ids)

    def test_meme_patient_deux_instruments_du_cycle_pas_de_doublon(self):
        self._rattacher(
            self.patient1, self.admission1,
            [self.instrument1, self.instrument2])

        patients = patients_par_cycle_sterilisation(self.company, self.cycle)
        self.assertEqual([p.id for p in patients], [self.patient1.id])

    def test_instrument_dun_autre_cycle_jamais_confondu(self):
        self._rattacher(
            self.patient1, self.admission1, [self.instrument_autre_cycle])

        patients = patients_par_cycle_sterilisation(self.company, self.cycle)
        self.assertEqual(patients, [])

    def test_une_seule_requete_indexee(self):
        """Critère d'acceptation : UNE SEULE requête SQL pour la
        traçabilité par cycle."""
        self._rattacher(self.patient1, self.admission1, [self.instrument1])
        self._rattacher(self.patient2, self.admission2, [self.instrument2])

        with CaptureQueriesContext(connection) as ctx:
            patients_par_cycle_sterilisation(self.company, self.cycle)
        self.assertEqual(len(ctx.captured_queries), 1)

    def test_endpoint_patients_concernes(self):
        self._rattacher(self.patient1, self.admission1, [self.instrument1])

        resp = self.client.get(
            f'/api/django/sante/cycles-sterilisation/{self.cycle.id}/'
            'patients-concernes/')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['count'], 1)
        self.assertEqual(resp.data['results'][0]['id'], self.patient1.id)
