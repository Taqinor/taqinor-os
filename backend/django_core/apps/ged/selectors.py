"""Lectures de la GED — point d'entrée pour les lectures cross-app.

Conformément au CLAUDE.md (frontière cross-app), une autre app qui a besoin de
LIRE la GED passe par ces fonctions plutôt que d'importer `ged.models`.
Toutes les lectures sont bornées à une société.
"""
from .models import Cabinet, Document, DocumentLien, DocumentVersion, Folder


def cabinets_for_company(company):
    """Cabinets d'une société (QuerySet, ordonné par nom)."""
    return Cabinet.objects.filter(company=company)


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
