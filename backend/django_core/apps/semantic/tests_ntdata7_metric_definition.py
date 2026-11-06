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

    def test_mesure_requise_a_la_creation_et_au_schema(self):
        """ENF45 d (api-fuzz-full 41958593088) : ``mesure`` absente = refus
        nommé, et le schéma la dit REQUISE (POST/PUT) — un corps « complet »
        au schéma n'est plus refusé par ``clean``. PATCH reste partiel."""
        from apps.semantic.serializers import MetricDefinitionSerializer
        donnees = {'cle': 'sans_mesure', 'libelle': 'Sans mesure',
                   'dataset': 'ntdata10_societes'}
        reponse = self._vue('post', {'post': 'create'}, BASE, donnees)
        self.assertEqual(reponse.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(reponse.data['mesure'][0].code, 'required')
        self.assertTrue(MetricDefinitionSerializer().fields['mesure'].required)
        pk = self._creer().data['id']
        reponse = self._vue('patch', {'patch': 'partial_update'},
                            f'{BASE}{pk}/', {'libelle': 'Renommée'}, pk=pk)
        self.assertEqual(reponse.status_code, status.HTTP_200_OK, reponse.data)

    def test_forme_de_mesure_publiee_et_appliquee(self):
        """ENF47 (api-fuzz-full 42017839549) : ``mesure: null`` (et ``{}``)
        étaient conformes au schéma ``{}`` puis refusés — la forme est
        publiée (``anyOf``, non nullable) et la MÊME est appliquée (400)."""
        from apps.semantic.serializers import (
            SCHEMA_MESURE, MetricDefinitionSerializer)
        for mesure in (None, {}, {'agg': 'sum'}, {'adapter': ''}):
            reponse = self._creer(mesure=mesure)
            self.assertEqual(reponse.status_code,
                             status.HTTP_400_BAD_REQUEST, (mesure, reponse.data))
            self.assertIn('mesure', reponse.data)
        champ = MetricDefinitionSerializer().fields['mesure']
        self.assertEqual(champ._spectacular_annotation['field'], SCHEMA_MESURE)
        self.assertEqual(self._creer(mesure={'agg': 'count', 'formula': ''})
                         .status_code, status.HTTP_201_CREATED)

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
        """ENF48 — jamais de DELETE (405, « use after free » au fuzz) :
        désactiver = PATCH ``actif: false`` ; la métrique reste lisible."""
        pk = self._creer().data['id']
        reponse = self._vue('delete', {'delete': 'destroy'}, f'{BASE}{pk}/',
                            pk=pk)
        self.assertEqual(reponse.status_code,
                         status.HTTP_405_METHOD_NOT_ALLOWED)
        self.assertTrue(MetricDefinition.objects.get(pk=pk).actif)
        reponse = self._vue('patch', {'patch': 'partial_update'},
                            f'{BASE}{pk}/', {'actif': False}, pk=pk)
        self.assertEqual(reponse.status_code, status.HTTP_200_OK, reponse.data)
        self.assertFalse(MetricDefinition.objects.get(pk=pk).actif)
        # ENF50 — désactivée mais EXISTANTE : état de la métrique, 409.
        self.assertEqual(self._valeur('nb_societes').status_code,
                         status.HTTP_409_CONFLICT)

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

    def test_adaptateur_ou_dataset_absent_409(self):
        """ENF49 (api-fuzz-full 42128456456, UDnVtL) : la métrique ENREGISTRÉE
        désigne un adaptateur / dataset absent de ce serveur → 409 (état de
        la métrique), plus 400 sur un GET conforme."""
        MetricDefinition.objects.create(
            company=self.company, cle='adaptateur_absent', libelle='A',
            mesure={'adapter': '0'})
        MetricDefinition.objects.create(
            company=self.company, cle='dataset_absent', libelle='D',
            dataset='dataset_jamais_enregistre', mesure={'agg': 'count'})
        for cle in ('adaptateur_absent', 'dataset_absent'):
            reponse = self._valeur(cle)
            self.assertEqual(reponse.status_code, status.HTTP_409_CONFLICT,
                             (cle, reponse.data))
            self.assertIn('detail', reponse.data)

    def test_parametres_objet_json_publies_en_content_json(self):
        """ENF45 c (api-fuzz-full 41958593088) : ``period``/``filters`` (et
        ``cellule`` d'expliquer) sont publiés ``content: application/json``
        + schéma objet — plus ``type: string``, dont « 2 » était conforme puis
        refusé ; un objet conforme est bien lu par la vue."""
        from django.urls import include, path
        from drf_spectacular.generators import SchemaGenerator
        doc = SchemaGenerator(patterns=[
            path('api/django/semantic/', include('apps.semantic.urls')),
        ]).get_schema(request=None, public=True)
        attendus = {
            '/api/django/semantic/metriques/{cle}/valeur/': {'period', 'filters'},
            '/api/django/semantic/metriques/{cle}/expliquer/': {'filters', 'cellule'},
        }
        for chemin, noms in attendus.items():
            parametres = {p['name']: p for p in doc['paths'][chemin]['get']['parameters']}
            for nom in noms:
                with self.subTest(chemin=chemin, nom=nom):
                    parametre = parametres[nom]
                    self.assertNotIn('schema', parametre)
                    schema = parametre['content']['application/json']['schema']
                    self.assertEqual(schema['type'], 'object')
        self._creer()
        reponse = self._valeur('nb_societes', {'group_by': '', 'filters': '{}'})
        self.assertEqual(reponse.status_code, status.HTTP_200_OK, reponse.data)

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
        # ENF48 : la forme d'une entrée est PUBLIÉE (clés portables,
        # ``additionalProperties: false``) — 400 nommé sur le corps.
        self.assertEqual(reponse.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('metriques', reponse.data)
        self.assertIn('company', str(reponse.data['metriques']))
        self.assertFalse(MetricDefinition.objects.filter(
            company=self.company).exists())
        # Même en dry-run (le schéma ne dépend pas du mode).
        reponse = self._import({'metriques': [{'cle': 'x', 'id': 1}]})
        self.assertEqual(reponse.status_code, status.HTTP_400_BAD_REQUEST)
        # Valeur de forme invalide (motif de clé publié) : 400 aussi.
        reponse = self._import({'metriques': [{'cle': 'Pas Une Cle'}]})
        self.assertEqual(reponse.status_code, status.HTTP_400_BAD_REQUEST)

    def test_refus_d_etat_en_commit_409_rien_ecrit(self):
        """ENF48 — création incomplète (dataset/mesure absents pour une clé
        nouvelle) ou clé en double dans le document : dépend de l'état ou
        du document entier, inexprimable au schéma → 409, rapport nommé."""
        bonne = {'cle': 'bonne', 'libelle': 'B',
                 'dataset': 'ntdata10_societes', 'mesure': {'agg': 'count'}}
        for metriques in ([bonne, {'cle': 'incomplete'}], [bonne, bonne]):
            reponse = self._import({'commit': True, 'metriques': metriques})
            self.assertEqual(reponse.status_code, status.HTTP_409_CONFLICT,
                             reponse.data)
            self.assertFalse(reponse.data['applique'])
            self.assertEqual(reponse.data['resultats'][1]['action'],
                             'refusee')
        self.assertFalse(MetricDefinition.objects.filter(
            company=self.company).exists())

    def test_filtres_et_dimensions_nuls_acceptes_liste_refusee(self):
        """ENF48 (api-fuzz-pr XL1gwd) : ``null`` est publié pour filtres et
        dimensions (ramené à {} / []) ; une LISTE de filtres sort du schéma
        publié (objet) → 400 nommé."""
        entree = {'cle': 'bonne', 'libelle': 'B', 'dataset': 'ntdata10_societes',
                  'mesure': {'agg': 'count'}, 'filtres': None,
                  'dimensions_par_defaut': None}
        reponse = self._import({'metriques': [entree]})
        self.assertEqual(reponse.status_code, status.HTTP_200_OK, reponse.data)
        reponse = self._import({'metriques': [{**entree, 'filtres': [None]}]})
        self.assertEqual(reponse.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('filtres', str(reponse.data['metriques']))

    def test_modification_signee(self):
        self._creer()
        rapport = self._import({'commit': True, 'metriques': [{
            'cle': 'nb_societes', 'mesure': {'field': 'id', 'agg': 'max'}}]})
        self.assertEqual(rapport.data['resultats'][0]['action'], 'modifiee')
        derniere = MetricDefinitionVersion.objects.filter(
            metric_definition__cle='nb_societes').order_by('-version').first()
        self.assertEqual(derniere.version, 2)
        self.assertEqual(derniere.auteur_id, self.admin.pk)

    def test_entree_non_objet_refusee_par_la_forme(self):
        """ENF47 (api-fuzz-full 42017839549) : une entrée liste était
        conforme au schéma (élément ``{}``) puis refusée ligne à ligne — une
        entrée est un OBJET, publié et appliqué (400 nommé, rien d'écrit)."""
        reponse = self._import({'commit': True, 'metriques': [[{}], None]})
        self.assertEqual(reponse.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('metriques', reponse.data)
        self.assertFalse(MetricDefinition.objects.filter(
            company=self.company).exists())

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
