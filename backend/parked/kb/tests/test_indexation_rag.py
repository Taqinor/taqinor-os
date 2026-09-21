"""Tests KB6 — articles comme source de contenu pour le RAG/DocQA (FG352).

Couvre :
  * no-op clé-gated PAR DÉFAUT : sans clé d'embedding, ``indexer_article_kb``
    renvoie 0 et n'écrit AUCUN fragment (aucun appel réseau, aucun coût) ;
  * le signal post_save d'un article est aussi un no-op sans clé ;
  * avec un provider simulé (clé activée + ``compute_embedding`` monkeypatché),
    des fragments embeddés sont produits et stockés ;
  * idempotence : une ré-indexation ne duplique pas les fragments ;
  * isolation multi-société : chaque fragment porte la company de son article.

On RÉUTILISE la porte clé-gated et l'embedding de la GED (``apps.ged.services``)
— c'est cette même fonction qu'on monkeypatch pour simuler un provider présent.
"""
from unittest import mock

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings

from authentication.models import Company

from apps.kb import services
from apps.kb.models import KbArticle, KbArticleChunk

User = get_user_model()


def make_company(slug, nom):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


def _fake_embed(text):
    """Vecteur 1024 déterministe orienté par un mot-clé (provider simulé)."""
    base = [0.0] * 1024
    low = (text or '').lower()
    if 'pompe' in low or 'pompage' in low:
        base[0] = 1.0
    elif 'onduleur' in low:
        base[1] = 1.0
    else:
        base[2] = 1.0
    return base


class IndexationRagKbTests(TestCase):
    def setUp(self):
        self.co_a = make_company('kb-rag-a', 'Société A')
        self.co_b = make_company('kb-rag-b', 'Société B')

    # — Sans clé : no-op total (chemin par défaut, CI sans clé) —
    def test_indexer_noop_sans_cle(self):
        art = KbArticle.objects.create(
            company=self.co_a, titre='Manuel pompe solaire',
            corps='La pompe solaire de pompage agricole. ' * 60)
        # Par défaut GED_EMBEDDING_ENABLED est faux → no-op total.
        n = services.indexer_article_kb(art)
        self.assertEqual(n, 0)
        self.assertEqual(KbArticleChunk.objects.filter(article=art).count(), 0)

    def test_signal_post_save_noop_sans_cle(self):
        # La création de l'article déclenche le signal post_save : sans clé il
        # ne doit écrire aucun fragment ni lever d'erreur.
        art = KbArticle.objects.create(
            company=self.co_a, titre='Onduleur hybride',
            corps='Branchement onduleur réseau. ' * 60)
        self.assertEqual(KbArticleChunk.objects.filter(article=art).count(), 0)

    # — Avec un provider simulé (clé présente) —
    def test_indexer_produit_des_fragments_avec_stub(self):
        art = KbArticle.objects.create(
            company=self.co_a, titre='Manuel pompe solaire', corps='')
        texte = ('La pompe solaire de pompage agricole. ' * 60
                 + 'Branchement onduleur réseau. ' * 60)
        art.corps = texte
        art.save(update_fields=['corps'])
        with override_settings(GED_EMBEDDING_ENABLED=True), \
                mock.patch('apps.ged.services.compute_embedding',
                           side_effect=_fake_embed):
            n = services.indexer_article_kb(art)
            self.assertGreater(n, 1)
            chunks = KbArticleChunk.objects.filter(article=art)
            self.assertEqual(chunks.count(), n)
            # Chaque fragment porte la company de l'article + un embedding.
            self.assertTrue(all(c.company_id == self.co_a.id for c in chunks))
            self.assertTrue(all(c.embedding is not None for c in chunks))

    def test_indexer_idempotent_avec_stub(self):
        art = KbArticle.objects.create(
            company=self.co_a, titre='Manuel onduleur',
            corps='Onduleur hybride. ' * 100)
        with override_settings(GED_EMBEDDING_ENABLED=True), \
                mock.patch('apps.ged.services.compute_embedding',
                           side_effect=_fake_embed):
            n1 = services.indexer_article_kb(art)
            n2 = services.indexer_article_kb(art)
            self.assertEqual(n1, n2)
            self.assertEqual(
                KbArticleChunk.objects.filter(article=art).count(), n2)

    def test_fragments_company_isolated(self):
        art_a = KbArticle.objects.create(
            company=self.co_a, titre='Pompe A', corps='pompe solaire A ' * 80)
        art_b = KbArticle.objects.create(
            company=self.co_b, titre='Pompe B', corps='pompe solaire B ' * 80)
        with override_settings(GED_EMBEDDING_ENABLED=True), \
                mock.patch('apps.ged.services.compute_embedding',
                           side_effect=_fake_embed):
            services.indexer_article_kb(art_a)
            services.indexer_article_kb(art_b)
        chunks_a = KbArticleChunk.objects.filter(article=art_a)
        chunks_b = KbArticleChunk.objects.filter(article=art_b)
        self.assertTrue(chunks_a.exists())
        self.assertTrue(chunks_b.exists())
        # Aucun fragment de A ne porte la company de B et inversement.
        self.assertTrue(all(c.company_id == self.co_a.id for c in chunks_a))
        self.assertTrue(all(c.company_id == self.co_b.id for c in chunks_b))

    def test_indexer_purge_si_contenu_vide(self):
        art = KbArticle.objects.create(
            company=self.co_a, titre='Vide', corps='contenu ' * 100)
        with override_settings(GED_EMBEDDING_ENABLED=True), \
                mock.patch('apps.ged.services.compute_embedding',
                           side_effect=_fake_embed):
            self.assertGreater(services.indexer_article_kb(art), 0)
            # Article vidé → la ré-indexation purge les anciens fragments.
            art.titre = ''
            art.corps = ''
            art.save(update_fields=['titre', 'corps'])
            self.assertEqual(services.indexer_article_kb(art), 0)
            self.assertEqual(
                KbArticleChunk.objects.filter(article=art).count(), 0)
