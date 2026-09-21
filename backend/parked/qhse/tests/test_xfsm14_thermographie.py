"""Tests XFSM14 — Thermographie IR : points chauds classés + baseline/suivi.

Couvre :

* le classement automatique de sévérité par seuil (observation / à surveiller
  / intervention requise) ;
* la NCR auto-créée sur sévérité maximale ;
* la comparaison recette (baseline) vs dernier suivi.
"""
from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company

from apps.qhse.models import NonConformite, ReleveThermographie
from apps.qhse.services import (
    comparer_campagnes_thermographie, enregistrer_releve_thermographie,
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


class ClassementSeveriteTests(TestCase):
    def setUp(self):
        self.company = make_company('co-xfsm14-classe', 'CoXfsm14Classe')

    def test_observation_sous_seuil(self):
        releve = ReleveThermographie.objects.create(
            company=self.company, equipement_ref='ONDULEUR-1', delta_t=2)
        self.assertEqual(
            releve.classe_severite, ReleveThermographie.Severite.OBSERVATION)

    def test_a_surveiller_entre_seuils(self):
        releve = ReleveThermographie.objects.create(
            company=self.company, equipement_ref='ONDULEUR-1', delta_t=8)
        self.assertEqual(
            releve.classe_severite, ReleveThermographie.Severite.A_SURVEILLER)

    def test_intervention_requise_au_dessus_seuil(self):
        releve = ReleveThermographie.objects.create(
            company=self.company, equipement_ref='ONDULEUR-1', delta_t=20)
        self.assertEqual(
            releve.classe_severite,
            ReleveThermographie.Severite.INTERVENTION_REQUISE)

    def test_seuils_parametrables(self):
        releve = ReleveThermographie.objects.create(
            company=self.company, equipement_ref='ONDULEUR-1', delta_t=4,
            seuil_a_surveiller=3, seuil_intervention=10)
        self.assertEqual(
            releve.classe_severite, ReleveThermographie.Severite.A_SURVEILLER)


class EnregistrerReleveThermographieTests(TestCase):
    def setUp(self):
        self.company = make_company('co-xfsm14-ncr', 'CoXfsm14Ncr')

    def test_intervention_requise_leve_ncr(self):
        releve = enregistrer_releve_thermographie(
            company=self.company, equipement_ref='STRING-3', delta_t=25)
        self.assertIsNotNone(releve.ncr_id)
        ncr = NonConformite.objects.get(pk=releve.ncr_id)
        self.assertEqual(ncr.gravite, NonConformite.Gravite.MAJEURE)
        self.assertEqual(ncr.company, self.company)

    def test_observation_ne_leve_pas_ncr(self):
        releve = enregistrer_releve_thermographie(
            company=self.company, equipement_ref='STRING-4', delta_t=1)
        self.assertIsNone(releve.ncr_id)

    def test_a_surveiller_ne_leve_pas_ncr(self):
        releve = enregistrer_releve_thermographie(
            company=self.company, equipement_ref='STRING-5', delta_t=8)
        self.assertIsNone(releve.ncr_id)


class CompararCampagnesTests(TestCase):
    def setUp(self):
        self.company = make_company('co-xfsm14-comp', 'CoXfsm14Comp')

    def test_compare_recette_et_suivi(self):
        ReleveThermographie.objects.create(
            company=self.company, equipement_ref='ONDULEUR-2', delta_t=3,
            campagne=ReleveThermographie.Campagne.RECETTE,
            date_releve=date(2026, 1, 1))
        ReleveThermographie.objects.create(
            company=self.company, equipement_ref='ONDULEUR-2', delta_t=9,
            campagne=ReleveThermographie.Campagne.SUIVI,
            date_releve=date(2026, 6, 1))
        result = comparer_campagnes_thermographie(self.company, 'ONDULEUR-2')
        self.assertIsNotNone(result['recette'])
        self.assertIsNotNone(result['suivi'])
        self.assertEqual(result['delta'], 6)

    def test_sans_recette_delta_none(self):
        ReleveThermographie.objects.create(
            company=self.company, equipement_ref='ONDULEUR-3', delta_t=4,
            campagne=ReleveThermographie.Campagne.SUIVI)
        result = comparer_campagnes_thermographie(self.company, 'ONDULEUR-3')
        self.assertIsNone(result['recette'])
        self.assertIsNone(result['delta'])

    def test_isolation_societe(self):
        autre = make_company('co-xfsm14-comp-autre', 'CoXfsm14CompAutre')
        ReleveThermographie.objects.create(
            company=self.company, equipement_ref='ONDULEUR-4', delta_t=3,
            campagne=ReleveThermographie.Campagne.RECETTE)
        result = comparer_campagnes_thermographie(autre, 'ONDULEUR-4')
        self.assertIsNone(result['recette'])


class ReleveThermographieApiTests(TestCase):
    """AUDV15 (DRAFT165-91/92) — aucun serializer ni viewset n'existait,
    capacité totalement invisible côté API malgré le service déjà testé
    ci-dessus."""
    BASE = '/api/django/qhse/releves-thermographie/'

    def setUp(self):
        self.co = make_company('co-xfsm14-api', 'CoXfsm14Api')
        self.user = make_user(self.co, 'xfsm14-api-user')

    def test_create_leve_ncr_sur_severite_maximale(self):
        resp = auth(self.user).post(self.BASE, {
            'equipement_ref': 'STRING-9', 'delta_t': '25.00',
        }, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        self.assertEqual(resp.data['classe_severite'], 'intervention_requise')
        self.assertIsNotNone(resp.data['ncr'])
        releve = ReleveThermographie.objects.get(id=resp.data['id'])
        self.assertEqual(releve.company, self.co)
        self.assertEqual(releve.releve_par, self.user)

    def test_classe_severite_non_receptible_en_ecriture(self):
        """``classe_severite``/``ncr`` sont DÉRIVÉS — un POST qui tente de les
        forcer est ignoré (dérivation serveur seule fait foi)."""
        resp = auth(self.user).post(self.BASE, {
            'equipement_ref': 'STRING-10', 'delta_t': '1.00',
            'classe_severite': 'intervention_requise',
        }, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        self.assertEqual(resp.data['classe_severite'], 'observation')
        self.assertIsNone(resp.data['ncr'])

    def test_filtre_par_equipement_ref(self):
        ReleveThermographie.objects.create(
            company=self.co, equipement_ref='A', delta_t=1)
        ReleveThermographie.objects.create(
            company=self.co, equipement_ref='B', delta_t=1)
        resp = auth(self.user).get(f'{self.BASE}?equipement_ref=A')
        self.assertEqual(resp.status_code, 200)
        rows = resp.data['results'] if isinstance(resp.data, dict) else resp.data
        self.assertEqual(len(rows), 1)

    def test_isolation_societe(self):
        autre = make_company('co-xfsm14-api-b', 'B')
        ReleveThermographie.objects.create(
            company=autre, equipement_ref='X', delta_t=1)
        resp = auth(self.user).get(self.BASE)
        rows = resp.data['results'] if isinstance(resp.data, dict) else resp.data
        self.assertEqual(len(rows), 0)

    def test_comparer_action(self):
        ReleveThermographie.objects.create(
            company=self.co, equipement_ref='ONDULEUR-9', delta_t=3,
            campagne=ReleveThermographie.Campagne.RECETTE)
        ReleveThermographie.objects.create(
            company=self.co, equipement_ref='ONDULEUR-9', delta_t=9,
            campagne=ReleveThermographie.Campagne.SUIVI)
        resp = auth(self.user).get(
            f'{self.BASE}comparer/?equipement_ref=ONDULEUR-9')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertIsNotNone(resp.data['recette'])
        self.assertIsNotNone(resp.data['suivi'])
        self.assertEqual(resp.data['delta'], Decimal('6.00'))

    def test_comparer_equipement_ref_requis(self):
        resp = auth(self.user).get(f'{self.BASE}comparer/')
        self.assertEqual(resp.status_code, 400)
