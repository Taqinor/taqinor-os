"""Tests de la génération IA d'un plan de tâches depuis le devis (XPRJ29).

``proposer_plan_taches_ia`` délègue au service FastAPI ``POST /projets/
generer-plan`` (mocké via ``requests.post`` — jamais de réseau réel dans les
tests) ; ``materialiser_plan_taches`` matérialise ensuite le plan CONFIRMÉ
(phases/tâches/dépendances FS), sans jamais rien écrire avant confirmation.

Couvre : proposition JSON valide sur un devis type ; confirmation crée les
tâches/dépendances ; sans clé LLM (503 FastAPI) → 503 côté ERP, propre, sans
écriture ; réponse FastAPI invalide → erreur métier propre ; isolation
société ; aucune tâche créée tant que ``confirmer-plan-ia`` n'est pas appelé.
"""
from unittest import mock

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company

from apps.gestion_projet import services
from apps.gestion_projet.models import (
    DependanceTache, Projet, Tache,
)

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


def _fake_response(status_code, json_payload=None):
    resp = mock.Mock()
    resp.status_code = status_code
    resp.json.return_value = json_payload or {}
    return resp


_DEVIS_DATA = {
    'id': 1, 'montant_materiel': 100000, 'montant_main_oeuvre': 20000,
    'nb_lignes_materiel': 5, 'nb_lignes_main_oeuvre': 2,
}

_PLAN_PROPOSE = {
    'taches': [
        {'code': '1', 'libelle': 'Étude technique', 'phase': 'etude',
         'duree_jours': 2, 'dependances_fs': []},
        {'code': '2', 'libelle': 'Pose des panneaux', 'phase': 'pose',
         'duree_jours': 5, 'dependances_fs': ['1']},
    ]
}


class ProposerPlanTachesIAServiceTests(TestCase):
    def setUp(self):
        self.co = make_company('gp-x29-svc', 'S')
        self.user = make_user(self.co, 'gp-x29-svc-u')

    def test_proposition_json_valide(self):
        with mock.patch(
                'requests.post',
                return_value=_fake_response(200, _PLAN_PROPOSE)):
            plan = services.proposer_plan_taches_ia(
                _DEVIS_DATA, 'residentiel', user=self.user)
        self.assertEqual(len(plan['taches']), 2)
        self.assertEqual(plan['taches'][0]['code'], '1')

    def test_sans_cle_llm_503_leve_indisponible(self):
        with mock.patch(
                'requests.post', return_value=_fake_response(503)):
            with self.assertRaises(services.PlanTachesIAIndisponible):
                services.proposer_plan_taches_ia(
                    _DEVIS_DATA, 'residentiel', user=self.user)

    def test_service_injoignable_leve_indisponible(self):
        import requests
        with mock.patch(
                'requests.post',
                side_effect=requests.ConnectionError('refused')):
            with self.assertRaises(services.PlanTachesIAIndisponible):
                services.proposer_plan_taches_ia(
                    _DEVIS_DATA, 'residentiel', user=self.user)

    def test_reponse_invalide_leve_erreur_metier(self):
        with mock.patch(
                'requests.post', return_value=_fake_response(502)):
            with self.assertRaises(services.PlanTachesIAError):
                services.proposer_plan_taches_ia(
                    _DEVIS_DATA, 'residentiel', user=self.user)

    def test_plan_vide_leve_erreur_metier(self):
        with mock.patch(
                'requests.post',
                return_value=_fake_response(200, {'taches': []})):
            with self.assertRaises(services.PlanTachesIAError):
                services.proposer_plan_taches_ia(
                    _DEVIS_DATA, 'residentiel', user=self.user)


class MaterialiserPlanTachesServiceTests(TestCase):
    def setUp(self):
        self.co = make_company('gp-x29-mat', 'S')
        self.projet = Projet.objects.create(
            company=self.co, code='P-X29', nom='P')

    def test_materialise_taches_et_dependances(self):
        creees = services.materialiser_plan_taches(self.projet, _PLAN_PROPOSE)
        self.assertEqual(len(creees), 2)
        self.assertEqual(Tache.objects.filter(projet=self.projet).count(), 2)
        t1 = Tache.objects.get(projet=self.projet, code_wbs='1')
        t2 = Tache.objects.get(projet=self.projet, code_wbs='2')
        self.assertTrue(
            DependanceTache.objects.filter(
                predecesseur=t1, successeur=t2).exists())

    def test_phases_creees_idempotent(self):
        services.materialiser_plan_taches(self.projet, _PLAN_PROPOSE)
        self.assertEqual(self.projet.phases.count(), 2)  # etude + pose

    def test_dates_derivees_sequentiellement(self):
        from datetime import date, timedelta
        self.projet.date_debut = date(2026, 6, 1)
        self.projet.save(update_fields=['date_debut'])
        creees = services.materialiser_plan_taches(self.projet, _PLAN_PROPOSE)
        t1, t2 = creees
        self.assertEqual(t1.date_debut_prevue, date(2026, 6, 1))
        self.assertEqual(t1.date_fin_prevue, date(2026, 6, 2))
        self.assertEqual(t2.date_debut_prevue, date(2026, 6, 3))
        self.assertEqual(
            t2.date_fin_prevue, date(2026, 6, 3) + timedelta(days=4))

    def test_plan_vide_leve_erreur(self):
        with self.assertRaises(services.PlanTachesIAError):
            services.materialiser_plan_taches(self.projet, {'taches': []})

    def test_dependance_code_inconnu_ignoree(self):
        plan = {'taches': [
            {'code': '1', 'libelle': 'X', 'phase': 'etude',
             'duree_jours': 1, 'dependances_fs': ['999']},
        ]}
        creees = services.materialiser_plan_taches(self.projet, plan)
        self.assertEqual(len(creees), 1)
        self.assertEqual(DependanceTache.objects.count(), 0)


