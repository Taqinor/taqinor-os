"""Tests QHSE11 — Pont Réserve (``installations.Reserve``) → NCR.

Couvre :

* le service ``creer_ncr_depuis_reserve`` crée une non-conformité reliée à la
  réserve (lien lâche), avec description/chantier repris de la réserve ;
* idempotence : une seule NCR par réserve ;
* scoping société : une réserve d'une autre société lève ``ValueError`` (404
  côté API) ;
* l'endpoint ``POST …/non-conformites/depuis-reserve/`` pose ``company`` et
  ``signale_par`` côté serveur et reste réservé au palier Responsable/Admin ;
* le pont passe par le sélecteur d'``installations`` (aucun import de modèle
  cross-app dans qhse).
"""
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company

from apps.crm.models import Client
from apps.installations.models import Installation, Intervention, Reserve
from apps.qhse.models import NonConformite
from apps.qhse.services import creer_ncr_depuis_reserve

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


def make_reserve(company, user, description='Câble à reprendre', ref='CHT'):
    client = Client.objects.create(company=company, nom='Cli')
    inst = Installation.objects.create(
        company=company, reference=f'{ref}-{company.id}', client=client)
    interv = Intervention.objects.create(
        company=company, installation=inst, type_intervention='pose',
        created_by=user)
    return Reserve.objects.create(
        company=company, intervention=interv, description=description)


class ReserveNcrServiceTests(TestCase):
    def setUp(self):
        self.co = make_company('qhse11-svc', 'Svc')
        self.user = make_user(self.co, 'qhse11-svc')
        self.reserve = make_reserve(self.co, self.user)

    def test_creates_linked_ncr(self):
        ncr, created = creer_ncr_depuis_reserve(
            self.reserve.id, self.co, signale_par=self.user)
        self.assertTrue(created)
        self.assertEqual(ncr.reserve_id, self.reserve.id)
        self.assertEqual(ncr.company, self.co)
        self.assertIn('Câble à reprendre', ncr.description)
        self.assertEqual(
            ncr.chantier_id, self.reserve.intervention.installation_id)
        self.assertEqual(ncr.signale_par, self.user)

    def test_idempotent(self):
        ncr1, c1 = creer_ncr_depuis_reserve(self.reserve.id, self.co)
        ncr2, c2 = creer_ncr_depuis_reserve(self.reserve.id, self.co)
        self.assertTrue(c1)
        self.assertFalse(c2)
        self.assertEqual(ncr1.id, ncr2.id)
        self.assertEqual(
            NonConformite.objects.filter(reserve_id=self.reserve.id).count(), 1)

    def test_other_company_reserve_raises(self):
        other = make_company('qhse11-svc-b', 'B')
        other_user = make_user(other, 'qhse11-svc-b')
        other_reserve = make_reserve(other, other_user, ref='OTH')
        with self.assertRaises(ValueError):
            creer_ncr_depuis_reserve(other_reserve.id, self.co)


class ReserveNcrApiTests(TestCase):
    BASE = '/api/django/qhse/non-conformites/depuis-reserve/'

    def setUp(self):
        self.co = make_company('qhse11-api', 'Api')
        self.user = make_user(self.co, 'qhse11-api')
        self.reserve = make_reserve(self.co, self.user)

    def test_endpoint_creates_ncr_server_side(self):
        resp = auth(self.user).post(
            self.BASE, {'reserve': self.reserve.id}, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        ncr = NonConformite.objects.get(id=resp.data['id'])
        self.assertEqual(ncr.company, self.co)
        self.assertEqual(ncr.signale_par, self.user)
        self.assertEqual(ncr.reserve_id, self.reserve.id)

    def test_endpoint_idempotent_returns_200(self):
        first = auth(self.user).post(
            self.BASE, {'reserve': self.reserve.id}, format='json')
        second = auth(self.user).post(
            self.BASE, {'reserve': self.reserve.id}, format='json')
        self.assertEqual(first.status_code, 201)
        self.assertEqual(second.status_code, 200)
        self.assertEqual(first.data['id'], second.data['id'])

    def test_endpoint_other_company_404(self):
        other = make_company('qhse11-api-b', 'B')
        other_user = make_user(other, 'qhse11-api-b')
        other_reserve = make_reserve(other, other_user, ref='OTH')
        resp = auth(self.user).post(
            self.BASE, {'reserve': other_reserve.id}, format='json')
        self.assertEqual(resp.status_code, 404)

    def test_endpoint_missing_reserve_400(self):
        resp = auth(self.user).post(self.BASE, {}, format='json')
        self.assertEqual(resp.status_code, 400)

    def test_role_normal_refuse(self):
        normal = make_user(self.co, 'qhse11-normal', role='normal')
        resp = auth(normal).post(
            self.BASE, {'reserve': self.reserve.id}, format='json')
        self.assertEqual(resp.status_code, 403)
