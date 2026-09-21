"""Tests NTHCM14 — enquêtes d'engagement multi-questions.

Couvre :
* GARDE-FOU STRUCTUREL (test de schéma comme XRH32) : ``ReponseEnquete`` ne
  porte AUCUNE FK ``user`` ;
* une enquête ANONYME ne peut pas porter d'``employe`` (contrainte de base) ;
* une enquête NOMINATIVE garde la FK ``employe``, résolue côté serveur ;
* double-réponse impossible dans les DEUX modes (409) ;
* vocabulaire des questions fermé (type inconnu refusé 400) ;
* isolation société.
"""
from django.contrib.auth import get_user_model
from django.db import IntegrityError, transaction
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.rh import services
from apps.rh.models import (
    DossierEmploye,
    EnqueteEngagement,
    ParticipationEnquete,
    ReponseEnquete,
)

User = get_user_model()

QUESTIONS = [
    {'libelle': 'Je me sens reconnu', 'type': 'note1_5',
     'categorie': 'reconnaissance'},
    {'libelle': 'Ma charge est tenable', 'type': 'note1_5',
     'categorie': 'charge_travail'},
    {'libelle': 'Un mot libre ?', 'type': 'texte_libre',
     'categorie': 'perspectives'},
]


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


class SchemaAnonymatTests(TestCase):
    def test_reponse_enquete_aucune_fk_user(self):
        """Garde-fou structurel : la réponse ne peut PAS être reliée au
        COMPTE qui a répondu — aucun champ ``user`` sur le modèle."""
        noms_champs = {f.name for f in ReponseEnquete._meta.get_fields()}
        self.assertNotIn('user', noms_champs)

    def test_participation_ne_reference_aucune_reponse(self):
        """On sait QUI a répondu, jamais CE QU'IL A RÉPONDU."""
        noms_champs = {f.name for f in ParticipationEnquete._meta.get_fields()}
        self.assertNotIn('reponse', noms_champs)
        self.assertNotIn('reponses', noms_champs)


class EnqueteAnonymeTests(TestCase):
    def setUp(self):
        self.co = make_company('nthcm14-a', 'A')
        self.rh = make_user(self.co, 'nthcm14-rh')
        self.employe_user = make_user(
            self.co, 'nthcm14-e1', role='normal')
        self.dossier = DossierEmploye.objects.create(
            company=self.co, matricule='Q-1', nom='Alpha', prenom='Un',
            user=self.employe_user)
        self.enquete = EnqueteEngagement.objects.create(
            company=self.co, titre='Baromètre T1', questions=QUESTIONS,
            anonyme=True)

    def _repondre(self, user, reponses=None):
        return auth(user).post(
            f'/api/django/rh/enquetes-engagement/{self.enquete.id}/repondre/',
            {'reponses': reponses or {'0': 4, '1': 3, '2': 'RAS'}},
            format='json')

    def test_reponse_anonyme_sans_employe(self):
        resp = self._repondre(self.employe_user)
        self.assertEqual(resp.status_code, 201, resp.data)
        reponse = ReponseEnquete.objects.get(enquete=self.enquete)
        self.assertTrue(reponse.anonyme)
        self.assertIsNone(reponse.employe_id)

    def test_contrainte_base_interdit_employe_sur_reponse_anonyme(self):
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                ReponseEnquete.objects.create(
                    company=self.co, enquete=self.enquete, anonyme=True,
                    employe=self.dossier, reponses={})

    def test_double_reponse_refusee_409(self):
        self.assertEqual(self._repondre(self.employe_user).status_code, 201)
        resp = self._repondre(self.employe_user)
        self.assertEqual(resp.status_code, 409, resp.data)
        self.assertEqual(
            ReponseEnquete.objects.filter(enquete=self.enquete).count(), 1)

    def test_double_reponse_refusee_au_service(self):
        services.repondre_enquete(
            self.enquete, self.employe_user, reponses={'0': 5})
        with self.assertRaises(services.DejaRepondueError):
            services.repondre_enquete(
                self.enquete, self.employe_user, reponses={'0': 1})

    def test_reponses_doivent_etre_un_objet(self):
        resp = auth(self.employe_user).post(
            f'/api/django/rh/enquetes-engagement/{self.enquete.id}/repondre/',
            {'reponses': 'oui'}, format='json')
        self.assertEqual(resp.status_code, 400, resp.data)


