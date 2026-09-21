"""Tests XKB20 — Récupération RAG des articles KB, respectueuse des ACL.

Couvre :
* sans clé d'embedding, ``retrieve_chunks`` est un no-op propre (liste vide) ;
* avec un provider simulé, les fragments d'un article VISIBLE sont récupérés ;
* un article restreint (ACL de rôle KB7) n'est PAS cité pour un utilisateur
  non autorisé mais L'EST pour un admin ;
* isolation cross-société (jamais de fragment d'une autre société).
"""
from unittest import mock

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings

from authentication.models import Company

from apps.kb import selectors, services
from apps.kb.models import KbArticle, KbArticleAcl

User = get_user_model()


def make_company(slug, nom):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


def make_user(company, username, role='normal'):
    return User.objects.create_user(
        username=username, password='x', company=company, role_legacy=role)


def _fake_embed(text):
    return [1.0] + [0.0] * 1023


class KbRagRetrievalNoopTests(TestCase):
    def setUp(self):
        self.co = make_company('kb-rag-noop', 'N')
        self.user = make_user(self.co, 'kb-rag-noop-u1')

    def test_retrieve_chunks_noop_without_key(self):
        art = KbArticle.objects.create(
            company=self.co, titre='Procédure', corps='contenu ' * 50,
            statut=KbArticle.Statut.PUBLIE)
        services.indexer_article_kb(art)  # no-op sans clé
        chunks = selectors.retrieve_chunks(self.user, 'procédure')
        self.assertEqual(chunks, [])

    def test_retrieve_chunks_noop_on_empty_query(self):
        with override_settings(GED_EMBEDDING_ENABLED=True), \
                mock.patch('apps.ged.services.compute_embedding',
                           side_effect=_fake_embed):
            self.assertEqual(selectors.retrieve_chunks(self.user, ''), [])


class KbRagRetrievalAclTests(TestCase):
    def setUp(self):
        self.co = make_company('kb-rag-acl', 'A')
        self.admin = make_user(self.co, 'kb-rag-acl-admin', role='admin')
        self.normal = make_user(self.co, 'kb-rag-acl-normal', role='normal')
        self.restricted = KbArticle.objects.create(
            company=self.co, titre='Procédure restreinte',
            corps='contenu confidentiel ' * 50,
            statut=KbArticle.Statut.PUBLIE)
        # KB7 — restreint la LECTURE au palier 'responsable' uniquement.
        KbArticleAcl.objects.create(
            company=self.co, article=self.restricted, role='responsable',
            niveau=KbArticleAcl.Niveau.LECTURE)

    def _index_with_stub(self, article):
        with override_settings(GED_EMBEDDING_ENABLED=True), \
                mock.patch('apps.ged.services.compute_embedding',
                           side_effect=_fake_embed):
            services.indexer_article_kb(article)

    def test_restricted_article_not_retrieved_for_unauthorized_user(self):
        self._index_with_stub(self.restricted)
        with override_settings(GED_EMBEDDING_ENABLED=True), \
                mock.patch('apps.ged.services.compute_embedding',
                           side_effect=_fake_embed):
            chunks = selectors.retrieve_chunks(self.normal, 'confidentiel')
        self.assertEqual(chunks, [])

    def test_restricted_article_retrieved_for_admin(self):
        self._index_with_stub(self.restricted)
        with override_settings(GED_EMBEDDING_ENABLED=True), \
                mock.patch('apps.ged.services.compute_embedding',
                           side_effect=_fake_embed):
            chunks = selectors.retrieve_chunks(self.admin, 'confidentiel')
        self.assertTrue(len(chunks) > 0)
        self.assertTrue(all(c.article_id == self.restricted.id for c in chunks))

    def test_cross_company_isolation(self):
        other_co = make_company('kb-rag-acl-other', 'O')
        other_user = make_user(other_co, 'kb-rag-acl-other-u1', role='admin')
        self._index_with_stub(self.restricted)
        with override_settings(GED_EMBEDDING_ENABLED=True), \
                mock.patch('apps.ged.services.compute_embedding',
                           side_effect=_fake_embed):
            chunks = selectors.retrieve_chunks(other_user, 'confidentiel')
        self.assertEqual(chunks, [])
