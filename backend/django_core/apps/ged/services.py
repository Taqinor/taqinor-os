"""Écritures / orchestration de la GED.

Point d'entrée des écritures cross-app (CLAUDE.md). La société est TOUJOURS
fournie par l'appelant (résolue côté serveur depuis `request.user.company`) —
jamais lue d'un corps de requête. Réutilise les conventions de stockage de
`records.storage` (clé MinIO `file_key`) sans réimplémenter le stockage.
"""
import hashlib

from django.contrib.postgres.search import SearchVector
from django.db import transaction
from django.db.models import Value

from .models import Cabinet, Document, DocumentVersion, Folder


def update_search_vector(document):
    """GED11 — Recalcule le tsvector plein-texte d'un document.

    Le vecteur agrège le nom (poids A), la description + métadonnées (poids B)
    et le texte OCR (poids C, alimenté par GED12). Calculé en base via
    `SearchVector` (config 'french'). Idempotent — à rappeler après toute
    écriture qui change le contenu indexable.
    """
    meta = ''
    if isinstance(document.custom_data, dict):
        meta = ' '.join(str(v) for v in document.custom_data.values() if v)
    Document.objects.filter(pk=document.pk).update(
        search_vector=(
            SearchVector('nom', weight='A', config='french')
            + SearchVector(Value(document.description or ''),
                           weight='B', config='french')
            + SearchVector(Value(meta), weight='B', config='french')
            + SearchVector('texte_ocr', weight='C', config='french')
        )
    )


def set_ocr_text(document, texte):
    """GED12/GED11 — Pose le texte OCR d'un document et réindexe le tsvector.

    Sert de point d'entrée unique pour l'indexation OCR : on stocke le texte
    extrait, on rafraîchit la recherche plein-texte (GED11), puis on (ré)indexe
    l'embedding sémantique (GED12, no-op sans clé)."""
    Document.objects.filter(pk=document.pk).update(texte_ocr=texte or '')
    document.texte_ocr = texte or ''
    update_search_vector(document)
    index_embedding(document)
    # FG352 — (ré)indexe les fragments RAG/DocQA (no-op sans clé).
    index_document_chunks(document)
    return document


# ── GED12 — Index OCR + recherche sémantique (pgvector, KEY-GATED no-op) ──

def embedding_enabled():
    """True si la recherche sémantique est activée (clé d'embedding présente).

    KEY-GATED : sans `settings.GED_EMBEDDING_ENABLED` à vrai, tout est un no-op
    (aucun appel réseau, aucun coût) et la recherche sémantique retombe sur la
    recherche plein-texte GED11. Le founder active la fonctionnalité en posant
    le flag + la clé du provider dans l'environnement."""
    from django.conf import settings
    return bool(getattr(settings, 'GED_EMBEDDING_ENABLED', False))


def compute_embedding(text):
    """Calcule l'embedding d'un texte via le provider configuré, ou None.

    NO-OP par défaut : renvoie None tant que `embedding_enabled()` est faux —
    le squelette d'appel provider est isolé ici pour un futur branchement
    (Zhipu/OpenAI-compatible) sans toucher au reste du module. Un provider réel
    devra renvoyer une liste de `EMBEDDING_DIM` flottants."""
    if not text or not embedding_enabled():
        return None
    # Branchement provider à venir (clé-gated). Tant qu'aucun provider concret
    # n'est câblé, on reste no-op même flag activé — jamais d'appel fantôme.
    provider = None
    try:  # pragma: no cover - dépend d'un provider externe non câblé ici.
        from . import embedding_provider as provider  # noqa: F401
    except ImportError:
        provider = None
    if provider is None:
        return None
    vec = provider.embed(text)  # pragma: no cover
    return vec  # pragma: no cover


def index_embedding(document):
    """GED12 — (Ré)indexe l'embedding sémantique d'un document (no-op sans clé).

    Concatène nom + texte OCR, calcule l'embedding (no-op sans clé) et le stocke
    dans `Document.embedding`. Idempotent ; ne lève jamais (l'indexation ne doit
    pas casser une écriture documentaire). Renvoie True si un vecteur a été posé.
    """
    if not embedding_enabled():
        return False
    text = f'{document.nom}\n{document.texte_ocr or ""}'.strip()
    try:
        vec = compute_embedding(text)
    except Exception:  # pragma: no cover - robustesse : jamais bloquer l'écriture.
        vec = None
    if vec is None:
        return False
    Document.objects.filter(pk=document.pk).update(embedding=vec)
    document.embedding = vec
    return True


# ── FG352 — RAG / DocQA : indexation par fragments (pgvector, no-op sans clé) ──

# Paramètres de découpage par défaut (caractères). Un chevauchement préserve le
# contexte aux frontières de fragments. Modestes : un manuel reste lisible et le
# nombre de fragments par document reste raisonnable.
CHUNK_SIZE = 1000
CHUNK_OVERLAP = 150


def chunk_text(text, *, chunk_size=CHUNK_SIZE, chunk_overlap=CHUNK_OVERLAP):
    """FG352 — Découpe un texte en fragments chevauchants pour le RAG.

    Utilise `langchain-textsplitters` (RecursiveCharacterTextSplitter) quand il
    est disponible — il coupe en priorité sur les frontières naturelles
    (paragraphes, phrases) avant de tomber sur les caractères. Import gardé : si
    la dépendance n'est pas installée, on retombe sur un découpage fenêtré pur
    Python équivalent, pour que le code reste import-safe partout (CI sans clé).

    Renvoie une liste de fragments non vides (jamais None). Un texte vide donne
    une liste vide.
    """
    if not text or not str(text).strip():
        return []
    text = str(text)
    try:  # Dépendance optionnelle — import gardé (no-op-safe sans la lib).
        from langchain_text_splitters import RecursiveCharacterTextSplitter
        splitter = RecursiveCharacterTextSplitter(
            chunk_size=chunk_size, chunk_overlap=chunk_overlap)
        chunks = splitter.split_text(text)
    except Exception:  # pragma: no cover - chemin de repli sans la lib.
        # Repli pur Python : fenêtre glissante avec chevauchement.
        chunks = []
        step = max(1, chunk_size - chunk_overlap)
        for start in range(0, len(text), step):
            piece = text[start:start + chunk_size]
            if piece:
                chunks.append(piece)
    return [c.strip() for c in chunks if c and c.strip()]


def index_document_chunks(document):
    """FG352 — (Ré)indexe les fragments RAG d'un document (no-op sans clé).

    Découpe le texte du document (nom + texte OCR) en fragments, calcule un
    embedding par fragment (no-op sans clé) et les stocke dans `DocumentChunk`,
    dans le MÊME magasin pgvector que `Document.embedding` — pas un second
    magasin. Idempotent : remplace les fragments existants du document. Ne lève
    jamais (l'indexation ne doit pas casser une écriture documentaire).

    KEY-GATED : sans clé d'embedding, c'est un no-op total — on n'écrit aucun
    fragment et on renvoie 0. La company de chaque fragment est posée côté
    serveur (celle du document), jamais lue d'un corps de requête.

    Renvoie le nombre de fragments embeddés et stockés.
    """
    from .models import DocumentChunk
    if not embedding_enabled():
        return 0
    text = f'{document.nom}\n{document.texte_ocr or ""}'.strip()
    pieces = chunk_text(text)
    if not pieces:
        # Plus aucun contenu indexable : purge les anciens fragments.
        DocumentChunk.objects.filter(document=document).delete()
        return 0
    rows = []
    for idx, piece in enumerate(pieces):
        try:
            vec = compute_embedding(piece)
        except Exception:  # pragma: no cover - robustesse : jamais bloquer.
            vec = None
        if vec is None:
            continue
        rows.append(DocumentChunk(
            company=document.company, document=document,
            chunk_index=idx, texte=piece, embedding=vec))
    with transaction.atomic():
        DocumentChunk.objects.filter(document=document).delete()
        if rows:
            DocumentChunk.objects.bulk_create(rows)
    return len(rows)


