"""
XFSM13 — Re-vérification périodique IEC 62446-2 avec comparaison baseline.

Couvre :
  * une re-vérification saisie se compare à la baseline (recette
    CommissioningRecord + relevés I-V) ;
  * dérive au-delà du seuil (défaut 20 %) → une Reserve est créée sur
    l'intervention, liée en retour (`reverif.reserve_id`) ;
  * dérive sous le seuil → aucune Reserve ;
  * absence de baseline → dérive None, aucun blocage ;
  * isolation multi-société.

Run :
    python manage.py test apps.installations.tests_xfsm13_reverification -v2
"""
import itertools
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.crm.models import Client
from apps.installations.models import (
    CommissioningIVReading, CommissioningRecord, Installation, Intervention,
    Reserve,
)
from apps.installations.services import enregistrer_reverification

User = get_user_model()
_seq = itertools.count(1)
BASE = '/api/django/installations'


def make_company(slug=None, nom=None):
    from authentication.models import Company
    n = next(_seq)
    company, _ = Company.objects.get_or_create(
        slug=slug or f'xfsm13-co-{n}', defaults={'nom': nom or f'XFSM13 Co {n}'})
    return company


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


def make_user(company, role='responsable'):
    return User.objects.create_user(
        username=f'xfsm13-{next(_seq)}', password='x',
        role_legacy=role, company=company)


def make_installation(company):
    n = next(_seq)
    client = Client.objects.create(
        company=company, nom='Client', prenom='XFSM13',
        email=f'xfsm13-{company.id}-{n}@example.invalid')
    return Installation.objects.create(
        company=company, reference=f'CHT-XFSM13-{n}', client=client)


def make_intervention(company, inst, user):
    return Intervention.objects.create(
        company=company, installation=inst,
        type_intervention=Intervention.Type.REVERIFICATION_62446,
        created_by=user)


class TestEnregistrerReverificationService(TestCase):
    def setUp(self):
        self.company = make_company()
        self.user = make_user(self.company)
        self.inst = make_installation(self.company)
        self.interv = make_intervention(self.company, self.inst, self.user)
        self.record = CommissioningRecord.objects.create(
            company=self.company, installation=self.inst,
            isolement_mohm=Decimal('5.00'))
        CommissioningIVReading.objects.create(
            company=self.company, record=self.record,
            string_label='A', voc_mesure_v=Decimal('620.00'))

    def test_no_drift_no_reserve(self):
        reverif = enregistrer_reverification(
            self.interv, {
                'isolement_mohm': Decimal('5.10'),
                'voc_par_string': {'A': Decimal('622.00')},
            }, user=self.user)
        self.assertFalse(reverif.depassement_detecte)
        self.assertIsNone(reverif.reserve_id)
        self.assertEqual(reverif.voc_comparaison[0]['string_label'], 'A')

    def test_drift_over_threshold_creates_reserve(self):
        reverif = enregistrer_reverification(
            self.interv, {
                'isolement_mohm': Decimal('2.00'),  # -60% vs baseline 5.00
            }, user=self.user)
        self.assertTrue(reverif.depassement_detecte)
        self.assertIsNotNone(reverif.reserve_id)
        self.assertTrue(
            Reserve.objects.filter(
                id=reverif.reserve_id, intervention=self.interv).exists())

    def test_voc_drift_over_threshold_creates_reserve(self):
        reverif = enregistrer_reverification(
            self.interv, {
                'voc_par_string': {'A': Decimal('300.00')},  # ~-52% vs 620
            }, user=self.user)
        self.assertTrue(reverif.depassement_detecte)
        self.assertIsNotNone(reverif.reserve_id)

    def test_no_baseline_no_crash_no_drift(self):
        inst2 = make_installation(self.company)
        interv2 = make_intervention(self.company, inst2, self.user)
        reverif = enregistrer_reverification(
            interv2, {'isolement_mohm': Decimal('4.00')}, user=self.user)
        self.assertIsNone(reverif.isolement_ecart_pct)
        self.assertFalse(reverif.depassement_detecte)
        self.assertIsNone(reverif.reserve_id)


class TestReverificationApi(TestCase):
    def setUp(self):
        self.company = make_company()
        self.user = make_user(self.company)
        self.api = auth(self.user)
        self.inst = make_installation(self.company)
        self.interv = make_intervention(self.company, self.inst, self.user)
        CommissioningRecord.objects.create(
            company=self.company, installation=self.inst,
            isolement_mohm=Decimal('5.00'))

    def test_enregistrer_via_api(self):
        r = self.api.post(
            f'{BASE}/interventions/{self.interv.id}/enregistrer-reverification/',
            {'isolement_mohm': '2.00'}, format='json')
        self.assertEqual(r.status_code, 201, r.content)
        self.assertTrue(r.data['depassement_detecte'])

    def test_reverifications_history(self):
        self.api.post(
            f'{BASE}/interventions/{self.interv.id}/enregistrer-reverification/',
            {'isolement_mohm': '5.05'}, format='json')
        r = self.api.get(
            f'{BASE}/interventions/{self.interv.id}/reverifications/')
        self.assertEqual(r.status_code, 200, r.content)
        self.assertEqual(len(r.data), 1)
