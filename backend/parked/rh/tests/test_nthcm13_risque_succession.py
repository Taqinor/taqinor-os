"""Tests NTHCM13 — cockpit succession, criticité du poste × flight-risk.

Couvre :
* un poste critique SANS successeur prêt + titulaire à risque élevé remonte
  en tête (``risque_vacance=True``) ;
* un poste COUVERT par un successeur ``pret_immediat`` n'apparaît pas en
  risque, même titulaire exposé ;
* le seuil est configurable (Paramètres RH + override ``?seuil=``) ;
* le scorer XRH31 n'est pas modifié (il est seulement lu, via un patch de
  ``risque_attrition_employe`` pour rendre le test déterministe) ;
* isolation société.
"""
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.rh import selectors
from apps.rh.models import (
    DossierEmploye,
    PlanSuccession,
    PosteCle,
    Poste,
    ReglageRH,
)

User = get_user_model()

RISQUE = 'apps.rh.selectors.risque_attrition_employe'


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


def score_fixe(score):
    """Remplace le scorer XRH31 (pur) par un score déterministe."""
    def _faux(employe, today=None):
        return {'employe_id': employe.id, 'score': score,
                'band': 'élevé' if score >= 67 else 'moyen', 'factors': {}}
    return _faux


class RisqueSuccessionTests(TestCase):
    def setUp(self):
        self.co = make_company('nthcm13-a', 'A')
        self.rh = make_user(self.co, 'nthcm13-rh')
        self.api = auth(self.rh)
        self.poste = Poste.objects.create(
            company=self.co, intitule='Chef de chantier')
        self.titulaire = DossierEmploye.objects.create(
            company=self.co, matricule='T-1', nom='Titulaire', prenom='Un',
            poste_ref=self.poste)
        self.poste_cle = PosteCle.objects.create(
            company=self.co, poste=self.poste,
            criticite=PosteCle.Criticite.CRITIQUE)
        self.successeur = DossierEmploye.objects.create(
            company=self.co, matricule='S-1', nom='Successeur', prenom='Un')

    def test_poste_critique_non_couvert_titulaire_a_risque_remonte(self):
        with patch(RISQUE, side_effect=score_fixe(85.0)):
            lignes = selectors.risque_succession(self.co)
        self.assertEqual(len(lignes), 1)
        self.assertTrue(lignes[0]['risque_vacance'])
        self.assertEqual(lignes[0]['seuil'], 60)
        self.assertEqual(len(lignes[0]['titulaires_a_risque']), 1)

    def test_poste_couvert_par_un_successeur_pret_n_apparait_pas(self):
        PlanSuccession.objects.create(
            company=self.co, poste_cle=self.poste_cle,
            successeur=self.successeur,
            readiness=PlanSuccession.Readiness.PRET_IMMEDIAT)
        with patch(RISQUE, side_effect=score_fixe(85.0)):
            lignes = selectors.risque_succession(self.co)
        self.assertFalse(lignes[0]['risque_vacance'])
        self.assertEqual(lignes[0]['successeurs_prets_immediat'], 1)

    def test_successeur_non_pret_ne_couvre_pas(self):
        PlanSuccession.objects.create(
            company=self.co, poste_cle=self.poste_cle,
            successeur=self.successeur,
            readiness=PlanSuccession.Readiness.PRET_3ANS)
        with patch(RISQUE, side_effect=score_fixe(85.0)):
            lignes = selectors.risque_succession(self.co)
        self.assertTrue(lignes[0]['risque_vacance'])

    def test_titulaire_sous_le_seuil_n_est_pas_a_risque(self):
        with patch(RISQUE, side_effect=score_fixe(30.0)):
            lignes = selectors.risque_succession(self.co)
        self.assertFalse(lignes[0]['risque_vacance'])
        self.assertEqual(lignes[0]['titulaires_a_risque'], [])

    def test_poste_sans_titulaire_n_est_pas_a_risque(self):
        self.titulaire.statut = DossierEmploye.Statut.SORTI
        self.titulaire.save(update_fields=['statut'])
        with patch(RISQUE, side_effect=score_fixe(99.0)):
            lignes = selectors.risque_succession(self.co)
        self.assertFalse(lignes[0]['risque_vacance'])

    def test_seuil_configurable_par_reglage(self):
        ReglageRH.objects.create(
            company=self.co, seuil_risque_succession=20)
        with patch(RISQUE, side_effect=score_fixe(30.0)):
            lignes = selectors.risque_succession(self.co)
        self.assertEqual(lignes[0]['seuil'], 20)
        self.assertTrue(lignes[0]['risque_vacance'])

    def test_seuil_override_par_parametre(self):
        with patch(RISQUE, side_effect=score_fixe(30.0)):
            lignes = selectors.risque_succession(self.co, seuil=25)
        self.assertEqual(lignes[0]['seuil'], 25)
        self.assertTrue(lignes[0]['risque_vacance'])

    def test_postes_a_risque_en_tete(self):
        poste_calme = Poste.objects.create(
            company=self.co, intitule='Aide-poseur')
        PosteCle.objects.create(
            company=self.co, poste=poste_calme,
            criticite=PosteCle.Criticite.FAIBLE)
        with patch(RISQUE, side_effect=score_fixe(85.0)):
            lignes = selectors.risque_succession(self.co)
        self.assertEqual(len(lignes), 2)
        self.assertTrue(lignes[0]['risque_vacance'])
        self.assertEqual(lignes[0]['poste_intitule'], 'Chef de chantier')

    def test_endpoint_risque_succession(self):
        with patch(RISQUE, side_effect=score_fixe(85.0)):
            resp = self.api.get(
                '/api/django/rh/postes-cles/risque-succession/')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertTrue(resp.data[0]['risque_vacance'])

    def test_endpoint_cockpit_postes_a_risque(self):
        with patch(RISQUE, side_effect=score_fixe(85.0)):
            resp = self.api.get('/api/django/rh/cockpit/postes-a-risque/')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(len(resp.data), 1)
        self.assertEqual(resp.data[0]['poste_cle_id'], self.poste_cle.id)

    def test_cockpit_postes_a_risque_vide_quand_couvert(self):
        PlanSuccession.objects.create(
            company=self.co, poste_cle=self.poste_cle,
            successeur=self.successeur,
            readiness=PlanSuccession.Readiness.PRET_IMMEDIAT)
        with patch(RISQUE, side_effect=score_fixe(85.0)):
            resp = self.api.get('/api/django/rh/cockpit/postes-a-risque/')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(list(resp.data), [])

    def test_isolation_societe(self):
        co_b = make_company('nthcm13-b', 'B')
        rh_b = make_user(co_b, 'nthcm13-rh-b')
        with patch(RISQUE, side_effect=score_fixe(85.0)):
            self.assertEqual(selectors.risque_succession(co_b), [])
            resp = auth(rh_b).get(
                '/api/django/rh/postes-cles/risque-succession/')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(list(resp.data), [])
