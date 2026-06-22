"""Écritures / orchestration de la Base de connaissances.

La société est TOUJOURS fournie par l'appelant (résolue côté serveur depuis
``request.user.company``) — jamais lue d'un corps de requête. Le numéro de
version est incrémental PAR article et calculé côté serveur (max(version)+1,
sous verrou — JAMAIS count()+1, qui collisionne sous concurrence).
"""
from django.db import transaction

from .models import KbArticleVersion


def snapshot_article(article, *, auteur=None):
    """Fige titre + contenu de l'article dans une nouvelle ligne de version.

    Le numéro est calculé côté serveur (dernière version + 1) sous verrou, et la
    société est forcée à celle de l'article (jamais du corps de requête). Idempotent
    par appel : chaque appel crée exactement une version, sans toucher l'article.
    """
    with transaction.atomic():
        last = (KbArticleVersion.objects
                .select_for_update()
                .filter(article=article)
                .order_by('-version')
                .first())
        next_version = (last.version + 1) if last else 1
        return KbArticleVersion.objects.create(
            company=article.company,
            article=article,
            version=next_version,
            titre=article.titre,
            contenu=article.corps,
            auteur=auteur,
        )
