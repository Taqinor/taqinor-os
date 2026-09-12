"""Tests NTHCM15 — résultats d'enquête par catégorie + plans d'action.

Couvre :
* la moyenne et la distribution sont agrégées PAR CATÉGORIE de question ;
* seules les questions ``note1_5`` alimentent la moyenne (le texte libre non) ;
* le seuil d'anonymat (≥ 5 réponses) masque les résultats d'une enquête
  ANONYME, jamais ceux d'une enquête nominative ;
* créer un plan d'action l'assigne à un responsable avec échéance ;
* isolation société.
"""
from datetime import date

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.rh import selectors
from apps.rh.models import (
    DossierEmploye,
    EnqueteEngagement,
    PlanActionEngagement,
    ReponseEnquete,
)

User = get_user_model()

QUESTIONS = [
    {'libelle': 'Je me sens reconnu', 'type': 'note1_5',
     'categorie': 'reconnaissance'},
    {'libelle': 'Mon travail est valorisé', 'type': 'note1_5',
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


class ResultatsEnqueteTests(TestCase):
    def setUp(self):
        self.co = make_company('nthcm15-a', 'A')
        self.rh = make_user(self.co, 'nthcm15-rh')
        self.api = auth(self.rh)
        self.enquete = EnqueteEngagement.objects.create(
            company=self.co, titre='Baromètre T1', questions=QUESTIONS,
            anonyme=True)

    def _reponse(self, valeurs):
        return ReponseEnquete.objects.create(
            company=self.co, enquete=self.enquete, anonyme=True,
            reponses=valeurs)

    def test_masque_sous_le_seuil_anonymat(self):
        for _ in range(4):
            self._reponse({'0': 5, '1': 5, '2': 5})
        resultats = selectors.resultats_enquete(self.co, self.enquete.id)
        self.assertTrue(resultats['masque'])
        self.assertEqual(resultats['nb_reponses'], 4)
        self.assertEqual(resultats['categories'], [])

    def test_moyenne_par_categorie_au_dela_du_seuil(self):
        # 5 réponses : reconnaissance = (4+2) par réponse → moyenne 3 ;
        # charge_travail = 5 partout → moyenne 5.
        for _ in range(5):
            self._reponse({'0': 4, '1': 2, '2': 5, '3': 'RAS'})
        resultats = selectors.resultats_enquete(self.co, self.enquete.id)
        self.assertFalse(resultats['masque'])
        par_categorie = {c['categorie']: c for c in resultats['categories']}
        self.assertEqual(par_categorie['reconnaissance']['moyenne'], 3.0)
        self.assertEqual(par_categorie['reconnaissance']['nb_notes'], 10)
        self.assertEqual(par_categorie['charge_travail']['moyenne'], 5.0)

    def test_texte_libre_sans_moyenne(self):
        for _ in range(5):
            self._reponse({'0': 4, '1': 4, '2': 4, '3': 'Beaucoup de texte'})
        resultats = selectors.resultats_enquete(self.co, self.enquete.id)
        par_categorie = {c['categorie']: c for c in resultats['categories']}
        self.assertIn('perspectives', par_categorie)
        self.assertIsNone(par_categorie['perspectives']['moyenne'])
        self.assertEqual(par_categorie['perspectives']['nb_notes'], 0)

    def test_distribution_par_categorie(self):
        for note in (1, 2, 3, 4, 5):
            self._reponse({'2': note})
        resultats = selectors.resultats_enquete(self.co, self.enquete.id)
        par_categorie = {c['categorie']: c for c in resultats['categories']}
        distribution = par_categorie['charge_travail']['distribution']
        self.assertEqual(
            {int(k): v for k, v in distribution.items()},
            {1: 1, 2: 1, 3: 1, 4: 1, 5: 1})

    def test_valeur_hors_bornes_ignoree(self):
        for _ in range(5):
            self._reponse({'2': 9})
        resultats = selectors.resultats_enquete(self.co, self.enquete.id)
        par_categorie = {c['categorie']: c for c in resultats['categories']}
        self.assertEqual(par_categorie['charge_travail']['nb_notes'], 0)
        self.assertIsNone(par_categorie['charge_travail']['moyenne'])

    def test_enquete_nominative_jamais_masquee(self):
        nominative = EnqueteEngagement.objects.create(
            company=self.co, titre='Sondage ciblé', questions=QUESTIONS,
            anonyme=False)
        ReponseEnquete.objects.create(
            company=self.co, enquete=nominative, anonyme=False,
            reponses={'2': 4})
        resultats = selectors.resultats_enquete(self.co, nominative.id)
        self.assertFalse(resultats['masque'])
        par_categorie = {c['categorie']: c for c in resultats['categories']}
        self.assertEqual(par_categorie['charge_travail']['moyenne'], 4.0)

    def test_endpoint_resultats(self):
        for _ in range(5):
            self._reponse({'0': 3, '1': 3, '2': 3})
        resp = self.api.get(
            f'/api/django/rh/enquetes-engagement/{self.enquete.id}'
            '/resultats/')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertFalse(resp.data['masque'])
        self.assertEqual(resp.data['nb_reponses'], 5)

    def test_isolation_societe(self):
        co_b = make_company('nthcm15-b', 'B')
        self.assertIsNone(
            selectors.resultats_enquete(co_b, self.enquete.id))


class PlanActionEngagementTests(TestCase):
    def setUp(self):
        self.co = make_company('nthcm15-c', 'C')
        self.rh = make_user(self.co, 'nthcm15-rh-c')
        self.api = auth(self.rh)
        self.enquete = EnqueteEngagement.objects.create(
            company=self.co, titre='Baromètre', questions=QUESTIONS)
        self.responsable = DossierEmploye.objects.create(
            company=self.co, matricule='R-1', nom='Chef', prenom='Un')

    def test_creation_plan_action_assigne_responsable_et_echeance(self):
        resp = self.api.post(
            '/api/django/rh/plans-action-engagement/',
            {'enquete': self.enquete.id,
             'categorie_ciblee': 'reconnaissance',
             'action': 'Mettre en place un rituel de feedback mensuel',
             'responsable': self.responsable.id,
             'echeance': '2027-03-31'}, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        plan = PlanActionEngagement.objects.get(id=resp.data['id'])
        self.assertEqual(plan.company_id, self.co.id)
        self.assertEqual(plan.responsable_id, self.responsable.id)
        self.assertEqual(plan.echeance, date(2027, 3, 31))
        self.assertEqual(plan.statut, PlanActionEngagement.Statut.PROPOSE)

    def test_filtre_par_enquete(self):
        autre = EnqueteEngagement.objects.create(
            company=self.co, titre='Autre', questions=QUESTIONS)
        PlanActionEngagement.objects.create(
            company=self.co, enquete=self.enquete, action='A')
        PlanActionEngagement.objects.create(
            company=self.co, enquete=autre, action='B')
        resp = self.api.get(
            f'/api/django/rh/plans-action-engagement/?enquete={autre.id}')
        self.assertEqual(resp.status_code, 200, resp.data)
        resultats = (resp.data['results'] if isinstance(resp.data, dict)
                     else resp.data)
        self.assertEqual(len(resultats), 1)
        self.assertEqual(resultats[0]['action'], 'B')

    def test_responsable_autre_societe_refuse(self):
        co_b = make_company('nthcm15-d', 'D')
        etranger = DossierEmploye.objects.create(
            company=co_b, matricule='X-1', nom='Etranger', prenom='Un')
        resp = self.api.post(
            '/api/django/rh/plans-action-engagement/',
            {'enquete': self.enquete.id, 'action': 'A',
             'responsable': etranger.id}, format='json')
        self.assertEqual(resp.status_code, 400, resp.data)

    def test_isolation_societe(self):
        PlanActionEngagement.objects.create(
            company=self.co, enquete=self.enquete, action='Interne')
        co_b = make_company('nthcm15-e', 'E')
        rh_b = make_user(co_b, 'nthcm15-rh-e')
        resp = auth(rh_b).get('/api/django/rh/plans-action-engagement/')
        self.assertEqual(resp.status_code, 200, resp.data)
        resultats = (resp.data['results'] if isinstance(resp.data, dict)
                     else resp.data)
        self.assertEqual(len(resultats), 0)
