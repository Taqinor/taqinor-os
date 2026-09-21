"""Tests NTHCM8 — OKR d'entreprise (cascade OPTIONNELLE).

Couvre :
* créer un objectif d'entreprise + des OKR individuels rattachés ;
* un OKR SANS parent reste parfaitement valide (cascade optionnelle) ;
* ``progression_pct`` calculée (actuelle/cible) et BORNÉE 0-100 ;
* cible à 0 ⇒ progression 0 (jamais de division par zéro, jamais 100 %) ;
* CRUD société-scopé + société posée côté serveur ;
* isolation société.
"""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.rh.models import (
    DossierEmploye,
    KeyResult,
    KeyResultIndividuel,
    ObjectifEntreprise,
    OkrIndividuel,
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


class ProgressionTests(TestCase):
    def setUp(self):
        self.co = make_company('nthcm8-a', 'A')
        self.employe = DossierEmploye.objects.create(
            company=self.co, matricule='O-1', nom='Alpha', prenom='Un')
        self.okr = OkrIndividuel.objects.create(
            company=self.co, employe=self.employe, periode='T1-2027',
            titre='Réduire le délai de pose')

    def _kr(self, actuelle, cible):
        return KeyResultIndividuel.objects.create(
            company=self.co, okr=self.okr, libelle='KR',
            valeur_actuelle=Decimal(actuelle), valeur_cible=Decimal(cible))

    def test_progression_calculee(self):
        kr = self._kr('25', '100')
        self.assertEqual(kr.progression_pct, Decimal('25.00'))

    def test_progression_plafonnee_a_cent(self):
        kr = self._kr('250', '100')
        self.assertEqual(kr.progression_pct, Decimal('100.00'))

    def test_progression_plancher_a_zero(self):
        kr = self._kr('-10', '100')
        self.assertEqual(kr.progression_pct, Decimal('0.00'))

    def test_cible_nulle_donne_zero(self):
        kr = self._kr('40', '0')
        self.assertEqual(kr.progression_pct, Decimal('0.00'))

    def test_progression_recalculee_a_la_mise_a_jour(self):
        kr = self._kr('25', '100')
        kr.valeur_actuelle = Decimal('80')
        kr.save(update_fields=['valeur_actuelle'])
        kr.refresh_from_db()
        self.assertEqual(kr.progression_pct, Decimal('80.00'))

    def test_progression_okr_est_la_moyenne_de_ses_kr(self):
        self._kr('20', '100')
        self._kr('60', '100')
        self.assertEqual(self.okr.progression_pct, Decimal('40.00'))

    def test_okr_sans_kr_reste_a_zero(self):
        self.assertEqual(self.okr.progression_pct, Decimal('0.00'))

    def test_progression_key_result_entreprise(self):
        objectif = ObjectifEntreprise.objects.create(
            company=self.co, titre='Croissance', periode='T1-2027')
        kr = KeyResult.objects.create(
            company=self.co, objectif=objectif, libelle='CA',
            valeur_actuelle=Decimal('30'), valeur_cible=Decimal('60'))
        self.assertEqual(kr.progression_pct, Decimal('50.00'))


class OkrApiTests(TestCase):
    def setUp(self):
        self.co = make_company('nthcm8-api', 'API')
        self.rh = make_user(self.co, 'nthcm8-rh')
        self.api = auth(self.rh)
        self.employe = DossierEmploye.objects.create(
            company=self.co, matricule='A-1', nom='Beta', prenom='Deux')

    def test_creation_objectif_entreprise_pose_la_societe(self):
        resp = self.api.post(
            '/api/django/rh/objectifs-entreprise/',
            {'titre': 'Doubler la capacité', 'periode': 'T1-2027'},
            format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        objectif = ObjectifEntreprise.objects.get(id=resp.data['id'])
        self.assertEqual(objectif.company_id, self.co.id)

    def test_okr_rattache_a_un_objectif_entreprise(self):
        objectif = ObjectifEntreprise.objects.create(
            company=self.co, titre='Croissance', periode='T1-2027')
        resp = self.api.post(
            '/api/django/rh/okr-individuels/',
            {'employe': self.employe.id, 'periode': 'T1-2027',
             'titre': 'Signer 10 chantiers',
             'objectif_parent': objectif.id}, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        self.assertEqual(
            OkrIndividuel.objects.get(id=resp.data['id']).objectif_parent_id,
            objectif.id)

    def test_okr_sans_parent_reste_valide(self):
        resp = self.api.post(
            '/api/django/rh/okr-individuels/',
            {'employe': self.employe.id, 'periode': 'T1-2027',
             'titre': 'Monter en compétence'}, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        self.assertIsNone(
            OkrIndividuel.objects.get(id=resp.data['id']).objectif_parent_id)

    def test_progression_pct_non_ecrasable_par_le_client(self):
        okr = OkrIndividuel.objects.create(
            company=self.co, employe=self.employe, titre='T')
        resp = self.api.post(
            '/api/django/rh/key-results-individuels/',
            {'okr': okr.id, 'libelle': 'KR', 'valeur_cible': '100',
             'valeur_actuelle': '10', 'progression_pct': '99'},
            format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        self.assertEqual(
            KeyResultIndividuel.objects.get(id=resp.data['id'])
            .progression_pct, Decimal('10.00'))

    def test_objectif_entreprise_autre_societe_rejete(self):
        co_b = make_company('nthcm8-api-b', 'B')
        objectif_b = ObjectifEntreprise.objects.create(
            company=co_b, titre='Ailleurs', periode='T1-2027')
        resp = self.api.post(
            '/api/django/rh/okr-individuels/',
            {'employe': self.employe.id, 'titre': 'X',
             'objectif_parent': objectif_b.id}, format='json')
        self.assertEqual(resp.status_code, 400, resp.data)

    def test_isolation_societe(self):
        ObjectifEntreprise.objects.create(
            company=self.co, titre='Interne', periode='T1-2027')
        co_b = make_company('nthcm8-api-c', 'C')
        rh_b = make_user(co_b, 'nthcm8-rh-c')
        resp = auth(rh_b).get('/api/django/rh/objectifs-entreprise/')
        self.assertEqual(resp.status_code, 200, resp.data)
        resultats = (resp.data['results'] if isinstance(resp.data, dict)
                     else resp.data)
        self.assertEqual(len(resultats), 0)

    def test_filtre_par_periode(self):
        ObjectifEntreprise.objects.create(
            company=self.co, titre='T1', periode='T1-2027')
        ObjectifEntreprise.objects.create(
            company=self.co, titre='T2', periode='T2-2027')
        resp = self.api.get(
            '/api/django/rh/objectifs-entreprise/?periode=T2-2027')
        self.assertEqual(resp.status_code, 200, resp.data)
        resultats = (resp.data['results'] if isinstance(resp.data, dict)
                     else resp.data)
        self.assertEqual(len(resultats), 1)
        self.assertEqual(resultats[0]['titre'], 'T2')
