"""Tests FG190 — Entretiens & évaluations annuelles (appréciation RH).

Couvre :
* Campagne : création ``company`` posée CÔTÉ SERVEUR (jamais lue du corps),
  CRUD, action ``cloturer`` (idempotente, scopée société), isolation.
* Entretien (EvaluationEmploye) : création avec objectifs imbriqués (company
  propagée côté serveur) ; FK ``employe`` / ``evaluateur`` / ``campagne``
  d'une autre société refusés ; unicité (campagne, employe) ; transitions de
  statut via ``valider`` (idempotente, 404 autre tenant) ; update remplace les
  objectifs ; isolation multi-société ; permission (rôle normal 403).
* DRF : ``?format=`` réservé ne casse pas la liste (reste JSON).
"""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.db import IntegrityError
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.rh.models import (
    CampagneEvaluation,
    DossierEmploye,
    EvaluationEmploye,
    ObjectifIndividuel,
)

User = get_user_model()

CAMP_URL = '/api/django/rh/campagnes-evaluation/'
EVAL_URL = '/api/django/rh/evaluations-employe/'


def make_company(slug, nom):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


def make_user(company, username, role='responsable'):
    return User.objects.create_user(
        username=username, password='x', company=company, role_legacy=role)


def make_employe(company, matricule, nom='Nom', prenom='Prenom'):
    return DossierEmploye.objects.create(
        company=company, matricule=matricule, nom=nom, prenom=prenom)


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


def rows(resp):
    data = resp.data
    return data['results'] if isinstance(data, dict) and 'results' in data \
        else data


