"""Signaux de la Base de connaissances (apps.kb).

KB6 — (ré)indexe automatiquement un :class:`KbArticle` dans le pipeline
RAG/DocQA (FG352) à chaque enregistrement. KEY-GATED : sans clé d'embedding,
``indexer_article_kb`` est un no-op total (aucune écriture, aucun appel réseau,
aucun coût) — le signal ne fait alors rien d'observable. Le récepteur ne lève
jamais : l'indexation ne doit jamais casser une écriture d'article.

XKB13 — notifie l'AUTEUR d'un article KB quand un commentaire est posté sur
sa fiche (en plus des @mentions déjà gérées par ``records.views``). ``records``
est une app FONDATION (exempte de la frontière cross-app — voir CLAUDE.md) :
on écoute directement ``records.models.Comment`` ici plutôt que de dupliquer
le mécanisme de commentaires dans ``kb``.
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


def _kb_comment_receiver():
    """Construit le récepteur de commentaire une fois ``records`` chargé.

    Import fonction-local du modèle ``Comment`` (app fondation) pour éviter
    tout souci d'ordre de chargement des apps au démarrage.
    """
    from apps.records.models import Comment

    @receiver(post_save, sender=Comment, dispatch_uid='kb_notify_article_author')
    def notify_article_author_on_comment(sender, instance, created, **kwargs):
        """XKB13 — notifie l'auteur de l'article KB commenté (pas seulement
        les @mentions, déjà gérées par ``records.views._notify_mentions``).

        No-op pour tout commentaire NON rattaché à un ``kb.kbarticle``, pour
        une mise à jour (``created=False``), ou si l'article n'a pas d'auteur
        (ou si l'auteur commente son propre article — pas de self-notify).
        Jamais bloquant : toute erreur est avalée.
        """
        if not created:
            return
        try:
            ct = instance.content_type
            if ct.app_label != 'kb' or ct.model != 'kbarticle':
                return
            article = KbArticle.objects.filter(id=instance.object_id).first()
            if article is None or not article.auteur_id:
                return
            if instance.author_id and instance.author_id == article.auteur_id:
                return  # pas de self-notify.
            from apps.notifications.models import EventType
            from apps.notifications.services import notify
            notify(
                article.auteur, EventType.DIGEST,
                f'Nouveau commentaire sur « {article.titre} »',
                body=(instance.body or '')[:200],
                link=f'/kb/articles/{article.id}',
                company=article.company,
            )
        except Exception:  # pragma: no cover - défensif : jamais bloquer.
            pass

    return notify_article_author_on_comment
