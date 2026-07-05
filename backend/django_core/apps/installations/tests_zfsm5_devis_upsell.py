"""
ZFSM5 — Devis d'upsell créé sur place depuis l'intervention.

Couvre :
  * `interventions/{id}/generer-devis/` crée un `ventes.Devis` brouillon via
    `apps.ventes.services.create_devis_upsell_from_intervention` (client du
    chantier résolu server-side, description pré-remplie) ;
  * `devis_upsell_id` posé en retour sur l'intervention ;
  * idempotent : un second appel renvoie le même devis sans en créer un
    second ;
  * DISTINCT de `generer-devis-reserve` (XFSM18) — même intervention peut
    avoir les deux, sans collision ;
  * aucun statut devis touché au-delà du brouillon (règle #4) ;
  * sans client résolu sur le chantier → 400.

Run :
    python manage.py test apps.installations.tests_zfsm5_devis_upsell -v2
"""
import itertools

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.crm.models import Client
from apps.installations.models import Installation, Intervention, Reserve
from apps.ventes.models import Devis

User = get_user_model()
_seq = itertools.count(1)
BASE = '/api/django/installations'


def make_company(slug=None, nom=None):
    from authentication.models import Company
    n = next(_seq)
    company, _ = Company.objects.get_or_create(
        slug=slug or f'zfsm5-co-{n}', defaults={'nom': nom or f'ZFSM5 Co {n}'})
    return company


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


def make_user(company, role='responsable'):
    return User.objects.create_user(
        username=f'zfsm5-{next(_seq)}', password='x',
        role_legacy=role, company=company)


def make_installation(company, with_client=True):
    n = next(_seq)
    client = None
    if with_client:
        client = Client.objects.create(
            company=company, nom='Client', prenom='ZFSM5',
            email=f'zfsm5-{company.id}-{n}@example.invalid')
    return Installation.objects.create(
        company=company, reference=f'CHT-ZFSM5-{n}', client=client)


class TestGenererDevisUpsell(TestCase):
    def setUp(self):
        self.company = make_company()
        self.user = make_user(self.company)
        self.api = auth(self.user)
        self.inst = make_installation(self.company)
        self.interv = Intervention.objects.create(
            company=self.company, installation=self.inst,
            type_intervention='controle', created_by=self.user)

    def test_generates_draft_devis(self):
        r = self.api.post(
            f'{BASE}/interventions/{self.interv.id}/generer-devis/',
            format='json')
        self.assertEqual(r.status_code, 201, r.content)
        devis = Devis.objects.get(id=r.data['devis_id'])
        self.assertEqual(devis.statut, Devis.Statut.BROUILLON)
        self.assertEqual(devis.client_id, self.inst.client_id)
        self.assertIn(self.inst.reference, devis.note)
        self.interv.refresh_from_db()
        self.assertEqual(self.interv.devis_upsell_id, devis.id)

    def test_idempotent_second_call_returns_same_devis(self):
        r1 = self.api.post(
            f'{BASE}/interventions/{self.interv.id}/generer-devis/',
            format='json')
        r2 = self.api.post(
            f'{BASE}/interventions/{self.interv.id}/generer-devis/',
            format='json')
        self.assertEqual(r2.status_code, 200, r2.content)
        self.assertTrue(r2.data['deja_existant'])
        self.assertEqual(r1.data['devis_id'], r2.data['devis_id'])
        self.assertEqual(
            Devis.objects.filter(client_id=self.inst.client_id).count(), 1)

    def test_no_client_on_chantier_returns_400(self):
        inst_sans_client = make_installation(self.company, with_client=False)
        interv2 = Intervention.objects.create(
            company=self.company, installation=inst_sans_client,
            type_intervention='controle', created_by=self.user)
        r = self.api.post(
            f'{BASE}/interventions/{interv2.id}/generer-devis/',
            format='json')
        self.assertEqual(r.status_code, 400)

    def test_distinct_from_reserve_devis_reparation(self):
        """ZFSM5 (upsell) et XFSM18 (réserve → réparation) coexistent sans
        collision sur la même intervention."""
        reserve = Reserve.objects.create(
            company=self.company, intervention=self.interv,
            description='Fissure sur le rail.', created_by=self.user)
        r_reserve = self.api.post(
            f'{BASE}/interventions/{self.interv.id}/generer-devis-reserve/',
            {'reserve': reserve.id}, format='json')
        r_upsell = self.api.post(
            f'{BASE}/interventions/{self.interv.id}/generer-devis/',
            format='json')
        self.assertEqual(r_reserve.status_code, 201, r_reserve.content)
        self.assertEqual(r_upsell.status_code, 201, r_upsell.content)
        self.assertNotEqual(r_reserve.data['devis_id'], r_upsell.data['devis_id'])
        self.interv.refresh_from_db()
        reserve.refresh_from_db()
        self.assertEqual(self.interv.devis_upsell_id, r_upsell.data['devis_id'])
        self.assertEqual(reserve.devis_repare_id, r_reserve.data['devis_id'])
