"""Lectures de la GED — point d'entrée pour les lectures cross-app.

Conformément au CLAUDE.md (frontière cross-app), une autre app qui a besoin de
LIRE la GED passe par ces fonctions plutôt que d'importer `ged.models`.
Toutes les lectures sont bornées à une société.
"""
from .models import (
    ACL_RANK, AclGed, Cabinet, Coffre, DemandeApprobation, Document,
    DocumentLien, DocumentTag, DocumentVersion, Folder, PartageGed,
    PolitiqueRetention,
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
    """GED8 + GED19 — Documents d'une société filtrés par l'ACL coffre-fort + GED19.

    Couche 1 (GED8) : les documents hors coffre (`coffre__isnull`) sont visibles
    de tout rôle ; ceux dans un coffre ne sont visibles que du propriétaire du
    coffre et des administrateurs. Couche 2 (GED19, SOFT) : si un document — ou
    un de ses dossiers ancêtres — porte une ACL GED19, l'utilisateur ne le voit
    QUE s'il y a au moins « lecture » effective (`acl_effective`). Les documents
    NON gouvernés par une ACL GED19 conservent strictement le comportement
    existant (backward-compat). Borné à la société de l'utilisateur ; l'admin /
    superuser voit tout.
    """
    from django.db.models import Q
    if not user.company_id and not user.is_superuser:
        return Document.objects.none()
    qs = Document.objects.all()
    if user.company_id:
        qs = qs.filter(company_id=user.company_id)
    if getattr(user, 'is_admin_role', False) or user.is_superuser:
        return qs
    # Couche 1 — ACL coffre-fort (GED8).
    qs = qs.filter(Q(coffre__isnull=True) | Q(coffre__proprietaire_id=user.id))
    # Couche 2 — ACL GED19 (SOFT, backward-compatible). Si AUCUNE entrée ACL
    # n'existe dans la société, on n'a rien à filtrer : comportement existant
    # préservé sans le moindre travail supplémentaire (court-circuit).
    if not AclGed.objects.filter(company_id=user.company_id).exists():
        return qs
    # Sinon, on affine : on RETIRE les seuls documents gouvernés par une ACL
    # GED19 sur lesquels l'utilisateur n'a aucun droit de lecture effectif. Les
    # documents non gouvernés restent visibles tels quels.
    refused = [
        d.pk for d in qs.select_related('folder')
        if acl_governs_target(d) and acl_effective(d, user) is None
    ]
    if refused:
        qs = qs.exclude(pk__in=refused)
    return qs


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


def retrieve_chunks(user, query, *, limit=5):
    """FG352 — Outil de récupération RAG : top-k fragments pour une question.

    Renvoie les `limit` fragments de documents (`DocumentChunk`) les plus proches
    de la question par distance cosinus dans le magasin pgvector partagé. Les
    fragments sont bornés aux documents que l'utilisateur peut VOIR (ACL
    coffre-fort + société, via `documents_visible_to_user`) — jamais de fuite
    cross-société.

    KEY-GATED no-op : sans clé d'embedding ou si la question n'est pas
    vectorisable, on renvoie une liste vide (aucun appel réseau, aucun coût) — le
    DocQA dégrade proprement plutôt que d'échouer. Le résultat est une liste de
    `DocumentChunk` (ordre = plus proche d'abord), chacun annoté de `distance`.
    """
    from .models import DocumentChunk
    from . import services
    if not services.embedding_enabled():
        return []
    if not query or not str(query).strip():
        return []
    vec = services.compute_embedding(str(query))
    if vec is None:
        return []
    from pgvector.django import CosineDistance
    # Restreint aux documents visibles de l'utilisateur (ACL + société).
    visible_ids = documents_visible_to_user(user).values_list('id', flat=True)
    base = (DocumentChunk.objects
            .filter(document_id__in=visible_ids, embedding__isnull=False))
    return list(base.annotate(distance=CosineDistance('embedding', vec))
                .order_by('distance')[:max(1, int(limit))])


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


def partages_for_company(company):
    """GED20 — Partages publics tokenisés d'une société (QuerySet).

    Borné à la société — jamais de fuite cross-société. Sert le CRUD de gestion
    (création/révocation/liste), distinct de l'accès public (token-only)."""
    return PartageGed.objects.filter(company=company)


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


def demandes_approbation_for_company(company):
    """GED18 — Demandes d'approbation/revue d'une société (QuerySet)."""
    return DemandeApprobation.objects.filter(company=company)


def demandes_approbation_for_document(document):
    """GED18 — Demandes d'approbation d'un document (QuerySet, récentes d'abord)."""
    return DemandeApprobation.objects.filter(
        company=document.company, document=document)


def pending_demande_for_document(document):
    """GED18 — Demande EN ATTENTE d'un document (au plus une), ou None."""
    from .models import APPROBATION_EN_ATTENTE
    return (DemandeApprobation.objects
            .filter(company=document.company, document=document,
                    statut=APPROBATION_EN_ATTENTE)
            .first())


# ── GED19 — ACL par dossier/document (héritage + override) ──────────────

def _folder_chain_ids(folder):
    """pk des dossiers de la cible (le plus PROCHE d'abord) → racine.

    Décode le chemin matérialisé `Folder.path` ("/1/4/9/") en liste de pk du
    plus proche (la cible elle-même) au plus lointain (la racine). Pas de
    requête : la chaîne entière est portée par `path`.
    """
    if folder is None or not folder.path:
        return [folder.pk] if folder is not None and folder.pk else []
    ids = [int(p) for p in folder.path.strip('/').split('/') if p]
    ids.reverse()  # plus proche (self) d'abord, racine en dernier
    return ids


def acl_entries_for_target(target):
    """GED19 — Entrées ACL pertinentes pour une cible (document OU dossier).

    Retourne un QuerySet `AclGed` borné à la société, couvrant :
      * l'override direct sur la cible (document ou dossier), ET
      * toute la chaîne de dossiers ancêtres (héritage), via `Folder.path`.
    Ordonné du plus PROCHE (override) au plus lointain (racine) — la résolution
    `acl_effective` n'a plus qu'à prendre le premier scope qui statue.
    """
    from django.db.models import Q
    if isinstance(target, Document):
        company = target.company
        folder = target.folder
        cond = Q(document=target)
    else:  # Folder
        company = target.company
        folder = target
        cond = Q()
    chain = _folder_chain_ids(folder)
    if chain:
        cond = cond | Q(folder_id__in=chain)
    if not cond:
        return AclGed.objects.none()
    return AclGed.objects.filter(cond, company=company)


def _principal_matches(entry, user):
    """True si l'entrée ACL s'applique à `user` (par utilisateur OU par rôle)."""
    if entry.utilisateur_id and entry.utilisateur_id == user.id:
        return True
    if entry.role_id and getattr(user, 'role_id', None) == entry.role_id:
        return True
    return False


def acl_effective(document_or_folder, user):
    """GED19 — Niveau d'accès EFFECTIF d'un utilisateur sur un document/dossier.

    Résout les droits en remontant la chaîne du chemin matérialisé `Folder.path`
    (HÉRITAGE) et en appliquant l'OVERRIDE le plus proche :

      * l'admin / superuser de la société a toujours « gestion » (jamais bloqué
        par une ACL) ;
      * le scope le PLUS PROCHE qui statue gagne — un override direct sur le
        document l'emporte sur son dossier, un dossier proche sur un ancêtre ;
      * à scope égal, le niveau le PLUS PERMISSIF parmi les entrées qui matchent
        le principal (utilisateur ET/OU rôle) gagne ;
      * une entrée d'un dossier ANCÊTRE ne se propage que si `herite=True` ; une
        entrée posée DIRECTEMENT sur la cible (document, ou le dossier lui-même)
        s'applique toujours, `herite` ou non.

    BACKWARD-COMPAT : si AUCUNE entrée ne couvre la cible, on renvoie ``None``
    (« pas d'ACL GED19 sur cette cible ») — l'appelant retombe alors sur le
    comportement existant (ACL coffre-fort GED8 + scoping société). Renvoie
    l'un de 'lecture'/'ecriture'/'gestion', ou ``None`` si non gouverné.

    Toujours borné à la société ; jamais de fuite cross-société.
    """
    if user is None or not getattr(user, 'is_authenticated', False):
        return None
    # Hors société de la cible : non gouverné par cette ACL (le scoping société
    # de l'appelant tranche). Superuser excepté.
    target_company_id = getattr(document_or_folder, 'company_id', None)
    if not user.is_superuser and user.company_id != target_company_id:
        return None
    if getattr(user, 'is_admin_role', False) or user.is_superuser:
        return 'gestion'

    is_document = isinstance(document_or_folder, Document)
    if is_document:
        direct_id = ('document', document_or_folder.pk)
        chain = _folder_chain_ids(document_or_folder.folder)
    else:
        direct_id = ('folder', document_or_folder.pk)
        chain = _folder_chain_ids(document_or_folder)

    entries = list(acl_entries_for_target(document_or_folder))
    if not entries:
        return None

    # Rang de proximité de chaque scope : 0 = override direct (le plus proche),
    # puis 1, 2… en remontant la chaîne de dossiers vers la racine.
    proximity = {}
    if is_document:
        proximity[('document', document_or_folder.pk)] = 0
        for depth, fid in enumerate(chain):
            proximity[('folder', fid)] = depth + 1
    else:
        for depth, fid in enumerate(chain):
            proximity[('folder', fid)] = depth

    best_scope = None       # rang de proximité le plus petit qui statue
    best_rank = 0           # niveau le plus permissif à ce scope
    for entry in entries:
        if not _principal_matches(entry, user):
            continue
        scope = (('document', entry.document_id) if entry.document_id
                 else ('folder', entry.folder_id))
        prox = proximity.get(scope)
        if prox is None:
            continue
        # Une entrée d'un ancêtre (pas le scope direct) ne compte que si elle
        # est marquée héritée vers le bas.
        is_direct = (scope == direct_id)
        if not is_direct and not entry.herite:
            continue
        rank = ACL_RANK.get(entry.niveau, 0)
        if best_scope is None or prox < best_scope:
            best_scope = prox
            best_rank = rank
        elif prox == best_scope and rank > best_rank:
            best_rank = rank

    if best_scope is None:
        return None
    for code, r in ACL_RANK.items():
        if r == best_rank:
            return code
    return None


def acl_governs_target(target):
    """GED19 — True si AU MOINS une entrée ACL couvre la cible (override/héritage).

    Permet à l'appelant de savoir si la cible est gouvernée par une ACL GED19
    (et donc si `acl_effective` est l'autorité) ou si elle retombe sur le
    comportement existant (backward-compat).
    """
    return acl_entries_for_target(target).exists()


def acls_for_document(document):
    """GED19 — Entrées ACL posées DIRECTEMENT sur un document (QuerySet)."""
    return AclGed.objects.filter(company=document.company, document=document)


def acls_for_folder(folder):
    """GED19 — Entrées ACL posées DIRECTEMENT sur un dossier (QuerySet)."""
    return AclGed.objects.filter(company=folder.company, folder=folder)


# ── GED22 — Politiques de rétention (durée de conservation + échéance) ─────

def politiques_retention_for_company(company, *, actif_only=False):
    """GED22 — Politiques de rétention d'une société (QuerySet, scopé société).

    Avec `actif_only`, ne renvoie que les politiques actives. Borné à la société
    — jamais de fuite cross-société.
    """
    qs = PolitiqueRetention.objects.filter(company=company)
    if actif_only:
        qs = qs.filter(actif=True)
    return qs


def _politique_couvre_document(politique, document):
    """True si une politique (active) couvre ce document, selon sa portée.

    Portées :
      * dossier  : le document vit dans ce dossier OU son sous-arbre (chemin
        matérialisé `Folder.path`) ;
      * cabinet  : le dossier du document appartient à ce cabinet ;
      * type     : la catégorie (`type_document`) correspond — comparée au
        `type_document` du document s'il existe (sinon non couvert) ;
      * global   : couvre tous les documents de la société.
    Toujours dans la même société (présupposé par l'appelant).
    """
    scope = politique.scope
    if scope == 'dossier':
        folder = document.folder
        if folder is None:
            return False
        target = politique.folder
        if target is None:
            return False
        # Le dossier du document est la cible elle-même OU un descendant
        # (son chemin matérialisé commence par celui de la cible).
        return bool(folder.path and target.path
                    and folder.path.startswith(target.path))
    if scope == 'cabinet':
        folder = document.folder
        return folder is not None and folder.cabinet_id == politique.cabinet_id
    if scope == 'type':
        doc_type = _document_type(document)
        if not doc_type:
            return False
        return doc_type.lower() == politique.type_document.strip().lower()
    # global — couvre tout document de la société.
    return True


def _document_type(document):
    """Catégorie libre d'un document, pour la portée `type` d'une politique.

    Le modèle Document n'a pas de champ catégorie dédié : on lit une éventuelle
    valeur dans ses métadonnées typées (`custom_data`) sous l'une des clés
    usuelles (`type_document`/`type`/`categorie`). Renvoie '' si absente — un
    document sans catégorie n'est jamais couvert par une politique typée."""
    data = getattr(document, 'custom_data', None) or {}
    if not isinstance(data, dict):
        return ''
    for key in ('type_document', 'type', 'categorie'):
        val = data.get(key)
        if val:
            return str(val).strip()
    return ''


def politique_applicable(document, *, politiques=None):
    """GED22 — Politique de rétention ACTIVE la PLUS SPÉCIFIQUE pour un document.

    Parmi les politiques actives de la société qui couvrent le document, retient
    la plus spécifique (dossier > cabinet > type > global) ; à spécificité égale,
    la durée de conservation la PLUS COURTE l'emporte (la contrainte la plus
    stricte gagne), puis le plus petit id (déterministe). Renvoie la
    `PolitiqueRetention` retenue, ou ``None`` si aucune ne couvre le document.

    `politiques` permet de passer une liste pré-chargée (évite une requête par
    document quand on en balaie plusieurs).
    """
    if politiques is None:
        politiques = list(
            politiques_retention_for_company(document.company, actif_only=True))
    best = None
    for pol in politiques:
        if not _politique_couvre_document(pol, document):
            continue
        if best is None:
            best = pol
            continue
        if pol.scope_rank > best.scope_rank:
            best = pol
        elif pol.scope_rank == best.scope_rank:
            if pol.duree_conservation_jours < best.duree_conservation_jours:
                best = pol
            elif (pol.duree_conservation_jours == best.duree_conservation_jours
                  and pol.pk < best.pk):
                best = pol
    return best


def documents_echus(company, today=None):
    """GED22 — Documents ÉCHUS au regard de leur politique de rétention applicable.

    Pour chaque document de la société, on résout la politique de rétention
    ACTIVE la plus spécifique (`politique_applicable`) puis on compare l'ÂGE du
    document — calculé depuis sa date de création (`Document.created_at`) jusqu'à
    `today` — à la durée de conservation. Un document est échu quand son âge (en
    jours) DÉPASSE STRICTEMENT la durée de conservation de sa politique.

    L'échéance est purement CONSULTATIVE : cette fonction LIT et LISTE seulement
    — elle ne modifie ni ne supprime jamais aucun document (jamais destructif).

    `today` (date OU datetime) est INJECTABLE et propagé jusqu'au calcul d'âge ;
    par défaut on prend la date du jour (`timezone.localdate()`). Renvoie une
    liste de tuples ``(document, politique, jours_depasses)`` triée du plus en
    retard au moins en retard, bornée à la société.
    """
    import datetime

    from django.utils import timezone

    if today is None:
        today = timezone.localdate()
    elif isinstance(today, datetime.datetime):
        # datetime → date (on raisonne en jours pleins)
        today = today.date()

    politiques = list(
        politiques_retention_for_company(company, actif_only=True))
    if not politiques:
        return []

    documents = (Document.objects.filter(company=company)
                 .select_related('folder', 'folder__cabinet'))
    echus = []
    for document in documents:
        politique = politique_applicable(document, politiques=politiques)
        if politique is None:
            continue
        created = document.created_at
        if created is None:
            continue
        created_date = created.date() if hasattr(created, 'date') else created
        age_jours = (today - created_date).days
        depasses = age_jours - politique.duree_conservation_jours
        if depasses > 0:
            echus.append((document, politique, depasses))
    echus.sort(key=lambda item: (-item[2], item[0].pk))
    return echus
