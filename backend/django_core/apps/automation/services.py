"""Services XKB2 — demandes d'approbation ad-hoc (types + soumission).

Toute la logique de validation/soumission des ``ApprovalRequest`` vit ici
pour que les vues restent minces. Reste à l'intérieur de ``apps.automation`` ;
utilise ``apps.records`` (app fondation, exemptée de la règle de frontière
cross-app) directement pour les pièces jointes génériques.
"""
from django.contrib.contenttypes.models import ContentType

from .models import ApprovalRequest


class ApprovalError(Exception):
    """Erreur métier FR destinée à être renvoyée telle quelle en 400."""


def _approval_request_content_type():
    return ContentType.objects.get_for_model(ApprovalRequest)


def count_attachments(request_obj):
    """Nombre de pièces jointes (records.Attachment) sur cette demande."""
    from apps.records.models import Attachment
    return Attachment.objects.filter(
        content_type=_approval_request_content_type(),
        object_id=request_obj.pk,
    ).count()


def attach_file(request_obj, file, *, user, company):
    """Stocke un fichier (records.storage) et le rattache à la demande."""
    from apps.records.models import Attachment
    from apps.records.storage import store_attachment

    meta, err = store_attachment(file)
    if err:
        raise ApprovalError(err)
    return Attachment.objects.create(
        company=company,
        content_type=_approval_request_content_type(),
        object_id=request_obj.pk,
        uploaded_by=user,
        **meta,
    )


def submit_request(*, request_type, demandeur, company, payload):
    """Valide (champs requis du type) puis crée une ``ApprovalRequest``.

    Lève ``ApprovalError`` (message FR) si un champ requis manque.
    """
    errors = request_type.validate_payload(payload)
    if errors:
        raise ApprovalError(' '.join(errors))
    return ApprovalRequest.objects.create(
        company=company,
        request_type=request_type,
        demandeur=demandeur,
        payload=payload or {},
    )
