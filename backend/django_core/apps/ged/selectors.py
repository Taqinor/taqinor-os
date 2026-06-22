"""Lectures de la GED — point d'entrée pour les lectures cross-app.

Conformément au CLAUDE.md (frontière cross-app), une autre app qui a besoin de
LIRE la GED passe par ces fonctions plutôt que d'importer `ged.models`.
Toutes les lectures sont bornées à une société.
"""
from .models import (
    Cabinet, Coffre, Document, DocumentLien, DocumentTag,
    DocumentTagAssignment, DocumentVersion, Folder,
)


def tags_for_company(company):
    """GED9 — Tags de la taxonomie d'une société (QuerySet)."""
    return DocumentTag.objects.filter(company=company)


def tags_for_document(document):
    """GED9 — Tags appliqués à un document (QuerySet, distinct)."""
    return DocumentTag.objects.filter(
        company=document.company, assignments__document=document).distinct()


def documents_with_tag(tag, *, include_descendants=False):
    """GED9 — Documents portant un tag (option : + ses sous-tags descendants).

    Avec `include_descendants`, on inclut les documents étiquetés par n'importe
    quel descendant du tag dans la taxonomie (filtre hiérarchique). Borné à la
    société du tag.
    """
    tag_ids = [tag.pk]
    if include_descendants:
        frontier = [tag.pk]
        while frontier:
            children = list(DocumentTag.objects.filter(
                company=tag.company, parent_id__in=frontier
            ).values_list('pk', flat=True))
            children = [c for c in children if c not in tag_ids]
            tag_ids.extend(children)
            frontier = children
    return Document.objects.filter(
        company=tag.company, tag_assignments__tag_id__in=tag_ids).distinct()


def cabinets_for_company(company):
    """Cabinets d'une société (QuerySet, ordonné par nom)."""
    return Cabinet.objects.filter(company=company)


def coffres_for_user(user):
    """GED8 — Coffres-forts qu'un utilisateur peut voir (ACL propriétaire+admin).

    Un admin (ou superuser) voit tous les coffres de sa société ; un employé ne
    voit que SES coffres (`proprietaire`). Toujours borné à la société de
    l'utilisateur — jamais de fuite cross-société.
    """
    from django.db.models import Q
    company = getattr(user, 'company', None)
    if company is None and not user.is_superuser:
        return Coffre.objects.none()
    qs = Coffre.objects.all()
    if user.company_id:
        qs = qs.filter(company_id=user.company_id)
    elif not user.is_superuser:
        return Coffre.objects.none()
    if getattr(user, 'is_admin_role', False) or user.is_superuser:
        return qs
    return qs.filter(proprietaire_id=user.id)


def documents_visible_to_user(user):
    """GED8 — Documents d'une société FILTRÉS par l'ACL coffre-fort.

    Les documents hors coffre (`coffre__isnull`) sont visibles de tout rôle ;
    ceux dans un coffre ne sont visibles que du propriétaire du coffre et des
    administrateurs. Borné à la société de l'utilisateur.
    """
    from django.db.models import Q
    if not user.company_id and not user.is_superuser:
        return Document.objects.none()
    qs = Document.objects.all()
    if user.company_id:
        qs = qs.filter(company_id=user.company_id)
    if getattr(user, 'is_admin_role', False) or user.is_superuser:
        return qs
    # Non-admin : documents hors coffre OU dans un coffre dont il est proprio.
    return qs.filter(Q(coffre__isnull=True) | Q(coffre__proprietaire_id=user.id))


def documents_in_coffre(coffre):
    """Documents rattachés à un coffre (même société)."""
    return Document.objects.filter(company=coffre.company, coffre=coffre)


def search_documents(user, query):
    """GED11 — Recherche plein-texte Postgres (SearchVector + GIN) avec ACL.

    Filtre les documents visibles de l'utilisateur (ACL coffre-fort + société)
    par le tsvector `search_vector` (config 'french'), ordonnés par pertinence
    (`SearchRank`). Une requête vide renvoie le queryset vide. La recherche
    couvre nom, description, métadonnées et texte OCR (cf.
    `services.update_search_vector`).
    """
    from django.contrib.postgres.search import SearchQuery, SearchRank
    base = documents_visible_to_user(user)
    if not query or not str(query).strip():
        return base.none()
    sq = SearchQuery(str(query), config='french', search_type='websearch')
    return (base.filter(search_vector=sq)
            .annotate(rank=SearchRank('search_vector', sq))
            .order_by('-rank', 'nom'))


def semantic_search_documents(user, query, *, limit=20):
    """GED12 — Recherche sémantique (pgvector cosinus), KEY-GATED no-op.

    Quand l'embedding est activé (clé présente) et la requête vectorisable, on
    classe les documents visibles par distance cosinus à l'embedding de la
    requête. Sinon (clé absente / requête non vectorisable), on RETOMBE
    proprement sur la recherche plein-texte GED11 — la fonctionnalité dégrade
    sans jamais échouer ni appeler un service payant. Borné par l'ACL/société.
    """
    from . import services
    if not services.embedding_enabled():
        return search_documents(user, query)[:limit]
    vec = services.compute_embedding(str(query) if query else '')
    if vec is None:
        return search_documents(user, query)[:limit]
    from pgvector.django import CosineDistance
    base = documents_visible_to_user(user).filter(embedding__isnull=False)
    return (base.annotate(distance=CosineDistance('embedding', vec))
            .order_by('distance')[:limit])


def folders_for_company(company):
    """Dossiers d'une société (QuerySet)."""
    return Folder.objects.filter(company=company)


def folder_descendants(folder):
    """Sous-arbre strict d'un dossier via le chemin matérialisé."""
    return folder.descendants()


def documents_in_folder(folder):
    """Documents directement rattachés à un dossier (même société)."""
    return Document.objects.filter(company=folder.company, folder=folder)


def documents_for_company(company):
    """Documents d'une société (QuerySet)."""
    return Document.objects.filter(company=company)


def latest_version(document):
    """Dernière version (numéro le plus élevé) d'un document, ou None."""
    return document.versions.order_by('-version').first()


def versions_for_document(document):
    """Versions d'un document (QuerySet, plus récente d'abord)."""
    return DocumentVersion.objects.filter(document=document)


def documents_for_target(company, target):
    """GED6 — Documents GED liés à un objet métier (reverse lookup, scopé société).

    `target` est une instance métier autorisée (lead, devis, facture, chantier…).
    Retourne les Documents (distincts) rattachés à cette cible via `DocumentLien`,
    bornés à `company`. Lecture cross-app sans importer `ged.models` ailleurs.
    """
    from django.contrib.contenttypes.models import ContentType
    ct = ContentType.objects.get_for_model(type(target))
    return Document.objects.filter(
        company=company,
        liens__content_type=ct,
        liens__object_id=target.pk,
    ).distinct()


def liens_for_target(company, target):
    """GED6 — Liens (DocumentLien) rattachés à un objet métier, scopés société."""
    from django.contrib.contenttypes.models import ContentType
    ct = ContentType.objects.get_for_model(type(target))
    return DocumentLien.objects.filter(
        company=company, content_type=ct, object_id=target.pk)
