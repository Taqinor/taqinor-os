"""Tests NTMIG21 — type d'article « playbook » + structure phases → étapes.

Couvre le critère d'acceptation : créer un playbook « Déploiement module
Ventes » avec 3 phases le rend consultable ET versionné comme un article kb
ordinaire. Couvre aussi la RÉTRO-COMPATIBILITÉ (un article normal reste un
article normal, structure vide) et les refus de structure incalculable.
"""
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company

from apps.kb import selectors
from apps.kb.models import KbArticle, KbArticleVersion

User = get_user_model()

STRUCTURE_VENTES = [
    {'cle': 'prerequis', 'titre': 'Prérequis', 'etapes': [
        {'cle': 'p1', 'libelle': 'Créer la société'},
        {'cle': 'p2', 'libelle': 'Créer les rôles'},
    ]},
    {'cle': 'reglages', 'titre': 'Réglages', 'etapes': [
        {'cle': 'r1', 'libelle': 'TVA par défaut'},
        {'cle': 'r2', 'libelle': 'Numérotation des devis'},
        {'cle': 'r3', 'libelle': 'Catalogue produits'},
    ]},
    {'cle': 'golive', 'titre': 'Go-live', 'etapes': [
        {'cle': 'g1', 'libelle': 'Tests d’acceptation'},
        {'cle': 'g2', 'libelle': 'Bascule'},
        {'cle': 'g3', 'libelle': 'Formation'},
    ]},
]


def make_company(slug, nom):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


