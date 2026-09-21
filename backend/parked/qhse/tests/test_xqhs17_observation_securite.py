"""XQHS17 — Observations sécurité comportementales (BBS).

Couvre :
  * la saisie rapide fonctionne (création via API, observateur/company posés
    côté serveur) ;
  * la conversion en un clic en NCR / CAPA lie les records et reste
    idempotente ;
  * une observation « sûre » ne peut pas être convertie ;
  * les compteurs cockpit (ratio sûr/à-risque, par superviseur/mois) ;
  * le scoping société.
"""
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company

from apps.qhse.models import (
    ActionCorrectivePreventive, NonConformite, ObservationSecurite,
)
from apps.qhse.services import (
    compteurs_observations_securite, convertir_observation_en_capa,
    convertir_observation_en_ncr,
)

User = get_user_model()


def make_company(slug, nom):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


def make_user(company, username, role='admin'):
    return User.objects.create_user(
        username=username, password='x', company=company, role_legacy=role)


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


def make_observation(company, observateur=None, **kwargs):
    defaults = dict(
        company=company,
        categorie=ObservationSecurite.Categorie.EPI,
        type_observation=ObservationSecurite.TypeObservation.A_RISQUE,
        description='Casque non porté',
        observateur=observateur,
    )
    defaults.update(kwargs)
    return ObservationSecurite.objects.create(**defaults)


class ObservationSecuriteApiTests(TestCase):
    def setUp(self):
        self.company = make_company('xqhs17-api', 'Xqhs17 Api')
        self.user = make_user(self.company, 'xqhs17-superviseur')

    def test_creation_pose_company_et_observateur_serveur(self):
        resp = auth(self.user).post(
            '/api/django/qhse/observations-securite/',
            {'categorie': 'hauteur', 'type_observation': 'sur',
             'description': 'Harnais correctement attaché'}, format='json')
        self.assertEqual(resp.status_code, 201)
        obs = ObservationSecurite.objects.get(id=resp.data['id'])
        self.assertEqual(obs.company_id, self.company.pk)
        self.assertEqual(obs.observateur_id, self.user.pk)

    def test_isolation_societe(self):
        other_co = make_company('xqhs17-other', 'Xqhs17 Other')
        other_user = make_user(other_co, 'xqhs17-other-user')
        make_observation(self.company, self.user)
        resp = auth(other_user).get('/api/django/qhse/observations-securite/')
        ids = [item['id'] for item in resp.data.get('results', resp.data)]
        self.assertEqual(len(ids), 0)


class ConvertirObservationEnNcrTests(TestCase):
    def setUp(self):
        self.company = make_company('xqhs17-ncr', 'Xqhs17 Ncr')
        self.user = make_user(self.company, 'xqhs17-obs-user')

    def test_convertit_observation_a_risque(self):
        obs = make_observation(self.company, self.user)
        ncr, created = convertir_observation_en_ncr(obs)
        self.assertTrue(created)
        self.assertIsInstance(ncr, NonConformite)
        obs.refresh_from_db()
        self.assertEqual(obs.non_conformite_liee_id, ncr.pk)

    def test_conversion_idempotente(self):
        obs = make_observation(self.company, self.user)
        ncr1, created1 = convertir_observation_en_ncr(obs)
        ncr2, created2 = convertir_observation_en_ncr(obs)
        self.assertTrue(created1)
        self.assertFalse(created2)
        self.assertEqual(ncr1.pk, ncr2.pk)

    def test_observation_sure_ne_se_convertit_pas(self):
        obs = make_observation(
            self.company, self.user,
            type_observation=ObservationSecurite.TypeObservation.SUR)
        with self.assertRaises(ValueError):
            convertir_observation_en_ncr(obs)


class ConvertirObservationEnCapaTests(TestCase):
    def setUp(self):
        self.company = make_company('xqhs17-capa', 'Xqhs17 Capa')
        self.user = make_user(self.company, 'xqhs17-obs-user2')

    def test_convertit_en_capa_lie_ncr(self):
        obs = make_observation(self.company, self.user)
        capa, created = convertir_observation_en_capa(obs)
        self.assertTrue(created)
        self.assertIsInstance(capa, ActionCorrectivePreventive)
        obs.refresh_from_db()
        self.assertEqual(obs.action_liee_id, capa.pk)
        self.assertIsNotNone(obs.non_conformite_liee_id)
        self.assertEqual(capa.non_conformite_id, obs.non_conformite_liee_id)

    def test_conversion_capa_idempotente(self):
        obs = make_observation(self.company, self.user)
        capa1, created1 = convertir_observation_en_capa(obs)
        capa2, created2 = convertir_observation_en_capa(obs)
        self.assertTrue(created1)
        self.assertFalse(created2)
        self.assertEqual(capa1.pk, capa2.pk)


class ConvertirActionsApiTests(TestCase):
    def setUp(self):
        self.company = make_company('xqhs17-api2', 'Xqhs17 Api2')
        self.user = make_user(self.company, 'xqhs17-api-user')

    def test_convertir_ncr_action(self):
        obs = make_observation(self.company, self.user)
        resp = auth(self.user).post(
            f'/api/django/qhse/observations-securite/{obs.pk}/convertir-ncr/')
        self.assertEqual(resp.status_code, 201)

    def test_convertir_capa_action(self):
        obs = make_observation(self.company, self.user)
        resp = auth(self.user).post(
            f'/api/django/qhse/observations-securite/{obs.pk}/convertir-capa/')
        self.assertEqual(resp.status_code, 201)

    def test_convertir_sur_renvoie_400(self):
        obs = make_observation(
            self.company, self.user,
            type_observation=ObservationSecurite.TypeObservation.SUR)
        resp = auth(self.user).post(
            f'/api/django/qhse/observations-securite/{obs.pk}/convertir-ncr/')
        self.assertEqual(resp.status_code, 400)


class CompteursObservationsSecuriteTests(TestCase):
    def setUp(self):
        self.company = make_company('xqhs17-compt', 'Xqhs17 Compt')
        self.sup1 = make_user(self.company, 'xqhs17-sup1')
        self.sup2 = make_user(self.company, 'xqhs17-sup2')

    def test_ratio_sur_a_risque(self):
        make_observation(
            self.company, self.sup1,
            type_observation=ObservationSecurite.TypeObservation.SUR)
        make_observation(
            self.company, self.sup1,
            type_observation=ObservationSecurite.TypeObservation.SUR)
        make_observation(
            self.company, self.sup2,
            type_observation=ObservationSecurite.TypeObservation.A_RISQUE)
        compteurs = compteurs_observations_securite(self.company)
        self.assertEqual(compteurs['total'], 3)
        self.assertEqual(compteurs['sures'], 2)
        self.assertEqual(compteurs['a_risque'], 1)
        self.assertAlmostEqual(compteurs['ratio_sur_pct'], 66.7, places=1)

    def test_par_superviseur_mois(self):
        make_observation(self.company, self.sup1)
        make_observation(self.company, self.sup2)
        compteurs = compteurs_observations_securite(self.company)
        superviseurs = {
            item['observateur_id'] for item in compteurs['par_superviseur_mois']
        }
        self.assertEqual(superviseurs, {self.sup1.pk, self.sup2.pk})

    def test_scope_societe(self):
        other_co = make_company('xqhs17-compt-other', 'Xqhs17 Compt Other')
        other_user = make_user(other_co, 'xqhs17-compt-other-user')
        make_observation(other_co, other_user)
        compteurs = compteurs_observations_securite(self.company)
        self.assertEqual(compteurs['total'], 0)