def validate_coffre_owner(proprietaire, client):
    """GED8 — Un coffre porte EXACTEMENT un propriétaire (employé XOR client).

    Lève ValueError si aucun ou si les deux sont fournis. Sert de garde unique
    pour la création/mise à jour, côté service comme côté serializer.
    """
    has_user = proprietaire is not None
    has_client = client is not None
    if has_user and has_client:
        raise ValueError(
            "Un coffre-fort a un seul propriétaire : un employé OU un client.")
    if not has_user and not has_client:
        raise ValueError(
            "Un coffre-fort doit avoir un propriétaire (employé ou client).")


def compute_checksum(data):
    """SHA-256 hex d'un contenu binaire — sert à la déduplication."""
    if isinstance(data, str):
        data = data.encode('utf-8')
    return hashlib.sha256(data).hexdigest()


def _document_archive_legalement(document):
    """GED23 — True si un document est archivé légalement (write-once).

    Helper interne partagé par les gardes d'écriture (déplacement, verrou,
    transition de cycle de vie…). Lecture en base de l'existence d'un
    `ArchivageLegal` sur le document. Import paresseux pour éviter tout cycle."""
    from .models import ArchivageLegal
    if document.pk is None:
        return False
    return ArchivageLegal.objects.filter(document_id=document.pk).exists()


def validate_tag_parent(tag, new_parent):
    """GED9 — Garde anti-cycle / cross-société pour la taxonomie de tags.

    Refuse qu'un tag devienne son propre parent, qu'il descende sous l'un de ses
    descendants (cycle), ou qu'il pointe sur un parent d'une autre société. À
    appeler avant de poser `parent`. `new_parent` peut être None (tag racine).
    """
    if new_parent is None:
        return
    if tag is not None and new_parent.pk == tag.pk:
        raise ValueError("Un tag ne peut pas être son propre parent.")
    if tag is not None and tag.company_id is not None \
            and new_parent.company_id != tag.company_id:
        raise ValueError("Le parent doit appartenir à la même société.")
    if tag is not None and tag.pk is not None:
        # Empêche un cycle : le nouveau parent ne doit pas être un descendant.
        courant = new_parent
        seen = set()
        while courant is not None and courant.pk not in seen:
            if courant.pk == tag.pk:
                raise ValueError(
                    "Déplacement impossible : le parent est un descendant.")
            seen.add(courant.pk)
            courant = courant.parent


def assign_tag(document, tag, *, created_by=None):
    """GED9 — Applique un tag de la taxonomie à un document (idempotent).

    Le tag et le document doivent appartenir à la même société (jamais de fuite
    cross-société). Renvoie (assignment, created).
    """
    from .models import DocumentTag, DocumentTagAssignment  # noqa: F401
    if tag.company_id != document.company_id:
        raise ValueError("Le tag doit appartenir à la même société.")
    return DocumentTagAssignment.objects.get_or_create(
        document=document, tag=tag,
        defaults={'company': document.company, 'created_by': created_by})


def move_folder(folder, new_parent):
    """Déplace un dossier sous un nouveau parent et recalcule les chemins.

    Recalcule le chemin matérialisé du dossier ET de tout son sous-arbre — la
    contrainte de cohérence du chemin matérialisé. `new_parent` peut être None
    (dossier remis à la racine). Refuse un cycle (devenir son propre ancêtre).
    """
    if new_parent is not None:
        if new_parent.pk == folder.pk:
            raise ValueError("Un dossier ne peut pas être son propre parent.")
        # Empêche de déplacer un dossier sous l'un de ses descendants (cycle).
        if folder.path and new_parent.path.startswith(folder.path):
            raise ValueError(
                "Déplacement impossible : cible dans le sous-arbre du dossier.")
        if new_parent.cabinet_id != folder.cabinet_id:
            raise ValueError(
                "Le dossier cible doit appartenir au même cabinet.")
    with transaction.atomic():
        old_path = folder.path
        folder.parent = new_parent
        folder.save()  # recalcule folder.path via Folder.save()
        new_path = folder.path
        # Réécrit le préfixe de chemin de chaque descendant.
        if old_path and old_path != new_path:
            for desc in Folder.objects.filter(
                    company=folder.company, path__startswith=old_path
            ).exclude(pk=folder.pk):
                desc.path = new_path + desc.path[len(old_path):]
                desc.save(update_fields=['path'])
    return folder


def move_document(document, new_folder):
    """Déplace un document dans un autre dossier (même société).

    Le dossier cible DOIT appartenir à la même société que le document — sinon
    on refuse (jamais de fuite cross-société). La société du document n'est
    jamais modifiée (elle reste posée côté serveur). Renvoie le document.
    """
    if new_folder.company_id != document.company_id:
        raise ValueError(
            "Le dossier cible doit appartenir à la même société.")
    # GED23 — write-once : un document archivé légalement est figé (jamais
    # déplacé). On refuse en `ValueError` (→ 400 côté vue `deplacer`).
    if _document_archive_legalement(document):
        raise ValueError(
            "Document archivé à valeur probante (write-once) : il ne peut plus "
            "être déplacé.")
    if document.folder_id != new_folder.id:
        document.folder = new_folder
        document.save(update_fields=['folder', 'updated_at'])
    return document


def add_version(document, *, file_key, company, filename='', size=0, mime='',
                checksum='', uploaded_by=None, restored_from=None):
    """Ajoute une nouvelle version à un document (numéro auto-incrémenté).

    Le numéro de version est calculé côté serveur (dernière + 1) et la société
    est forcée à celle du document (jamais du corps de requête). `checksum`
    permet la déduplication : un appelant peut vérifier au préalable s'il
    existe déjà une version de même empreinte (voir `find_duplicate`).

    GED15 — `restored_from` : si cette version est le résultat d'une restauration,
    on passe ici la version source pour traçabilité (posé côté serveur dans
    `restore_version`, jamais lu du corps de requête).
    """
    with transaction.atomic():
        last = (DocumentVersion.objects
                .select_for_update()
                .filter(document=document)
                .order_by('-version')
                .first())
        next_version = (last.version + 1) if last else 1
        return DocumentVersion.objects.create(
            company=company,
            document=document,
            version=next_version,
            file_key=file_key,
            filename=filename,
            size=size,
            mime=mime,
            checksum=checksum,
            uploaded_by=uploaded_by,
            restored_from=restored_from,
        )


def restore_version(document, source_version, *, uploaded_by=None):
    """GED15 — Restaure un document à une version antérieure (non destructif).

    Crée une NOUVELLE version (numéro max + 1) dont le contenu (file_key,
    filename, size, mime, checksum) est copié depuis `source_version`, en
    traçant le lien via `restored_from`. L'historique est ENTIÈREMENT PRÉSERVÉ —
    aucune version n'est modifiée ou supprimée.

    La `source_version` doit appartenir au même document ET à la même société
    (validé ici côté serveur — jamais du corps de requête). La société de la
    nouvelle version est toujours celle du document.

    Renvoie la nouvelle version créée.
    """
    # Garde : la version source doit appartenir à ce document et cette société.
    if source_version.document_id != document.pk:
        raise ValueError("La version source n'appartient pas à ce document.")
    if source_version.company_id != document.company_id:
        raise ValueError(
            "La version source n'appartient pas à la même société.")
    return add_version(
        document,
        file_key=source_version.file_key,
        company=document.company,
        filename=source_version.filename,
        size=source_version.size,
        mime=source_version.mime,
        checksum=source_version.checksum,
        uploaded_by=uploaded_by,
        restored_from=source_version,
    )


def find_duplicate(company, checksum):
    """Première version d'une société portant ce checksum, ou None (dedup)."""
    if not checksum:
        return None
    return (DocumentVersion.objects
            .filter(company=company, checksum=checksum)
            .order_by('id')
            .first())


def create_document(*, company, folder, nom, description='', created_by=None,
                    custom_data=None):
    """Crée un document dans un dossier (société cohérente avec le dossier).

    `custom_data` (optionnel) permet de poser des métadonnées typées dès la
    création (ex. la trace de l'objet métier source pour un dépôt cross-app) —
    posées côté serveur, jamais lues d'un corps de requête.
    """
    if folder.company_id != getattr(company, 'id', company):
        raise ValueError("Le dossier doit appartenir à la même société.")
    return Document.objects.create(
        company=company, folder=folder, nom=nom,
        description=description, created_by=created_by,
        custom_data=custom_data if custom_data is not None else dict())