class GenererPlanIaApiTests(TestCase):
    BASE = '/api/django/gestion-projet/projets/'

    def setUp(self):
        self.co_a = make_company('gp-x29-a', 'A')
        self.co_b = make_company('gp-x29-b', 'B')
        self.user_a = make_user(self.co_a, 'gp-x29-a-u')
        self.user_b = make_user(self.co_b, 'gp-x29-b-u')
        self.projet_a = Projet.objects.create(
            company=self.co_a, code='P-X29A', nom='A')

    def test_devis_id_manquant_400(self):
        api = auth(self.user_a)
        resp = api.post(
            f'{self.BASE}{self.projet_a.id}/generer-plan-ia/', {},
            format='json')
        self.assertEqual(resp.status_code, 400)

    def test_devis_inexistant_404(self):
        api = auth(self.user_a)
        resp = api.post(
            f'{self.BASE}{self.projet_a.id}/generer-plan-ia/',
            {'devis_id': 99999}, format='json')
        self.assertEqual(resp.status_code, 404)

    @mock.patch('apps.ventes.selectors.devis_pour_projet',
                return_value=_DEVIS_DATA)
    def test_sans_cle_llm_503(self, mock_devis):
        with mock.patch(
                'requests.post', return_value=_fake_response(503)):
            api = auth(self.user_a)
            resp = api.post(
                f'{self.BASE}{self.projet_a.id}/generer-plan-ia/',
                {'devis_id': 1}, format='json')
        self.assertEqual(resp.status_code, 503)

    @mock.patch('apps.ventes.selectors.devis_pour_projet',
                return_value=_DEVIS_DATA)
    def test_proposition_reussie_200(self, mock_devis):
        with mock.patch(
                'requests.post',
                return_value=_fake_response(200, _PLAN_PROPOSE)):
            api = auth(self.user_a)
            resp = api.post(
                f'{self.BASE}{self.projet_a.id}/generer-plan-ia/',
                {'devis_id': 1}, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(len(resp.data['taches']), 2)
        # Rien n'est écrit avant confirmation explicite.
        self.assertEqual(Tache.objects.filter(projet=self.projet_a).count(), 0)

    def test_isolation_societe_404(self):
        api = auth(self.user_b)
        resp = api.post(
            f'{self.BASE}{self.projet_a.id}/generer-plan-ia/',
            {'devis_id': 1}, format='json')
        self.assertEqual(resp.status_code, 404)


class ConfirmerPlanIaApiTests(TestCase):
    BASE = '/api/django/gestion-projet/projets/'

    def setUp(self):
        self.co_a = make_company('gp-x29-c-a', 'A')
        self.co_b = make_company('gp-x29-c-b', 'B')
        self.user_a = make_user(self.co_a, 'gp-x29-c-a-u')
        self.user_b = make_user(self.co_b, 'gp-x29-c-b-u')
        self.projet_a = Projet.objects.create(
            company=self.co_a, code='P-X29CA', nom='A')

    def test_confirmation_cree_taches_et_dependances(self):
        api = auth(self.user_a)
        resp = api.post(
            f'{self.BASE}{self.projet_a.id}/confirmer-plan-ia/',
            {'taches': _PLAN_PROPOSE['taches']}, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        self.assertEqual(len(resp.data), 2)
        self.assertEqual(
            Tache.objects.filter(projet=self.projet_a).count(), 2)

    def test_taches_manquantes_400(self):
        api = auth(self.user_a)
        resp = api.post(
            f'{self.BASE}{self.projet_a.id}/confirmer-plan-ia/', {},
            format='json')
        self.assertEqual(resp.status_code, 400)

    def test_isolation_societe_404(self):
        api = auth(self.user_b)
        resp = api.post(
            f'{self.BASE}{self.projet_a.id}/confirmer-plan-ia/',
            {'taches': _PLAN_PROPOSE['taches']}, format='json')
        self.assertEqual(resp.status_code, 404)
        self.assertEqual(
            Tache.objects.filter(projet=self.projet_a).count(), 0)
