"""Vue du journal d'audit des paramètres (N55) — LECTURE SEULE.

Domaine « Avancé / Journal d'audit ». Ouverte à l'Administrateur ET au
Responsable (promu) — comme le reste de l'écran Paramètres — jamais au palier
limité."""
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response

from authentication.permissions import IsAdminOrResponsableTier, IsAdminRole
from .models import SettingsAuditLog
from .serializers import SettingsAuditLogSerializer


@api_view(['GET'])
@permission_classes([IsAdminOrResponsableTier])
def settings_audit_log(request):
    """Journal des changements de paramètres (qui, quoi, quand).

    Filtres : `?section=...`, `?user=<id>`, `?limit=N` (défaut 100, max 500).
    Company-scopé. Sections connues (FG18) :
    `profil`, `messages`, `roles`, `utilisateurs`, `automatisations`.
    L'endpoint `sections/` retourne la liste des sections présentes pour
    alimenter le filtre côté UI.
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


# FG18 — sections connues du journal d'audit (pour alimenter le filtre UI).
# Curées (ordre d'affichage) + complétées par celles réellement présentes en
# base pour la société, afin que le filtre n'omette jamais une section.
KNOWN_AUDIT_SECTIONS = [
    {'value': 'profil', 'label': 'Profil entreprise'},
    {'value': 'messages', 'label': 'Modèles de message'},
    {'value': 'roles', 'label': 'Rôles & permissions'},
    {'value': 'utilisateurs', 'label': 'Utilisateurs'},
    {'value': 'automatisations', 'label': 'Automatisations'},
    {'value': 'tarification', 'label': 'Tarification & ROI'},
]


@api_view(['GET'])
@permission_classes([IsAdminOrResponsableTier])
def settings_audit_sections(request):
    """Liste des sections du journal d'audit (filtre UI). Company-scopée.

    Renvoie les sections curées connues + toute section supplémentaire
    réellement présente en base (libellée par sa valeur brute)."""
    company = request.user.company if request.user.company_id else None
    present = set(
        SettingsAuditLog.objects.filter(company=company)
        .values_list('section', flat=True).distinct())
    known_values = {s['value'] for s in KNOWN_AUDIT_SECTIONS}
    sections = list(KNOWN_AUDIT_SECTIONS)
    for extra in sorted(present - known_values):
        sections.append({'value': extra, 'label': extra})
    return Response({'sections': sections})


@api_view(['POST'])
@permission_classes([IsAdminRole])
def purge_audit_retention(request):
    """FG26 — purge le journal d'audit de la société au-delà de sa fenêtre de
    rétention (``CompanyProfile.audit_retention_days``). Admin uniquement.

    No-op (0, 0) si la société n'a pas fixé de fenêtre (rétention illimitée)."""
    from .retention import purge_company_audit
    company = request.user.company if request.user.company_id else None
    if company is None:
        return Response({'detail': 'Aucune société.'}, status=400)
    audit_deleted, settings_deleted = purge_company_audit(company)
    return Response({
        'audit_deleted': audit_deleted,
        'settings_deleted': settings_deleted,
    })
