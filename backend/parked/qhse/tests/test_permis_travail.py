"""Tests QHSE23 — Permis de travail (hauteur / consignation / point chaud).

Couvre :
* CRUD scopé société : création d'un permis (``company`` posée côté serveur,
  ``reference`` attribuée côté serveur — jamais lue du corps) ;
* validité (``date_debut``/``date_fin`` ; fin avant début refusée) ;
* transitions ``valider`` (brouillon → validé) et ``cloturer`` (→ clôturé),
  avec garde-fous (pas de validation d'un permis clôturé, pas de double
  clôture) ;
* filtres ``?type_permis=`` / ``?statut=`` / ``?chantier_id=`` ;
* garde-fou de rôle (IsResponsableOrAdmin → 403 pour un rôle normal) ;
* isolation entre sociétés (liste filtrée + détail 404 hors société).
"""
from datetime import date

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company

from apps.qhse.models import PermisTravail

User = get_user_model()

PERMIS_URL = '/api/django/qhse/permis-travail/'


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


def make_permis(company, titre='Pose toiture', type_permis='hauteur',
                statut='brouillon', reference='PT-202606-0001',
                chantier_id=None):
    return PermisTravail.objects.create(
        company=company, titre=titre, type_permis=type_permis, statut=statut,
        reference=reference, chantier_id=chantier_id,
        date_debut=date(2026, 6, 1), date_fin=date(2026, 6, 30))


# ── API : CRUD scopé société ─────────────────────────────────────────────────

