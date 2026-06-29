"""Tests QHSE21 — Évaluation des risques (document unique) + lignes.

Couvre :
* CRUD scopé société : création d'une évaluation (``company``/``evaluateur``
  posés côté serveur, ``reference`` attribuée côté serveur — jamais lue du
  corps), création de lignes ;
* criticité calculée et stockée côté serveur (gravité × probabilité, jamais
  lue du corps) ;
* statut (brouillon par défaut, transition vers validée/archivée) ;
* résumé de criticité (action ``criticite`` + garde-fou division par zéro) ;
* bornes gravité/probabilité ([1, 5]) ;
* garde-fou de rôle (IsResponsableOrAdmin → 403 pour un rôle normal) ;
* isolation entre sociétés (liste filtrée + détail 404 hors société, FK
  ``evaluation`` d'une autre société refusé).
"""
from datetime import date

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company

from apps.qhse.models import EvaluationRisque, LigneEvaluationRisque
from apps.qhse.selectors import criticite_summary

User = get_user_model()

EVAL_URL = '/api/django/qhse/evaluations-risque/'
LIGNE_URL = '/api/django/qhse/lignes-evaluation-risque/'


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


def make_eval(company, titre='DUERP 2026', statut='brouillon',
              reference='DUER-202606-0001'):
    return EvaluationRisque.objects.create(
        company=company, titre=titre, statut=statut, reference=reference,
        date_evaluation=date(2026, 6, 1))


def make_ligne(evaluation, danger='Chute de hauteur', gravite=4,
               probabilite=3):
    return LigneEvaluationRisque.objects.create(
        company=evaluation.company, evaluation=evaluation, danger=danger,
        gravite=gravite, probabilite=probabilite)


# ── Modèle : criticité calculée côté serveur ─────────────────────────────────

class CriticiteModelTests(TestCase):
    def setUp(self):
        self.company = make_company('co-er', 'CoER')

    def test_criticite_calculee_au_save(self):
        ev = make_eval(self.company)
        ligne = make_ligne(ev, gravite=4, probabilite=3)
        self.assertEqual(ligne.criticite, 12)

    def test_criticite_recalculee_a_la_modification(self):
        ev = make_eval(self.company)
        ligne = make_ligne(ev, gravite=2, probabilite=2)
        self.assertEqual(ligne.criticite, 4)
        ligne.gravite = 5
        ligne.probabilite = 5
        ligne.save()
        self.assertEqual(ligne.criticite, 25)

    def test_summary_garde_fou_division_zero(self):
        ev = make_eval(self.company)
        summary = criticite_summary(ev)
        self.assertEqual(summary['nb_lignes'], 0)
        self.assertIsNone(summary['criticite_max'])
        self.assertIsNone(summary['criticite_moyenne'])

    def test_summary_agrege_lignes(self):
        ev = make_eval(self.company)
        make_ligne(ev, gravite=4, probabilite=3)   # 12 → élevée
        make_ligne(ev, gravite=5, probabilite=5)   # 25 → critique
        make_ligne(ev, gravite=1, probabilite=2)   # 2  → faible
        summary = criticite_summary(ev)
        self.assertEqual(summary['nb_lignes'], 3)
        self.assertEqual(summary['criticite_max'], 25)
        self.assertEqual(summary['criticite_moyenne'], round((12 + 25 + 2) / 3,
                                                             2))
        self.assertEqual(summary['par_niveau']['faible'], 1)
        self.assertEqual(summary['par_niveau']['elevee'], 1)
        self.assertEqual(summary['par_niveau']['critique'], 1)


# ── API : CRUD scopé société ─────────────────────────────────────────────────

