"""Signaux de la Base de connaissances (apps.kb).

KB6 — (ré)indexe automatiquement un :class:`KbArticle` dans le pipeline
RAG/DocQA (FG352) à chaque enregistrement. KEY-GATED : sans clé d'embedding,
``indexer_article_kb`` est un no-op total (aucune écriture, aucun appel réseau,
aucun coût) — le signal ne fait alors rien d'observable. Le récepteur ne lève
jamais : l'indexation ne doit jamais casser une écriture d'article.
"""
from django.db.models.signals import post_save
from django.dispatch import receiver

from .models import KbArticle


@receiver(post_save, sender=KbArticle, dispatch_uid='kb_index_article_rag')
def index_article_on_save(sender, instance, **kwargs):
    """Réindexe l'article pour le RAG/DocQA après chaque enregistrement.

    No-op sans clé d'embedding (voir ``services.indexer_article_kb``). Toute
    erreur est avalée : indexer ne doit jamais empêcher de sauver un article.
    """
    from . import services
    try:
        services.indexer_article_kb(instance)
    except Exception:  # pragma: no cover - robustesse : jamais bloquer l'écriture.
        pass