# ── Dépôt cross-app : enregistrer un fichier/des octets existants en GED ─────

# Clés réservées dans `Document.custom_data` qui tracent l'objet métier source
# d'un document déposé par une AUTRE app (ex. contrats). Sert d'ancre
# d'idempotence : un dépôt répété pour le même objet source retrouve le document
# déjà créé au lieu d'en dupliquer un. Ces clés vivent dans le JSONField additif
# `custom_data` — on n'invente aucun nouveau schéma de FK.
SOURCE_TYPE_KEY = 'source_type'
SOURCE_ID_KEY = 'source_id'


def ensure_cabinet(company, nom):
    """Retourne (ou crée) le cabinet `nom` d'une société (idempotent).

    Sert l'auto-provisionnement d'un espace documentaire pour un dépôt cross-app
    (ex. un cabinet « Contrats »). La société est posée côté serveur."""
    cabinet, _ = Cabinet.objects.get_or_create(company=company, nom=nom)
    return cabinet


def ensure_root_folder(company, *, cabinet, nom):
    """Retourne (ou crée) un dossier racine `nom` d'un cabinet (idempotent).

    Cherche un dossier RACINE (sans parent) de ce nom dans le cabinet ; sinon le
    crée. Société/cabinet posés côté serveur. Sert l'auto-provisionnement d'un
    dossier de classement pour un dépôt cross-app."""
    folder = Folder.objects.filter(
        company=company, cabinet=cabinet, parent__isnull=True, nom=nom
    ).first()
    if folder is None:
        folder = Folder.objects.create(
            company=company, cabinet=cabinet, nom=nom)
    return folder


def find_document_by_source(company, *, source_type, source_id):
    """Document déjà déposé pour cet objet métier source (idempotence), ou None.

    Borné à la société et résolu DEPUIS la trace `custom_data` (`source_type` +
    `source_id`) — jamais d'un corps de requête. Permet à un appelant cross-app
    de ne pas re-déposer (dédupliquer) le même objet source."""
    if source_type is None or source_id is None:
        return None
    return (Document.objects
            .filter(company=company,
                    custom_data__contains={
                        SOURCE_TYPE_KEY: source_type,
                        SOURCE_ID_KEY: source_id,
                    })
            .order_by('id')
            .first())


def _store_bytes(data, *, mime='application/pdf'):
    """Téléverse des octets bruts dans le stockage objet et renvoie (clé, méta).

    RÉUTILISE les conventions de `records.storage` (bucket
    `settings.MINIO_BUCKET_UPLOADS`, clé `attachments/<uuid>.<ext>`,
    `ensure_uploads_bucket`) — on ne réimplémente PAS de couche de stockage, on
    reprend exactement le même client MinIO partagé. Import paresseux pour rester
    import-safe (CI/dev sans MinIO) et éviter tout cycle d'import.

    Renvoie `(file_key, {'filename', 'size', 'mime'})`.
    """
    import io
    import uuid

    from django.conf import settings

    from apps.ventes.utils.minio_client import (
        ensure_uploads_bucket, get_minio_client,
    )

    ext = 'pdf' if 'pdf' in (mime or '') else 'bin'
    key = f'attachments/{uuid.uuid4().hex}.{ext}'
    client = get_minio_client()
    ensure_uploads_bucket()
    client.upload_fileobj(
        io.BytesIO(data), settings.MINIO_BUCKET_UPLOADS, key,
        ExtraArgs={'ContentType': mime or 'application/octet-stream'})
    return key, {'filename': f'{key.rsplit("/", 1)[-1]}',
                 'size': len(data), 'mime': mime or ''}


def deposit_document(*, company, nom, source_type, source_id,
                     file_key='', filename='', size=0, mime='', checksum='',
                     contenu_bytes=None, description='', cabinet_nom='Contrats',
                     folder_nom='Contrats', created_by=None):
    """Enregistre un fichier/des octets EXISTANTS comme document GED (cross-app).

    Point d'entrée d'ÉCRITURE pour qu'une AUTRE app (ex. `contrats`) dépose un
    document déjà produit (un PDF signé, un instantané de version…) dans le
    référentiel central, SANS importer les modèles GED. On RÉUTILISE les
    primitives existantes (`create_document`, `add_version`) et les conventions
    de stockage `records.storage` — on ne réimplémente ni le stockage ni le
    versionnage.

    Multi-tenant : `company` est posée CÔTÉ SERVEUR par l'appelant (jamais lue
    d'un corps de requête) ; le cabinet, le dossier, le document et sa version
    héritent tous de cette société.

    Source du contenu (au moins l'un) :
      - `file_key` : la clé d'un objet déjà stocké en MinIO (records.storage).
      - `contenu_bytes` : des octets bruts téléversés ici via `_store_bytes`
        (mêmes conventions de stockage objet que `records.storage` : bucket
        erp-uploads, clé `attachments/<uuid>.ext`). Utilisé quand l'appelant
        n'a qu'un rendu en mémoire (ex. un PDF de contrat).
      Si AUCUN n'est fourni, le document est tout de même créé avec une version
      « pointeur vide » (file_key='') — utile pour tracer un instantané textuel
      dont seul le contenu vit dans l'app source.

    IDEMPOTENCE : `source_type`/`source_id` identifient l'objet métier source
    (ex. 'contrats.versioncontrat' + pk). Un dépôt répété pour le MÊME objet
    source ne crée JAMAIS un second document : on retrouve et on renvoie le
    document déjà déposé (pas de doublon GED).

    Renvoie `(document, created)` : le `Document` GED et un booléen indiquant
    s'il vient d'être créé (False = déjà présent, dépôt idempotent).
    """
    # Idempotence : déjà déposé pour cet objet source ? On renvoie l'existant.
    existant = find_document_by_source(
        company, source_type=source_type, source_id=source_id)
    if existant is not None:
        return existant, False

    # Si l'appelant fournit des octets bruts (sans clé), on les stocke via le
    # MÊME stockage objet que `records.storage` (bucket erp-uploads, clé
    # `attachments/<uuid>.ext`) — on RÉUTILISE les conventions de stockage sans
    # réimplémenter de couche. Import paresseux pour rester import-safe sans
    # MinIO et éviter tout cycle.
    if not file_key and contenu_bytes is not None:
        file_key, store_meta = _store_bytes(
            contenu_bytes, mime=mime or 'application/pdf')
        filename = filename or store_meta.get('filename', '')
        size = size or store_meta.get('size', 0)
        mime = mime or store_meta.get('mime', '')
        checksum = checksum or compute_checksum(contenu_bytes)

    cabinet = ensure_cabinet(company, cabinet_nom)
    folder = ensure_root_folder(company, cabinet=cabinet, nom=folder_nom)
    document = create_document(
        company=company, folder=folder, nom=nom, description=description,
        created_by=created_by,
        custom_data={SOURCE_TYPE_KEY: source_type, SOURCE_ID_KEY: source_id})
    # Première version : pointe vers le binaire (ou un pointeur vide si l'app
    # source ne gère qu'un contenu textuel). Numéro auto (add_version, max+1).
    add_version(
        document, file_key=file_key or '', company=company,
        filename=filename or '', size=size or 0, mime=mime or '',
        checksum=checksum or '', uploaded_by=created_by)
    return document, True


# ── GED16 — Check-out / check-in (verrouillage optimiste) ──────────

