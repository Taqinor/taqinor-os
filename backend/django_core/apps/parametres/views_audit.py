"""Vue du journal d'audit des paramètres (N55) — LECTURE SEULE.

Domaine « Avancé / Journal d'audit ». Ouverte à l'Administrateur ET au
Responsable (promu) — comme le reste de l'écran Paramètres — jamais au palier
limité."""
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response

from authentication.permissions import IsAdminOrResponsableTier
from .models import SettingsAuditLog
from .serializers import SettingsAuditLogSerializer


@api_view(['GET'])
@permission_classes([IsAdminOrResponsableTier])
def settings_audit_log(request):
    """Journal des changements de paramètres (qui, quoi, quand).

    Filtres : `?section=profil|messages`, `?user=<id>`, `?limit=N`
    (défaut 100, max 500). Company-scopé.
    """
    company = request.user.company if request.user.company_id else None
    qs = SettingsAuditLog.objects.filter(company=company)
    section = request.GET.get('section')
    if section:
        qs = qs.filter(section=section)
    user_id = request.GET.get('user')
    if user_id:
        qs = qs.filter(user_id=user_id)
    try:
        limit = min(int(request.GET.get('limit', 100)), 500)
    except (TypeError, ValueError):
        limit = 100
    data = SettingsAuditLogSerializer(qs[:limit], many=True).data
    return Response({'count': len(data), 'results': data})