class CampagneTests(TestCase):
    def setUp(self):
        self.co_a = make_company('eval-camp-a', 'A')
        self.co_b = make_company('eval-camp-b', 'B')
        self.user_a = make_user(self.co_a, 'eval-camp-user-a')
        self.user_b = make_user(self.co_b, 'eval-camp-user-b')

    def test_create_company_cote_serveur(self):
        resp = auth(self.user_a).post(CAMP_URL, {
            'intitule': 'Entretiens annuels 2026',
            'annee': 2026,
            'periode': 'S2',
            'date_debut': '2026-09-01',
            'date_fin': '2026-12-15',
            'description': 'Cycle annuel.',
        }, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        camp = CampagneEvaluation.objects.get(id=resp.data['id'])
        self.assertEqual(camp.company, self.co_a)
        self.assertEqual(camp.annee, 2026)
        self.assertEqual(camp.statut, 'ouverte')

    def test_company_du_corps_ignoree(self):
        resp = auth(self.user_a).post(CAMP_URL, {
            'intitule': 'C', 'annee': 2026, 'company': self.co_b.id,
        }, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        camp = CampagneEvaluation.objects.get(id=resp.data['id'])
        self.assertEqual(camp.company, self.co_a)

    def test_cloturer_passe_en_cloturee_idempotent(self):
        camp = CampagneEvaluation.objects.create(
            company=self.co_a, intitule='C', annee=2026)
        first = auth(self.user_a).post(
            f'{CAMP_URL}{camp.id}/cloturer/', {}, format='json')
        self.assertEqual(first.status_code, 200, first.data)
        camp.refresh_from_db()
        self.assertEqual(camp.statut, 'cloturee')
        again = auth(self.user_a).post(
            f'{CAMP_URL}{camp.id}/cloturer/', {}, format='json')
        self.assertEqual(again.status_code, 200)
        camp.refresh_from_db()
        self.assertEqual(camp.statut, 'cloturee')

    def test_cloturer_autre_societe_404(self):
        camp = CampagneEvaluation.objects.create(
            company=self.co_a, intitule='C', annee=2026)
        resp = auth(self.user_b).post(
            f'{CAMP_URL}{camp.id}/cloturer/', {}, format='json')
        self.assertEqual(resp.status_code, 404)

    def test_filtre_annee_statut(self):
        CampagneEvaluation.objects.create(
            company=self.co_a, intitule='C2025', annee=2025)
        CampagneEvaluation.objects.create(
            company=self.co_a, intitule='C2026', annee=2026,
            statut='cloturee')
        resp = auth(self.user_a).get(f'{CAMP_URL}?annee=2026')
        self.assertEqual(len(rows(resp)), 1)
        resp2 = auth(self.user_a).get(f'{CAMP_URL}?statut=cloturee')
        self.assertEqual(len(rows(resp2)), 1)

    def test_isolation_list(self):
        CampagneEvaluation.objects.create(
            company=self.co_a, intitule='C', annee=2026)
        resp = auth(self.user_b).get(CAMP_URL)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(rows(resp)), 0)

    def test_role_normal_refuse(self):
        normal = make_user(self.co_a, 'eval-camp-normal', role='normal')
        resp = auth(normal).get(CAMP_URL)
        self.assertEqual(resp.status_code, 403)

    def test_format_param_ne_casse_pas_la_liste(self):
        resp = auth(self.user_a).get(CAMP_URL)
        self.assertEqual(resp.status_code, 200)
        self.assertNotIn('text/csv', resp.get('Content-Type', ''))


class EvaluationTests(TestCase):
    def setUp(self):
        self.co_a = make_company('eval-emp-a', 'A')
        self.co_b = make_company('eval-emp-b', 'B')
        self.user_a = make_user(self.co_a, 'eval-emp-user-a')
        self.user_b = make_user(self.co_b, 'eval-emp-user-b')
        self.camp_a = CampagneEvaluation.objects.create(
            company=self.co_a, intitule='2026', annee=2026)
        self.emp_a = make_employe(self.co_a, 'A-EMP', 'Alaoui', 'Sara')
        self.mgr_a = make_employe(self.co_a, 'A-MGR', 'Idrissi', 'Youssef')

    def test_create_avec_objectifs_company_cote_serveur(self):
        resp = auth(self.user_a).post(EVAL_URL, {
            'campagne': self.camp_a.id,
            'employe': self.emp_a.id,
            'evaluateur': self.mgr_a.id,
            'date_entretien': '2026-10-01',
            'note_globale': '4.5',
            'synthese': 'Bon collaborateur.',
            'objectifs': [
                {
                    'libelle': 'Certification onduleurs',
                    'ponderation': '40.00',
                    'cible': '2 certifs',
                    'atteinte': '2 obtenues',
                    'note': '5',
                },
                {'libelle': 'Réduire les retards', 'ponderation': '60.00'},
            ],
        }, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        ev = EvaluationEmploye.objects.get(id=resp.data['id'])
        self.assertEqual(ev.company, self.co_a)
        self.assertEqual(ev.note_globale, Decimal('4.5'))
        self.assertEqual(ev.statut, 'planifie')
        objs = list(ev.objectifs.all())
        self.assertEqual(len(objs), 2)
        for o in objs:
            self.assertEqual(o.company, self.co_a)
        self.assertEqual(len(resp.data['objectifs']), 2)

    def test_campagne_autre_societe_refuse(self):
        camp_b = CampagneEvaluation.objects.create(
            company=self.co_b, intitule='B', annee=2026)
        resp = auth(self.user_a).post(EVAL_URL, {
            'campagne': camp_b.id, 'employe': self.emp_a.id,
        }, format='json')
        self.assertEqual(resp.status_code, 400)
        self.assertIn('campagne', resp.data)

    def test_employe_autre_societe_refuse(self):
        emp_b = make_employe(self.co_b, 'B-EMP')
        resp = auth(self.user_a).post(EVAL_URL, {
            'campagne': self.camp_a.id, 'employe': emp_b.id,
        }, format='json')
        self.assertEqual(resp.status_code, 400)
        self.assertIn('employe', resp.data)

    def test_evaluateur_autre_societe_refuse(self):
        mgr_b = make_employe(self.co_b, 'B-MGR')
        resp = auth(self.user_a).post(EVAL_URL, {
            'campagne': self.camp_a.id, 'employe': self.emp_a.id,
            'evaluateur': mgr_b.id,
        }, format='json')
        self.assertEqual(resp.status_code, 400)
        self.assertIn('evaluateur', resp.data)

    def test_unique_campagne_employe(self):
        EvaluationEmploye.objects.create(
            company=self.co_a, campagne=self.camp_a, employe=self.emp_a)
        with self.assertRaises(IntegrityError):
            EvaluationEmploye.objects.create(
                company=self.co_a, campagne=self.camp_a, employe=self.emp_a)

    def test_valider_transition_idempotent(self):
        ev = EvaluationEmploye.objects.create(
            company=self.co_a, campagne=self.camp_a, employe=self.emp_a)
        self.assertEqual(ev.statut, 'planifie')
        resp = auth(self.user_a).post(
            f'{EVAL_URL}{ev.id}/valider/', {}, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        ev.refresh_from_db()
        self.assertEqual(ev.statut, 'valide')
        again = auth(self.user_a).post(
            f'{EVAL_URL}{ev.id}/valider/', {}, format='json')
        self.assertEqual(again.status_code, 200)
        ev.refresh_from_db()
        self.assertEqual(ev.statut, 'valide')

    def test_valider_autre_societe_404(self):
        ev = EvaluationEmploye.objects.create(
            company=self.co_a, campagne=self.camp_a, employe=self.emp_a)
        resp = auth(self.user_b).post(
            f'{EVAL_URL}{ev.id}/valider/', {}, format='json')
        self.assertEqual(resp.status_code, 404)

    def test_patch_statut_realise(self):
        ev = EvaluationEmploye.objects.create(
            company=self.co_a, campagne=self.camp_a, employe=self.emp_a)
        resp = auth(self.user_a).patch(
            f'{EVAL_URL}{ev.id}/', {'statut': 'realise'}, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        ev.refresh_from_db()
        self.assertEqual(ev.statut, 'realise')

    def test_update_remplace_objectifs(self):
        ev = EvaluationEmploye.objects.create(
            company=self.co_a, campagne=self.camp_a, employe=self.emp_a)
        ObjectifIndividuel.objects.create(
            company=self.co_a, evaluation=ev, libelle='Ancien')
        resp = auth(self.user_a).patch(
            f'{EVAL_URL}{ev.id}/',
            {'objectifs': [
                {'libelle': 'Nouveau 1'},
                {'libelle': 'Nouveau 2'},
            ]},
            format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        libelles = set(ev.objectifs.values_list('libelle', flat=True))
        self.assertEqual(libelles, {'Nouveau 1', 'Nouveau 2'})

    def test_filtre_campagne_employe_statut(self):
        ev = EvaluationEmploye.objects.create(
            company=self.co_a, campagne=self.camp_a, employe=self.emp_a,
            statut='realise')
        EvaluationEmploye.objects.create(
            company=self.co_a, campagne=self.camp_a, employe=self.mgr_a)
        resp = auth(self.user_a).get(f'{EVAL_URL}?employe={self.emp_a.id}')
        self.assertEqual(len(rows(resp)), 1)
        resp2 = auth(self.user_a).get(f'{EVAL_URL}?statut=realise')
        self.assertEqual(len(rows(resp2)), 1)
        resp3 = auth(self.user_a).get(f'{EVAL_URL}?campagne={self.camp_a.id}')
        self.assertEqual(len(rows(resp3)), 2)
        self.assertEqual(ev.statut, 'realise')

    def test_isolation_list(self):
        EvaluationEmploye.objects.create(
            company=self.co_a, campagne=self.camp_a, employe=self.emp_a)
        resp = auth(self.user_b).get(EVAL_URL)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(rows(resp)), 0)

    def test_role_normal_refuse(self):
        normal = make_user(self.co_a, 'eval-emp-normal', role='normal')
        resp = auth(normal).get(EVAL_URL)
        self.assertEqual(resp.status_code, 403)

    def test_format_param_ne_casse_pas_la_liste(self):
        resp = auth(self.user_a).get(EVAL_URL)
        self.assertEqual(resp.status_code, 200)
        self.assertNotIn('text/csv', resp.get('Content-Type', ''))