def checkout_document(document, user):
    """GED16 — Pose un verrou sur un document (check-out).

    Si le document est LIBRE (locked_by == None), pose locked_by=user et
    locked_at=now dans une transaction sérialisée (select_for_update) pour
    éviter les doubles check-out simultanés.

    Si le document est déjà verrouillé PAR UN AUTRE utilisateur, lève
    PermissionError (→ 409 dans la vue). Si le même utilisateur re-check-out
    son propre document, l'opération est idempotente.

    Multi-tenant : vérifie que user.company_id == document.company_id.
    """
    from django.utils import timezone
    if document.company_id != user.company_id:
        raise PermissionError("Document inaccessible.")
    # GED23 — write-once : on n'extrait pas (check-out) un document archivé
    # légalement — il est figé. Refus en `PermissionError` (→ 409 côté vue).
    if _document_archive_legalement(document):
        raise PermissionError(
            "Document archivé à valeur probante (write-once) : il est immuable "
            "et ne peut plus être extrait pour modification.")
    with transaction.atomic():
        doc = Document.objects.select_for_update().get(pk=document.pk)
        if doc.locked_by_id is not None and doc.locked_by_id != user.pk:
            raise PermissionError(
                "Le document est déjà extrait par un autre utilisateur.")
        if doc.locked_by_id == user.pk:
            # Déjà verrouillé par ce même utilisateur — idempotent.
            return doc
        doc.locked_by = user
        doc.locked_at = timezone.now()
        doc.save(update_fields=['locked_by', 'locked_at', 'updated_at'])
    document.locked_by = doc.locked_by
    document.locked_at = doc.locked_at
    return doc


def checkin_document(document, user):
    """GED16 — Libère le verrou d'un document (check-in).

    Seul le détenteur du verrou OU un administrateur peut libérer le verrou.
    Si le document est déjà libre, l'opération est silencieusement idempotente.

    Multi-tenant : vérifie que user.company_id == document.company_id.
    """
    if document.company_id != user.company_id:
        raise PermissionError("Document inaccessible.")
    with transaction.atomic():
        doc = Document.objects.select_for_update().get(pk=document.pk)
        if doc.locked_by_id is None:
            # Déjà libre — idempotent.
            return doc
        is_locker = doc.locked_by_id == user.pk
        is_admin = getattr(user, 'is_admin_role', False) or user.is_superuser
        if not is_locker and not is_admin:
            raise PermissionError(
                "Seul le détenteur du verrou ou un administrateur peut "
                "libérer ce document.")
        doc.locked_by = None
        doc.locked_at = None
        doc.save(update_fields=['locked_by', 'locked_at', 'updated_at'])
    document.locked_by = None
    document.locked_at = None
    return doc


def assert_not_locked_by_other(document, user):
    """GED16 — Garde : rejette si document verrouillé par un autre utilisateur.

    À appeler avant add_version ou toute autre écriture sur le contenu du
    document. Ne lève rien si le document est libre OU si c'est le détenteur
    du verrou qui écrit.
    """
    if document.locked_by_id is not None and document.locked_by_id != user.pk:
        raise PermissionError(
            "Le document est extrait par un autre utilisateur. "
            "Attendez le check-in avant de téléverser une nouvelle version."
        )


def change_lifecycle_status(document, target_status, *, user):
    """GED17 — Fait avancer un document dans son cycle de vie (statut LOCAL).

    Garde la machine à états `LIFECYCLE_TRANSITIONS` : seule une transition
    autorisée depuis le statut COURANT vers `target_status` est appliquée ;
    toute autre lève `ValueError` (→ 400 dans la vue). Ce cycle de vie est
    DISTINCT du funnel commercial `STAGES.py` (rule #2) — on ne l'importe pas.

    Multi-tenant : refuse si `user.company_id != document.company_id`. La
    mise à jour est sérialisée (`select_for_update`) pour éviter deux
    transitions concurrentes depuis le même statut.

    Renvoie le `Document` rafraîchi avec son nouveau statut.
    """
    from .models import (
        Document, LIFECYCLE_CHOICES, LIFECYCLE_TRANSITIONS,
    )
    if document.company_id != user.company_id:
        raise PermissionError("Document inaccessible.")
    # GED23 — write-once : un document archivé légalement est figé — son cycle
    # de vie ne bouge plus. Refus en `PermissionError` (→ 403 côté vue).
    if _document_archive_legalement(document):
        raise PermissionError(
            "Document archivé à valeur probante (write-once) : son cycle de "
            "vie est figé.")
    valides = {code for code, _ in LIFECYCLE_CHOICES}
    if target_status not in valides:
        raise ValueError(
            f"Statut « {target_status} » inconnu. "
            f"Statuts valides : {', '.join(sorted(valides))}."
        )
    with transaction.atomic():
        doc = Document.objects.select_for_update().get(pk=document.pk)
        if target_status == doc.statut:
            # Aucune transition réelle — on n'autorise PAS un no-op silencieux :
            # avancer vers le statut courant n'est pas une transition valide.
            raise ValueError(
                f"Le document est déjà au statut « {doc.statut} »."
            )
        autorisees = LIFECYCLE_TRANSITIONS.get(doc.statut, set())
        if target_status not in autorisees:
            attendus = ', '.join(sorted(autorisees)) or 'aucun'
            raise ValueError(
                f"Transition refusée : « {doc.statut} » → "
                f"« {target_status} » n'est pas permise "
                f"(transitions possibles : {attendus})."
            )
        doc.statut = target_status
        doc.save(update_fields=['statut', 'updated_at'])
    document.statut = doc.statut
    return doc


# ── GED18 — Workflow d'approbation / revue documentaire ─────────────

def request_review(document, *, user, approbateur=None, commentaire=''):
    """GED18 — Lance une demande d'approbation/revue sur un document.

    Crée une `DemandeApprobation` « en_attente » et — si le document n'est pas
    déjà en revue — le fait avancer « brouillon → revue » via la machine à états
    GED17 (`change_lifecycle_status`, jamais dupliquée ici). Le `demandeur` et la
    `company` sont posés côté serveur (jamais lus du corps de requête).

    Refuse (`ValueError`) s'il existe déjà une demande EN ATTENTE pour ce
    document (une seule revue active à la fois) ou si `approbateur` appartient à
    une autre société. Multi-tenant : `PermissionError` si l'utilisateur n'est
    pas de la société du document.

    Renvoie la `DemandeApprobation` créée.
    """
    from .models import (
        APPROBATION_EN_ATTENTE, DemandeApprobation, LIFECYCLE_BROUILLON,
        LIFECYCLE_REVUE,
    )
    if document.company_id != user.company_id:
        raise PermissionError("Document inaccessible.")
    if approbateur is not None and approbateur.company_id != document.company_id:
        raise ValueError("L'approbateur doit appartenir à la même société.")
    with transaction.atomic():
        doc = Document.objects.select_for_update().get(pk=document.pk)
        existe = (DemandeApprobation.objects
                  .filter(document=doc, statut=APPROBATION_EN_ATTENTE)
                  .exists())
        if existe:
            raise ValueError(
                "Une demande d'approbation est déjà en attente pour ce "
                "document.")
        demande = DemandeApprobation.objects.create(
            company=doc.company,
            document=doc,
            demandeur=user,
            approbateur=approbateur,
            statut=APPROBATION_EN_ATTENTE,
            commentaire=commentaire or '',
        )
        # Met le document « en revue » s'il est encore brouillon (transition
        # GED17 réutilisée — on ne duplique pas la machine à états).
        if doc.statut == LIFECYCLE_BROUILLON:
            change_lifecycle_status(doc, LIFECYCLE_REVUE, user=user)
    document.statut = doc.statut
    return demande


def _decide_demande(demande, *, user, statut_cible, commentaire=''):
    """GED18 — Tranche une demande d'approbation (approbation OU rejet).

    Garde commune à `approve_demande`/`reject_demande` : seule une demande
    ENCORE EN ATTENTE peut être décidée (sinon `ValueError` — pas de double
    décision). L'`approbateur`, le statut, l'horodatage `decision_le` et le
    commentaire sont posés côté serveur. Multi-tenant : `PermissionError` si
    l'utilisateur n'est pas de la société de la demande.

    Renvoie la `DemandeApprobation` rafraîchie.
    """
    from django.utils import timezone
    from .models import APPROBATION_EN_ATTENTE, DemandeApprobation
    if demande.company_id != user.company_id:
        raise PermissionError("Demande inaccessible.")
    with transaction.atomic():
        dem = (DemandeApprobation.objects
               .select_for_update()
               .get(pk=demande.pk))
        if dem.statut != APPROBATION_EN_ATTENTE:
            raise ValueError(
                f"La demande est déjà « {dem.statut} » — décision impossible.")
        dem.statut = statut_cible
        dem.approbateur = user
        dem.decision_le = timezone.now()
        if commentaire:
            dem.commentaire = commentaire
        dem.save(update_fields=[
            'statut', 'approbateur', 'decision_le', 'commentaire',
            'updated_at'])
    demande.statut = dem.statut
    demande.approbateur = dem.approbateur
    demande.decision_le = dem.decision_le
    demande.commentaire = dem.commentaire
    return dem


