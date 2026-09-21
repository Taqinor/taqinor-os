"""Tests FG185 — Tableau de bord HSE (agrégation lecture seule).

Couvre :
* Calcul des taux normalisés : taux de fréquence (accidents avec arrêt
  × 1 000 000 / heures travaillées) et taux de gravité (journées d'arrêt
  × 1 000 / heures travaillées), à partir d'AccidentTravail + FeuilleTemps.
* Compteurs bruts : accidents total / avec arrêt / jours d'arrêt, presqu'accidents.
* Alertes d'expiration agrégées : habilitations, certifications, visites
  médicales, EPI (renouvellement + péremption/recontrôle).
* Incidents HSE par chantier : presqu'accidents regroupés par chantier_id.
* Société vide : tout à zéro, taux None — AUCUNE division par zéro.
* Isolation multi-société : B ne voit jamais les chiffres de A.
* Permission : un rôle normal est refusé (403).
"""
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.rh import selectors
from apps.rh.models import (
    AccidentTravail,
    Certification,
    DossierEmploye,
    DotationEpi,
    EpiCatalogue,
    FeuilleTemps,
    Habilitation,
    PresquAccident,
    VisiteMedicale,
)

User = get_user_model()

URL = '/api/django/rh/tableau-bord-hse/'


def make_company(slug, nom):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


def make_user(company, username, role='responsable'):
    return User.objects.create_user(
        username=username, password='x', company=company, role_legacy=role)


def make_employe(company, matricule):
    return DossierEmploye.objects.create(
        company=company, matricule=matricule, nom='Test', prenom='E')


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


class TableauBordHseSelectorTests(TestCase):
    def setUp(self):
        self.co = make_company('hse-a', 'A')
        self.emp = make_employe(self.co, 'E1')
        self.today = timezone.localdate()

    def test_taux_frequence_et_gravite_calcules(self):
        # 200 heures travaillées sur la période.
        FeuilleTemps.objects.create(
            company=self.co, employe=self.emp, installation_id=1,
            date=self.today, heures=200)
        # 1 accident AVEC arrêt (10 jours) + 1 sans arrêt.
        AccidentTravail.objects.create(
            company=self.co, employe=self.emp, reference='AT-1',
            date_accident=self.today, arret_travail=True, nb_jours_arret=10)
        AccidentTravail.objects.create(
            company=self.co, employe=self.emp, reference='AT-2',
            date_accident=self.today, arret_travail=False)

        data = selectors.tableau_bord_hse(self.co, within_days=30,
                                          today=self.today)

        self.assertEqual(data['heures_travaillees'], 200.0)
        self.assertEqual(data['accidents_total'], 2)
        self.assertEqual(data['accidents_avec_arret'], 1)
        self.assertEqual(data['jours_arret_total'], 10)
        # TF = 1 * 1_000_000 / 200 = 5000.0
        self.assertEqual(data['taux_frequence'], 5000.0)
        # TG = 10 * 1_000 / 200 = 50.0
        self.assertEqual(data['taux_gravite'], 50.0)

    def test_societe_vide_zero_sans_division_par_zero(self):
        data = selectors.tableau_bord_hse(self.co, within_days=30,
                                          today=self.today)
        self.assertIsNone(data['taux_frequence'])
        self.assertIsNone(data['taux_gravite'])
        self.assertEqual(data['heures_travaillees'], 0.0)
        self.assertEqual(data['accidents_total'], 0)
        self.assertEqual(data['presqu_accidents_total'], 0)
        self.assertEqual(data['alertes']['total'], 0)
        self.assertEqual(data['incidents_par_chantier'], [])

    def test_company_none_renvoie_zero(self):
        data = selectors.tableau_bord_hse(None)
        self.assertIsNone(data['taux_frequence'])
        self.assertEqual(data['alertes']['total'], 0)
        self.assertEqual(data['incidents_par_chantier'], [])

    def test_accidents_avec_arret_mais_zero_heures_taux_none(self):
        AccidentTravail.objects.create(
            company=self.co, employe=self.emp, reference='AT-1',
            date_accident=self.today, arret_travail=True, nb_jours_arret=5)
        data = selectors.tableau_bord_hse(self.co, within_days=30,
                                          today=self.today)
        # Pas d'heures travaillées -> taux non calculables (gardé), pas de crash.
        self.assertIsNone(data['taux_frequence'])
        self.assertIsNone(data['taux_gravite'])
        self.assertEqual(data['accidents_avec_arret'], 1)
        self.assertEqual(data['jours_arret_total'], 5)

    def test_incidents_par_chantier_regroupes_et_tries(self):
        PresquAccident.objects.create(
            company=self.co, reference='NM-1', date_constat=self.today,
            chantier_id='CH-A')
        PresquAccident.objects.create(
            company=self.co, reference='NM-2', date_constat=self.today,
            chantier_id='CH-A')
        PresquAccident.objects.create(
            company=self.co, reference='NM-3', date_constat=self.today,
            chantier_id='CH-B')
        PresquAccident.objects.create(
            company=self.co, reference='NM-4', date_constat=self.today,
            chantier_id='')

        data = selectors.tableau_bord_hse(self.co, within_days=30,
                                          today=self.today)
        self.assertEqual(data['presqu_accidents_total'], 4)
        par = data['incidents_par_chantier']
        # Trié par nombre décroissant : CH-A (2) avant CH-B (1) / '' (1).
        self.assertEqual(par[0], {'chantier_id': 'CH-A', 'nombre': 2})
        chantiers = {r['chantier_id']: r['nombre'] for r in par}
        self.assertEqual(chantiers['CH-B'], 1)
        self.assertEqual(chantiers[''], 1)

    def test_alertes_expiration_agregees(self):
        soon = self.today + timedelta(days=10)
        Habilitation.objects.create(
            company=self.co, employe=self.emp,
            type_habilitation='b1v', actif=True, date_validite=soon)
        Certification.objects.create(
            company=self.co, employe=self.emp,
            type_certification='harnais', actif=True, date_validite=soon)
        VisiteMedicale.objects.create(
            company=self.co, employe=self.emp,
            actif=True, prochaine_visite=soon)
        epi = EpiCatalogue.objects.create(
            company=self.co, designation='Harnais')
        DotationEpi.objects.create(
            company=self.co, employe=self.emp, epi=epi,
            date_renouvellement=soon)

        data = selectors.tableau_bord_hse(self.co, within_days=30,
                                          today=self.today)
        al = data['alertes']
        self.assertEqual(al['habilitations'], 1)
        self.assertEqual(al['certifications'], 1)
        self.assertEqual(al['visites_medicales'], 1)
        self.assertEqual(al['epi'], 1)
        self.assertEqual(al['total'], 4)

    def test_accident_hors_periode_exclu(self):
        FeuilleTemps.objects.create(
            company=self.co, employe=self.emp, installation_id=1,
            date=self.today, heures=100)
        vieux = self.today - timedelta(days=60)
        AccidentTravail.objects.create(
            company=self.co, employe=self.emp, reference='AT-OLD',
            date_accident=vieux, arret_travail=True, nb_jours_arret=99)
        data = selectors.tableau_bord_hse(self.co, within_days=30,
                                          today=self.today)
        # L'accident vieux de 60 j est hors fenêtre de 30 j -> ignoré.
        self.assertEqual(data['accidents_total'], 0)
        self.assertEqual(data['taux_frequence'], 0.0)


