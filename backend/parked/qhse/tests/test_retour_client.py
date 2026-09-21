"""Tests QHSE19 — Retour client qualité (satisfaction).

Couvre :
* CRUD scopé société : création (``company`` posée côté serveur, jamais lue du
  corps), filtres ``?chantier_id=`` / ``?traite=`` ;
* bornes de la note (``note_satisfaction`` ∈ [1, 5]) ;
* sélecteur ``satisfaction_moyenne`` (globale + par chantier, None si vide) et
  l'action ``moyenne`` ;
* garde-fou de rôle (IsResponsableOrAdmin → 403 pour un rôle normal) ;
* isolation entre sociétés (liste filtrée + détail 404 hors société).
"""
from datetime import date

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company

from apps.qhse.models import RetourClientQualite
from apps.qhse.selectors import satisfaction_moyenne

User = get_user_model()

URL = '/api/django/qhse/retours-client/'


# ── Helpers ───────────────────────────────────────────────────────────────────

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
    return data['results'] if isinstance(data, dict) and 'results' in data else data


def make_retour(company, note, chantier_id=None, traite=False,
                date_retour=None):
    return RetourClientQualite.objects.create(
        company=company,
        note_satisfaction=note,
        chantier_id=chantier_id,
        traite=traite,
        date_retour=date_retour or date(2026, 6, 1),
    )


# ── Sélecteur : moyenne ─────────────────────────────────────────────────────

class SatisfactionMoyenneTests(TestCase):
    def setUp(self):
        self.company = make_company('co-rc', 'CoRC')
        self.other = make_company('co-rc-2', 'CoRC2')

    def test_moyenne_none_si_aucun_retour(self):
        self.assertIsNone(satisfaction_moyenne(self.company))

    def test_moyenne_globale(self):
        make_retour(self.company, 5)
        make_retour(self.company, 4)
        make_retour(self.company, 3)
        self.assertEqual(satisfaction_moyenne(self.company), 4.0)

    def test_moyenne_par_chantier(self):
        make_retour(self.company, 5, chantier_id=10)
        make_retour(self.company, 1, chantier_id=10)
        make_retour(self.company, 4, chantier_id=20)
        self.assertEqual(
            satisfaction_moyenne(self.company, chantier_id=10), 3.0)
        self.assertEqual(
            satisfaction_moyenne(self.company, chantier_id=20), 4.0)

    def test_moyenne_scopee_societe(self):
        make_retour(self.company, 5)
        make_retour(self.other, 1)
        self.assertEqual(satisfaction_moyenne(self.company), 5.0)


# ── API ─────────────────────────────────────────────────────────────────────

class RetourClientQualiteApiTests(TestCase):
    def setUp(self):
        self.company = make_company('co-rc-api', 'CoAPI')
        self.user = make_user(self.company, 'rc-api-user')
        self.client_api = auth_client(self.user)
        self.other_company = make_company('co-rc-api-2', 'CoAPI2')
        self.other_user = make_user(self.other_company, 'rc-api-other')
        self.other_client = auth_client(self.other_user)

    def test_create_pose_company_serveur(self):
        resp = self.client_api.post(
            URL,
            {'note_satisfaction': 5, 'commentaire': 'Très satisfait',
             'date_retour': '2026-06-10', 'canal': 'whatsapp',
             'chantier_id': 42},
            format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        retour = RetourClientQualite.objects.get(id=resp.data['id'])
        self.assertEqual(retour.company_id, self.company.id)
        self.assertEqual(retour.note_satisfaction, 5)
        self.assertEqual(retour.chantier_id, 42)
        self.assertEqual(resp.data['canal_display'], 'WhatsApp')

    def test_create_ignore_company_du_corps(self):
        resp = self.client_api.post(
            URL,
            {'note_satisfaction': 3, 'date_retour': '2026-06-10',
             'company': self.other_company.id},
            format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        retour = RetourClientQualite.objects.get(id=resp.data['id'])
        self.assertEqual(retour.company_id, self.company.id)

    def test_note_hors_bornes_refusee(self):
        for bad in (0, 6, 10):
            resp = self.client_api.post(
                URL,
                {'note_satisfaction': bad, 'date_retour': '2026-06-10'},
                format='json')
            self.assertEqual(resp.status_code, 400, (bad, resp.data))

    def test_filtre_chantier(self):
        make_retour(self.company, 5, chantier_id=10)
        make_retour(self.company, 4, chantier_id=20)
        resp = self.client_api.get(URL, {'chantier_id': 10})
        results = rows(resp)
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]['chantier_id'], 10)

    def test_filtre_traite(self):
        make_retour(self.company, 5, traite=True)
        make_retour(self.company, 4, traite=False)
        resp = self.client_api.get(URL, {'traite': '1'})
        self.assertEqual(len(rows(resp)), 1)
        resp = self.client_api.get(URL, {'traite': '0'})
        self.assertEqual(len(rows(resp)), 1)

    def test_moyenne_endpoint(self):
        make_retour(self.company, 5)
        make_retour(self.company, 3)
        resp = self.client_api.get(f'{URL}moyenne/')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(resp.data['moyenne'], 4.0)
        self.assertEqual(resp.data['total'], 2)

    def test_moyenne_endpoint_par_chantier(self):
        make_retour(self.company, 5, chantier_id=7)
        make_retour(self.company, 1, chantier_id=8)
        resp = self.client_api.get(f'{URL}moyenne/', {'chantier_id': 7})
        self.assertEqual(resp.data['moyenne'], 5.0)
        self.assertEqual(resp.data['total'], 1)

    def test_moyenne_endpoint_vide(self):
        resp = self.client_api.get(f'{URL}moyenne/')
        self.assertEqual(resp.status_code, 200)
        self.assertIsNone(resp.data['moyenne'])
        self.assertEqual(resp.data['total'], 0)

    def test_role_normal_refuse(self):
        normal = make_user(self.company, 'rc-normal', role='normal')
        resp = auth_client(normal).get(URL)
        self.assertEqual(resp.status_code, 403)

    def test_isolation_societe_liste(self):
        make_retour(self.company, 5)
        make_retour(self.other_company, 1)
        resp = self.other_client.get(URL)
        notes = [r['note_satisfaction'] for r in rows(resp)]
        self.assertEqual(notes, [1])

    def test_isolation_societe_detail_404(self):
        retour = make_retour(self.company, 5)
        resp = self.other_client.get(f'{URL}{retour.id}/')
        self.assertEqual(resp.status_code, 404)
