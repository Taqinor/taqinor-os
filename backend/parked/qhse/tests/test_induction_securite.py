"""Tests QHSE26 — Accueil / induction sécurité (accès site, sous-traitants).

Couvre :
* CRUD scopé société : création d'un accueil (``company`` posée côté serveur —
  jamais lue du corps) ;
* le parcours sous-traitant externe (``personne_nom`` libre +
  ``est_sous_traitant`` + ``entreprise_externe``, sans dossier RH) ;
* le rattachement optionnel à un salarié interne (``employe`` →
  ``rh.DossierEmploye``), avec garde-fou inter-société ;
* l'action ``acquitter`` (pose ``acquittement`` + horodate ``acquittement_le``),
  ``acquittement_le`` jamais lu du corps à la création ;
* filtres ``?chantier_id=`` / ``?est_sous_traitant=`` ;
* garde-fou de rôle (IsResponsableOrAdmin → 403 pour un rôle normal) ;
* isolation entre sociétés (liste filtrée, détail 404 hors société).
"""
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company

from apps.qhse.models import InductionSecurite
from apps.rh.models import DossierEmploye

User = get_user_model()

URL = '/api/django/qhse/inductions-securite/'


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


def make_employe(company, matricule='M001', prenom='Karim', nom='Bennani'):
    return DossierEmploye.objects.create(
        company=company, matricule=matricule, prenom=prenom, nom=nom)


def make_induction(company, personne_nom='Visiteur', **kwargs):
    return InductionSecurite.objects.create(
        company=company, personne_nom=personne_nom, **kwargs)


# ── API : CRUD scopé société ─────────────────────────────────────────────────

