"""
XFSM18 — Réserve/déficience → devis de réparation.

Couvre :
  * `reserves/{id}/generer-devis-reserve/` (nested sous
    `interventions/{id}/...`, même patron que les autres actions réserve)
    crée un `ventes.Devis` brouillon, client du chantier résolu server-side,
    description pré-remplie ;
  * `devis_repare_id` posé en retour sur la réserve ;
  * idempotent : un second appel renvoie le même devis sans en créer un
    second ;
  * aucun statut devis/document touché au-delà du brouillon (règle #4) ;
  * isolation multi-société.

Run :
    python manage.py test apps.installations.tests_xfsm18_reserve_devis -v2
"""
import itertools
import threading
import time
from unittest import mock

from django.contrib.auth import get_user_model
from django.db import connection
from django.test import TestCase, TransactionTestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.crm.models import Client
from apps.installations.models import Installation, Intervention, Reserve
from apps.ventes.models import Devis
from core.test_utils import WideTeardownTimeoutMixin

User = get_user_model()
_seq = itertools.count(1)
BASE = '/api/django/installations'


def make_company(slug=None, nom=None):
    from authentication.models import Company
    n = next(_seq)
    company, _ = Company.objects.get_or_create(
        slug=slug or f'xfsm18-co-{n}', defaults={'nom': nom or f'XFSM18 Co {n}'})
    return company


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


def make_user(company, role='responsable'):
    return User.objects.create_user(
        username=f'xfsm18-{next(_seq)}', password='x',
        role_legacy=role, company=company)


def make_installation(company):
    n = next(_seq)
    client = Client.objects.create(
        company=company, nom='Client', prenom='XFSM18',
        email=f'xfsm18-{company.id}-{n}@example.invalid')
    return Installation.objects.create(
        company=company, reference=f'CHT-XFSM18-{n}', client=client)


class TestGenererDevisReserve(TestCase):
    def setUp(self):
        self.company = make_company()
        self.user = make_user(self.company)
        self.api = auth(self.user)
        self.inst = make_installation(self.company)
        self.interv = Intervention.objects.create(
            company=self.company, installation=self.inst,
            type_intervention='depannage', created_by=self.user)
        self.reserve = Reserve.objects.create(
            company=self.company, intervention=self.interv,
            description='Fissure sur le rail de fixation.',
            created_by=self.user)

    def test_generates_draft_devis(self):
        r = self.api.post(
            f'{BASE}/interventions/{self.interv.id}/generer-devis-reserve/',
            {'reserve': self.reserve.id}, format='json')
        self.assertEqual(r.status_code, 201, r.content)
        devis = Devis.objects.get(id=r.data['devis_id'])
        self.assertEqual(devis.statut, Devis.Statut.BROUILLON)
        self.assertEqual(devis.client_id, self.inst.client_id)
        self.assertIn('Fissure sur le rail', devis.note)
        self.reserve.refresh_from_db()
        self.assertEqual(self.reserve.devis_repare_id, devis.id)

    def test_idempotent_second_call_returns_same_devis(self):
        r1 = self.api.post(
            f'{BASE}/interventions/{self.interv.id}/generer-devis-reserve/',
            {'reserve': self.reserve.id}, format='json')
        r2 = self.api.post(
            f'{BASE}/interventions/{self.interv.id}/generer-devis-reserve/',
            {'reserve': self.reserve.id}, format='json')
        self.assertEqual(r2.status_code, 200, r2.content)
        self.assertTrue(r2.data['deja_existant'])
        self.assertEqual(r1.data['devis_id'], r2.data['devis_id'])
        self.assertEqual(
            Devis.objects.filter(client_id=self.inst.client_id).count(), 1)

    def test_unknown_reserve_409(self):
        # ENF11 : réserve de corps absente, l'intervention existe = refus d'état.
        r = self.api.post(
            f'{BASE}/interventions/{self.interv.id}/generer-devis-reserve/',
            {'reserve': 999999}, format='json')
        self.assertEqual(r.status_code, 409)

    def test_reserve_serializer_exposes_devis_repare_id(self):
        r = self.api.post(
            f'{BASE}/interventions/{self.interv.id}/generer-devis-reserve/',
            {'reserve': self.reserve.id}, format='json')
        devis_id = r.data['devis_id']
        r2 = self.api.get(f'{BASE}/interventions/{self.interv.id}/reserves/')
        self.assertEqual(r2.data[0]['devis_repare_id'], devis_id)


class TestGenererDevisReserveCourse(WideTeardownTimeoutMixin, TransactionTestCase):
    """ACNC34 — deux VRAIES connexions (patron ``apps/sav/tests_pieces.py::
    TestSavPiecesConcurrence._course``) : deux « Générer le devis » croisés sur
    la même réserve. Classe ``TransactionTestCase`` dédiée :
    ``TestGenererDevisReserve`` est un ``TestCase`` (une seule connexion)."""

    def setUp(self):
        self.company = make_company()
        self.user = make_user(self.company)
        self.inst = make_installation(self.company)
        self.interv = Intervention.objects.create(
            company=self.company, installation=self.inst,
            type_intervention='depannage', created_by=self.user)
        self.reserve = Reserve.objects.create(
            company=self.company, intervention=self.interv,
            description='Fissure sur le rail de fixation.',
            created_by=self.user)

    def test_deux_generations_croisees_un_seul_devis(self):
        from apps.ventes import services as ventes_services
        original = ventes_services.create_devis_from_reserve
        a_tient, b_tente, res = threading.Event(), threading.Event(), {}
        url = f'{BASE}/interventions/{self.interv.id}/generer-devis-reserve/'

        def creation_lente(**kwargs):
            if not a_tient.is_set():  # A : tient sa transaction ouverte
                a_tient.set()
                b_tente.wait(5)
                time.sleep(0.5)  # B atteint la relecture de la réserve
            return original(**kwargs)

        def fil(nom):
            if nom == 'b':
                a_tient.wait(5)
                b_tente.set()
            r = auth(self.user).post(url, {'reserve': self.reserve.id}, format='json')
            res[nom] = (r.status_code, r.data.get('devis_id'))
            connection.close()

        with mock.patch.object(ventes_services, 'create_devis_from_reserve', side_effect=creation_lente):
            fils = [threading.Thread(target=fil, args=(n,)) for n in ('a', 'b')]
            for f in fils:
                f.start()
            for f in fils:
                f.join(20)
        self.assertEqual(sorted(code for code, _ in res.values()), [200, 201], res)
        self.assertEqual(res['a'][1], res['b'][1])
        self.assertEqual(Devis.objects.filter(client_id=self.inst.client_id).count(), 1)
        self.reserve.refresh_from_db()
        self.assertEqual(self.reserve.devis_repare_id, res['a'][1])
