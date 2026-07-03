"""Écritures / orchestration de la Base de connaissances.

La société est TOUJOURS fournie par l'appelant (résolue côté serveur depuis
``request.user.company``) — jamais lue d'un corps de requête. Le numéro de
version est incrémental PAR article et calculé côté serveur (max(version)+1,
sous verrou — JAMAIS count()+1, qui collisionne sous concurrence).
"""
import logging

from django.db import transaction

from .models import KbArticle, KbLecture, KbArticleVersion, KbArticleChunk

logger = logging.getLogger(__name__)


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


# ── XKB12 — Gabarits d'articles utilisateur ─────────────────────────────────

def creer_depuis_gabarit(gabarit, *, auteur, company):
    """XKB12 — Crée un nouvel article BROUILLON pré-rempli depuis un gabarit.

    Copie titre + corps + format + catégorie/tags du gabarit ; le nouvel
    article N'EST PAS lui-même un gabarit (``est_gabarit=False``). La société
    et l'auteur sont fournis par l'appelant (résolus côté serveur, jamais du
    corps de requête) — jamais celle du gabarit si elle diffère (protège
    contre un gabarit d'une autre société, même si ce cas est déjà bloqué en
    amont par le scoping du queryset appelant).
    """
    return KbArticle.objects.create(
        company=company,
        titre=gabarit.titre,
        corps=gabarit.corps,
        corps_format=gabarit.corps_format,
        categorie=gabarit.categorie,
        tags=gabarit.tags,
        statut=KbArticle.Statut.BROUILLON,
        auteur=auteur,
        est_gabarit=False,
    )


# ── XKB7 — Relance des non-lecteurs de lecture obligatoire ─────────────────

def relancer_lectures_obligatoires(company=None):
    """Relance (notify()) tous les non-lecteurs de lecture obligatoire.

    Best-effort et jamais bloquant : une notification qui échoue n'empêche pas
    les suivantes. ``company`` restreint à une seule société (sweep par
    société) ; ``None`` balaie toutes les sociétés actives. Import
    fonction-local des apps notifications (lecture de service, jamais de
    models/views directement — voir CLAUDE.md). Renvoie le nombre de relances
    émises.
    """
    from apps.notifications.models import EventType
    from apps.notifications.services import notify

    from . import selectors
    from .models import KbArticle, KbLectureObligatoire

    qs = KbLectureObligatoire.objects.select_related('article')
    if company is not None:
        qs = qs.filter(company=company)
    total = 0
    for assignation in qs:
        article = assignation.article
        if article.statut != KbArticle.Statut.PUBLIE:
            continue
        try:
            deja_lu = set(
                KbLecture.objects.filter(article=article)
                .values_list('utilisateur_id', flat=True))
            for user in selectors.assignees_for_assignation(assignation):
                if user.id in deja_lu:
                    continue
                try:
                    notify(
                        user, EventType.DIGEST,
                        f'Lecture obligatoire : {article.titre}',
                        body="Cet article requiert votre lecture.",
                        link=f'/kb/articles/{article.id}',
                        company=assignation.company,
                    )
                    total += 1
                except Exception:  # pragma: no cover - défensif
                    logger.warning(
                        'relancer_lectures_obligatoires: notify échoué',
                        exc_info=True)
        except Exception:  # pragma: no cover - défensif
            logger.warning(
                'relancer_lectures_obligatoires: assignation %s échouée',
                getattr(assignation, 'pk', None), exc_info=True)
    return total


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
