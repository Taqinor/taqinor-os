"""Tests QHSE33 — Inspection sécurité planifiée (→ NCR).

Couvre :
* CRUD scopé société : création (``company``/``inspecteur``/``reference`` posés
  côté serveur — jamais lus du corps) ;
* action ``lever-ncr`` : une inspection NON CONFORME lève une NCR (idempotente —
  une seule par inspection) ; une inspection conforme / en attente est refusée ;
* filtres ``?statut=`` / ``?resultat=`` / ``?chantier_id=`` ;
* garde-fou de rôle (IsResponsableOrAdmin → 403) ;
* isolation entre sociétés (liste + détail 404 hors société).
"""
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company

from apps.qhse.models import InspectionSecurite, NonConformite
from apps.qhse.services import lever_ncr_inspection

User = get_user_model()

INSP_URL = '/api/django/qhse/inspections-securite/'


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


def make_inspection(company, titre='Ronde HSE', statut='planifiee',
                    resultat='en_attente', reference='INSP-202606-0001',
                    chantier_id=None, observations=''):
    return InspectionSecurite.objects.create(
        company=company, titre=titre, statut=statut, resultat=resultat,
        reference=reference, chantier_id=chantier_id,
        observations=observations)


class InspectionSecuriteApiTests(TestCase):
    def setUp(self):
        self.company = make_company('co-insp-api', 'CoInspApi')
        self.other_company = make_company('co-insp-api-2', 'CoInspApi2')
        self.user = make_user(self.company, 'insp-resp')
        self.client_api = auth_client(self.user)
        self.other_user = make_user(self.other_company, 'insp-resp-2')
        self.other_client = auth_client(self.other_user)

    def test_creation_company_inspecteur_et_reference(self):
        resp = self.client_api.post(
            INSP_URL, {'titre': 'Visite sécurité chantier'}, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        insp = InspectionSecurite.objects.get(id=resp.data['id'])
        self.assertEqual(insp.company, self.company)
        self.assertEqual(insp.inspecteur, self.user)
        self.assertEqual(insp.statut, 'planifiee')
        self.assertEqual(insp.resultat, 'en_attente')
        self.assertTrue(insp.reference.startswith('INSP-'))

    def test_company_jamais_lue_du_corps(self):
        resp = self.client_api.post(
            INSP_URL,
            {'titre': 'X', 'company': self.other_company.id}, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        insp = InspectionSecurite.objects.get(id=resp.data['id'])
        self.assertEqual(insp.company, self.company)

    def test_reference_jamais_lue_du_corps(self):
        resp = self.client_api.post(
            INSP_URL, {'titre': 'X', 'reference': 'HACK-0001'}, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        self.assertNotEqual(resp.data['reference'], 'HACK-0001')

    def test_lever_ncr_non_conforme(self):
        insp = make_inspection(
            self.company, resultat='non_conforme',
            chantier_id=4, observations='Garde-corps manquant')
        resp = self.client_api.post(
            f'{INSP_URL}{insp.id}/lever-ncr/', {'gravite': 'majeure'},
            format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        ncr = NonConformite.objects.get(id=resp.data['id'])
        self.assertEqual(ncr.company, self.company)
        self.assertEqual(ncr.gravite, 'majeure')
        self.assertEqual(ncr.chantier_id, 4)
        self.assertEqual(ncr.signale_par, self.user)
        insp.refresh_from_db()
        self.assertEqual(insp.ncr_id, ncr.id)

    def test_lever_ncr_idempotent(self):
        insp = make_inspection(self.company, resultat='non_conforme')
        r1 = self.client_api.post(
            f'{INSP_URL}{insp.id}/lever-ncr/', {}, format='json')
        r2 = self.client_api.post(
            f'{INSP_URL}{insp.id}/lever-ncr/', {}, format='json')
        self.assertEqual(r1.status_code, 201, r1.data)
        self.assertEqual(r2.status_code, 200, r2.data)
        self.assertEqual(r1.data['id'], r2.data['id'])
        self.assertEqual(
            NonConformite.objects.filter(company=self.company).count(), 1)

    def test_lever_ncr_refuse_si_conforme(self):
        insp = make_inspection(self.company, resultat='conforme')
        resp = self.client_api.post(
            f'{INSP_URL}{insp.id}/lever-ncr/', {}, format='json')
        self.assertEqual(resp.status_code, 400, resp.data)
        self.assertEqual(NonConformite.objects.count(), 0)

    def test_service_lever_ncr_refuse_en_attente(self):
        insp = make_inspection(self.company, resultat='en_attente')
        with self.assertRaises(ValueError):
            lever_ncr_inspection(insp)

    def test_filtre_resultat(self):
        make_inspection(self.company, resultat='conforme',
                        reference='INSP-202606-0001')
        make_inspection(self.company, resultat='non_conforme',
                        reference='INSP-202606-0002')
        resp = self.client_api.get(INSP_URL, {'resultat': 'non_conforme'})
        results = [r['resultat'] for r in rows(resp)]
        self.assertEqual(results, ['non_conforme'])

    def test_filtre_statut(self):
        make_inspection(self.company, statut='planifiee',
                        reference='INSP-202606-0001')
        make_inspection(self.company, statut='realisee',
                        reference='INSP-202606-0002')
        resp = self.client_api.get(INSP_URL, {'statut': 'realisee'})
        statuts = [r['statut'] for r in rows(resp)]
        self.assertEqual(statuts, ['realisee'])

    def test_filtre_chantier_id(self):
        make_inspection(self.company, chantier_id=7,
                        reference='INSP-202606-0001')
        make_inspection(self.company, chantier_id=9,
                        reference='INSP-202606-0002')
        resp = self.client_api.get(INSP_URL, {'chantier_id': 7})
        chantiers = [r['chantier_id'] for r in rows(resp)]
        self.assertEqual(chantiers, [7])

    def test_role_normal_refuse(self):
        normal = make_user(self.company, 'insp-normal', role='normal')
        resp = auth_client(normal).get(INSP_URL)
        self.assertEqual(resp.status_code, 403)

    def test_isolation_societe_detail_404(self):
        insp = make_inspection(self.company)
        resp = self.other_client.get(f'{INSP_URL}{insp.id}/')
        self.assertEqual(resp.status_code, 404)

    def test_lever_ncr_autre_societe_404(self):
        insp = make_inspection(self.company, resultat='non_conforme')
        resp = self.other_client.post(
            f'{INSP_URL}{insp.id}/lever-ncr/', {}, format='json')
        self.assertEqual(resp.status_code, 404)