class Ntmig21PlaybookTests(TestCase):
    ARTICLES = '/api/django/kb/articles/'
    VERSIONS = '/api/django/kb/versions/'

    def setUp(self):
        self.company = make_company('ntmig21', 'NTMIG21')
        self.user = User.objects.create_user(
            username='ntmig21-admin', password='x', company=self.company,
            role_legacy='admin')
        self.api = auth(self.user)

    def _creer_playbook(self):
        return self.api.post(self.ARTICLES, {
            'titre': 'Déploiement module Ventes',
            'type_article': 'playbook',
            'contenu_structure': STRUCTURE_VENTES,
        }, format='json')

    def test_playbook_cree_consultable_et_versionne(self):
        resp = self._creer_playbook()
        self.assertEqual(resp.status_code, 201, resp.data)
        article_id = resp.data['id']
        self.assertEqual(resp.data['type_article'], 'playbook')
        self.assertEqual(len(resp.data['contenu_structure']), 3)
        # Consultable comme un article kb ordinaire, avec ses phases
        # NORMALISÉES (8 étapes au total sur les 3 phases).
        detail = self.api.get(f'{self.ARTICLES}{article_id}/')
        self.assertEqual(detail.status_code, 200)
        phases = detail.data['phases']
        self.assertEqual([p['titre'] for p in phases],
                         ['Prérequis', 'Réglages', 'Go-live'])
        self.assertEqual(sum(len(p['etapes']) for p in phases), 8)
        # Versionné par le moteur EXISTANT (KbArticleVersion) : l'instantané
        # fige aussi la structure, sinon restaurer une version rendrait un
        # playbook sans ses phases.
        version = self.api.post(
            f'{self.ARTICLES}{article_id}/nouvelle-version/', {}, format='json')
        self.assertIn(version.status_code, (200, 201), version.data)
        versions = KbArticleVersion.objects.filter(article_id=article_id)
        self.assertTrue(versions.exists())
        derniere = versions.order_by('-version').first()
        self.assertEqual(len(derniere.contenu_structure), 3)

    def test_article_ordinaire_inchange(self):
        """Rétro-compatibilité : un article normal reste un article normal."""
        resp = self.api.post(
            self.ARTICLES, {'titre': 'Procédure ONEE'}, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        self.assertEqual(resp.data['type_article'], 'article')
        self.assertEqual(resp.data['contenu_structure'], [])
        self.assertEqual(resp.data['phases'], [])

    def test_structure_refusee_sur_article_ordinaire(self):
        resp = self.api.post(self.ARTICLES, {
            'titre': 'Faux playbook',
            'contenu_structure': STRUCTURE_VENTES,
        }, format='json')
        self.assertEqual(resp.status_code, 400)
        self.assertIn('contenu_structure', resp.data)

    def test_cles_etapes_en_double_refusees(self):
        """Deux étapes de même clé feraient MENTIR la progression NTMIG22."""
        resp = self.api.post(self.ARTICLES, {
            'titre': 'Playbook cassé',
            'type_article': 'playbook',
            'contenu_structure': [
                {'titre': 'A', 'etapes': [{'cle': 'x', 'libelle': 'un'}]},
                {'titre': 'B', 'etapes': [{'cle': 'x', 'libelle': 'deux'}]},
            ],
        }, format='json')
        self.assertEqual(resp.status_code, 400)
        self.assertIn('contenu_structure', resp.data)

    def test_structure_non_liste_refusee(self):
        resp = self.api.post(self.ARTICLES, {
            'titre': 'Playbook cassé',
            'type_article': 'playbook',
            'contenu_structure': {'phase': 'unique'},
        }, format='json')
        self.assertEqual(resp.status_code, 400)

    def test_filtre_type_article(self):
        self._creer_playbook()
        self.api.post(self.ARTICLES, {'titre': 'Article normal'}, format='json')
        resp = self.api.get(self.ARTICLES, {'type_article': 'playbook'})
        data = resp.data
        lignes = data['results'] if isinstance(data, dict) else data
        self.assertEqual(len(lignes), 1)
        self.assertEqual(lignes[0]['titre'], 'Déploiement module Ventes')
        # Sans filtre : les deux articles (comportement historique inchangé).
        resp = self.api.get(self.ARTICLES)
        data = resp.data
        lignes = data['results'] if isinstance(data, dict) else data
        self.assertEqual(len(lignes), 2)

    def test_selectors_normalisent_une_structure_partielle(self):
        """Un playbook à demi rempli reste lisible (dégradation propre)."""
        article = KbArticle.objects.create(
            company=self.company, titre='Partiel',
            type_article=KbArticle.TypeArticle.PLAYBOOK,
            contenu_structure=[
                {'titre': 'Sans clé', 'etapes': ['étape en texte', 42]},
                'phase invalide',
                {'titre': 'Sans étape'},
            ])
        phases = selectors.phases_playbook(article)
        self.assertEqual(len(phases), 2)
        self.assertEqual(phases[0]['cle'], 'phase1')
        self.assertEqual(len(phases[0]['etapes']), 1)
        self.assertEqual(phases[1]['etapes'], [])
        self.assertEqual(selectors.cles_etapes_playbook(article), ['phase1.1'])

    def test_playbook_par_id_scope_societe_et_type(self):
        autre = make_company('ntmig21-bis', 'NTMIG21 bis')
        playbook = KbArticle.objects.create(
            company=self.company, titre='PB',
            type_article=KbArticle.TypeArticle.PLAYBOOK,
            contenu_structure=STRUCTURE_VENTES)
        ordinaire = KbArticle.objects.create(
            company=self.company, titre='Ordinaire')
        self.assertIsNotNone(
            selectors.playbook_par_id(playbook.pk, self.company))
        # Autre société → None (jamais le playbook d'un autre tenant).
        self.assertIsNone(selectors.playbook_par_id(playbook.pk, autre))
        # Article ordinaire → None (non instanciable).
        self.assertIsNone(
            selectors.playbook_par_id(ordinaire.pk, self.company))
        self.assertIsNone(selectors.playbook_par_id(None, self.company))
        self.assertEqual(
            list(selectors.playbooks_qs(self.company)), [playbook])
        self.assertEqual(list(selectors.playbooks_qs(None)), [])
