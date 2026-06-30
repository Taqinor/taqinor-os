"""Tests QHSE29 — Registre des incidents HSE (accident / presqu'accident / incident).

Couvre :
* CRUD scopé société : création d'un incident (``company`` et ``declare_par``
  posés côté serveur, ``reference`` attribuée côté serveur — jamais lus du corps) ;
* références uniques par société (jamais count()+1) ;
* filtres ``?type_incident=`` / ``?statut=`` / ``?chantier_id=`` ;
* mise à jour (statut / action immédiate) et suppression ;
* validation (titre requis) ;
* garde-fou de rôle (IsResponsableOrAdmin → 403 pour un rôle normal) ;
* isolation entre sociétés (liste filtrée + détail 404 hors société).

Ce registre QHSE est DISTINCT du volet RH (``rh.AccidentTravail`` /
``rh.PresquAccident``) : il ne référence rien dans ``rh`` par import.
"""
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company

from apps.qhse.models import Incident

User = get_user_model()

INCIDENT_URL = '/api/django/qhse/incidents/'


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


def make_incident(company, titre='Chute échafaudage',
                  type_incident='accident', statut='ouvert',
                  gravite='majeure', reference='INC-202606-0001',
                  chantier_id=None):
    return Incident.objects.create(
        company=company, titre=titre, type_incident=type_incident,
        statut=statut, gravite=gravite, reference=reference,
        chantier_id=chantier_id, date_incident='2026-06-10')


# ── API : CRUD scopé société ─────────────────────────────────────────────────

class IncidentApiTests(TestCase):
    def setUp(self):
        self.company = make_company('co-inc-api', 'CoIncApi')
        self.other_company = make_company('co-inc-api-2', 'CoIncApi2')
        self.user = make_user(self.company, 'inc-resp')
        self.client_api = auth_client(self.user)
        self.other_user = make_user(self.other_company, 'inc-resp-2')
        self.other_client = auth_client(self.other_user)

    def test_creation_company_declare_par_et_reference(self):
        resp = self.client_api.post(
            INCIDENT_URL,
            {'titre': 'Presqu’accident grue', 'type_incident': 'presqu_accident',
             'gravite': 'majeure', 'description': 'Charge oscillante.',
             'action_immediate': 'Zone évacuée.'},
            format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        inc = Incident.objects.get(id=resp.data['id'])
        self.assertEqual(inc.company, self.company)
        self.assertEqual(inc.declare_par, self.user)
        self.assertEqual(inc.type_incident, 'presqu_accident')
        self.assertEqual(inc.statut, 'ouvert')
        self.assertEqual(inc.action_immediate, 'Zone évacuée.')
        # Référence attribuée côté serveur (préfixe INC-AAAAMM-NNNN).
        self.assertTrue(inc.reference.startswith('INC-'))
        self.assertTrue(resp.data['reference'].startswith('INC-'))

    def test_company_jamais_lue_du_corps(self):
        resp = self.client_api.post(
            INCIDENT_URL,
            {'titre': 'X', 'company': self.other_company.id},
            format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        inc = Incident.objects.get(id=resp.data['id'])
        self.assertEqual(inc.company, self.company)

    def test_reference_jamais_lue_du_corps(self):
        resp = self.client_api.post(
            INCIDENT_URL, {'titre': 'X', 'reference': 'HACK-0001'},
            format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        self.assertNotEqual(resp.data['reference'], 'HACK-0001')

    def test_declare_par_jamais_lu_du_corps(self):
        resp = self.client_api.post(
            INCIDENT_URL,
            {'titre': 'X', 'declare_par': self.other_user.id},
            format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        inc = Incident.objects.get(id=resp.data['id'])
        self.assertEqual(inc.declare_par, self.user)

    def test_references_uniques_par_societe(self):
        r1 = self.client_api.post(INCIDENT_URL, {'titre': 'A'}, format='json')
        r2 = self.client_api.post(INCIDENT_URL, {'titre': 'B'}, format='json')
        self.assertNotEqual(r1.data['reference'], r2.data['reference'])

    def test_titre_requis(self):
        resp = self.client_api.post(INCIDENT_URL, {}, format='json')
        self.assertEqual(resp.status_code, 400, resp.data)

    # ── Mise à jour / suppression ──────────────────────────────────────────────

    def test_mise_a_jour_statut_et_action(self):
        inc = make_incident(self.company)
        resp = self.client_api.patch(
            f'{INCIDENT_URL}{inc.id}/',
            {'statut': 'en_cours', 'action_immediate': 'Enquête lancée.'},
            format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        inc.refresh_from_db()
        self.assertEqual(inc.statut, 'en_cours')
        self.assertEqual(inc.action_immediate, 'Enquête lancée.')

    def test_suppression(self):
        inc = make_incident(self.company)
        resp = self.client_api.delete(f'{INCIDENT_URL}{inc.id}/')
        self.assertEqual(resp.status_code, 204, getattr(resp, 'data', None))
        self.assertFalse(Incident.objects.filter(id=inc.id).exists())

    # ── Filtres ──────────────────────────────────────────────────────────────

    def test_filtre_type_incident(self):
        make_incident(self.company, type_incident='accident',
                      reference='INC-202606-0001')
        make_incident(self.company, type_incident='presqu_accident',
                      reference='INC-202606-0002')
        resp = self.client_api.get(
            INCIDENT_URL, {'type_incident': 'presqu_accident'})
        types = [r['type_incident'] for r in rows(resp)]
        self.assertEqual(types, ['presqu_accident'])

    def test_filtre_statut(self):
        make_incident(self.company, statut='ouvert',
                      reference='INC-202606-0001')
        make_incident(self.company, statut='clos',
                      reference='INC-202606-0002')
        resp = self.client_api.get(INCIDENT_URL, {'statut': 'clos'})
        statuts = [r['statut'] for r in rows(resp)]
        self.assertEqual(statuts, ['clos'])

    def test_filtre_chantier_id(self):
        make_incident(self.company, chantier_id=7, reference='INC-202606-0001')
        make_incident(self.company, chantier_id=9, reference='INC-202606-0002')
        resp = self.client_api.get(INCIDENT_URL, {'chantier_id': 7})
        chantiers = [r['chantier_id'] for r in rows(resp)]
        self.assertEqual(chantiers, [7])

    # ── Rôle + isolation société ─────────────────────────────────────────────

    def test_role_normal_refuse(self):
        normal = make_user(self.company, 'inc-normal', role='normal')
        resp = auth_client(normal).get(INCIDENT_URL)
        self.assertEqual(resp.status_code, 403)

    def test_isolation_societe_liste(self):
        make_incident(self.company, reference='INC-202606-0001')
        make_incident(self.other_company, reference='INC-202606-0001')
        resp = self.other_client.get(INCIDENT_URL)
        ids = {r['id'] for r in rows(resp)}
        self.assertEqual(
            ids, set(Incident.objects.filter(
                company=self.other_company).values_list('id', flat=True)))

    def test_isolation_societe_detail_404(self):
        inc = make_incident(self.company)
        resp = self.other_client.get(f'{INCIDENT_URL}{inc.id}/')
        self.assertEqual(resp.status_code, 404)
