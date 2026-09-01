"""Tests NTDATA32 — filtres globaux de dashboard.

Couvre :
  * changer la PÉRIODE met à jour TOUS les widgets en UNE seule requête ;
  * un widget qui ne déclare pas la dimension n'est pas filtré de travers ;
  * les filtres du ``layout`` s'appliquent par défaut ;
  * un champ hors liste blanche remonte en erreur DU widget (pas de 500, et le
    dashboard n'est pas blanchi) ;
  * ``?filtre=`` illisible → 400 FR ; aucune persistance du filtre transitoire ;
  * isolation société (le dashboard d'une autre société est introuvable).
"""
import json
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIRequestFactory, force_authenticate

from authentication.models import Company
from core import dashboard_data, data_explorer
from core.models import ChangelogEntry, Dashboard
from core.views import DashboardViewSet

User = get_user_model()


def _changelog_dataset(company, user):
    return ChangelogEntry.objects.all()


class FiltresGlobauxTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.company = Company.objects.create(nom='ACME')
        cls.autre = Company.objects.create(nom='Autre')
        cls.user = User.objects.create_user(
            username='dash_user', password='x', role_legacy='normal',
            company=cls.company)
        cls.factory = APIRequestFactory()
        cls.t0 = timezone.now() - timedelta(days=30)
        cls.t1 = timezone.now() - timedelta(days=1)

    def setUp(self):
        data_explorer.register_dataset(
            'changelog', 'Nouveautés', ['id', 'titre', 'publie_le', 'categorie'],
            _changelog_dataset)
        ChangelogEntry.objects.create(titre='Vieux', publie_le=self.t0)
        ChangelogEntry.objects.create(titre='Récent', publie_le=self.t1)

    def _dashboard(self, layout, company=None):
        return Dashboard.objects.create(
            company=company or self.company, titre='Direction', layout=layout)

    def _layout(self, **extra):
        layout = {
            'widgets': [
                {'id': 'liste', 'titre': 'Notes', 'dataset': 'changelog',
                 'spec': {'select': ['titre']},
                 'filtres_globaux': {'periode': 'publie_le'}},
                {'id': 'sans_mapping', 'titre': 'Toutes',
                 'dataset': 'changelog', 'spec': {'select': ['titre']}},
            ],
        }
        layout.update(extra)
        return layout

    def _get_donnees(self, dashboard, filtre=None):
        data = {} if filtre is None else {'filtre': filtre}
        req = self.factory.get(f'/dashboards/{dashboard.pk}/donnees/', data)
        force_authenticate(req, user=self.user)
        return DashboardViewSet.as_view({'get': 'donnees'})(
            req, pk=dashboard.pk)

    def test_periode_met_a_jour_tous_les_widgets_en_une_requete(self):
        dash = self._dashboard(self._layout())
        filtre = json.dumps({'periode': {
            'debut': (self.t1 - timedelta(days=2)).isoformat()}})
        resp = self._get_donnees(dash, filtre)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        widgets = {w['id']: w for w in resp.data['widgets']}
        self.assertEqual(len(widgets), 2)
        # Le widget qui DÉCLARE la période est filtré…
        self.assertEqual([r['titre'] for r in widgets['liste']['rows']],
                         ['Récent'])
        # …celui qui ne la déclare pas garde sa population complète.
        self.assertEqual(len(widgets['sans_mapping']['rows']), 2)

    def test_filtres_du_layout_appliques_par_defaut(self):
        layout = self._layout(global_filters={
            'periode': {'debut': (self.t1 - timedelta(days=2)).isoformat()}})
        dash = self._dashboard(layout)
        resp = self._get_donnees(dash)
        widgets = {w['id']: w for w in resp.data['widgets']}
        self.assertEqual([r['titre'] for r in widgets['liste']['rows']],
                         ['Récent'])
        self.assertIn('periode', resp.data['filtres_globaux'])

    def test_filtre_transitoire_nest_jamais_persiste(self):
        dash = self._dashboard(self._layout())
        filtre = json.dumps({'periode': {'debut': self.t1.isoformat()}})
        self._get_donnees(dash, filtre)
        dash.refresh_from_db()
        self.assertNotIn('global_filters', dash.layout)

    def test_champ_hors_liste_blanche_erreur_du_widget_seulement(self):
        layout = {
            'widgets': [
                {'id': 'ko', 'dataset': 'changelog',
                 'spec': {'select': ['titre']},
                 'filtres_globaux': {'periode': 'secret'}},
                {'id': 'ok', 'dataset': 'changelog',
                 'spec': {'select': ['titre']}},
            ],
            'global_filters': {'periode': {'debut': self.t0.isoformat()}},
        }
        dash = self._dashboard(layout)
        resp = self._get_donnees(dash)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        widgets = {w['id']: w for w in resp.data['widgets']}
        self.assertIn('erreur', widgets['ko'])
        self.assertIn('rows', widgets['ok'])

    def test_dataset_inconnu_erreur_du_widget(self):
        dash = self._dashboard({'widgets': [
            {'id': 'x', 'dataset': 'inexistant', 'spec': {}}]})
        resp = self._get_donnees(dash)
        self.assertIn('erreur', resp.data['widgets'][0])

    def test_filtre_json_invalide_renvoie_400(self):
        dash = self._dashboard(self._layout())
        resp = self._get_donnees(dash, 'pas-du-json')
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_filtre_non_objet_renvoie_400(self):
        dash = self._dashboard(self._layout())
        resp = self._get_donnees(dash, '[1,2]')
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_isolation_societe(self):
        dash = self._dashboard(self._layout(), company=self.autre)
        resp = self._get_donnees(dash)
        self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)


class SpecFiltreeTests(TestCase):
    def test_egalite_simple_et_periode(self):
        widget = {'dataset': 'x', 'spec': {'filters': {'actif': True}},
                  'filtres_globaux': {'periode': 'jour',
                                      'responsable': 'owner'}}
        spec = dashboard_data.spec_filtree(widget, {
            'periode': {'debut': '2026-01-01', 'fin': '2026-03-31'},
            'responsable': 7,
        })
        self.assertEqual(spec['filters'], {
            'actif': True, 'jour__gte': '2026-01-01',
            'jour__lte': '2026-03-31', 'owner': 7})
        # La spec d'origine n'est jamais mutée.
        self.assertEqual(widget['spec']['filters'], {'actif': True})

    def test_valeurs_vides_ignorees(self):
        self.assertEqual(
            dashboard_data.normaliser_filtres(
                {'responsable': '', 'departement': None, 'canal': 'web'}),
            {'canal': 'web'})

    def test_periode_mal_formee_rejetee(self):
        with self.assertRaises(dashboard_data.FiltreGlobalInvalide):
            dashboard_data.normaliser_filtres({'periode': '2026'})
