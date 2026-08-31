"""Tests NTDATA33 — drill-down d'une cellule de pivot vers les enregistrements.

Couvre :
  * « 12 notes en catégorie X » renvoie les 12 identifiants cliquables ;
  * chaque enregistrement porte un lien profond vers l'écran de l'app ;
  * un dataset sans route déclarée reste forable (lien vide, jamais d'invention) ;
  * la liste blanche du dataset est respectée (champ inconnu → 400 FR) ;
  * dataset inconnu → 404 FR ;
  * le catalogue des mappings est consultable ;
  * la borne dure de lignes n'est pas contournable.
"""
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIRequestFactory, force_authenticate

from authentication.models import Company
from core import dashboard_data, data_explorer
from core.drill_api import DrillDownView
from core.models import ChangelogEntry

User = get_user_model()


def _changelog_dataset(company, user):
    return ChangelogEntry.objects.all()


class DrillDownTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.company = Company.objects.create(nom='ACME')
        cls.user = User.objects.create_user(
            username='drill_user', password='x', role_legacy='normal',
            company=cls.company)
        cls.factory = APIRequestFactory()

    def setUp(self):
        dashboard_data._reset_drill_for_tests()
        data_explorer.register_dataset(
            'changelog', 'Nouveautés', ['id', 'titre', 'categorie'],
            _changelog_dataset)
        dashboard_data.register_drill(
            'changelog', id_field='id', route='/parametres/nouveautes/{id}')
        self.correctifs = [
            ChangelogEntry.objects.create(titre=f'C{i}', categorie='correctif')
            for i in range(3)
        ]
        ChangelogEntry.objects.create(titre='N', categorie='nouveaute')

    def _post(self, corps):
        req = self.factory.post('/data-explorer/drill/', corps, format='json')
        force_authenticate(req, user=self.user)
        return DrillDownView.as_view()(req)

    def test_cellule_renvoie_les_enregistrements_cliquables(self):
        resp = self._post({'dataset': 'changelog',
                           'group_by': {'categorie': 'correctif'}})
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data['nb'], 3)
        ids = {e['id'] for e in resp.data['enregistrements']}
        self.assertEqual(ids, {c.pk for c in self.correctifs})

    def test_lien_profond_vers_lecran_de_lapp(self):
        resp = self._post({'dataset': 'changelog',
                           'group_by': {'categorie': 'correctif'}})
        premier = resp.data['enregistrements'][0]
        self.assertEqual(premier['lien'],
                         f"/parametres/nouveautes/{premier['id']}")
        self.assertEqual(resp.data['route'], '/parametres/nouveautes/{id}')

    def test_dataset_sans_route_reste_forable_sans_lien_invente(self):
        dashboard_data._reset_drill_for_tests()
        resp = self._post({'dataset': 'changelog',
                           'group_by': {'categorie': 'nouveaute'}})
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data['nb'], 1)
        self.assertEqual(resp.data['enregistrements'][0]['lien'], '')

    def test_champ_hors_liste_blanche_renvoie_400(self):
        resp = self._post({'dataset': 'changelog',
                           'group_by': {'secret': 'x'}})
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_dataset_inconnu_renvoie_404(self):
        resp = self._post({'dataset': 'inexistant', 'group_by': {}})
        self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)

    def test_dataset_manquant_renvoie_400(self):
        resp = self._post({'group_by': {}})
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_group_by_non_objet_renvoie_400(self):
        resp = self._post({'dataset': 'changelog', 'group_by': ['x']})
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_catalogue_des_mappings(self):
        req = self.factory.get('/data-explorer/drill/')
        force_authenticate(req, user=self.user)
        resp = DrillDownView.as_view()(req)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        datasets = {m['dataset'] for m in resp.data['mappings']}
        self.assertIn('changelog', datasets)

    def test_borne_dure_de_lignes(self):
        resultat = dashboard_data.drill(
            'changelog', self.company, self.user, limit=99999)
        self.assertLessEqual(resultat['nb'], 1000)

    def test_lien_profond_sans_gabarit_id(self):
        self.assertEqual(
            dashboard_data.lien_profond('/ventes/devis/', 12),
            '/ventes/devis/12')
        self.assertEqual(dashboard_data.lien_profond('', 12), '')
