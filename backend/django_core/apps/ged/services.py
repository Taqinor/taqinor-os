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

from .models import Document, DocumentVersion, Folder


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


def create_document(*, company, folder, nom, description='', created_by=None):
    """Crée un document dans un dossier (société cohérente avec le dossier)."""
    if folder.company_id != getattr(company, 'id', company):
        raise ValueError("Le dossier doit appartenir à la même société.")
    return Document.objects.create(
        company=company, folder=folder, nom=nom,
        description=description, created_by=created_by)


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