def approve_demande(demande, *, user, commentaire=''):
    """GED18 — Approuve une demande de revue et fait avancer le document.

    Tranche la demande (« approuve », horodatage + approbateur côté serveur),
    puis — si le document est « en revue » — le fait avancer « revue →
    approuvé » via la machine à états GED17 (`change_lifecycle_status`, jamais
    dupliquée). L'avancement du cycle de vie n'est tenté QUE depuis « revue » :
    un document à un autre statut reste inchangé (la décision est tout de même
    enregistrée). Renvoie la `DemandeApprobation` décidée.
    """
    from .models import (
        APPROBATION_APPROUVE, LIFECYCLE_APPROUVE, LIFECYCLE_REVUE,
    )
    dem = _decide_demande(
        demande, user=user, statut_cible=APPROBATION_APPROUVE,
        commentaire=commentaire)
    document = dem.document
    if document.statut == LIFECYCLE_REVUE:
        change_lifecycle_status(document, LIFECYCLE_APPROUVE, user=user)
    return dem


def reject_demande(demande, *, user, commentaire=''):
    """GED18 — Rejette une demande de revue et renvoie le document en correction.

    Tranche la demande (« rejete », horodatage + approbateur côté serveur),
    puis — si le document est « en revue » — le renvoie « revue → brouillon »
    via la machine à états GED17 (`change_lifecycle_status`, jamais dupliquée),
    pour qu'il reparte en correction. Un document à un autre statut reste
    inchangé. Renvoie la `DemandeApprobation` décidée.
    """
    from .models import (
        APPROBATION_REJETE, LIFECYCLE_BROUILLON, LIFECYCLE_REVUE,
    )
    dem = _decide_demande(
        demande, user=user, statut_cible=APPROBATION_REJETE,
        commentaire=commentaire)
    document = dem.document
    if document.statut == LIFECYCLE_REVUE:
        change_lifecycle_status(document, LIFECYCLE_BROUILLON, user=user)
    return dem


# ── GED20 — Partage public d'un document par lien tokenisé ──────────

def create_partage(*, document, company, created_by=None, expires_at=None,
                   password=None, quota_max=None, watermark=False):
    """GED20 — Crée un partage public tokenisé pour un document (côté gestion).

    `company` est posée côté serveur et doit être celle du document (jamais lue
    du corps de requête). Le `token` long/imprévisible est généré par le défaut
    du modèle. Le mot de passe (optionnel) est HACHÉ via `set_password` — jamais
    stocké en clair. `expires_at`/`quota_max` sont optionnels (NULL = pas de
    limite). `watermark` (GED21) force le filigrane sur ce lien public. Renvoie
    le `PartageGed` créé.
    """
    from .models import PartageGed
    if document.company_id != getattr(company, 'id', company):
        raise ValueError("Le document doit appartenir à la même société.")
    partage = PartageGed(
        company=company,
        document=document,
        expires_at=expires_at,
        quota_max=quota_max,
        watermark=watermark,
        created_by=created_by,
    )
    partage.set_password(password)
    partage.save()
    return partage


def revoke_partage(partage):
    """GED20 — Révoque un partage (kill-switch : `actif=False`).

    Idempotent : un partage déjà révoqué reste révoqué. Après révocation,
    l'endpoint public renvoie 404 (lien mort) sans fuite."""
    if partage.actif:
        partage.actif = False
        partage.save(update_fields=['actif', 'updated_at'])
    return partage


# Sentinelles de résultat pour la résolution publique (le SEUL chemin d'accès
# public au document). Chaque cas mappe vers un code HTTP côté endpoint.
PARTAGE_OK = 'ok'
PARTAGE_INTROUVABLE = 'introuvable'        # jeton inconnu ou révoqué → 404
PARTAGE_EXPIRE = 'expire'                  # expiré ou quota épuisé → 410
PARTAGE_MDP_REQUIS = 'mot_de_passe_requis'  # mot de passe manquant/erroné → 403


def resolve_partage_public(token, *, password=None):
    """GED20 — Résout un partage public DEPUIS le seul jeton (aucune identité).

    C'est le cœur sécurité de l'accès public : on ne fait JAMAIS confiance à une
    société/identité venue de la requête — tout est résolu à partir du `token`
    (qui ne référence qu'un seul document d'une seule société). Renvoie un tuple
    `(statut, partage_ou_None)` où `statut` est l'une des sentinelles :

      - PARTAGE_INTROUVABLE : jeton inconnu OU partage révoqué (actif=False).
        → 404, sans distinguer les deux (pas de fuite « ce jeton existe »).
      - PARTAGE_EXPIRE       : partage expiré OU quota de téléchargements épuisé.
        → 410 Gone.
      - PARTAGE_MDP_REQUIS   : un mot de passe protège le partage et le mot de
        passe fourni est manquant ou erroné. → 403.
      - PARTAGE_OK           : accès autorisé, `partage` est servable.

    Note : un partage révoqué est traité comme INTROUVABLE (404) — révoquer doit
    « faire disparaître » le lien, pas révéler qu'il a existé.
    """
    from .models import PartageGed
    partage = (PartageGed.objects
               .select_related('document', 'company')
               .filter(token=token)
               .first())
    # Jeton inconnu OU partage révoqué → 404 indistinct (pas de fuite).
    if partage is None or not partage.actif:
        return PARTAGE_INTROUVABLE, None
    # Expiré ou quota épuisé → 410 Gone.
    if partage.is_expired or partage.quota_exhausted:
        return PARTAGE_EXPIRE, partage
    # Mot de passe (le cas échéant) — 403 si manquant/erroné.
    if partage.has_password and not partage.check_password(password):
        return PARTAGE_MDP_REQUIS, partage
    return PARTAGE_OK, partage


def consume_partage_download(partage):
    """GED20 — Incrémente atomiquement le compteur de téléchargements.

    Race-safe : incrément via F-expression + filtre conditionnel sur le quota
    (un GET concurrent ne peut pas dépasser `quota_max`). Renvoie True si le
    téléchargement a été comptabilisé, False si le quota venait d'être épuisé
    par un accès concurrent (l'appelant doit alors renvoyer 410 et NE PAS
    servir le document).

    `quota_max=None` → quota illimité : on incrémente toujours sans condition.
    """
    from django.db.models import F
    from .models import PartageGed
    if partage.quota_max is None:
        PartageGed.objects.filter(pk=partage.pk).update(
            telechargements=F('telechargements') + 1)
        partage.refresh_from_db(fields=['telechargements'])
        return True
    # Incrément CONDITIONNEL : ne passe que si le quota n'est pas déjà atteint.
    # Sous concurrence, exactement `quota_max` GET réussissent l'update.
    updated = PartageGed.objects.filter(
        pk=partage.pk, telechargements__lt=partage.quota_max
    ).update(telechargements=F('telechargements') + 1)
    if not updated:
        return False
    partage.refresh_from_db(fields=['telechargements'])
    return True


# ── GED21 — Filigrane & contrôle de diffusion ───────────────────────────────

# Types de contenu que le filigrane sait traiter. Tout autre type est renvoyé
# tel quel (jamais d'erreur) — le filigrane est best-effort, jamais bloquant.
_WATERMARK_PDF_MIMES = {'application/pdf'}
_WATERMARK_IMAGE_MIMES = {
    'image/png', 'image/jpeg', 'image/jpg', 'image/webp', 'image/gif',
}


