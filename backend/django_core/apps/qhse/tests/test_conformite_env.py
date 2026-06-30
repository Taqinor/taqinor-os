"""Tests QHSE38 — ConformiteEnvironnementale + relances.

Couvre :
* CRUD scopé société (``company`` posée côté serveur) + ``statut_courant``
  recalculé (expiré / à renouveler / statut enregistré) ;
* sélecteur ``conformites_a_relancer`` + action ``a-relancer`` ;
* service / action ``relancer`` (digest, best-effort) ;
* rôle + isolation société.
"""
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company

from apps.qhse.models import ConformiteEnvironnementale
from apps.qhse.selectors import conformites_a_relancer
from apps.qhse.services import relancer_conformites

User = get_user_model()

CONF_URL = '/api/django/qhse/conformites-environnementales/'


def make_company(slug, nom):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


def make_user(company, username, role='responsable'):
    return User.objects.create_user(
        username=username, password='x', company=company, role_legacy=role)


def auth_client(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


def make_conf(company, intitule='Autorisation env', date_expiration=None,
              prealerte_jours=60, statut='conforme', responsable=None):
    return ConformiteEnvironnementale.objects.create(
        company=company, intitule=intitule, date_expiration=date_expiration,
        prealerte_jours=prealerte_jours, statut=statut,
        responsable=responsable)


class ConformiteEnvSelectorTests(TestCase):
    def setUp(self):
        self.company = make_company('co-conf', 'CoConf')
        self.today = timezone.localdate()

    def test_statut_calcule_expire(self):
        conf = make_conf(
            self.company, date_expiration=self.today - timedelta(days=1))
        self.assertEqual(conf.statut_calcule(self.today), 'expire')

    def test_statut_calcule_a_renouveler(self):
        conf = make_conf(
            self.company, date_expiration=self.today + timedelta(days=30),
            prealerte_jours=60)
        self.assertEqual(conf.statut_calcule(self.today), 'a_renouveler')

    def test_statut_calcule_conforme(self):
        conf = make_conf(
            self.company, date_expiration=self.today + timedelta(days=365),
            prealerte_jours=60)
        self.assertEqual(conf.statut_calcule(self.today), 'conforme')

    def test_conformites_a_relancer(self):
        make_conf(self.company, intitule='Loin',
                  date_expiration=self.today + timedelta(days=365))
        make_conf(self.company, intitule='Bientôt',
                  date_expiration=self.today + timedelta(days=10))
        make_conf(self.company, intitule='Expirée',
                  date_expiration=self.today - timedelta(days=5))
        make_conf(self.company, intitule='Sans échéance')
        confs = conformites_a_relancer(self.company, today=self.today)
        intitules = {c.intitule for c in confs}
        self.assertEqual(intitules, {'Bientôt', 'Expirée'})

    def test_relancer_digest(self):
        resp = make_user(self.company, 'conf-owner')
        make_conf(self.company, intitule='Bientôt', responsable=resp,
                  date_expiration=self.today + timedelta(days=10))
        make_conf(self.company, intitule='Orpheline',
                  date_expiration=self.today + timedelta(days=10))
        digest = relancer_conformites(self.company, today=self.today)
        self.assertEqual(digest['total'], 2)
        self.assertEqual(digest['notifiees'], 1)
        self.assertEqual(digest['sans_responsable'], 1)


class ConformiteEnvApiTests(TestCase):
    def setUp(self):
        self.company = make_company('co-conf-api', 'CoConfApi')
        self.other_company = make_company('co-conf-api-2', 'CoConfApi2')
        self.user = make_user(self.company, 'conf-resp')
        self.client_api = auth_client(self.user)
        self.other_user = make_user(self.other_company, 'conf-resp-2')
        self.other_client = auth_client(self.other_user)
        self.today = timezone.localdate()

    def test_creation_company_serveur(self):
        resp = self.client_api.post(
            CONF_URL,
            {'intitule': 'EIE parc solaire', 'type_conformite': 'etude_impact',
             'company': self.other_company.id},
            format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        conf = ConformiteEnvironnementale.objects.get(id=resp.data['id'])
        self.assertEqual(conf.company, self.company)

    def test_statut_courant_expose(self):
        conf = make_conf(
            self.company, date_expiration=self.today + timedelta(days=10))
        resp = self.client_api.get(f'{CONF_URL}{conf.id}/')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(resp.data['statut_courant'], 'a_renouveler')

    def test_responsable_autre_societe_refuse(self):
        autre = make_user(self.other_company, 'autre-resp')
        resp = self.client_api.post(
            CONF_URL,
            {'intitule': 'X', 'responsable': autre.id}, format='json')
        self.assertEqual(resp.status_code, 400, resp.data)

    def test_a_relancer_action(self):
        make_conf(self.company, intitule='Bientôt',
                  date_expiration=self.today + timedelta(days=10))
        make_conf(self.company, intitule='Loin',
                  date_expiration=self.today + timedelta(days=365))
        resp = self.client_api.get(f'{CONF_URL}a-relancer/')
        self.assertEqual(resp.status_code, 200, resp.data)
        data = resp.data['results'] if isinstance(resp.data, dict) \
            and 'results' in resp.data else resp.data
        intitules = [c['intitule'] for c in data]
        self.assertEqual(intitules, ['Bientôt'])

    def test_relancer_action(self):
        make_conf(self.company, intitule='Bientôt',
                  date_expiration=self.today + timedelta(days=10))
        resp = self.client_api.post(f'{CONF_URL}relancer/', {}, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(resp.data['total'], 1)

    def test_role_normal_refuse(self):
        normal = make_user(self.company, 'conf-normal', role='normal')
        resp = auth_client(normal).get(CONF_URL)
        self.assertEqual(resp.status_code, 403)

    def test_isolation_societe_detail_404(self):
        conf = make_conf(self.company)
        resp = self.other_client.get(f'{CONF_URL}{conf.id}/')
        self.assertEqual(resp.status_code, 404)