class EnqueteNominativeTests(TestCase):
    def setUp(self):
        self.co = make_company('nthcm14-b', 'B')
        self.employe_user = make_user(self.co, 'nthcm14-n1', role='normal')
        self.dossier = DossierEmploye.objects.create(
            company=self.co, matricule='N-1', nom='Beta', prenom='Deux',
            user=self.employe_user)
        self.enquete = EnqueteEngagement.objects.create(
            company=self.co, titre='Sondage ciblé', questions=QUESTIONS,
            anonyme=False)

    def test_reponse_nominative_garde_la_fk_employe(self):
        reponse = services.repondre_enquete(
            self.enquete, self.employe_user, reponses={'0': 5})
        self.assertFalse(reponse.anonyme)
        self.assertEqual(reponse.employe_id, self.dossier.id)

    def test_double_reponse_refusee_en_nominatif_aussi(self):
        services.repondre_enquete(
            self.enquete, self.employe_user, reponses={'0': 5})
        with self.assertRaises(services.DejaRepondueError):
            services.repondre_enquete(
                self.enquete, self.employe_user, reponses={'0': 1})

    def test_employe_sans_dossier_reste_sans_fk(self):
        sans_dossier = make_user(self.co, 'nthcm14-n2', role='normal')
        reponse = services.repondre_enquete(
            self.enquete, sans_dossier, reponses={'0': 3})
        self.assertIsNone(reponse.employe_id)


class AdministrationEnqueteTests(TestCase):
    def setUp(self):
        self.co = make_company('nthcm14-c', 'C')
        self.rh = make_user(self.co, 'nthcm14-rh-c')
        self.api = auth(self.rh)

    def test_creation_enquete_pose_la_societe(self):
        resp = self.api.post(
            '/api/django/rh/enquetes-engagement/',
            {'titre': 'Baromètre', 'questions': QUESTIONS}, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        enquete = EnqueteEngagement.objects.get(id=resp.data['id'])
        self.assertEqual(enquete.company_id, self.co.id)
        self.assertTrue(enquete.anonyme)

    def test_type_de_question_inconnu_refuse(self):
        resp = self.api.post(
            '/api/django/rh/enquetes-engagement/',
            {'titre': 'Bancale',
             'questions': [{'libelle': 'X', 'type': 'inventé',
                            'categorie': 'management'}]},
            format='json')
        self.assertEqual(resp.status_code, 400, resp.data)
        self.assertIn('questions', resp.data)

    def test_libelle_de_question_obligatoire(self):
        resp = self.api.post(
            '/api/django/rh/enquetes-engagement/',
            {'titre': 'Bancale',
             'questions': [{'libelle': '  ', 'type': 'note1_5',
                            'categorie': 'management'}]},
            format='json')
        self.assertEqual(resp.status_code, 400, resp.data)

    def test_anonymat_fige_des_la_premiere_reponse(self):
        enquete = EnqueteEngagement.objects.create(
            company=self.co, titre='Figée', questions=QUESTIONS,
            anonyme=True)
        votant = make_user(self.co, 'nthcm14-votant', role='normal')
        services.repondre_enquete(enquete, votant, reponses={'0': 4})
        resp = self.api.patch(
            f'/api/django/rh/enquetes-engagement/{enquete.id}/',
            {'anonyme': False}, format='json')
        self.assertEqual(resp.status_code, 400, resp.data)
        self.assertIn('anonyme', resp.data)

    def test_isolation_societe(self):
        EnqueteEngagement.objects.create(
            company=self.co, titre='Interne', questions=QUESTIONS)
        co_b = make_company('nthcm14-d', 'D')
        rh_b = make_user(co_b, 'nthcm14-rh-d')
        resp = auth(rh_b).get('/api/django/rh/enquetes-engagement/')
        self.assertEqual(resp.status_code, 200, resp.data)
        resultats = (resp.data['results'] if isinstance(resp.data, dict)
                     else resp.data)
        self.assertEqual(len(resultats), 0)