class TableauBordHseIsolationTests(TestCase):
    def setUp(self):
        self.co_a = make_company('hse-iso-a', 'A')
        self.co_b = make_company('hse-iso-b', 'B')
        self.emp_a = make_employe(self.co_a, 'EA')
        self.emp_b = make_employe(self.co_b, 'EB')
        self.today = timezone.localdate()
        FeuilleTemps.objects.create(
            company=self.co_a, employe=self.emp_a, installation_id=1,
            date=self.today, heures=100)
        AccidentTravail.objects.create(
            company=self.co_a, employe=self.emp_a, reference='AT-A',
            date_accident=self.today, arret_travail=True, nb_jours_arret=4)
        PresquAccident.objects.create(
            company=self.co_a, reference='NM-A', date_constat=self.today,
            chantier_id='CH-A')

    def test_societe_b_ne_voit_pas_les_chiffres_de_a(self):
        data = selectors.tableau_bord_hse(self.co_b, within_days=30,
                                          today=self.today)
        self.assertEqual(data['accidents_total'], 0)
        self.assertEqual(data['presqu_accidents_total'], 0)
        self.assertIsNone(data['taux_frequence'])
        self.assertEqual(data['incidents_par_chantier'], [])


class TableauBordHseApiTests(TestCase):
    def setUp(self):
        self.co = make_company('hse-api', 'A')
        self.emp = make_employe(self.co, 'E1')
        self.today = timezone.localdate()
        self.responsable = make_user(self.co, 'hse-resp', role='responsable')
        self.normal = make_user(self.co, 'hse-normal', role='technicien')
        FeuilleTemps.objects.create(
            company=self.co, employe=self.emp, installation_id=1,
            date=self.today, heures=200)
        AccidentTravail.objects.create(
            company=self.co, employe=self.emp, reference='AT-1',
            date_accident=self.today, arret_travail=True, nb_jours_arret=10)

    def test_endpoint_renvoie_le_tableau(self):
        resp = auth(self.responsable).get(URL)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['taux_frequence'], 5000.0)
        self.assertEqual(resp.data['taux_gravite'], 50.0)
        self.assertEqual(resp.data['accidents_avec_arret'], 1)

    def test_alias_action_tableau_bord_hse(self):
        resp = auth(self.responsable).get(URL + 'tableau-bord-hse/')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['accidents_total'], 1)

    def test_within_param_respecte(self):
        resp = auth(self.responsable).get(URL, {'within': 7})
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['periode_jours'], 7)

    def test_role_normal_refuse(self):
        resp = auth(self.normal).get(URL)
        self.assertEqual(resp.status_code, 403)
