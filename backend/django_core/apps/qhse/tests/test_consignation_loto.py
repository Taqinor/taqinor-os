"""Tests QHSE24 — Consignation électrique (LOTO) sur permis de travail.

Couvre :
* CRUD scopé société : création d'une consignation rattachée à un permis
  (``company`` posée côté serveur, ``reference`` attribuée côté serveur — jamais
  lue du corps) ;
* action ``deconsigner`` (consignée → déconsignée) qui enregistre
  ``date_deconsignation`` et bascule le ``statut``, avec garde-fou (pas de
  double déconsignation) ;
* filtres ``?permis=`` / ``?statut=`` ;
* garde-fou de rôle (IsResponsableOrAdmin → 403 pour un rôle normal) ;
* isolation entre sociétés (liste filtrée, détail 404 hors société, permis
  d'une autre société refusé à la création).
"""
from datetime import date

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company

from apps.qhse.models import ConsignationLoto, PermisTravail

User = get_user_model()

LOTO_URL = '/api/django/qhse/consignations-loto/'


# ── Helpers ──────────────────────────────────────────────────────────────────

def make_company(slug, nom):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


def make_user(company, username, role='responsable'):
    return User.objects.create_user(
        username=username, password='x', company=company, role_legacy=role)


def auth_client(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


def rows(resp):
    data = resp.data
    return (data['results']
            if isinstance(data, dict) and 'results' in data else data)


def make_permis(company, reference='PT-202606-0001'):
    return PermisTravail.objects.create(
        company=company, titre='Consignation TGBT',
        type_permis='consignation_elec', statut='valide',
        reference=reference, date_debut=date(2026, 6, 1),
        date_fin=date(2026, 6, 30))


def make_loto(company, permis, reference='LOTO-202606-0001',
              statut='consignee', equipement='TGBT'):
    return ConsignationLoto.objects.create(
        company=company, permis=permis, reference=reference, statut=statut,
        equipement=equipement, point_consignation='Disjoncteur Q1',
        consignateur='Chargé de consignation')


# ── API : CRUD scopé société ─────────────────────────────────────────────────

class ConsignationLotoApiTests(TestCase):
    def setUp(self):
        self.company = make_company('co-loto-api', 'CoLotoApi')
        self.other_company = make_company('co-loto-api-2', 'CoLotoApi2')
        self.user = make_user(self.company, 'loto-resp')
        self.client_api = auth_client(self.user)
        self.other_user = make_user(self.other_company, 'loto-resp-2')
        self.other_client = auth_client(self.other_user)
        self.permis = make_permis(self.company)

    def test_creation_sur_permis_pose_company_et_reference(self):
        resp = self.client_api.post(
            LOTO_URL,
            {'permis': self.permis.id, 'equipement': 'TGBT atelier',
             'point_consignation': 'Disjoncteur général',
             'consignateur': 'M. Alami', 'verifie_absence_tension': True},
            format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        loto = ConsignationLoto.objects.get(id=resp.data['id'])
        self.assertEqual(loto.company, self.company)
        self.assertEqual(loto.permis, self.permis)
        self.assertEqual(loto.statut, 'consignee')
        self.assertTrue(loto.verifie_absence_tension)
        # Référence attribuée côté serveur (préfixe LOTO-AAAAMM-NNNN).
        self.assertTrue(loto.reference.startswith('LOTO-'))
        self.assertTrue(resp.data['reference'].startswith('LOTO-'))

    def test_company_jamais_lue_du_corps(self):
        resp = self.client_api.post(
            LOTO_URL,
            {'permis': self.permis.id, 'company': self.other_company.id},
            format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        loto = ConsignationLoto.objects.get(id=resp.data['id'])
        self.assertEqual(loto.company, self.company)

    def test_reference_jamais_lue_du_corps(self):
        resp = self.client_api.post(
            LOTO_URL, {'permis': self.permis.id, 'reference': 'HACK-0001'},
            format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        self.assertNotEqual(resp.data['reference'], 'HACK-0001')

    def test_statut_jamais_lu_du_corps(self):
        resp = self.client_api.post(
            LOTO_URL, {'permis': self.permis.id, 'statut': 'deconsignee'},
            format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        self.assertEqual(resp.data['statut'], 'consignee')

    def test_date_deconsignation_jamais_lue_du_corps_a_la_creation(self):
        resp = self.client_api.post(
            LOTO_URL,
            {'permis': self.permis.id,
             'date_deconsignation': '2026-06-10T10:00:00Z'},
            format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        loto = ConsignationLoto.objects.get(id=resp.data['id'])
        self.assertIsNone(loto.date_deconsignation)

    def test_references_uniques_par_societe(self):
        r1 = self.client_api.post(
            LOTO_URL, {'permis': self.permis.id}, format='json')
        r2 = self.client_api.post(
            LOTO_URL, {'permis': self.permis.id}, format='json')
        self.assertNotEqual(r1.data['reference'], r2.data['reference'])

    def test_permis_autre_societe_refuse(self):
        autre_permis = make_permis(self.other_company)
        resp = self.client_api.post(
            LOTO_URL, {'permis': autre_permis.id}, format='json')
        self.assertEqual(resp.status_code, 400, resp.data)

    # ── Action déconsigner ───────────────────────────────────────────────────

    def test_deconsigner(self):
        loto = make_loto(self.company, self.permis)
        resp = self.client_api.post(
            f'{LOTO_URL}{loto.id}/deconsigner/', {}, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        loto.refresh_from_db()
        self.assertEqual(loto.statut, 'deconsignee')
        self.assertIsNotNone(loto.date_deconsignation)

    def test_deconsigner_avec_date_fournie(self):
        loto = make_loto(self.company, self.permis)
        resp = self.client_api.post(
            f'{LOTO_URL}{loto.id}/deconsigner/',
            {'date_deconsignation': '2026-06-12T08:30:00Z'}, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        loto.refresh_from_db()
        self.assertEqual(loto.statut, 'deconsignee')
        self.assertEqual(loto.date_deconsignation.year, 2026)
        self.assertEqual(loto.date_deconsignation.month, 6)
        self.assertEqual(loto.date_deconsignation.day, 12)

    def test_deconsigner_refuse_si_deja_deconsignee(self):
        loto = make_loto(self.company, self.permis, statut='deconsignee')
        resp = self.client_api.post(
            f'{LOTO_URL}{loto.id}/deconsigner/', {}, format='json')
        self.assertEqual(resp.status_code, 400, resp.data)

    # ── Filtres ──────────────────────────────────────────────────────────────

    def test_filtre_permis(self):
        permis2 = make_permis(self.company, reference='PT-202606-0002')
        make_loto(self.company, self.permis, reference='LOTO-202606-0001')
        make_loto(self.company, permis2, reference='LOTO-202606-0002')
        resp = self.client_api.get(LOTO_URL, {'permis': permis2.id})
        permis_ids = [r['permis'] for r in rows(resp)]
        self.assertEqual(permis_ids, [permis2.id])

    def test_filtre_statut(self):
        make_loto(self.company, self.permis, statut='consignee',
                  reference='LOTO-202606-0001')
        make_loto(self.company, self.permis, statut='deconsignee',
                  reference='LOTO-202606-0002')
        resp = self.client_api.get(LOTO_URL, {'statut': 'deconsignee'})
        statuts = [r['statut'] for r in rows(resp)]
        self.assertEqual(statuts, ['deconsignee'])

    # ── Rôle + isolation société ─────────────────────────────────────────────

    def test_role_normal_refuse(self):
        normal = make_user(self.company, 'loto-normal', role='normal')
        resp = auth_client(normal).get(LOTO_URL)
        self.assertEqual(resp.status_code, 403)

    def test_isolation_societe_liste(self):
        make_loto(self.company, self.permis, reference='LOTO-202606-0001')
        other_permis = make_permis(self.other_company)
        make_loto(self.other_company, other_permis,
                  reference='LOTO-202606-0001')
        resp = self.other_client.get(LOTO_URL)
        ids = {r['id'] for r in rows(resp)}
        self.assertEqual(
            ids,
            set(ConsignationLoto.objects.filter(
                company=self.other_company).values_list('id', flat=True)))

    def test_isolation_societe_detail_404(self):
        loto = make_loto(self.company, self.permis)
        resp = self.other_client.get(f'{LOTO_URL}{loto.id}/')
        self.assertEqual(resp.status_code, 404)

    def test_deconsigner_autre_societe_404(self):
        loto = make_loto(self.company, self.permis)
        resp = self.other_client.post(
            f'{LOTO_URL}{loto.id}/deconsigner/', {}, format='json')
        self.assertEqual(resp.status_code, 404)
