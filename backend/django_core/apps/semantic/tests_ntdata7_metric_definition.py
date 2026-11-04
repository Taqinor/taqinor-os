"""NTDATA7 — modèle `MetricDefinition` (couche sémantique).

Couvre :
  * multi-tenant : la clé est unique PAR SOCIÉTÉ (deux sociétés peuvent avoir
    chacune leur `marge_brute`) ;
  * la validation structurelle de `mesure` (simple et formule), en FRANÇAIS et
    en nommant le champ fautif ;
  * `est_formule`.

NTDATA10 — API : CRUD des métriques + résolution par clé :
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
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.test import TestCase
from django.urls import resolve
from rest_framework import status
from rest_framework.test import APIRequestFactory, force_authenticate

from apps.semantic.models import MetricDefinition, MetricDefinitionVersion
from apps.semantic.views import (
    GlossaireView, MetricDefinitionViewSet, MetriqueValeurView,
    parametres_de_resolution,
)
from authentication.models import Company
from core import data_explorer

User = get_user_model()

BASE = '/api/django/semantic/metriques/'


def _societes_dataset(company, user):
    return Company.objects.filter(pk=company.pk)


class _BaseApi(TestCase):
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


class CrudMetriquesTests(_BaseApi):
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


class ValeurParCleTests(_BaseApi):
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
        for action in ('export', 'import', 'pour-agent'):
            self.assertIs(resolve(f'{BASE}{action}/').func.cls,
                          MetricDefinitionViewSet)
        self.assertIs(resolve(f'{BASE}ca_ht/valeur/').func.view_class,
                      MetriqueValeurView)
        self.assertEqual(resolve(f'{BASE}12/').func.cls,
                         MetricDefinitionViewSet)


class PortabiliteTests(_BaseApi):
    """NTDATA48 — export JSON vendor-neutre + import symétrique."""

    FORMULE = {'formula': 'n * 2',
               'aggregates': [{'alias': 'n', 'fn': 'count', 'field': 'id'}]}

    def _export(self, user=None):
        return self._vue('get', {'get': 'export'}, f'{BASE}export/',
                         user=user)

    def _import(self, corps, user=None):
        return self._vue('post', {'post': 'importer'}, f'{BASE}import/',
                         corps, user=user)

    def test_export_puis_reimport_recree_a_l_identique(self):
        """Critère d'acceptation NTDATA48."""
        self._creer(description='Combien.', filtres={'nom': 'x'},
                    dimensions_par_defaut=['nom'])
        self._creer(cle='double', libelle='Double', mesure=self.FORMULE,
                    unite='%', format=1)
        document = self._export().data
        self.assertEqual(document['format'], 'taqinor.semantic.metriques')
        self.assertNotIn('id', document['metriques'][0])
        self.assertNotIn('company', document['metriques'][0])

        # Même société : tout est « identique », rien n'est écrit.
        rapport = self._import(dict(document, commit=True)).data
        self.assertEqual({r['action'] for r in rapport['resultats']},
                         {'identique'})

        # Société vide : recréées à l'identique.
        autre_admin = User.objects.create_user(
            username='ntdata48_autre', password='x', company=self.autre,
            role_legacy='admin')
        reponse = self._import(dict(document, commit=True), user=autre_admin)
        self.assertEqual(reponse.status_code, status.HTTP_200_OK, reponse.data)
        self.assertTrue(reponse.data['applique'])
        reexport = self._export(user=autre_admin).data
        self.assertEqual(reexport['metriques'], document['metriques'])

    def test_dry_run_n_ecrit_rien(self):
        reponse = self._import({'metriques': [{
            'cle': 'nb_societes', 'libelle': 'N', 'dataset': 'ntdata10_societes',
            'mesure': {'agg': 'count'}}]})
        self.assertEqual(reponse.status_code, status.HTTP_200_OK)
        self.assertFalse(reponse.data['applique'])
        self.assertEqual(reponse.data['resultats'][0]['action'], 'creee')
        self.assertFalse(MetricDefinition.objects.filter(
            company=self.company).exists())

    def test_cle_non_portable_refusee_tout_ou_rien(self):
        reponse = self._import({'commit': True, 'metriques': [
            {'cle': 'bonne', 'libelle': 'B', 'dataset': 'ntdata10_societes',
             'mesure': {'agg': 'count'}},
            {'cle': 'mauvaise', 'libelle': 'M', 'dataset': 'ntdata10_societes',
             'mesure': {'agg': 'count'}, 'company': self.autre.pk},
        ]})
        self.assertEqual(reponse.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertFalse(reponse.data['applique'])
        self.assertIn('company', reponse.data['resultats'][1]['erreurs'])
        self.assertFalse(MetricDefinition.objects.filter(
            company=self.company).exists())

    def test_modification_signee(self):
        self._creer()
        rapport = self._import({'commit': True, 'metriques': [{
            'cle': 'nb_societes', 'mesure': {'field': 'id', 'agg': 'max'}}]})
        self.assertEqual(rapport.data['resultats'][0]['action'], 'modifiee')
        derniere = MetricDefinitionVersion.objects.filter(
            metric_definition__cle='nb_societes').order_by('-version').first()
        self.assertEqual(derniere.version, 2)
        self.assertEqual(derniere.auteur_id, self.admin.pk)

    def test_document_etranger_400(self):
        reponse = self._import({'format': 'autre.outil', 'metriques': []})
        self.assertEqual(reponse.status_code, status.HTTP_400_BAD_REQUEST)


class GlossaireTests(_BaseApi):
    """NTDATA49 — dictionnaire de données lisible sans coder."""

    def _glossaire(self, user):
        requete = APIRequestFactory().get('/api/django/semantic/glossaire/')
        force_authenticate(requete, user=user)
        return GlossaireView.as_view()(requete)

    def test_commercial_lit_la_definition(self):
        """Critère d'acceptation NTDATA49."""
        self._creer(cle='marge_brute', libelle='Marge brute',
                    description='Produits moins charges de la période.',
                    unite='MAD')
        MetricDefinition.objects.create(
            company=self.company, cle='seme', libelle='Semée',
            dataset='ntdata10_societes', mesure={'agg': 'count'})
        MetricDefinition.objects.create(
            company=self.autre, cle='chez_le_voisin', libelle='Voisin',
            dataset='ntdata10_societes', mesure={'agg': 'count'})
        reponse = self._glossaire(self.simple)
        self.assertEqual(reponse.status_code, status.HTTP_200_OK)
        par_cle = {m['cle']: m for m in reponse.data['metriques']}
        self.assertEqual(set(par_cle), {'marge_brute', 'seme'})
        marge = par_cle['marge_brute']
        self.assertEqual(marge['definition'],
                         'Produits moins charges de la période.')
        self.assertEqual(marge['unite'], 'MAD')
        self.assertEqual(marge['unite_libelle'], 'Dirham (MAD)')
        self.assertEqual(marge['proprietaire'], 'ntdata10_admin')
        self.assertTrue(marge['derniere_modification'])
        # Aucune recette dans le glossaire.
        self.assertNotIn('mesure', marge)
        self.assertNotIn('dataset', marge)
        # Une métrique semée sans acteur n'a pas de propriétaire inventé.
        self.assertEqual(par_cle['seme']['proprietaire'], '')
        self.assertIs(resolve('/api/django/semantic/glossaire/').func.view_class,
                      GlossaireView)


class MetricDefinitionTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.company = Company.objects.create(nom='NTDATA7 SA',
                                             slug='ntdata7-sa')
        cls.autre = Company.objects.create(nom='NTDATA7 Autre',
                                           slug='ntdata7-autre')

    def _metrique(self, company=None, **kw):
        defaults = dict(
            company=company or self.company, cle='ca_ttc',
            libelle='Chiffre d\'affaires TTC', dataset='ventes_factures',
            mesure={'field': 'montant_ttc', 'agg': 'sum'},
            unite=MetricDefinition.Unite.MAD)
        defaults.update(kw)
        return MetricDefinition.objects.create(**defaults)

    def test_cle_unique_par_societe(self):
        self._metrique()
        # Même clé dans une AUTRE société : autorisé.
        self._metrique(company=self.autre)
        # Même clé dans la MÊME société : refusé.
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                self._metrique()

    def test_mesure_simple_valide(self):
        metrique = self._metrique()
        metrique.full_clean()
        self.assertFalse(metrique.est_formule)

    def test_mesure_formule_valide(self):
        metrique = self._metrique(
            cle='panier_moyen',
            mesure={
                'formula': 'ca / nb',
                'aggregates': [
                    {'alias': 'ca', 'fn': 'sum', 'field': 'montant_ttc'},
                    {'alias': 'nb', 'fn': 'count', 'field': 'id'},
                ],
            })
        metrique.full_clean()
        self.assertTrue(metrique.est_formule)

    def test_agregation_inconnue_refusee_en_nommant_le_champ(self):
        metrique = MetricDefinition(
            company=self.company, cle='x', libelle='X',
            dataset='ventes_factures',
            mesure={'field': 'montant_ttc', 'agg': 'mediane'})
        with self.assertRaises(ValidationError) as ctx:
            metrique.clean()
        self.assertIn('mesure', ctx.exception.message_dict)
        self.assertIn('mediane', str(ctx.exception.message_dict['mesure']))

    def test_formule_sans_aggregates_refusee(self):
        metrique = MetricDefinition(
            company=self.company, cle='y', libelle='Y',
            dataset='ventes_factures', mesure={'formula': 'a / b'})
        with self.assertRaises(ValidationError) as ctx:
            metrique.clean()
        self.assertIn('aggregates', str(ctx.exception.message_dict['mesure']))

    def test_dataset_obligatoire(self):
        metrique = MetricDefinition(
            company=self.company, cle='z', libelle='Z', dataset='',
            mesure={'field': 'id', 'agg': 'count'})
        with self.assertRaises(ValidationError) as ctx:
            metrique.clean()
        self.assertIn('dataset', ctx.exception.message_dict)

    def test_count_sans_field_accepte(self):
        metrique = self._metrique(cle='nb_factures',
                                  mesure={'agg': 'count'},
                                  unite=MetricDefinition.Unite.NOMBRE)
        metrique.clean()  # ne lève pas