def _watermark_pdf(file_bytes, text):
    """GED21 — Filigrane diagonal répété sur chaque page d'un PDF.

    Utilise PyMuPDF (`fitz`) quand il est disponible — import GARDÉ et
    PARESSEUX : si la lib n'est pas installée (elle n'est PAS une dépendance
    dure du backend), on dégrade proprement en renvoyant le PDF d'origine. Ne
    lève jamais : tout échec retombe sur l'original (best-effort).

    Renvoie `(out_bytes, watermarked)` où `watermarked` est False si la lib est
    absente ou si le rendu a échoué (octets inchangés).
    """
    try:  # Dépendance optionnelle — import paresseux (no-op-safe sans la lib).
        import fitz  # PyMuPDF
    except Exception:  # pragma: no cover - chemin de repli sans la lib.
        return file_bytes, False
    try:
        doc = fitz.open(stream=file_bytes, filetype='pdf')
        try:
            for page in doc:
                rect = page.rect
                # Filigrane diagonal centré, gris translucide, répété en bas.
                page.insert_textbox(
                    rect,
                    text,
                    fontsize=28,
                    color=(0.5, 0.5, 0.5),
                    rotate=45,
                    align=fitz.TEXT_ALIGN_CENTER,
                    overlay=True,
                )
            out = doc.tobytes()
        finally:
            doc.close()
        return out, True
    except Exception:  # pragma: no cover - robustesse : jamais bloquer.
        return file_bytes, False


