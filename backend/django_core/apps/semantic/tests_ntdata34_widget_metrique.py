"""NTDATA34 — widget de tableau de bord branché sur une MÉTRIQUE NOMMÉE.

Couvre :
  * le critère d'acceptation : éditer la MESURE de `marge_brute` met à jour
    TOUS les widgets qui la référencent, ensemble ;
  * un widget de métrique rend valeur + unité + libellé (pas seulement des
    lignes) ;
  * un regroupement rend la SÉRIE ;
  * les filtres GLOBAUX du tableau de bord s'appliquent au widget de métrique
    comme aux autres — et seulement s'il déclare le champ qui porte la
    dimension ;
  * une métrique inconnue rend une ERREUR NOMMÉE, jamais un tableau vide ;
  * la couche sémantique débranchée rend une erreur explicite ;
  * les widgets de dataset classiques restent inchangés (rétro-compatibilité).
"""
from django.contrib.auth import get_user_model
from django.test import TestCase

from apps.semantic.models import MetricDefinition
from apps.semantic.services import resolve_widget_metrique
from authentication.models import Company
from core import dashboard_data, data_explorer
from core.models import Dashboard

User = get_user_model()


def _societes_dataset(company, user):
    return Company.objects.filter(pk=company.pk)


class WidgetMetriqueTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.company = Company.objects.create(nom='NTDATA34 SA',
                                             slug='ntdata34-sa')
        cls.user = User.objects.create_user(
            username='ntdata34_u', password='x', company=cls.company,
            role_legacy='admin')

    def setUp(self):
        data_explorer.register_dataset(
            'societes_ntdata34', 'Sociétés', ['id', 'nom'],
            _societes_dataset,
            field_meta={'id': {'label': 'Sociétés', 'type': 'mesure'},
                        'nom': {'label': 'Nom', 'type': 'dimension'}})
        # Le résolveur est branché par `SemanticConfig.ready()` ; on le
        # rebranche explicitement pour que l'ordre des tests ne compte pas.
        dashboard_data.register_metric_resolver(resolve_widget_metrique)
        self.metrique = MetricDefinition.objects.create(
            company=self.company, cle='marge_brute', libelle='Marge brute',
            dataset='societes_ntdata34',
            mesure={'field': 'id', 'agg': 'count'},
            unite=MetricDefinition.Unite.MAD)

    def _dashboard(self, widgets, **kw):
        return Dashboard.objects.create(
            company=self.company, titre='Direction',
            layout=dict({'widgets': widgets}, **kw))

    def _widget_metrique(self, **kw):
        return dict({'id': 'marge', 'titre': 'Marge brute',
                     'type': 'metrique', 'metrique': 'marge_brute'}, **kw)

    def test_widget_rend_valeur_unite_et_libelle(self):
        tableau = self._dashboard([self._widget_metrique()])
        donnees = dashboard_data.executer_dashboard(
            tableau, self.company, self.user)
        widget = donnees['widgets'][0]
        self.assertEqual(widget['id'], 'marge')
        self.assertEqual(widget['type'], 'metrique')
        self.assertEqual(widget['metrique'], 'marge_brute')
        self.assertEqual(widget['valeur'], 1)
        self.assertEqual(widget['unite'], 'MAD')
        self.assertEqual(widget['libelle_metrique'], 'Marge brute')
        self.assertNotIn('erreur', widget)

    def test_editer_la_mesure_met_a_jour_tous_les_widgets(self):
        """Critère d'acceptation NTDATA34."""
        premier = self._dashboard([self._widget_metrique()])
        second = self._dashboard([self._widget_metrique(id='marge2')])

        avant = [
            dashboard_data.executer_dashboard(
                tableau, self.company, self.user)['widgets'][0]['valeur']
            for tableau in (premier, second)
        ]
        self.assertEqual(avant, [1, 1])

        # UNE seule édition, au SEUL endroit où la métrique est définie.
        self.metrique.mesure = {
            'formula': 'nb * 10',
            'aggregates': [{'alias': 'nb', 'fn': 'count', 'field': 'id'}],
        }
        self.metrique.save()

        apres = [
            dashboard_data.executer_dashboard(
                tableau, self.company, self.user)['widgets'][0]['valeur']
            for tableau in (premier, second)
        ]
        # Les DEUX tableaux de bord ont suivi — sans qu'on les touche.
        self.assertEqual(apres, [10, 10])

    def test_regroupement_rend_la_serie(self):
        tableau = self._dashboard([self._widget_metrique(group_by=['nom'])])
        widget = dashboard_data.executer_dashboard(
            tableau, self.company, self.user)['widgets'][0]
        self.assertIsNone(widget['valeur'])
        self.assertEqual(len(widget['rows']), 1)
        self.assertEqual(widget['rows'][0]['nom'], 'NTDATA34 SA')

    def test_filtre_global_applique_quand_le_widget_le_declare(self):
        tableau = self._dashboard(
            [self._widget_metrique(filtres_globaux={'nom': 'nom'})],
            global_filters={'nom': 'Inexistante'})
        widget = dashboard_data.executer_dashboard(
            tableau, self.company, self.user)['widgets'][0]
        # Le filtre a bien mordu : aucune ligne ne correspond.
        self.assertEqual(widget['valeur'], 0)

    def test_filtre_global_ignore_si_le_widget_ne_le_declare_pas(self):
        """Filtrer sur un champ DEVINÉ produirait un chiffre faux."""
        tableau = self._dashboard(
            [self._widget_metrique()],
            global_filters={'nom': 'Inexistante'})
        widget = dashboard_data.executer_dashboard(
            tableau, self.company, self.user)['widgets'][0]
        self.assertEqual(widget['valeur'], 1)

    def test_metrique_inconnue_rend_une_erreur_nommee(self):
        tableau = self._dashboard(
            [self._widget_metrique(metrique='jamais_definie')])
        widget = dashboard_data.executer_dashboard(
            tableau, self.company, self.user)['widgets'][0]
        self.assertIn('jamais_definie', widget['erreur'])
        self.assertNotIn('rows', widget)

    def test_widget_sans_cle_de_metrique(self):
        tableau = self._dashboard([{'id': 'vide', 'type': 'metrique'}])
        widget = dashboard_data.executer_dashboard(
            tableau, self.company, self.user)['widgets'][0]
        self.assertIn('sans clé', widget['erreur'])

    def test_couche_semantique_debranchee_rend_une_erreur_explicite(self):
        tableau = self._dashboard([self._widget_metrique()])
        dashboard_data._reset_metric_resolver_for_tests()
        try:
            widget = dashboard_data.executer_dashboard(
                tableau, self.company, self.user)['widgets'][0]
        finally:
            dashboard_data.register_metric_resolver(resolve_widget_metrique)
        self.assertIn('couche sémantique', widget['erreur'])
        self.assertIn('marge_brute', widget['erreur'])

    def test_widget_de_dataset_classique_inchange(self):
        """Rétro-compatibilité : un widget sans `type` reste un widget dataset."""
        tableau = self._dashboard([{
            'id': 'brut', 'titre': 'Sociétés',
            'dataset': 'societes_ntdata34', 'spec': {'select': ['nom']},
        }])
        widget = dashboard_data.executer_dashboard(
            tableau, self.company, self.user)['widgets'][0]
        self.assertEqual(widget['dataset'], 'societes_ntdata34')
        self.assertEqual(widget['rows'][0]['nom'], 'NTDATA34 SA')
        self.assertNotIn('metrique', widget)
