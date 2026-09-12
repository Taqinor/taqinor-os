"""NTDATA6 — endpoint d'exécution self-service `POST core/data-explorer/run/`.

Couvre :
  * une requête ad-hoc renvoie des lignes JSON (aucun SQL brut en entrée) ;
  * le scoping SOCIÉTÉ est celui du dataset (aucune fuite cross-tenant) ;
  * un champ hors liste blanche → 400, un dataset inconnu → 404 ;
  * le plafond de lignes est REFUSÉ explicitement, jamais rogné en silence ;
  * la permission : un utilisateur non responsable/admin est refusé.

Découplage : dataset de test sur un modèle de FONDATION — aucun import d'app
domaine.
"""
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIRequestFactory, force_authenticate

from authentication.models import Company
from core import data_explorer
from core.views import LIMITE_MAX_EXPLORATION, DataExplorerRunView

User = get_user_model()


def _provider(company, user):
    return User.objects.filter(company=company)


class RunEndpointTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.company = Company.objects.create(nom='NTDATA6 SA',
                                             slug='ntdata6-sa')
        cls.autre = Company.objects.create(nom='NTDATA6 Autre',
                                           slug='ntdata6-autre')
        cls.responsable = User.objects.create_user(
            username='ntdata6_resp', password='x', company=cls.company,
            role_legacy='admin')
        cls.simple = User.objects.create_user(
            username='ntdata6_simple', password='x', company=cls.company,
            role_legacy='normal')
        User.objects.create_user(
            username='ntdata6_ailleurs', password='x', company=cls.autre)

    def setUp(self):
        self.factory = APIRequestFactory()
        data_explorer.register_dataset(
            'ntdata6_ds', 'Utilisateurs NTDATA6',
            ['id', 'username', 'is_active'], _provider)

    def _post(self, corps, user=None):
        request = self.factory.post(
            '/api/django/core/data-explorer/run/', corps, format='json')
        force_authenticate(request, user=user or self.responsable)
        return DataExplorerRunView.as_view()(request)

    def test_requete_adhoc_renvoie_des_lignes(self):
        reponse = self._post({'dataset': 'ntdata6_ds',
                              'select': ['username']})
        self.assertEqual(reponse.status_code, status.HTTP_200_OK)
        noms = {r['username'] for r in reponse.data['rows']}
        self.assertIn('ntdata6_resp', noms)
        # Scoping société : l'utilisateur de l'autre société n'y est pas.
        self.assertNotIn('ntdata6_ailleurs', noms)
        self.assertEqual(reponse.data['nb'], len(reponse.data['rows']))

    def test_group_by_et_agregat(self):
        reponse = self._post({
            'dataset': 'ntdata6_ds',
            'group_by': ['is_active'],
            'aggregates': [{'alias': 'n', 'fn': 'count', 'field': 'id'}],
        })
        self.assertEqual(reponse.status_code, status.HTTP_200_OK)
        self.assertEqual(sum(r['n'] for r in reponse.data['rows']), 2)

    def test_order_alias_de_order_by(self):
        reponse = self._post({'dataset': 'ntdata6_ds',
                              'select': ['username'],
                              'order': ['-username']})
        self.assertEqual(reponse.status_code, status.HTTP_200_OK)
        noms = [r['username'] for r in reponse.data['rows']]
        self.assertEqual(noms, sorted(noms, reverse=True))

    def test_dataset_requis(self):
        reponse = self._post({'select': ['username']})
        self.assertEqual(reponse.status_code, status.HTTP_400_BAD_REQUEST)

    def test_dataset_inconnu_404(self):
        reponse = self._post({'dataset': 'ntdata6_absent'})
        self.assertEqual(reponse.status_code, status.HTTP_404_NOT_FOUND)

    def test_champ_hors_liste_blanche_400(self):
        reponse = self._post({'dataset': 'ntdata6_ds',
                              'select': ['password']})
        self.assertEqual(reponse.status_code, status.HTTP_400_BAD_REQUEST)

    def test_limite_au_dela_du_plafond_refusee(self):
        reponse = self._post({'dataset': 'ntdata6_ds',
                              'limit': LIMITE_MAX_EXPLORATION + 1})
        self.assertEqual(reponse.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn(str(LIMITE_MAX_EXPLORATION), reponse.data['detail'])

    def test_limite_invalide_refusee(self):
        for mauvaise in ('beaucoup', 0, -3):
            reponse = self._post({'dataset': 'ntdata6_ds', 'limit': mauvaise})
            self.assertEqual(reponse.status_code,
                             status.HTTP_400_BAD_REQUEST, mauvaise)

    def test_limite_respectee(self):
        reponse = self._post({'dataset': 'ntdata6_ds', 'select': ['id'],
                              'limit': 1})
        self.assertEqual(reponse.status_code, status.HTTP_200_OK)
        self.assertEqual(reponse.data['nb'], 1)

    def test_utilisateur_non_responsable_refuse(self):
        reponse = self._post({'dataset': 'ntdata6_ds'}, user=self.simple)
        self.assertEqual(reponse.status_code, status.HTTP_403_FORBIDDEN)
