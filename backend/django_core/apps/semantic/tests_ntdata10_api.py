"""NTDATA10 — CRUD des métriques + résolution par clé.

Couvre :
  * le critère d'acceptation : une métrique définie une fois (POST) est
    appelable par CLÉ (``GET metriques/<cle>/valeur/``) ;
  * la société est forcée serveur (un ``company`` dans le corps est ignoré),
    le catalogue ne liste que la société de l'appelant ;
  * clé dupliquée ⇒ 409, mesure malformée ⇒ 400 au message français ;
  * éditer la définition fige une version SIGNÉE de l'acteur (NTDATA9) ;
  * supprimer = désactiver (la valeur devient un 404, l'historique reste) ;
  * routage : une clé n'est jamais lue comme un identifiant de détail.
"""
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import resolve
from rest_framework import status
from rest_framework.test import APIRequestFactory, force_authenticate

from apps.semantic.models import MetricDefinition, MetricDefinitionVersion
from apps.semantic.views import (
    MetricDefinitionViewSet, MetriqueValeurView, parametres_de_resolution,
)
from authentication.models import Company
from core import data_explorer

User = get_user_model()

BASE = '/api/django/semantic/metriques/'


def _societes_dataset(company, user):
    return Company.objects.filter(pk=company.pk)


class _Base(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.company = Company.objects.create(nom='NTDATA10 SA',
                                             slug='ntdata10-sa')
        cls.autre = Company.objects.create(nom='NTDATA10 Autre',
                                           slug='ntdata10-autre')
        cls.admin = User.objects.create_user(
            username='ntdata10_admin', password='x', company=cls.company,
            role_legacy='admin')
        cls.simple = User.objects.create_user(
            username='ntdata10_simple', password='x', company=cls.company,
            role_legacy='normal')

    def setUp(self):
        data_explorer.register_dataset(
            'ntdata10_societes', 'Sociétés (test)', ['id', 'nom'],
            _societes_dataset)

    def _vue(self, methode, actions, url, data=None, user=None, **kwargs):
        factory = APIRequestFactory()
        requete = getattr(factory, methode)(url, data, format='json') \
            if data is not None else getattr(factory, methode)(url)
        force_authenticate(requete, user=user or self.admin)
        return MetricDefinitionViewSet.as_view(actions)(requete, **kwargs)

    def _creer(self, **corps):
        donnees = {'cle': 'nb_societes', 'libelle': 'Nombre de sociétés',
                   'dataset': 'ntdata10_societes',
                   'mesure': {'field': 'id', 'agg': 'count'},
                   'unite': 'nombre'}
        donnees.update(corps)
        return self._vue('post', {'post': 'create'}, BASE, donnees)

    def _valeur(self, cle, params=None, user=None):
        requete = APIRequestFactory().get(f'{BASE}{cle}/valeur/',
                                          params or {})
        force_authenticate(requete, user=user or self.admin)
        return MetriqueValeurView.as_view()(requete, cle=cle)


class CrudMetriquesTests(_Base):
    def test_definie_une_fois_appelable_par_cle(self):
        """Critère d'acceptation NTDATA10."""
        reponse = self._creer()
        self.assertEqual(reponse.status_code, status.HTTP_201_CREATED,
                         reponse.data)
        valeur = self._valeur('nb_societes', {'group_by': ''})
        self.assertEqual(valeur.status_code, status.HTTP_200_OK, valeur.data)
        # Le dataset de test rend la SEULE société de l'appelant.
        self.assertEqual(valeur.data['valeur'], 1)
        self.assertEqual(valeur.data['cle'], 'nb_societes')

    def test_societe_forcee_serveur(self):
        reponse = self._creer(company=self.autre.pk)
        self.assertEqual(reponse.status_code, status.HTTP_201_CREATED)
        definition = MetricDefinition.objects.get(pk=reponse.data['id'])
        self.assertEqual(definition.company_id, self.company.pk)

    def test_catalogue_borne_a_la_societe(self):
        MetricDefinition.objects.create(
            company=self.autre, cle='chez_le_voisin', libelle='Voisin',
            dataset='ntdata10_societes', mesure={'agg': 'count'})
        self._creer()
        reponse = self._vue('get', {'get': 'list'}, BASE)
        self.assertEqual(reponse.status_code, status.HTTP_200_OK)
        lignes = reponse.data.get('results', reponse.data)
        self.assertEqual([m['cle'] for m in lignes], ['nb_societes'])

    def test_cle_dupliquee_409(self):
        self._creer()
        self.assertEqual(self._creer().status_code, status.HTTP_409_CONFLICT)

    def test_mesure_malformee_400_en_francais(self):
        reponse = self._creer(mesure={'field': 'id', 'agg': 'median'})
        self.assertEqual(reponse.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('Agrégation inconnue', str(reponse.data))

    def test_cle_mal_formee_400(self):
        reponse = self._creer(cle='Marge Brute')
        self.assertEqual(reponse.status_code, status.HTTP_400_BAD_REQUEST)

    def test_edition_fige_une_version_signee(self):
        pk = self._creer().data['id']
        reponse = self._vue(
            'patch', {'patch': 'partial_update'}, f'{BASE}{pk}/',
            {'mesure': {'field': 'id', 'agg': 'max'}}, pk=pk)
        self.assertEqual(reponse.status_code, status.HTTP_200_OK, reponse.data)
        versions = MetricDefinitionVersion.objects.filter(
            metric_definition_id=pk).order_by('version')
        self.assertEqual([v.version for v in versions], [1, 2])
        self.assertTrue(all(v.auteur_id == self.admin.pk for v in versions))

    def test_suppression_desactive(self):
        pk = self._creer().data['id']
        reponse = self._vue('delete', {'delete': 'destroy'}, f'{BASE}{pk}/',
                            pk=pk)
        self.assertEqual(reponse.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(MetricDefinition.objects.get(pk=pk).actif)
        self.assertEqual(self._valeur('nb_societes').status_code,
                         status.HTTP_404_NOT_FOUND)

    def test_non_responsable_refuse(self):
        reponse = self._vue('get', {'get': 'list'}, BASE, user=self.simple)
        self.assertEqual(reponse.status_code, status.HTTP_403_FORBIDDEN)


class ValeurParCleTests(_Base):
    def test_inconnue_404(self):
        self.assertEqual(self._valeur('inexistante').status_code,
                         status.HTTP_404_NOT_FOUND)

    def test_filtre_hors_liste_blanche_400(self):
        self._creer()
        reponse = self._valeur('nb_societes',
                               {'group_by': '', 'filters': '{"slug": "x"}'})
        self.assertEqual(reponse.status_code, status.HTTP_400_BAD_REQUEST)

    def test_filters_json_invalide_400(self):
        self._creer()
        reponse = self._valeur('nb_societes', {'filters': '{pas du json'})
        self.assertEqual(reponse.status_code, status.HTTP_400_BAD_REQUEST)

    def test_parametres_lus(self):
        group_by, period, filters = parametres_de_resolution({
            'group_by': 'mois, statut', 'period': '2026-01-01,2026-03-31',
            'filters': '{"actif": true}'})
        self.assertEqual(group_by, ['mois', 'statut'])
        self.assertEqual(period, {'debut': '2026-01-01', 'fin': '2026-03-31'})
        self.assertEqual(filters, {'actif': True})
        # Absent ⇒ None (dimensions par défaut) ; vide ⇒ [] (valeur globale).
        self.assertIsNone(parametres_de_resolution({})[0])
        self.assertEqual(parametres_de_resolution({'group_by': ''})[0], [])

    def test_pour_agent_ntdata12(self):
        """NTDATA12 — catalogue lecture seule, sans recette, lisible par tout
        rôle interne, métriques ACTIVES de la société seulement."""
        self._creer(description='Combien de sociétés.')
        MetricDefinition.objects.create(
            company=self.company, cle='inactive', libelle='Inactive',
            dataset='ntdata10_societes', mesure={'agg': 'count'},
            actif=False)
        MetricDefinition.objects.create(
            company=self.autre, cle='chez_le_voisin', libelle='Voisin',
            dataset='ntdata10_societes', mesure={'agg': 'count'})
        reponse = self._vue('get', {'get': 'pour_agent'},
                            f'{BASE}pour-agent/', user=self.simple)
        self.assertEqual(reponse.status_code, status.HTTP_200_OK)
        self.assertEqual(reponse.data['metriques'], [{
            'cle': 'nb_societes', 'libelle': 'Nombre de sociétés',
            'description': 'Combien de sociétés.', 'unite': 'nombre'}])
        self.assertIs(resolve(f'{BASE}pour-agent/').func.cls,
                      MetricDefinitionViewSet)

    def test_routage_cle_jamais_lue_comme_detail(self):
        self.assertIs(resolve(f'{BASE}ca_ht/valeur/').func.view_class,
                      MetriqueValeurView)
        self.assertEqual(resolve(f'{BASE}12/').func.cls,
                         MetricDefinitionViewSet)
