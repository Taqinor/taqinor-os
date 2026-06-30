"""Écritures / orchestration de la Base de connaissances.

La société est TOUJOURS fournie par l'appelant (résolue côté serveur depuis
``request.user.company``) — jamais lue d'un corps de requête. Le numéro de
version est incrémental PAR article et calculé côté serveur (max(version)+1,
sous verrou — JAMAIS count()+1, qui collisionne sous concurrence).
"""
from django.db import transaction

from .models import KbLecture, KbArticleVersion, KbArticleChunk


def marquer_lu(article, *, utilisateur):
    """Enregistre (idempotemment) la LECTURE d'un article par un utilisateur.

    Une seule ligne par (article, utilisateur) : un premier appel crée la ligne,
    les suivants rafraîchissent ``lu_le`` (``auto_now``) sans dupliquer. La
    société est forcée à celle de l'article (jamais du corps de requête) et
    l'utilisateur agissant est fourni par la vue (jamais du corps). Renvoie le
    couple ``(lecture, created)``.
    """
    with transaction.atomic():
        lecture, created = KbLecture.objects.get_or_create(
            article=article,
            utilisateur=utilisateur,
            defaults={'company': article.company},
        )
        if not created:
            # Rafraîchit l'horodatage de dernière lecture (auto_now) et
            # ré-aligne la société par sécurité si l'article a migré.
            lecture.company = article.company
            lecture.save(update_fields=['company', 'lu_le'])
    return lecture, created


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


# ── KB6 — Source de contenu pour le RAG/DocQA (FG352, pgvector, no-op sans clé) ──

def indexer_article_kb(article):
    """KB6 — (Ré)indexe les fragments RAG/DocQA d'un article (no-op sans clé).

    Rend l'article de la base de connaissances exploitable par le pipeline
    RAG/DocQA déjà construit dans ``apps.ged`` (FG352). On RÉUTILISE les services
    de la GED via un import FONCTION-LOCAL — une lecture inter-app d'un *service*
    (autorisée par la frontière inter-app : on ne touche jamais aux
    ``models``/``views`` de la GED) plutôt que de réimplémenter le découpage ou
    l'embedding :

      * ``ged.services.embedding_enabled()`` — la MÊME porte clé-gated ;
      * ``ged.services.chunk_text(...)`` — le MÊME découpage chevauchant ;
      * ``ged.services.compute_embedding(...)`` — le MÊME provider d'embedding.

    Le texte indexé concatène le titre et le corps de l'article. Chaque fragment
    est stocké dans :class:`KbArticleChunk` — même type pgvector et même
    dimension que ``ged.DocumentChunk`` (pas un second magasin vectoriel).

    KEY-GATED : sans clé d'embedding, c'est un no-op TOTAL — aucun fragment écrit,
    aucun appel réseau, aucun coût, renvoie 0. Idempotent : remplace les fragments
    existants de l'article. Ne lève jamais (l'indexation ne doit pas casser une
    écriture documentaire). La company de chaque fragment est posée côté serveur
    (celle de l'article), jamais lue d'un corps de requête.

    Renvoie le nombre de fragments embeddés et stockés.
    """
    # Import FONCTION-LOCAL : lecture inter-app d'un SERVICE de la GED
    # (jamais ses models/views) — évite aussi tout cycle d'import au chargement.
    from apps.ged import services as ged_services

    if not ged_services.embedding_enabled():
        return 0
    texte = f'{article.titre}\n{article.corps or ""}'.strip()
    fragments = ged_services.chunk_text(texte)
    if not fragments:
        # Plus aucun contenu indexable : purge les anciens fragments.
        KbArticleChunk.objects.filter(article=article).delete()
        return 0
    lignes = []
    for idx, fragment in enumerate(fragments):
        try:
            vec = ged_services.compute_embedding(fragment)
        except Exception:  # pragma: no cover - robustesse : jamais bloquer.
            vec = None
        if vec is None:
            continue
        lignes.append(KbArticleChunk(
            company=article.company, article=article,
            chunk_index=idx, texte=fragment, embedding=vec))
    with transaction.atomic():
        KbArticleChunk.objects.filter(article=article).delete()
        if lignes:
            KbArticleChunk.objects.bulk_create(lignes)
    return len(lignes)
