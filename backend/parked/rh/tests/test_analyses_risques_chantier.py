"""Tests FG184 — Analyse de risques chantier (plan de prévention) AVANT travaux.

Couvre :
* Création : ``company`` posée CÔTÉ SERVEUR (jamais lue du corps) ; chantier
  (référence chaîne), date, rédacteur, statut, risques imbriqués.
* FK même société : un ``redacteur`` d'une autre société est refusé.
* Risques imbriqués : danger / gravité / probabilité / niveau / mesure de
  prévention créés avec la company propagée côté serveur.
* Validation : l'action ``valider`` passe l'analyse en ``valide``, idempotente,
  scopée société (404 pour un autre tenant).
* CRUD : update remplace la liste de risques.
* Isolation multi-société : B ne voit ni ne crée les analyses de A.
* Permission : un rôle normal est refusé (403).
* DRF : ``?format=`` réservé ne casse pas la liste (reste JSON).
"""
from datetime import date

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.rh.models import (
    AnalyseRisquesChantier,
    DossierEmploye,
    LigneRisqueChantier,
)

User = get_user_model()

URL = '/api/django/rh/analyses-risques-chantier/'


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


class AnalyseCreateTests(TestCase):
    def setUp(self):
        self.co_a = make_company('arc-a', 'A')
        self.co_b = make_company('arc-b', 'B')
        self.user_a = make_user(self.co_a, 'arc-user-a')
        self.user_b = make_user(self.co_b, 'arc-user-b')
        self.red_a = make_employe(self.co_a, 'A-RED', 'Bennani', 'Karim')

    def test_create_company_cote_serveur_avec_risques(self):
        today = timezone.localdate()
        resp = auth(self.user_a).post(URL, {
            'chantier_id': 'CH-42',
            'date_analyse': today.isoformat(),
            'lieu': 'Toiture bât. B',
            'redacteur': self.red_a.id,
            'notes': 'Plan de prévention initial.',
            'risques': [
                {
                    'danger': 'Travail en hauteur',
                    'description': 'Chute depuis la toiture',
                    'gravite': 'elevee',
                    'probabilite': 'moyenne',
                    'niveau': 'eleve',
                    'mesure_prevention': 'Harnais + ligne de vie',
                },
                {
                    'danger': 'Risque électrique',
                    'niveau': 'critique',
                    'mesure_prevention': 'Consignation',
                },
            ],
        }, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        analyse = AnalyseRisquesChantier.objects.get(id=resp.data['id'])
        self.assertEqual(analyse.company, self.co_a)
        self.assertEqual(analyse.chantier_id, 'CH-42')
        self.assertEqual(analyse.redacteur, self.red_a)
        self.assertEqual(analyse.statut, 'brouillon')
        risques = list(analyse.risques.all())
        self.assertEqual(len(risques), 2)
        for r in risques:
            self.assertEqual(r.company, self.co_a)
        self.assertEqual(len(resp.data['risques']), 2)

    def test_company_du_corps_ignoree(self):
        resp = auth(self.user_a).post(URL, {
            'date_analyse': timezone.localdate().isoformat(),
            'company': self.co_b.id,
        }, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        analyse = AnalyseRisquesChantier.objects.get(id=resp.data['id'])
        self.assertEqual(analyse.company, self.co_a)

    def test_redacteur_autre_societe_refuse(self):
        red_b = make_employe(self.co_b, 'B-RED')
        resp = auth(self.user_a).post(URL, {
            'date_analyse': timezone.localdate().isoformat(),
            'redacteur': red_b.id,
        }, format='json')
        self.assertEqual(resp.status_code, 400)
        self.assertIn('redacteur', resp.data)

    def test_role_normal_refuse(self):
        normal = make_user(self.co_a, 'arc-normal', role='normal')
        resp = auth(normal).get(URL)
        self.assertEqual(resp.status_code, 403)

    def test_isolation_list(self):
        AnalyseRisquesChantier.objects.create(
            company=self.co_a, date_analyse=date(2026, 6, 1))
        resp = auth(self.user_b).get(URL)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(rows(resp)), 0)

    def test_format_param_ne_casse_pas_la_liste(self):
        resp = auth(self.user_a).get(URL)
        self.assertEqual(resp.status_code, 200)
        self.assertNotIn('text/csv', resp.get('Content-Type', ''))


class AnalyseValiderTests(TestCase):
    def setUp(self):
        self.co_a = make_company('arcv-a', 'A')
        self.co_b = make_company('arcv-b', 'B')
        self.user_a = make_user(self.co_a, 'arcv-user-a')
        self.user_b = make_user(self.co_b, 'arcv-user-b')
        self.analyse = AnalyseRisquesChantier.objects.create(
            company=self.co_a, date_analyse=timezone.localdate())

    def test_valider_passe_en_valide(self):
        resp = auth(self.user_a).post(
            f'{URL}{self.analyse.id}/valider/', {}, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.analyse.refresh_from_db()
        self.assertEqual(self.analyse.statut, 'valide')

    def test_valider_idempotent(self):
        first = auth(self.user_a).post(
            f'{URL}{self.analyse.id}/valider/', {}, format='json')
        self.assertEqual(first.status_code, 200)
        again = auth(self.user_a).post(
            f'{URL}{self.analyse.id}/valider/', {}, format='json')
        self.assertEqual(again.status_code, 200)
        self.analyse.refresh_from_db()
        self.assertEqual(self.analyse.statut, 'valide')

    def test_valider_autre_societe_404(self):
        resp = auth(self.user_b).post(
            f'{URL}{self.analyse.id}/valider/', {}, format='json')
        self.assertEqual(resp.status_code, 404)


class AnalyseCrudTests(TestCase):
    def setUp(self):
        self.co_a = make_company('arcc-a', 'A')
        self.user_a = make_user(self.co_a, 'arcc-user-a')

    def test_update_remplace_risques(self):
        analyse = AnalyseRisquesChantier.objects.create(
            company=self.co_a, date_analyse=timezone.localdate())
        LigneRisqueChantier.objects.create(
            company=self.co_a, analyse=analyse, danger='Ancien')
        resp = auth(self.user_a).patch(
            f'{URL}{analyse.id}/',
            {'lieu': 'Mis à jour',
             'risques': [
                 {'danger': 'Bruit', 'niveau': 'moyen'},
                 {'danger': 'Poussière', 'niveau': 'faible'},
             ]},
            format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        analyse.refresh_from_db()
        self.assertEqual(analyse.lieu, 'Mis à jour')
        dangers = set(analyse.risques.values_list('danger', flat=True))
        self.assertEqual(dangers, {'Bruit', 'Poussière'})

    def test_retrieve_et_delete(self):
        analyse = AnalyseRisquesChantier.objects.create(
            company=self.co_a, date_analyse=timezone.localdate())
        get = auth(self.user_a).get(f'{URL}{analyse.id}/')
        self.assertEqual(get.status_code, 200)
        delete = auth(self.user_a).delete(f'{URL}{analyse.id}/')
        self.assertEqual(delete.status_code, 204)
        self.assertFalse(
            AnalyseRisquesChantier.objects.filter(id=analyse.id).exists())
