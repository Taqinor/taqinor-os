"""NTDATA43 — lignage d'une métrique : « d'où vient ce chiffre ».

Couvre :
  * le critère d'acceptation : le lignage cite son DATASET, l'APP propriétaire
    et sa FORMULE ;
  * l'app propriétaire est DÉRIVÉE du module qui a enregistré le dataset —
    aucune table de correspondance à tenir à jour ;
  * les champs réellement lus (mesure + racines des filtres) ;
  * le nombre de lignes agrégées est RÉEL, et VIDE (jamais 0) quand il n'est
    pas exprimable — métrique d'adaptateur, dataset désenregistré ;
  * la version de définition en vigueur (NTDATA9) est citée ;
  * une métrique inconnue/inactive est un 404 ;
  * l'endpoint `/semantic/metriques/<cle>/lignage/` et son scoping société.
"""
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIRequestFactory, force_authenticate

from apps.semantic import selectors, services
from apps.semantic.models import MetricDefinition
from apps.semantic.views import MetriqueLignageView
from authentication.models import Company
from core import data_explorer

User = get_user_model()


def _societes_dataset(company, user):
    return Company.objects.filter(pk=company.pk)


class LignageTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.company = Company.objects.create(nom='NTDATA43 SA',
                                             slug='ntdata43-sa')
        cls.autre = Company.objects.create(nom='NTDATA43 Autre',
                                           slug='ntdata43-autre')
        cls.user = User.objects.create_user(
            username='ntdata43_u', password='x', company=cls.company,
            role_legacy='admin')

    def setUp(self):
        data_explorer.register_dataset(
            'ventes_ntdata43', 'Factures (test)', ['id', 'nom', 'statut'],
            _societes_dataset)

    def _metrique(self, **kw):
        params = dict(company=self.company, cle='ca_ht', libelle='CA HT',
                      description='Chiffre d\'affaires hors taxe.',
                      dataset='ventes_ntdata43',
                      mesure={'field': 'id', 'agg': 'count'},
                      unite=MetricDefinition.Unite.MAD)
        params.update(kw)
        return MetricDefinition.objects.create(**params)

    def test_lignage_cite_dataset_app_et_formule(self):
        """Critère d'acceptation NTDATA43."""
        self._metrique(mesure={
            'formula': 'brut - remise',
            'aggregates': [
                {'alias': 'brut', 'fn': 'sum', 'field': 'id'},
                {'alias': 'remise', 'fn': 'sum', 'field': 'statut'},
            ],
        })
        arbre = selectors.lineage(self.company, 'ca_ht', user=self.user)

        self.assertEqual(arbre['metrique'], 'ca_ht')
        self.assertEqual(arbre['libelle'], 'CA HT')
        # Le DATASET source et son libellé.
        self.assertEqual(len(arbre['sources']), 1)
        source = arbre['sources'][0]
        self.assertEqual(source['dataset'], 'ventes_ntdata43')
        self.assertEqual(source['label'], 'Factures (test)')
        # La FORMULE, avec ses agrégats nommés.
        self.assertEqual(arbre['calcul']['type'], 'formule')
        self.assertEqual(arbre['calcul']['expression'], 'brut - remise')
        self.assertEqual(
            [a['alias'] for a in arbre['calcul']['agregats']],
            ['brut', 'remise'])

    def test_app_proprietaire_derivee_du_module_enregistreur(self):
        """Le dataset CRM est possédé par `crm` — sans table de correspondance."""
        self.assertEqual(selectors._app_proprietaire('crm_clients'), 'crm')

    def test_dataset_desenregistre_ne_fait_pas_echouer(self):
        self.assertEqual(selectors._app_proprietaire('jamais_enregistre'), '')

    def test_champs_reellement_lus(self):
        self._metrique(mesure={'field': 'statut', 'agg': 'count'},
                       filtres={'nom__icontains': 'SA'})
        arbre = selectors.lineage(self.company, 'ca_ht', user=self.user)
        champs = arbre['sources'][0]['champs_utilises']
        self.assertIn('statut', champs)
        # La COLONNE lue par un filtre est la RACINE de sa clé.
        self.assertIn('nom', champs)
        self.assertNotIn('nom__icontains', champs)

    def test_nb_lignes_agregees_reel(self):
        self._metrique()
        arbre = selectors.lineage(self.company, 'ca_ht', user=self.user)
        # Le dataset de test ne rend que la société courante.
        self.assertEqual(arbre['nb_lignes_agregees'], 1)

    def test_metrique_d_adaptateur_na_ni_source_ni_compte(self):
        """Un adaptateur n'est pas une requête : pas de lignes à compter."""
        self._metrique(cle='dso', dataset='',
                       mesure={'adapter': 'compta.dso'})
        arbre = selectors.lineage(self.company, 'dso', user=self.user)
        self.assertEqual(arbre['calcul']['type'], 'adaptateur')
        self.assertEqual(arbre['calcul']['adaptateur'], 'compta.dso')
        self.assertEqual(arbre['sources'], [])
        # VIDE, jamais 0 : « je ne sais pas » n'est pas « aucune ligne ».
        self.assertIsNone(arbre['nb_lignes_agregees'])

    def test_dataset_absent_rend_un_compte_vide(self):
        self._metrique(dataset='jamais_enregistre')
        arbre = selectors.lineage(self.company, 'ca_ht', user=self.user)
        self.assertIsNone(arbre['nb_lignes_agregees'])
        self.assertEqual(arbre['sources'][0]['app'], '')

    def test_version_en_vigueur_citee(self):
        definition = self._metrique()
        definition.filtres = {'statut': 'payee'}
        definition.save()
        arbre = selectors.lineage(self.company, 'ca_ht', user=self.user)
        self.assertIsNotNone(arbre['version'])
        self.assertEqual(arbre['version']['version'], 2)
        self.assertEqual(arbre['filtres'], {'statut': 'payee'})

    def test_metrique_inconnue_leve(self):
        with self.assertRaises(services.MetriqueInconnue):
            selectors.lineage(self.company, 'inexistante', user=self.user)

    def test_metrique_inactive_leve(self):
        definition = self._metrique()
        MetricDefinition.objects.filter(pk=definition.pk).update(actif=False)
        with self.assertRaises(services.MetriqueInconnue):
            selectors.lineage(self.company, 'ca_ht', user=self.user)


class LignageEndpointTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.company = Company.objects.create(nom='NTDATA43 API',
                                             slug='ntdata43-api')
        cls.autre = Company.objects.create(nom='NTDATA43 API2',
                                           slug='ntdata43-api2')
        cls.responsable = User.objects.create_user(
            username='ntdata43_resp', password='x', company=cls.company,
            role_legacy='admin')
        cls.simple = User.objects.create_user(
            username='ntdata43_simple', password='x', company=cls.company,
            role_legacy='normal')
        MetricDefinition.objects.create(
            company=cls.autre, cle='chez_le_voisin', libelle='Voisin',
            dataset='crm_clients', mesure={'field': 'id', 'agg': 'count'})
        MetricDefinition.objects.create(
            company=cls.company, cle='ca_ht', libelle='CA HT',
            dataset='ventes_ntdata43',
            mesure={'field': 'id', 'agg': 'count'})

    def setUp(self):
        data_explorer.register_dataset(
            'ventes_ntdata43', 'Factures (test)', ['id', 'nom', 'statut'],
            _societes_dataset)

    def _get(self, cle, user=None):
        requete = APIRequestFactory().get(
            f'/api/django/semantic/metriques/{cle}/lignage/')
        force_authenticate(requete, user=user or self.responsable)
        return MetriqueLignageView.as_view()(requete, cle=cle)

    def test_endpoint(self):
        reponse = self._get('ca_ht')
        self.assertEqual(reponse.status_code, status.HTTP_200_OK)
        self.assertEqual(reponse.data['metrique'], 'ca_ht')
        self.assertEqual(reponse.data['sources'][0]['dataset'],
                         'ventes_ntdata43')

    def test_metrique_d_une_autre_societe_est_un_404(self):
        reponse = self._get('chez_le_voisin')
        self.assertEqual(reponse.status_code, status.HTTP_404_NOT_FOUND)

    def test_utilisateur_non_responsable_refuse(self):
        self.assertEqual(self._get('ca_ht', user=self.simple).status_code,
                         status.HTTP_403_FORBIDDEN)
