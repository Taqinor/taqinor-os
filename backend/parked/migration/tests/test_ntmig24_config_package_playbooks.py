"""Tests NTMIG24 — playbooks véhiculés par un ``ConfigPackage`` (NTADM13/14).

Critère d'acceptation : exporter la config d'un tenant « modèle » puis
l'importer sur un tenant NEUF recrée aussi ses playbooks d'implémentation.

Couvre aussi : identité STABLE par ``cle`` (tag de graine ou titre) pour ne
jamais dupliquer sur un import répété, une structure de phases correctement
reconstituée, et qu'un article ORDINAIRE (non playbook) n'apparaît jamais
dans le snapshot.

Run :
    python manage.py test apps.migration.tests.test_ntmig24_config_package_playbooks -v2
"""
from django.test import TestCase

from apps.adminops import config_package_service
from apps.kb.models import KbArticle

from ._base import make_company

STRUCTURE = [
    {'cle': 'prerequis', 'titre': 'Prérequis', 'etapes': [
        {'cle': 'p1', 'libelle': 'Créer les accès'},
    ]},
]


class Ntmig24ConfigPackagePlaybooksTests(TestCase):

    def setUp(self):
        self.modele = make_company('ntmig24-modele', 'NTMIG24 modèle')
        self.neuf = make_company('ntmig24-neuf', 'NTMIG24 neuf')

    def test_export_puis_import_sur_tenant_neuf_recree_le_playbook(self):
        KbArticle.objects.create(
            company=self.modele, titre='Déploiement module Compta',
            categorie="Playbooks d'implémentation",
            tags='seed:playbook:compta',
            type_article=KbArticle.TypeArticle.PLAYBOOK,
            contenu_structure=STRUCTURE)
        # Un article ORDINAIRE ne doit jamais apparaître dans le snapshot.
        KbArticle.objects.create(
            company=self.modele, titre='Procédure interne')

        contenu = config_package_service.construire_contenu(self.modele)
        self.assertEqual(len(contenu['playbooks']), 1)
        self.assertEqual(contenu['playbooks'][0]['cle'],
                         'seed:playbook:compta')

        self.assertFalse(
            KbArticle.objects.filter(
                company=self.neuf,
                type_article=KbArticle.TypeArticle.PLAYBOOK).exists())

        config_package_service.appliquer_import(self.neuf, contenu)

        recree = KbArticle.objects.get(
            company=self.neuf, type_article=KbArticle.TypeArticle.PLAYBOOK)
        self.assertEqual(recree.titre, 'Déploiement module Compta')
        self.assertEqual(recree.contenu_structure, STRUCTURE)
        self.assertEqual(recree.tags, 'seed:playbook:compta')
        # L'article ordinaire n'a jamais été recréé sur le tenant neuf.
        self.assertEqual(
            KbArticle.objects.filter(company=self.neuf).count(), 1)

    def test_reimport_ne_duplique_jamais(self):
        """Rejouer le MÊME package sur le même tenant met à jour, pas de doublon."""
        KbArticle.objects.create(
            company=self.modele, titre='Déploiement module Ventes',
            tags='seed:playbook:ventes',
            type_article=KbArticle.TypeArticle.PLAYBOOK,
            contenu_structure=STRUCTURE)
        contenu = config_package_service.construire_contenu(self.modele)

        config_package_service.appliquer_import(self.neuf, contenu)
        config_package_service.appliquer_import(self.neuf, contenu)

        self.assertEqual(
            KbArticle.objects.filter(
                company=self.neuf,
                type_article=KbArticle.TypeArticle.PLAYBOOK).count(), 1)

    def test_playbook_sans_tag_identifie_par_titre(self):
        """Un playbook créé à la main (sans tag de graine) reste identifiable
        et réimportable sans doublon via son titre."""
        KbArticle.objects.create(
            company=self.modele, titre='Playbook maison',
            type_article=KbArticle.TypeArticle.PLAYBOOK,
            contenu_structure=STRUCTURE)
        contenu = config_package_service.construire_contenu(self.modele)
        self.assertEqual(contenu['playbooks'][0]['cle'],
                         'titre:Playbook maison')

        config_package_service.appliquer_import(self.neuf, contenu)
        config_package_service.appliquer_import(self.neuf, contenu)
        self.assertEqual(
            KbArticle.objects.filter(
                company=self.neuf,
                type_article=KbArticle.TypeArticle.PLAYBOOK).count(), 1)

    def test_previsualiser_import_diffuse_les_ajouts_de_playbook(self):
        KbArticle.objects.create(
            company=self.modele, titre='Déploiement module SAV',
            tags='seed:playbook:sav',
            type_article=KbArticle.TypeArticle.PLAYBOOK,
            contenu_structure=STRUCTURE)
        contenu = config_package_service.construire_contenu(self.modele)
        diff = config_package_service.previsualiser_import(
            self.neuf, contenu)
        self.assertEqual(len(diff['playbooks']['ajouts']), 1)
        self.assertEqual(diff['playbooks']['ajouts'][0]['cle'],
                         'seed:playbook:sav')
        # Toujours un dry-run : rien n'est écrit.
        self.assertFalse(
            KbArticle.objects.filter(company=self.neuf).exists())
