"""Tests NTFSM26 — vue équipe & compétences par zone géographique.

Critère d'acceptation : filtrer par zone « Casablanca » n'affiche QUE les
techniciens dont ``zone_intervention`` correspond.

Couvre aussi :
* les compétences (FG172) et habilitations VALIDES (FG173) accompagnent
  chaque technicien ;
* une habilitation expirée n'est pas listée ;
* un employé sans zone déclarée n'apparaît dans aucun filtre par zone ;
* les employés SORTIS sont exclus ;
* isolation société.
"""
from datetime import date, timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.rh import selectors
from apps.rh.models import (
    Competence,
    CompetenceEmploye,
    DossierEmploye,
    Habilitation,
)

User = get_user_model()

EQUIPE = '/api/django/rh/employes/equipe-terrain/'


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


class EquipeParZoneTests(TestCase):
    def setUp(self):
        self.co = make_company('ntfsm26-a', 'A')
        self.rh = make_user(self.co, 'ntfsm26-rh')
        self.api = auth(self.rh)
        self.casa = DossierEmploye.objects.create(
            company=self.co, matricule='Z-1', nom='Casaoui', prenom='Un',
            zone_intervention='Casablanca')
        self.rabat = DossierEmploye.objects.create(
            company=self.co, matricule='Z-2', nom='Rbati', prenom='Deux',
            zone_intervention='Rabat')
        self.sans_zone = DossierEmploye.objects.create(
            company=self.co, matricule='Z-3', nom='Nomade', prenom='Trois')
        self.competence = Competence.objects.create(
            company=self.co, code='POSE', libelle='Pose structure',
            domaine=Competence.Domaine.POSE_STRUCTURE)
        CompetenceEmploye.objects.create(
            company=self.co, employe=self.casa, competence=self.competence,
            niveau=CompetenceEmploye.Niveau.CONFIRME)
        Habilitation.objects.create(
            company=self.co, employe=self.casa,
            type_habilitation=Habilitation.TypeHabilitation.B1V,
            date_validite=date.today() + timedelta(days=365))

    def test_filtre_par_zone_casablanca(self):
        lignes = selectors.equipe_terrain(self.co, zone='Casablanca')
        self.assertEqual(len(lignes), 1)
        self.assertEqual(lignes[0]['employe_id'], self.casa.id)

    def test_filtre_par_zone_insensible_a_la_casse(self):
        lignes = selectors.equipe_terrain(self.co, zone='casablanca')
        self.assertEqual(
            [ligne['employe_id'] for ligne in lignes], [self.casa.id])

    def test_sans_filtre_toute_l_equipe(self):
        lignes = selectors.equipe_terrain(self.co)
        ids = {ligne['employe_id'] for ligne in lignes}
        self.assertEqual(
            ids, {self.casa.id, self.rabat.id, self.sans_zone.id})

    def test_employe_sans_zone_absent_du_filtre(self):
        lignes = selectors.equipe_terrain(self.co, zone='Casablanca')
        ids = {ligne['employe_id'] for ligne in lignes}
        self.assertNotIn(self.sans_zone.id, ids)

    def test_competences_et_habilitations_accompagnent_le_technicien(self):
        ligne = selectors.equipe_terrain(self.co, zone='Casablanca')[0]
        self.assertEqual(len(ligne['competences']), 1)
        self.assertEqual(ligne['competences'][0]['code'], 'POSE')
        self.assertEqual(len(ligne['habilitations']), 1)
        self.assertEqual(ligne['habilitations'][0]['type_habilitation'], 'b1v')

    def test_habilitation_expiree_non_listee(self):
        Habilitation.objects.create(
            company=self.co, employe=self.rabat,
            type_habilitation=Habilitation.TypeHabilitation.BR,
            date_validite=date.today() - timedelta(days=1))
        ligne = selectors.equipe_terrain(self.co, zone='Rabat')[0]
        self.assertEqual(ligne['habilitations'], [])

    def test_competence_niveau_zero_non_listee(self):
        CompetenceEmploye.objects.create(
            company=self.co, employe=self.rabat, competence=self.competence,
            niveau=CompetenceEmploye.Niveau.NON_ACQUIS)
        ligne = selectors.equipe_terrain(self.co, zone='Rabat')[0]
        self.assertEqual(ligne['competences'], [])

    def test_filtre_par_competence(self):
        lignes = selectors.equipe_terrain(self.co, competence_code='POSE')
        self.assertEqual(
            [ligne['employe_id'] for ligne in lignes], [self.casa.id])

    def test_employe_sorti_exclu(self):
        self.casa.statut = DossierEmploye.Statut.SORTI
        self.casa.save(update_fields=['statut'])
        self.assertEqual(
            selectors.equipe_terrain(self.co, zone='Casablanca'), [])

    def test_zones_declarees(self):
        self.assertEqual(
            selectors.zones_intervention(self.co), ['Casablanca', 'Rabat'])

    def test_endpoint_equipe_terrain_filtre_zone(self):
        resp = self.api.get(f'{EQUIPE}?zone=Casablanca')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(len(resp.data), 1)
        self.assertEqual(resp.data[0]['employe_id'], self.casa.id)
        self.assertEqual(resp.data[0]['zone_intervention'], 'Casablanca')

    def test_endpoint_zones_intervention(self):
        resp = self.api.get('/api/django/rh/employes/zones-intervention/')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(list(resp.data), ['Casablanca', 'Rabat'])

    def test_zone_modifiable_par_api(self):
        resp = self.api.patch(
            f'/api/django/rh/employes/{self.sans_zone.id}/',
            {'zone_intervention': 'Marrakech'}, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.sans_zone.refresh_from_db()
        self.assertEqual(self.sans_zone.zone_intervention, 'Marrakech')

    def test_isolation_societe(self):
        co_b = make_company('ntfsm26-b', 'B')
        DossierEmploye.objects.create(
            company=co_b, matricule='B-1', nom='Voisin', prenom='Un',
            zone_intervention='Casablanca')
        lignes = selectors.equipe_terrain(self.co, zone='Casablanca')
        self.assertEqual(
            [ligne['employe_id'] for ligne in lignes], [self.casa.id])
        rh_b = make_user(co_b, 'ntfsm26-rh-b')
        resp = auth(rh_b).get(f'{EQUIPE}?zone=Rabat')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(list(resp.data), [])
