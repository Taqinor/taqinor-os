"""NTDATA9 — versionnage des définitions de métriques.

Couvre :
  * le critère d'acceptation : MODIFIER une métrique FIGE l'ancienne
    définition, qui reste consultable ;
  * la création pose la version 1 ;
  * l'instantané est IMMUABLE (éditer la métrique ne réécrit pas les versions
    déjà figées) ;
  * un enregistrement SANS changement de définition ne crée pas de version
    (un historique qui compte les sauvegardes ne dit plus ce qui a changé) ;
  * un changement COSMÉTIQUE (libellé, décimales, activation) n'en crée pas
    non plus : il ne change aucun chiffre ;
  * la numérotation est « dernière + 1 », JAMAIS `count()+1` — une version
    supprimée ne fait pas collisionner le compteur ;
  * l'auteur est posé quand l'appelant le connaît, vide sinon (jamais
    attribué au hasard) ;
  * l'endpoint `/semantic/metriques/<id>/versions/` + son 404 cross-société.
"""
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIRequestFactory, force_authenticate

from apps.semantic import services
from apps.semantic.models import MetricDefinition, MetricDefinitionVersion
from apps.semantic.views import MetriqueVersionsView
from authentication.models import Company

User = get_user_model()


class VersionnageMetriqueTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.company = Company.objects.create(nom='NTDATA9 SA',
                                             slug='ntdata9-sa')
        cls.autre = Company.objects.create(nom='NTDATA9 Autre',
                                           slug='ntdata9-autre')
        cls.user = User.objects.create_user(
            username='ntdata9_u', password='x', company=cls.company,
            role_legacy='admin')

    def _metrique(self, **kw):
        params = dict(company=self.company, cle='marge_brute',
                      libelle='Marge brute', dataset='ventes_factures',
                      mesure={'field': 'montant_ht', 'agg': 'sum'},
                      unite=MetricDefinition.Unite.MAD)
        params.update(kw)
        return MetricDefinition.objects.create(**params)

    def _versions(self, definition):
        return list(MetricDefinitionVersion.objects
                    .filter(metric_definition=definition)
                    .order_by('version'))

    def test_creation_pose_la_version_1(self):
        definition = self._metrique()
        versions = self._versions(definition)
        self.assertEqual(len(versions), 1)
        self.assertEqual(versions[0].version, 1)
        self.assertEqual(versions[0].mesure,
                         {'field': 'montant_ht', 'agg': 'sum'})
        self.assertEqual(versions[0].company_id, self.company.pk)

    def test_modifier_fige_l_ancienne_definition(self):
        """Critère d'acceptation NTDATA9."""
        definition = self._metrique()
        definition.mesure = {
            'formula': 'ventes - achats',
            'aggregates': [
                {'alias': 'ventes', 'fn': 'sum', 'field': 'montant_ht'},
                {'alias': 'achats', 'fn': 'sum', 'field': 'montant_ttc'},
            ],
        }
        definition.save()

        versions = self._versions(definition)
        self.assertEqual([v.version for v in versions], [1, 2])
        # L'ANCIENNE définition reste consultable, telle qu'elle était.
        self.assertEqual(versions[0].mesure,
                         {'field': 'montant_ht', 'agg': 'sum'})
        self.assertIn('formula', versions[1].mesure)

    def test_instantane_immuable(self):
        definition = self._metrique()
        v1 = self._versions(definition)[0]
        definition.dataset = 'crm_leads'
        definition.save()
        v1.refresh_from_db()
        self.assertEqual(v1.dataset, 'ventes_factures')

    def test_enregistrement_sans_changement_ne_cree_rien(self):
        definition = self._metrique()
        definition.save()
        definition.save()
        self.assertEqual(len(self._versions(definition)), 1)

    def test_changement_cosmetique_ne_cree_rien(self):
        """Renommer ou changer les décimales ne change AUCUN chiffre."""
        definition = self._metrique()
        definition.libelle = 'Marge brute (MAD)'
        definition.format = 0
        definition.actif = False
        definition.save()
        self.assertEqual(len(self._versions(definition)), 1)

    def test_changement_de_filtres_cree_une_version(self):
        """Les filtres sont la POPULATION mesurée : les changer change le chiffre."""
        definition = self._metrique()
        definition.filtres = {'statut': 'payee'}
        definition.save()
        self.assertEqual([v.version for v in self._versions(definition)],
                         [1, 2])

    def test_numerotation_derniere_plus_un_jamais_count(self):
        definition = self._metrique()
        definition.dataset = 'crm_leads'
        definition.save()
        definition.dataset = 'crm_clients'
        definition.save()
        self.assertEqual([v.version for v in self._versions(definition)],
                         [1, 2, 3])
        # Une version SUPPRIMÉE ne doit pas faire collisionner le compteur.
        MetricDefinitionVersion.objects.filter(
            metric_definition=definition, version=2).delete()
        definition.dataset = 'stock_produits'
        definition.save()
        self.assertEqual([v.version for v in self._versions(definition)],
                         [1, 3, 4])

    def test_auteur_pose_quand_connu_vide_sinon(self):
        definition = self._metrique()
        # Chemin sans acteur (signal) : auteur vide, jamais attribué au hasard.
        self.assertIsNone(self._versions(definition)[0].auteur_id)
        definition.unite = MetricDefinition.Unite.POURCENT
        version = services.snapshot_metrique(definition, auteur=self.user)
        self.assertEqual(version.auteur_id, self.user.pk)

    def test_snapshot_explicite_puis_save_ne_duplique_pas(self):
        """Une vue qui fige AVANT d'enregistrer : le signal ne double pas."""
        definition = self._metrique()
        definition.unite = MetricDefinition.Unite.POURCENT
        services.snapshot_metrique(definition, auteur=self.user)
        definition.save()
        versions = self._versions(definition)
        self.assertEqual([v.version for v in versions], [1, 2])
        self.assertEqual(versions[1].auteur_id, self.user.pk)

    def test_force_cree_une_version_meme_sans_changement(self):
        definition = self._metrique()
        services.snapshot_metrique(definition, force=True)
        self.assertEqual([v.version for v in self._versions(definition)],
                         [1, 2])


class MetriqueVersionsEndpointTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.company = Company.objects.create(nom='NTDATA9 API',
                                             slug='ntdata9-api')
        cls.autre = Company.objects.create(nom='NTDATA9 API2',
                                           slug='ntdata9-api2')
        cls.responsable = User.objects.create_user(
            username='ntdata9_resp', password='x', company=cls.company,
            role_legacy='admin')
        cls.simple = User.objects.create_user(
            username='ntdata9_simple', password='x', company=cls.company,
            role_legacy='normal')
        cls.definition = MetricDefinition.objects.create(
            company=cls.company, cle='dso', libelle='DSO',
            dataset='ventes_factures',
            mesure={'field': 'montant_ttc', 'agg': 'avg'},
            unite=MetricDefinition.Unite.JOURS)
        cls.etrangere = MetricDefinition.objects.create(
            company=cls.autre, cle='dso', libelle='DSO voisin',
            dataset='ventes_factures',
            mesure={'field': 'montant_ttc', 'agg': 'avg'})

    def _get(self, pk, user=None):
        requete = APIRequestFactory().get(
            f'/api/django/semantic/metriques/{pk}/versions/')
        force_authenticate(requete, user=user or self.responsable)
        return MetriqueVersionsView.as_view()(requete, pk=pk)

    def test_endpoint_liste_les_versions(self):
        reponse = self._get(self.definition.pk)
        self.assertEqual(reponse.status_code, status.HTTP_200_OK)
        self.assertEqual(reponse.data['metrique'], 'dso')
        self.assertEqual(reponse.data['nb_versions'], 1)
        self.assertEqual(reponse.data['versions'][0]['version'], 1)
        self.assertEqual(reponse.data['versions'][0]['auteur'], '')

    def test_metrique_d_une_autre_societe_est_un_404(self):
        """404 et pas 403 : « interdit » confirmerait son existence."""
        reponse = self._get(self.etrangere.pk)
        self.assertEqual(reponse.status_code, status.HTTP_404_NOT_FOUND)

    def test_utilisateur_non_responsable_refuse(self):
        self.assertEqual(
            self._get(self.definition.pk, user=self.simple).status_code,
            status.HTTP_403_FORBIDDEN)