def _watermark_image(file_bytes, text):
    """GED21 — Incruste un filigrane texte translucide sur une image.

    Utilise Pillow (déjà épinglé dans requirements) via un import PARESSEUX et
    GARDÉ : si Pillow venait à manquer, on dégrade en renvoyant l'image
    d'origine. Ne lève jamais.

    Renvoie `(out_bytes, watermarked)`.
    """
    try:  # Import paresseux et gardé — Pillow présent, mais on reste robuste.
        from PIL import Image, ImageDraw, ImageFont
    except Exception:  # pragma: no cover - chemin de repli sans la lib.
        return file_bytes, False
    try:
        import io
        src = Image.open(io.BytesIO(file_bytes)).convert('RGBA')
        overlay = Image.new('RGBA', src.size, (0, 0, 0, 0))
        draw = ImageDraw.Draw(overlay)
        try:
            font = ImageFont.load_default()
        except Exception:  # pragma: no cover - police par défaut indisponible.
            font = None
        # Tuile le texte en diagonale sur toute la surface (gris translucide).
        step_x = max(160, src.width // 3)
        step_y = max(90, src.height // 4)
        for y in range(0, src.height + step_y, step_y):
            for x in range(0, src.width + step_x, step_x):
                draw.text((x, y), text, fill=(128, 128, 128, 110), font=font)
        watermarked = Image.alpha_composite(src, overlay)
        out = io.BytesIO()
        # On réémet en PNG : préserve l'alpha du filigrane, sans dépendance
        # supplémentaire (toujours supporté par Pillow).
        watermarked.save(out, format='PNG')
        return out.getvalue(), True
    except Exception:  # pragma: no cover - robustesse : jamais bloquer.
        return file_bytes, False


def apply_watermark(file_bytes, content_type, text):
    """GED21 — Applique un filigrane texte sur un contenu diffusé (best-effort).

    Point d'entrée unique du contrôle de diffusion : superpose un texte de
    confidentialité (ex. « CONFIDENTIEL — {société} — {utilisateur/date} ») sur
    les PDF (via PyMuPDF) et les images (via Pillow). Le filigrane est un RENDU
    À LA VOLÉE — il ne modifie JAMAIS le binaire stocké (MinIO/base) ni aucun
    statut documentaire ; il ne s'applique qu'au flux servi.

    SÉCURITÉ DÉPENDANCES : les libs sont importées PARESSEUSEMENT à l'intérieur
    des helpers. Si une lib est absente (PyMuPDF n'est PAS une dépendance dure)
    ou si le rendu échoue, on DÉGRADE proprement en renvoyant les octets
    d'origine + `watermarked=False` — aucune exception, aucun crash, aucun
    rebuild obligatoire. Un type non pris en charge (texte, zip…) est de même
    renvoyé tel quel.

    Renvoie un tuple `(out_bytes, watermarked)` :
      - `out_bytes`     : les octets à servir (filigranés ou identiques).
      - `watermarked`   : True seulement si un filigrane a effectivement été
        appliqué (utile pour ajuster le Content-Type côté appelant).

    Le contenu vide ou un texte vide laissent les octets inchangés.
    """
    if not file_bytes or not text:
        return file_bytes, False
    ct = (content_type or '').split(';')[0].strip().lower()
    if ct in _WATERMARK_PDF_MIMES:
        return _watermark_pdf(file_bytes, text)
    if ct in _WATERMARK_IMAGE_MIMES:
        return _watermark_image(file_bytes, text)
    # Type non filigranable (texte, archive, octet-stream…) → inchangé.
    return file_bytes, False


def watermark_label(*, company=None, user=None):
    """GED21 — Construit l'étiquette de filigrane de confidentialité.

    Format : « CONFIDENTIEL — {société} — {acteur} — {date} ». Tout segment
    absent est omis proprement. La société/l'utilisateur viennent TOUJOURS du
    serveur (jamais d'un corps de requête) — l'appelant les résout depuis le
    document partagé ou `request.user`.
    """
    from django.utils import timezone
    parts = ['CONFIDENTIEL']
    co_nom = getattr(company, 'nom', None)
    if co_nom:
        parts.append(str(co_nom))
    actor = None
    if user is not None:
        actor = (getattr(user, 'username', None)
                 or getattr(user, 'email', None))
    if actor:
        parts.append(str(actor))
    parts.append(timezone.now().strftime('%Y-%m-%d'))
    return ' — '.join(parts)


# ── GED23 — Archivage légal à valeur probante (write-once / object-lock) ─────

def _version_integrity_hash(version):
    """GED23 — Condensat SHA-256 (hex) du contenu d'une version, ou ''.

    Preuve d'intégrité à valeur probante. On PRIVILÉGIE un recalcul depuis le
    contenu réellement stocké (`records.storage.fetch_attachment`) — l'empreinte
    la plus fiable. Si le contenu n'est pas récupérable (stockage indisponible),
    on retombe sur le `checksum` déjà figé sur la version (lui-même un SHA-256).
    Best-effort : ne lève jamais — renvoie '' si rien n'est exploitable."""
    if version is None:
        return ''
    # 1) Recalcul depuis le contenu stocké (import paresseux de la couche
    #    storage partagée — on ne réimplémente pas le stockage objet).
    try:
        from apps.records.storage import fetch_attachment
        data, err = fetch_attachment(version.file_key)
        if not err and data:
            return compute_checksum(data)
    except Exception:
        pass
    # 2) Repli : le checksum déjà enregistré sur la version (SHA-256 hex).
    return version.checksum or ''


def _try_set_object_lock(version, retain_until):
    """GED23 — Pose un verrou objet (MinIO/S3 Object-Lock) — BEST-EFFORT.

    BONUS purement consolidant : l'immuabilité APPLICATIVE (write-once posée
    dans les modèles + services) est LA garantie ; ce verrou n'est qu'un
    renfort. Import PARESSEUX du client MinIO (mêmes conventions que
    `records.storage` — aucune nouvelle dépendance) puis `put_object_retention`.

    DÉGRADE PROPREMENT : si le backend ne supporte pas l'object-lock (MinIO sans
    bucket WORM, opération non implémentée…), ou si le client est absent, ou si
    quoi que ce soit échoue, on renvoie ``False`` SANS lever — l'archivage
    légal reste valide grâce à l'immuabilité applicative.

    Renvoie ``True`` seulement si le verrou a effectivement été posé.
    """
    if version is None or not version.file_key or retain_until is None:
        return False
    try:
        import datetime as _dt

        from django.conf import settings

        from apps.ventes.utils.minio_client import get_minio_client

        client = get_minio_client()
        # boto3 attend un datetime tz-aware pour RetainUntilDate.
        if isinstance(retain_until, _dt.datetime):
            until_dt = retain_until
        else:
            until_dt = _dt.datetime.combine(retain_until, _dt.time.min)
        if until_dt.tzinfo is None:
            until_dt = until_dt.replace(tzinfo=_dt.timezone.utc)
        client.put_object_retention(
            Bucket=settings.MINIO_BUCKET_UPLOADS,
            Key=version.file_key,
            Retention={'Mode': 'COMPLIANCE', 'RetainUntilDate': until_dt},
        )
        return True
    except Exception:
        # Object-lock non supporté / indisponible → on dégrade en silence.
        return False


def archiver_legalement(document, *, user, motif='', retain_until=None):
    """GED23 — Archive un document à VALEUR PROBANTE (write-once / object-lock).

    Pose un `ArchivageLegal` sur le document, ce qui le rend (et toutes ses
    versions) IMMUABLE — WRITE-ONCE : aucune modification ni suppression
    ultérieure (gardes au niveau modèle + service). On fige le `hash_integrite`
    (SHA-256 du contenu de la version courante) comme preuve d'intégrité, et —
    en BONUS best-effort — on tente de poser un verrou objet (object-lock
    retain-until) côté stockage SI le backend le supporte (sinon on dégrade
    proprement : l'immuabilité applicative reste LA garantie).

    Multi-tenant : `company` et `archive_par` sont posés CÔTÉ SERVEUR (jamais
    lus du corps de requête). `PermissionError` si l'utilisateur n'est pas de la
    société du document. Idempotence : un document déjà archivé légalement lève
    `ValueError` (un archivage est unique et définitif — write-once).

    `retain_until` (date OU datetime, OPTIONNEL) est la date de rétention du
    verrou objet — propagée jusqu'à la pose best-effort du verrou.

    Renvoie l'`ArchivageLegal` créé.
    """
    from .models import ArchivageLegal, DocumentVersion

    if document.company_id != getattr(user, 'company_id', None):
        raise PermissionError("Document inaccessible.")
    # Write-once : un document n'est archivé légalement qu'une seule fois.
    if ArchivageLegal.objects.filter(document=document).exists():
        raise ValueError("Ce document est déjà archivé légalement.")
    # Version courante figée (la plus récente) — sert au hash + à l'object-lock.
    version = (DocumentVersion.objects
               .filter(document=document)
               .order_by('-version')
               .first())
    hash_integrite = _version_integrity_hash(version)
    # Normalise retain_until → date (le champ modèle est une DateField).
    retain_date = None
    if retain_until is not None:
        import datetime as _dt
        retain_date = (retain_until.date()
                       if isinstance(retain_until, _dt.datetime)
                       else retain_until)
    # BONUS best-effort : pose l'object-lock AVANT de créer la trace, pour
    # refléter fidèlement s'il a réussi (dégrade en silence sinon).
    lock_applique = _try_set_object_lock(version, retain_date)
    with transaction.atomic():
        # Re-vérifie sous transaction (la contrainte d'unicité protège aussi en
        # base, mais on renvoie une erreur métier propre en cas de course).
        if ArchivageLegal.objects.filter(document=document).exists():
            raise ValueError("Ce document est déjà archivé légalement.")
        archivage = ArchivageLegal.objects.create(
            company=document.company,
            document=document,
            version=version,
            archive_par=user,
            motif=(motif or '').strip(),
            hash_integrite=hash_integrite,
            object_lock_retain_until=retain_date,
            object_lock_applique=lock_applique,
        )
    return archivage


def assert_not_archive_legalement(document):
    """GED23 — Garde : rejette toute écriture si le document est archivé (WORM).

    À appeler côté service avant toute écriture (ajout de version, changement de
    statut, déplacement, verrouillage…) sur un document. La garde au niveau
    modèle (`save`/`delete`) est le filet de sécurité ultime ; cette fonction
    permet de refuser TÔT avec un message clair (→ 403 dans la vue). Lève
    `ArchivageLegalError` si le document est archivé légalement."""
    from .models import ARCHIVE_LEGALE_MESSAGE, ArchivageLegalError
    if _document_archive_legalement(document):
        raise ArchivageLegalError(ARCHIVE_LEGALE_MESSAGE)


# ── GED24 — Rétention légale / legal hold (gel anti-suppression) ─────────────

def _document_sous_legal_hold(document):
    """GED24 — True si une rétention légale ACTIVE couvre le document.

    Helper interne partagé par les gardes de suppression. Lecture en base de
    l'existence d'un `LegalHold` `actif=True` sur le document. Import paresseux
    pour éviter tout cycle."""
    from .models import LegalHold
    if document.pk is None:
        return False
    return LegalHold.objects.filter(
        document_id=document.pk, actif=True).exists()


def placer_legal_hold(document, *, user, motif=''):
    """GED24 — Place une RÉTENTION LÉGALE (legal hold) sur un document.

    Pose un `LegalHold` ACTIF qui GÈLE la suppression/purge du document tant
    qu'il reste actif (garde au niveau modèle `Document.delete()` + service).
    Ce gel SURCLASSE toute purge de politique de rétention (GED22) et reste une
    couche distincte de l'archivage write-once (GED23) — il ne fige QUE
    l'effacement (le document reste éditable) et est TEMPORAIRE (levable).

    Multi-tenant : `company` et `place_par` posés CÔTÉ SERVEUR (jamais lus du
    corps). `PermissionError` si l'utilisateur n'est pas de la société du
    document. IDEMPOTENT : si un hold actif existe déjà sur ce document, on le
    renvoie tel quel sans en créer un second (on ne duplique pas le gel).

    Renvoie le `LegalHold` actif (créé ou réutilisé).
    """
    from .models import LegalHold

    if document.company_id != getattr(user, 'company_id', None):
        raise PermissionError("Document inaccessible.")
    with transaction.atomic():
        # Idempotence : un hold actif existant tient lieu de gel — on ne pose
        # pas de doublon (le document est déjà gelé).
        existant = (LegalHold.objects
                    .select_for_update()
                    .filter(document=document, actif=True)
                    .first())
        if existant is not None:
            return existant
        return LegalHold.objects.create(
            company=document.company,
            document=document,
            place_par=user,
            motif=(motif or '').strip(),
            actif=True,
        )


def lever_legal_hold(document, *, user):
    """GED24 — Lève la/les rétention(s) légale(s) active(s) d'un document.

    Bascule tous les `LegalHold` ACTIFS du document en `actif=False` et trace
    `date_levee`/`leve_par` (on ne supprime jamais la trace d'un hold —
    historique conservé). Une fois le dernier hold actif levé, le document
    redevient supprimable (sauf autre protection, ex. GED23). IDEMPOTENT : sans
    hold actif, l'appel est un no-op (renvoie 0).

    Multi-tenant : `company` du document vérifiée côté serveur ; `leve_par`
    posé côté serveur. `PermissionError` si l'utilisateur n'est pas de la
    société du document.

    Renvoie le nombre de holds levés.
    """
    from django.utils import timezone
    from .models import LegalHold

    if document.company_id != getattr(user, 'company_id', None):
        raise PermissionError("Document inaccessible.")
    with transaction.atomic():
        actifs = list(LegalHold.objects
                      .select_for_update()
                      .filter(document=document, actif=True))
        for hold in actifs:
            hold.actif = False
            hold.date_levee = timezone.now()
            hold.leve_par = user
            hold.save(update_fields=['actif', 'date_levee', 'leve_par'])
        return len(actifs)


def assert_not_legal_hold(document):
    """GED24 — Garde : rejette la suppression si le document est sous hold actif.

    À appeler côté service avant toute suppression/purge/destruction de cycle de
    vie d'un document. La garde au niveau modèle (`Document.delete()`) est le
    filet ultime ; cette fonction permet de refuser TÔT avec un message clair
    (→ 403 dans la vue, jamais 500). Lève `LegalHoldError` si une rétention
    légale active couvre le document."""
    from .models import LEGAL_HOLD_MESSAGE, LegalHoldError
    if _document_sous_legal_hold(document):
        raise LegalHoldError(LEGAL_HOLD_MESSAGE)


# ── GED26 — Corbeille & restauration (soft-delete réversible) ────────────────

def mettre_en_corbeille(document, user):
    """GED26 — Place un document dans la CORBEILLE (soft-delete réversible).

    Renseigne `supprime_le`/`supprime_par` côté serveur : le document disparaît
    des listes par défaut (`documents_visible_to_user`) mais N'EST PAS effacé —
    il reste intégralement récupérable via `restaurer_de_corbeille`.

    Gardes (mêmes refus que la suppression réelle) :
      * GED23 — un document archivé légalement (write-once) NE PEUT PAS être mis
        en corbeille → lève `ArchivageLegalError` (→ 403, jamais 500) ;
      * GED24 — un document sous rétention légale ACTIVE (legal hold) NE PEUT
        PAS être mis en corbeille → lève `LegalHoldError` (→ 403).
    On vérifie ces gardes AVANT toute écriture : `Document.save()` bloque déjà
    toute écriture sur un document archivé (write-once), donc on refuse en amont
    avec un message clair plutôt que de laisser remonter une 500.

    IDEMPOTENT : un document déjà dans la corbeille est renvoyé tel quel (on ne
    réécrase ni la date ni l'auteur d'origine). Renvoie le document.
    """
    assert_not_archive_legalement(document)   # GED23 → ArchivageLegalError
    assert_not_legal_hold(document)           # GED24 → LegalHoldError
    if document.supprime_le is not None:
        # Déjà en corbeille : no-op (on préserve la trace d'origine).
        return document
    from django.utils import timezone
    document.supprime_le = timezone.now()
    document.supprime_par = user
    document.save(update_fields=['supprime_le', 'supprime_par', 'updated_at'])
    return document


def restaurer_de_corbeille(document):
    """GED26 — Restaure un document DEPUIS la corbeille (efface le soft-delete).

    Vide `supprime_le`/`supprime_par` : le document réapparaît dans les listes
    par défaut. IDEMPOTENT : un document qui n'est pas en corbeille est renvoyé
    tel quel (no-op). Aucune garde légale ici — restaurer ne fait que ANNULER un
    soft-delete (rien n'est effacé). Renvoie le document.
    """
    if document.supprime_le is None:
        return document
    document.supprime_le = None
    document.supprime_par = None
    document.save(update_fields=['supprime_le', 'supprime_par', 'updated_at'])
    return document


def purger_definitivement(document):
    """GED26 — Supprime DÉFINITIVEMENT un document depuis la corbeille (réel delete).

    Effacement RÉEL et irréversible — réservé aux documents DÉJÀ en corbeille
    (on ne purge jamais un document « vivant » par cette voie : il faut le mettre
    en corbeille d'abord). Les gardes légales restent respectées : `delete()` au
    niveau modèle refuse encore un document archivé (GED23) ou sous legal hold
    actif (GED24) → `ArchivageLegalError`/`LegalHoldError` (→ 403, jamais 500).

    Lève `ValueError` si le document n'est pas dans la corbeille. Renvoie None.
    """
    if document.supprime_le is None:
        raise ValueError(
            "Le document doit d'abord être dans la corbeille avant la purge "
            "définitive.")
    # Les gardes légales (GED23/GED24) sont posées dans `Document.delete()` —
    # filet ultime ; on les laisse lever telles quelles (traduites en 403).
    document.delete()


# ── GED27 — Modèles de documents (fusion/mailing → PDF WeasyPrint) ───────────
#
# Couche GÉNÉRIQUE de documents INTERNES (attestations, courriers, mailing) :
# un modèle porte un corps HTML avec des jetons ``{{ champ }}``, fusionné avec un
# dictionnaire de données puis rendu en PDF via WeasyPrint. SÉPARÉE et DISTINCTE
# du chemin `/proposal` (rule #4) — qui reste l'UNIQUE chemin des PDF de DEVIS
# client. On n'importe ni ne route jamais par le moteur premium ici.


def fusionner_modele(corps_html, contexte):
    """GED27 — Fusionne un corps HTML avec un contexte (substitution SÛRE).

    Substitue les jetons ``{{ champ }}`` du corps par les valeurs de `contexte`
    via le moteur de gabarit Django dans un contexte EXPLICITE et borné — JAMAIS
    d'``eval`` ni d'exécution de code arbitraire. Un jeton inconnu est rendu vide
    (comportement standard du moteur), jamais une fuite d'objet Python.

    Le `contexte` est un dictionnaire plat fourni par l'appelant (les données de
    fusion d'un courrier/mailing). Renvoie le HTML fusionné (str).
    """
    from django.template import Context, Template
    if not corps_html:
        return ''
    safe_contexte = dict(contexte or {})
    template = Template(str(corps_html))
    return template.render(Context(safe_contexte))


def _modele_html_document(modele, contexte):
    """GED27 — Construit le HTML complet (en-tête + corps fusionné) d'un modèle.

    Enrobe le corps fusionné dans un squelette HTML imprimable minimal (police,
    marges) — même esprit que le PDF interne de `contrats` (hors `/proposal`).
    """
    corps = fusionner_modele(modele.corps_html, contexte)
    titre = (modele.nom or 'Document').replace('<', '&lt;').replace('>', '&gt;')
    return (
        "<!DOCTYPE html><html lang='fr'><head><meta charset='utf-8'>"
        "<style>"
        "body{font-family:sans-serif;font-size:11pt;color:#1a1a1a;"
        "margin:2cm;line-height:1.5;}"
        "h1{font-size:16pt;border-bottom:2px solid #2b5cab;padding-bottom:6px;}"
        "</style></head><body>"
        f"<h1>{titre}</h1>"
        f"<div class='corps'>{corps}</div>"
        "</body></html>"
    )


def rendre_modele(modele, contexte):
    """GED27 — Fusionne un modèle avec un contexte et rend un PDF (bytes).

    Substitue les jetons ``{{ champ }}`` du `corps_html` (via `fusionner_modele`,
    contexte borné, jamais d'exécution de code), enrobe le résultat dans un
    squelette HTML imprimable, puis rend un PDF via WeasyPrint.

    PDF INTERNE/administratif (attestation, courrier, mailing) — ce N'EST PAS un
    PDF de devis : `/proposal` reste l'unique chemin des PDF de devis client
    (rule #4). On n'importe ni ne route jamais par le moteur premium.

    Import de WeasyPrint FONCTION-LOCAL et gardé : la lib est lourde (chargée à
    la demande) et le module reste import-safe là où WeasyPrint n'est pas
    chargeable. WeasyPrint EST une dépendance du projet ; s'il venait à manquer
    on lève une `RuntimeError` claire (jamais un crash silencieux).

    Renvoie les octets du PDF (commençant par ``%PDF``).
    """
    try:
        import weasyprint  # import local : lib lourde, chargée à la demande.
    except Exception as exc:  # pragma: no cover - WeasyPrint est installé.
        raise RuntimeError(
            "WeasyPrint est requis pour rendre un modèle de document en PDF "
            f"mais n'a pas pu être chargé : {exc}")
    html_str = _modele_html_document(modele, contexte)
    return weasyprint.HTML(string=html_str).write_pdf()


def generer_document(modele, contexte, *, company, created_by=None,
                     nom=None, cabinet_nom='Modèles', folder_nom='Mailing'):
    """GED27 — Rend un modèle en PDF et le DÉPOSE comme document GED.

    Fusionne + rend le PDF (`rendre_modele`) puis l'enregistre dans le
    référentiel GED en RÉUTILISANT le service de dépôt existant
    (`deposit_document`, lui-même fondé sur `create_document`/`add_version` et le
    stockage objet `records.storage`) — on ne duplique ni le stockage ni le
    versionnage. Multi-tenant : `company` posée CÔTÉ SERVEUR (jamais lue du corps
    de requête), cohérente avec le modèle.

    L'idempotence du dépôt est ancrée sur (`source_type`='ged.modeledocument',
    `source_id`=pk du modèle) : un mailing répété pour le MÊME modèle retrouve le
    document déjà déposé au lieu d'en dupliquer un (comportement standard de
    `deposit_document`). Renvoie `(document, created)`.
    """
    if modele.company_id is not None \
            and modele.company_id != getattr(company, 'id', company):
        raise ValueError("Le modèle doit appartenir à la même société.")
    pdf_bytes = rendre_modele(modele, contexte)
    return deposit_document(
        company=company,
        nom=nom or modele.nom,
        source_type='ged.modeledocument',
        source_id=modele.pk,
        contenu_bytes=pdf_bytes,
        mime='application/pdf',
        description=modele.description or '',
        cabinet_nom=cabinet_nom,
        folder_nom=folder_nom,
        created_by=created_by,
    )