class PermisTravailApiTests(TestCase):
    def setUp(self):
        self.company = make_company('co-pt-api', 'CoPtApi')
        self.other_company = make_company('co-pt-api-2', 'CoPtApi2')
        self.user = make_user(self.company, 'pt-resp')
        self.client_api = auth_client(self.user)
        self.other_user = make_user(self.other_company, 'pt-resp-2')
        self.other_client = auth_client(self.other_user)

    def test_creation_pose_company_et_reference(self):
        resp = self.client_api.post(
            PERMIS_URL,
            {'titre': 'Soudure structure', 'type_permis': 'point_chaud'},
            format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        permis = PermisTravail.objects.get(id=resp.data['id'])
        self.assertEqual(permis.company, self.company)
        self.assertEqual(permis.statut, 'brouillon')
        self.assertEqual(permis.type_permis, 'point_chaud')
        # Référence attribuée côté serveur (préfixe PT-AAAAMM-NNNN).
        self.assertTrue(permis.reference.startswith('PT-'))
        self.assertTrue(resp.data['reference'].startswith('PT-'))

    def test_company_jamais_lue_du_corps(self):
        resp = self.client_api.post(
            PERMIS_URL,
            {'titre': 'X', 'company': self.other_company.id},
            format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        permis = PermisTravail.objects.get(id=resp.data['id'])
        self.assertEqual(permis.company, self.company)

    def test_reference_jamais_lue_du_corps(self):
        resp = self.client_api.post(
            PERMIS_URL, {'titre': 'X', 'reference': 'HACK-0001'},
            format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        self.assertNotEqual(resp.data['reference'], 'HACK-0001')

    def test_statut_jamais_lu_du_corps(self):
        resp = self.client_api.post(
            PERMIS_URL, {'titre': 'X', 'statut': 'cloture'}, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        self.assertEqual(resp.data['statut'], 'brouillon')

    def test_references_uniques_par_societe(self):
        r1 = self.client_api.post(PERMIS_URL, {'titre': 'A'}, format='json')
        r2 = self.client_api.post(PERMIS_URL, {'titre': 'B'}, format='json')
        self.assertNotEqual(r1.data['reference'], r2.data['reference'])

    def test_validite_dates_acceptees(self):
        resp = self.client_api.post(
            PERMIS_URL,
            {'titre': 'En hauteur', 'date_debut': '2026-06-01',
             'date_fin': '2026-06-15'},
            format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        permis = PermisTravail.objects.get(id=resp.data['id'])
        self.assertEqual(str(permis.date_debut), '2026-06-01')
        self.assertEqual(str(permis.date_fin), '2026-06-15')

    def test_fin_avant_debut_refusee(self):
        resp = self.client_api.post(
            PERMIS_URL,
            {'titre': 'X', 'date_debut': '2026-06-15',
             'date_fin': '2026-06-01'},
            format='json')
        self.assertEqual(resp.status_code, 400, resp.data)

    # ── Transitions ──────────────────────────────────────────────────────────

    def test_valider(self):
        # WIR128 — sans id explicite, le valideur = utilisateur courant (FK).
        permis = make_permis(self.company)
        resp = self.client_api.post(
            f'{PERMIS_URL}{permis.id}/valider/', {}, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        permis.refresh_from_db()
        self.assertEqual(permis.statut, 'valide')
        self.assertEqual(permis.valide_par_id, self.user.id)
        # Libellé lisible exposé par le sérialiseur.
        self.assertEqual(
            resp.data['valide_par_nom'], self.user.get_full_name()
            or self.user.username)

    def test_valider_avec_id_utilisateur_explicite(self):
        # WIR128 — un id explicite d'utilisateur de la société est accepté.
        autre = make_user(self.company, 'chef_secu')
        permis = make_permis(self.company)
        resp = self.client_api.post(
            f'{PERMIS_URL}{permis.id}/valider/',
            {'valide_par': autre.id}, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        permis.refresh_from_db()
        self.assertEqual(permis.valide_par_id, autre.id)

    def test_valider_id_hors_societe_refuse(self):
        # WIR128 — un id d'utilisateur d'une autre société est rejeté (400).
        autre_co = make_company('permis-co-x', 'Permis Co X')
        etranger = make_user(autre_co, 'etranger')
        permis = make_permis(self.company)
        resp = self.client_api.post(
            f'{PERMIS_URL}{permis.id}/valider/',
            {'valide_par': etranger.id}, format='json')
        self.assertEqual(resp.status_code, 400, resp.data)

    def test_valider_refuse_si_cloture(self):
        permis = make_permis(self.company, statut='cloture')
        resp = self.client_api.post(
            f'{PERMIS_URL}{permis.id}/valider/', {}, format='json')
        self.assertEqual(resp.status_code, 400, resp.data)
        permis.refresh_from_db()
        self.assertEqual(permis.statut, 'cloture')

    def test_cloturer(self):
        permis = make_permis(self.company, statut='valide')
        resp = self.client_api.post(
            f'{PERMIS_URL}{permis.id}/cloturer/', {}, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        permis.refresh_from_db()
        self.assertEqual(permis.statut, 'cloture')

    def test_cloturer_refuse_si_deja_cloture(self):
        permis = make_permis(self.company, statut='cloture')
        resp = self.client_api.post(
            f'{PERMIS_URL}{permis.id}/cloturer/', {}, format='json')
        self.assertEqual(resp.status_code, 400, resp.data)

    # ── Filtres ──────────────────────────────────────────────────────────────

    def test_filtre_type_permis(self):
        make_permis(self.company, type_permis='hauteur',
                    reference='PT-202606-0001')
        make_permis(self.company, type_permis='point_chaud',
                    reference='PT-202606-0002')
        resp = self.client_api.get(PERMIS_URL, {'type_permis': 'point_chaud'})
        types = [r['type_permis'] for r in rows(resp)]
        self.assertEqual(types, ['point_chaud'])

    def test_filtre_statut(self):
        make_permis(self.company, statut='brouillon',
                    reference='PT-202606-0001')
        make_permis(self.company, statut='cloture',
                    reference='PT-202606-0002')
        resp = self.client_api.get(PERMIS_URL, {'statut': 'cloture'})
        statuts = [r['statut'] for r in rows(resp)]
        self.assertEqual(statuts, ['cloture'])

    def test_filtre_chantier_id(self):
        make_permis(self.company, chantier_id=7, reference='PT-202606-0001')
        make_permis(self.company, chantier_id=9, reference='PT-202606-0002')
        resp = self.client_api.get(PERMIS_URL, {'chantier_id': 7})
        chantiers = [r['chantier_id'] for r in rows(resp)]
        self.assertEqual(chantiers, [7])

    # ── Rôle + isolation société ─────────────────────────────────────────────

    def test_role_normal_refuse(self):
        normal = make_user(self.company, 'pt-normal', role='normal')
        resp = auth_client(normal).get(PERMIS_URL)
        self.assertEqual(resp.status_code, 403)

    def test_isolation_societe_liste(self):
        make_permis(self.company, reference='PT-202606-0001')
        make_permis(self.other_company, reference='PT-202606-0001')
        resp = self.other_client.get(PERMIS_URL)
        ids = {r['id'] for r in rows(resp)}
        self.assertEqual(
            ids,
            set(PermisTravail.objects.filter(
                company=self.other_company).values_list('id', flat=True)))

    def test_isolation_societe_detail_404(self):
        permis = make_permis(self.company)
        resp = self.other_client.get(f'{PERMIS_URL}{permis.id}/')
        self.assertEqual(resp.status_code, 404)

    def test_valider_autre_societe_404(self):
        permis = make_permis(self.company)
        resp = self.other_client.post(
            f'{PERMIS_URL}{permis.id}/valider/', {}, format='json')
        self.assertEqual(resp.status_code, 404)