class InductionSecuriteApiTests(TestCase):
    def setUp(self):
        self.company = make_company('co-induc-api', 'CoInducApi')
        self.other_company = make_company('co-induc-api-2', 'CoInducApi2')
        self.user = make_user(self.company, 'induc-resp')
        self.client_api = auth_client(self.user)
        self.other_user = make_user(self.other_company, 'induc-resp-2')
        self.other_client = auth_client(self.other_user)

    def test_creation_pose_company_cote_serveur(self):
        resp = self.client_api.post(
            URL,
            {'personne_nom': 'Mohamed Alami', 'chantier_id': 7,
             'anime_par': 'HSE Chef', 'themes': 'EPI, balisage, secours',
             'date_induction': '2026-06-15'},
            format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        ind = InductionSecurite.objects.get(id=resp.data['id'])
        self.assertEqual(ind.company, self.company)
        self.assertEqual(ind.personne_nom, 'Mohamed Alami')
        self.assertEqual(ind.chantier_id, 7)
        self.assertFalse(ind.acquittement)

    def test_company_jamais_lue_du_corps(self):
        resp = self.client_api.post(
            URL,
            {'personne_nom': 'X', 'company': self.other_company.id},
            format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        ind = InductionSecurite.objects.get(id=resp.data['id'])
        self.assertEqual(ind.company, self.company)

    def test_acquittement_le_jamais_lu_du_corps_a_la_creation(self):
        resp = self.client_api.post(
            URL,
            {'personne_nom': 'X',
             'acquittement': True,
             'acquittement_le': '2026-06-10T10:00:00Z'},
            format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        ind = InductionSecurite.objects.get(id=resp.data['id'])
        self.assertIsNone(ind.acquittement_le)

    # ── Parcours sous-traitant externe ───────────────────────────────────────

    def test_sous_traitant_externe(self):
        resp = self.client_api.post(
            URL,
            {'personne_nom': 'Youssef Externe',
             'est_sous_traitant': True,
             'entreprise_externe': 'SARL Montage Solaire',
             'validite_jours': 90},
            format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        ind = InductionSecurite.objects.get(id=resp.data['id'])
        self.assertTrue(ind.est_sous_traitant)
        self.assertEqual(ind.entreprise_externe, 'SARL Montage Solaire')
        self.assertIsNone(ind.employe_id)
        self.assertEqual(ind.validite_jours, 90)

    # ── Rattachement salarié interne + garde-fou société ─────────────────────

    def test_employe_interne_relie(self):
        emp = make_employe(self.company)
        resp = self.client_api.post(
            URL,
            {'personne_nom': 'Karim Bennani', 'employe': emp.id},
            format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        ind = InductionSecurite.objects.get(id=resp.data['id'])
        self.assertEqual(ind.employe_id, emp.id)

    def test_employe_autre_societe_refuse(self):
        emp_autre = make_employe(self.other_company, matricule='M999')
        resp = self.client_api.post(
            URL,
            {'personne_nom': 'X', 'employe': emp_autre.id},
            format='json')
        self.assertEqual(resp.status_code, 400, resp.data)

    # ── Action acquitter ─────────────────────────────────────────────────────

    def test_acquitter(self):
        ind = make_induction(self.company, personne_nom='À signer')
        resp = self.client_api.post(
            f'{URL}{ind.id}/acquitter/', {}, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        ind.refresh_from_db()
        self.assertTrue(ind.acquittement)
        self.assertIsNotNone(ind.acquittement_le)

    def test_acquitter_avec_date_fournie(self):
        ind = make_induction(self.company)
        resp = self.client_api.post(
            f'{URL}{ind.id}/acquitter/',
            {'acquittement_le': '2026-06-12T08:30:00Z'}, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        ind.refresh_from_db()
        self.assertTrue(ind.acquittement)
        self.assertEqual(ind.acquittement_le.year, 2026)
        self.assertEqual(ind.acquittement_le.month, 6)
        self.assertEqual(ind.acquittement_le.day, 12)

    # ── CRUD update / delete ─────────────────────────────────────────────────

    def test_update_et_delete(self):
        ind = make_induction(self.company)
        patch = self.client_api.patch(
            f'{URL}{ind.id}/', {'anime_par': 'Nouveau HSE'}, format='json')
        self.assertEqual(patch.status_code, 200, patch.data)
        ind.refresh_from_db()
        self.assertEqual(ind.anime_par, 'Nouveau HSE')
        delete = self.client_api.delete(f'{URL}{ind.id}/')
        self.assertEqual(delete.status_code, 204)
        self.assertFalse(InductionSecurite.objects.filter(id=ind.id).exists())

    # ── Filtres ──────────────────────────────────────────────────────────────

    def test_filtre_chantier_id(self):
        make_induction(self.company, chantier_id=1)
        make_induction(self.company, chantier_id=2)
        resp = self.client_api.get(URL, {'chantier_id': 2})
        ids = [r['chantier_id'] for r in rows(resp)]
        self.assertEqual(ids, [2])

    def test_filtre_est_sous_traitant(self):
        make_induction(self.company, est_sous_traitant=True)
        make_induction(self.company, est_sous_traitant=False)
        resp = self.client_api.get(URL, {'est_sous_traitant': '1'})
        flags = [r['est_sous_traitant'] for r in rows(resp)]
        self.assertEqual(flags, [True])

    # ── Rôle + isolation société ─────────────────────────────────────────────

    def test_role_normal_refuse(self):
        normal = make_user(self.company, 'induc-normal', role='normal')
        resp = auth_client(normal).get(URL)
        self.assertEqual(resp.status_code, 403)

    def test_isolation_societe_liste(self):
        make_induction(self.company, personne_nom='Mien')
        make_induction(self.other_company, personne_nom='Autre')
        resp = self.other_client.get(URL)
        ids = {r['id'] for r in rows(resp)}
        self.assertEqual(
            ids,
            set(InductionSecurite.objects.filter(
                company=self.other_company).values_list('id', flat=True)))

    def test_isolation_societe_detail_404(self):
        ind = make_induction(self.company)
        resp = self.other_client.get(f'{URL}{ind.id}/')
        self.assertEqual(resp.status_code, 404)

    def test_acquitter_autre_societe_404(self):
        ind = make_induction(self.company)
        resp = self.other_client.post(
            f'{URL}{ind.id}/acquitter/', {}, format='json')
        self.assertEqual(resp.status_code, 404)
