"""
XFSM12 — Trace d'étalonnage de l'instrument sur le PV de recette.

Couvre :
  * `CommissioningRecord.instrument_id` (string-FK vers `outillage.Outillage`,
    nullable, additif) ;
  * `instrument_etalonnage_expire` calculé correctement (None sans instrument
    ou instrument non soumis à calibration ; True/False selon la date) ;
  * mode par défaut = AVERTISSEMENT non-bloquant (l'enregistrement réussit,
    le drapeau est simplement renvoyé) ;
  * mode strict (`INSTRUMENT_ETALONNAGE_BLOQUANT=True`) REFUSE (400)
    l'enregistrement d'une fiche référençant un instrument expiré ;
  * le nom + n° série de l'instrument sont exposés par l'API (mention
    imprimable sur le PV).

Run :
    python manage.py test apps.installations.tests_xfsm12_instrument_etalonnage -v2
"""
import itertools
from datetime import date, timedelta
from unittest import mock

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.crm.models import Client
from apps.installations.models import CommissioningRecord, Installation
from apps.outillage.models import Outillage

User = get_user_model()
_seq = itertools.count(1)
BASE = '/api/django/installations'


def make_company(slug=None, nom=None):
    from authentication.models import Company
    n = next(_seq)
    company, _ = Company.objects.get_or_create(
        slug=slug or f'xfsm12-co-{n}', defaults={'nom': nom or f'XFSM12 Co {n}'})
    return company


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


def make_user(company, role='responsable'):
    return User.objects.create_user(
        username=f'xfsm12-{next(_seq)}', password='x',
        role_legacy=role, company=company)


def make_installation(company):
    n = next(_seq)
    client = Client.objects.create(
        company=company, nom='Client', prenom='XFSM12',
        email=f'xfsm12-{company.id}-{n}@example.invalid')
    return Installation.objects.create(
        company=company, reference=f'CHT-XFSM12-{n}', client=client)


def make_outillage(company, **kwargs):
    return Outillage.objects.create(
        company=company, nom=kwargs.pop('nom', 'Multimètre Fluke'),
        numero_serie=kwargs.pop('numero_serie', 'SN-MULTI-1'), **kwargs)


class TestInstrumentEtalonnageExpire(TestCase):
    def setUp(self):
        self.company = make_company()
        self.inst = make_installation(self.company)

    def test_none_sans_instrument(self):
        record = CommissioningRecord.objects.create(
            company=self.company, installation=self.inst)
        self.assertIsNone(record.instrument_etalonnage_expire)

    def test_none_si_instrument_non_soumis(self):
        outil = make_outillage(self.company, intervalle_calibration_mois=0)
        record = CommissioningRecord.objects.create(
            company=self.company, installation=self.inst, instrument_id=outil.id)
        self.assertIsNone(record.instrument_etalonnage_expire)

    def test_true_si_jamais_calibre_mais_soumis(self):
        outil = make_outillage(self.company, intervalle_calibration_mois=12)
        record = CommissioningRecord.objects.create(
            company=self.company, installation=self.inst, instrument_id=outil.id)
        self.assertTrue(record.instrument_etalonnage_expire)

    def test_false_si_calibration_a_jour(self):
        outil = make_outillage(
            self.company, intervalle_calibration_mois=12,
            date_derniere_calibration=date.today(),
            date_prochaine_calibration=date.today() + timedelta(days=300))
        record = CommissioningRecord.objects.create(
            company=self.company, installation=self.inst, instrument_id=outil.id)
        self.assertFalse(record.instrument_etalonnage_expire)

    def test_true_si_calibration_expiree(self):
        outil = make_outillage(
            self.company, intervalle_calibration_mois=12,
            date_derniere_calibration=date.today() - timedelta(days=400),
            date_prochaine_calibration=date.today() - timedelta(days=35))
        record = CommissioningRecord.objects.create(
            company=self.company, installation=self.inst, instrument_id=outil.id)
        self.assertTrue(record.instrument_etalonnage_expire)


class TestInstrumentApiPayload(TestCase):
    def setUp(self):
        self.company = make_company()
        self.user = make_user(self.company)
        self.api = auth(self.user)
        self.inst = make_installation(self.company)

    def test_instrument_nom_et_serie_exposes(self):
        outil = make_outillage(
            self.company, nom='Testeur Isolement Megger',
            numero_serie='SN-MEGGER-9', intervalle_calibration_mois=12,
            date_derniere_calibration=date.today(),
            date_prochaine_calibration=date.today() + timedelta(days=300))
        r = self.api.post(f'{BASE}/recettes-commissioning/', {
            'installation': self.inst.id, 'instrument_id': outil.id,
        }, format='json')
        self.assertEqual(r.status_code, 201, r.content)
        self.assertEqual(r.data['instrument_nom'], 'Testeur Isolement Megger')
        self.assertEqual(r.data['instrument_numero_serie'], 'SN-MEGGER-9')
        self.assertFalse(r.data['instrument_etalonnage_expire'])


class TestWarnModeDefault(TestCase):
    """Mode par défaut = avertissement non-bloquant."""
    def setUp(self):
        self.company = make_company()
        self.user = make_user(self.company)
        self.api = auth(self.user)
        self.inst = make_installation(self.company)

    def test_expired_instrument_does_not_block_by_default(self):
        outil = make_outillage(self.company, intervalle_calibration_mois=12)
        r = self.api.post(f'{BASE}/recettes-commissioning/', {
            'installation': self.inst.id, 'instrument_id': outil.id,
        }, format='json')
        self.assertEqual(r.status_code, 201, r.content)
        self.assertTrue(r.data['instrument_etalonnage_expire'])


class TestBlockModeStrict(TestCase):
    """Mode strict (`INSTRUMENT_ETALONNAGE_BLOQUANT=True`) refuse."""
    def setUp(self):
        self.company = make_company()
        self.user = make_user(self.company)
        self.api = auth(self.user)
        self.inst = make_installation(self.company)

    @mock.patch(
        'apps.installations.views.commissioning.settings.INSTRUMENT_ETALONNAGE_BLOQUANT',
        True)
    def test_expired_instrument_blocked_in_strict_mode(self):
        outil = make_outillage(self.company, intervalle_calibration_mois=12)
        r = self.api.post(f'{BASE}/recettes-commissioning/', {
            'installation': self.inst.id, 'instrument_id': outil.id,
        }, format='json')
        self.assertEqual(r.status_code, 400, r.content)
        self.assertFalse(
            CommissioningRecord.objects.filter(installation=self.inst).exists())

    @mock.patch(
        'apps.installations.views.commissioning.settings.INSTRUMENT_ETALONNAGE_BLOQUANT',
        True)
    def test_valid_calibration_not_blocked_in_strict_mode(self):
        outil = make_outillage(
            self.company, intervalle_calibration_mois=12,
            date_derniere_calibration=date.today(),
            date_prochaine_calibration=date.today() + timedelta(days=300))
        r = self.api.post(f'{BASE}/recettes-commissioning/', {
            'installation': self.inst.id, 'instrument_id': outil.id,
        }, format='json')
        self.assertEqual(r.status_code, 201, r.content)
