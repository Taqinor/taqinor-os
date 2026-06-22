"""Écritures / orchestration de la GED.

Point d'entrée des écritures cross-app (CLAUDE.md). La société est TOUJOURS
fournie par l'appelant (résolue côté serveur depuis `request.user.company`) —
jamais lue d'un corps de requête. Réutilise les conventions de stockage de
`records.storage` (clé MinIO `file_key`) sans réimplémenter le stockage.
"""
import hashlib

from django.db import transaction

from .models import Document, DocumentVersion, Folder


def compute_checksum(data):
    """SHA-256 hex d'un contenu binaire — sert à la déduplication."""
    if isinstance(data, str):
        data = data.encode('utf-8')
    return hashlib.sha256(data).hexdigest()


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
                checksum='', uploaded_by=None):
    """Ajoute une nouvelle version à un document (numéro auto-incrémenté).

    Le numéro de version est calculé côté serveur (dernière + 1) et la société
    est forcée à celle du document (jamais du corps de requête). `checksum`
    permet la déduplication : un appelant peut vérifier au préalable s'il
    existe déjà une version de même empreinte (voir `find_duplicate`).
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
