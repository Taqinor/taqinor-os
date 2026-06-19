"""Vues « Modèles de documents » — D2/N60/N67/N26/N59.

Éditeur des portions de texte du devis premium (Paramètres → Modèles de
documents). Lecture pour tout rôle ; écriture réservée à Admin/Responsable
promu. ``company`` est résolue côté serveur (jamais lue du corps). À chaque
sauvegarde modifiée, ``version`` est incrémentée (N67) et chaque champ modifié
est journalisé (SettingsAuditLog).
"""
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response

from authentication.permissions import IsAdminOrResponsableTier, IsAnyRole
from .models import SettingsAuditLog
from .models_documents import DEVIS_TEXT_KEYS, DocumentTemplates
from .serializers_documents import DocumentTemplatesSerializer
from .views_common import _audit_company


# Libellé FR par champ pour l'audit (N55).
_DOC_AUDIT_FIELDS = {
    'validite_badge_p1': "Validité (badge page 1)",
    'validite_onepage': "Validité (format une page)",
    'cgv_titre': "Conditions générales — titre",
    'cgv_bullets': "Conditions générales — puces",
    'garantie_titre': "Garanties — titre",
    'garantie_detail': "Garanties — détail",
    'garantie_perf_label': "Garanties — libellé performance",
    'bpa_titre': "Bon pour accord — titre",
    'bpa_mention': "Bon pour accord — mention",
    'acceptance_stamp': "Tampon d'acceptation — libellé",
}


def _templates(request):
    """DocumentTemplates de la société de l'utilisateur (get-or-create)."""
    return DocumentTemplates.get(
        company=request.user.company if request.user.company_id else None
    )


@api_view(['GET'])
@permission_classes([IsAnyRole])
def get_document_templates(request):
    obj = _templates(request)
    return Response(DocumentTemplatesSerializer(obj).data)


@api_view(['PUT', 'PATCH'])
@permission_classes([IsAdminOrResponsableTier])
def update_document_templates(request):
    obj = _templates(request)
    partial = request.method == 'PATCH'
    before = {f: getattr(obj, f, None) for f in DEVIS_TEXT_KEYS}
    serializer = DocumentTemplatesSerializer(
        obj, data=request.data, partial=partial,
        context={'request': request},
    )
    serializer.is_valid(raise_exception=True)
    updated = serializer.save()

    # Détecte un vrai changement (un seul champ suffit) → version + audit.
    changed = False
    company = _audit_company(request)
    for field, label in _DOC_AUDIT_FIELDS.items():
        old = before.get(field)
        new = getattr(updated, field, None)
        if old == new:
            continue
        changed = True
        SettingsAuditLog.log_change(
            company=company, user=request.user, section='documents',
            field=field, field_label=label, old=old, new=new,
        )
    if changed:
        # N67 — versionnement : nouvelle révision des textes.
        updated.version = (updated.version or 1) + 1
        updated.save(update_fields=['version'])

    return Response(DocumentTemplatesSerializer(updated).data)