class EvaluationRisqueApiTests(TestCase):
    def setUp(self):
        self.company = make_company('co-er-api', 'CoERApi')
        self.other_company = make_company('co-er-api-2', 'CoERApi2')
        self.user = make_user(self.company, 'er-resp')
        self.client_api = auth_client(self.user)
        self.other_user = make_user(self.other_company, 'er-resp-2')
        self.other_client = auth_client(self.other_user)

    def test_creation_pose_company_et_evaluateur_et_reference(self):
        resp = self.client_api.post(
            EVAL_URL, {'titre': 'Évaluation atelier'}, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        ev = EvaluationRisque.objects.get(id=resp.data['id'])
        self.assertEqual(ev.company, self.company)
        self.assertEqual(ev.evaluateur, self.user)
        self.assertEqual(ev.statut, 'brouillon')
        # Référence attribuée côté serveur (préfixe DUER-AAAAMM-NNNN).
        self.assertTrue(ev.reference.startswith('DUER-'))
        self.assertTrue(resp.data['reference'].startswith('DUER-'))

    def test_company_jamais_lue_du_corps(self):
        resp = self.client_api.post(
            EVAL_URL,
            {'titre': 'X', 'company': self.other_company.id},
            format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        ev = EvaluationRisque.objects.get(id=resp.data['id'])
        self.assertEqual(ev.company, self.company)

    def test_reference_jamais_lue_du_corps(self):
        resp = self.client_api.post(
            EVAL_URL,
            {'titre': 'X', 'reference': 'HACK-0001'},
            format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        self.assertNotEqual(resp.data['reference'], 'HACK-0001')

    def test_references_uniques_par_societe(self):
        r1 = self.client_api.post(EVAL_URL, {'titre': 'A'}, format='json')
        r2 = self.client_api.post(EVAL_URL, {'titre': 'B'}, format='json')
        self.assertNotEqual(r1.data['reference'], r2.data['reference'])

    def test_transition_statut(self):
        ev = make_eval(self.company)
        resp = self.client_api.patch(
            f'{EVAL_URL}{ev.id}/', {'statut': 'validee'}, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        ev.refresh_from_db()
        self.assertEqual(ev.statut, 'validee')

    def test_filtre_statut(self):
        make_eval(self.company, statut='brouillon',
                  reference='DUER-202606-0001')
        make_eval(self.company, statut='archivee',
                  reference='DUER-202606-0002')
        resp = self.client_api.get(EVAL_URL, {'statut': 'archivee'})
        statuts = [r['statut'] for r in rows(resp)]
        self.assertEqual(statuts, ['archivee'])

    def test_action_criticite(self):
        ev = make_eval(self.company)
        make_ligne(ev, gravite=5, probabilite=4)   # 20
        make_ligne(ev, gravite=1, probabilite=1)   # 1
        resp = self.client_api.get(f'{EVAL_URL}{ev.id}/criticite/')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(resp.data['nb_lignes'], 2)
        self.assertEqual(resp.data['criticite_max'], 20)
        self.assertEqual(resp.data['criticite_moyenne'], 10.5)

    def test_action_criticite_vide(self):
        ev = make_eval(self.company)
        resp = self.client_api.get(f'{EVAL_URL}{ev.id}/criticite/')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(resp.data['nb_lignes'], 0)
        self.assertIsNone(resp.data['criticite_moyenne'])

    def test_role_normal_refuse(self):
        normal = make_user(self.company, 'er-normal', role='normal')
        resp = auth_client(normal).get(EVAL_URL)
        self.assertEqual(resp.status_code, 403)

    def test_isolation_societe_liste(self):
        make_eval(self.company, reference='DUER-202606-0001')
        make_eval(self.other_company, reference='DUER-202606-0001')
        resp = self.other_client.get(EVAL_URL)
        ids = {r['id'] for r in rows(resp)}
        self.assertEqual(
            ids,
            set(EvaluationRisque.objects.filter(
                company=self.other_company).values_list('id', flat=True)))

    def test_isolation_societe_detail_404(self):
        ev = make_eval(self.company)
        resp = self.other_client.get(f'{EVAL_URL}{ev.id}/')
        self.assertEqual(resp.status_code, 404)


# ── API : lignes ─────────────────────────────────────────────────────────────

class LigneEvaluationRisqueApiTests(TestCase):
    def setUp(self):
        self.company = make_company('co-ligne', 'CoLigne')
        self.other_company = make_company('co-ligne-2', 'CoLigne2')
        self.user = make_user(self.company, 'ligne-resp')
        self.client_api = auth_client(self.user)
        self.ev = make_eval(self.company)

    def test_creation_ligne_calcule_criticite(self):
        resp = self.client_api.post(
            LIGNE_URL,
            {'evaluation': self.ev.id, 'danger': 'Électrisation',
             'gravite': 4, 'probabilite': 2,
             'mesures_prevention': 'Consignation'},
            format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        self.assertEqual(resp.data['criticite'], 8)
        ligne = LigneEvaluationRisque.objects.get(id=resp.data['id'])
        self.assertEqual(ligne.company, self.company)

    def test_criticite_du_corps_ignoree(self):
        resp = self.client_api.post(
            LIGNE_URL,
            {'evaluation': self.ev.id, 'danger': 'Bruit',
             'gravite': 2, 'probabilite': 2, 'criticite': 999},
            format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        self.assertEqual(resp.data['criticite'], 4)

    def test_gravite_hors_bornes_refusee(self):
        for bad in (0, 6):
            resp = self.client_api.post(
                LIGNE_URL,
                {'evaluation': self.ev.id, 'danger': 'X',
                 'gravite': bad, 'probabilite': 2},
                format='json')
            self.assertEqual(resp.status_code, 400, (bad, resp.data))

    def test_probabilite_hors_bornes_refusee(self):
        resp = self.client_api.post(
            LIGNE_URL,
            {'evaluation': self.ev.id, 'danger': 'X',
             'gravite': 2, 'probabilite': 9},
            format='json')
        self.assertEqual(resp.status_code, 400, resp.data)

    def test_filtre_par_evaluation(self):
        autre = make_eval(self.company, reference='DUER-202606-0002')
        make_ligne(self.ev, danger='A')
        make_ligne(autre, danger='B')
        resp = self.client_api.get(LIGNE_URL, {'evaluation': self.ev.id})
        dangers = [r['danger'] for r in rows(resp)]
        self.assertEqual(dangers, ['A'])

    def test_evaluation_autre_societe_refusee(self):
        autre_ev = make_eval(self.other_company,
                             reference='DUER-202606-0001')
        resp = self.client_api.post(
            LIGNE_URL,
            {'evaluation': autre_ev.id, 'danger': 'X',
             'gravite': 1, 'probabilite': 1},
            format='json')
        self.assertEqual(resp.status_code, 400, resp.data)

    def test_role_normal_refuse(self):
        normal = make_user(self.company, 'ligne-normal', role='normal')
        resp = auth_client(normal).get(LIGNE_URL)
        self.assertEqual(resp.status_code, 403)
