"""Vue du journal d'audit des paramètres (N55) — LECTURE SEULE.

Domaine « Avancé / Journal d'audit ». Ouverte à l'Administrateur ET au
Responsable (promu) — comme le reste de l'écran Paramètres — jamais au palier
limité."""
from django.utils.dateparse import parse_date
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import (
    OpenApiParameter, extend_schema, inline_serializer,
)
from rest_framework import serializers, status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response

from authentication.permissions import IsAdminOrResponsableTier, IsAdminRole
from .models import SettingsAuditLog
from .serializers import SettingsAuditLogSerializer


def _entier(request, cle, defaut, mini=0):
    """APAR32 — paramètre entier ≥ ``mini`` ; illisible ⇒ ValueError (400)."""
    brut = request.GET.get(cle)
    if brut in (None, ''):
        return defaut
    try:
        valeur = int(brut)
    except (TypeError, ValueError):
        raise ValueError(cle)
    if valeur < mini:
        raise ValueError(cle)
    return valeur


def _date(request, cle):
    brut = request.GET.get(cle)
    if not brut:
        return None
    try:
        valeur = parse_date(brut)
    except ValueError:
        raise ValueError(cle)
    if valeur is None:
        raise ValueError(cle)
    return valeur


def _q(nom, type_, description, **kw):
    return OpenApiParameter(
        nom, type_, OpenApiParameter.QUERY, required=False,
        description=description, **kw)


@extend_schema(
    parameters=[
        _q('section', OpenApiTypes.STR, 'Section du journal.'),
        _q('field', OpenApiTypes.STR, 'Champ modifié.'),
        _q('user', OpenApiTypes.INT, "Identifiant de l'auteur."),
        _q('date_debut', OpenApiTypes.DATE, 'Date de début (incluse).'),
        _q('date_fin', OpenApiTypes.DATE, 'Date de fin (incluse).'),
        _q('limit', OpenApiTypes.INT, 'Taille de page (1 à 500, défaut 100).'),
        _q('offset', OpenApiTypes.INT, 'Décalage (défaut 0).'),
    ],
    responses=inline_serializer('JournalAuditPage', {
        'count': serializers.IntegerField(),
        'results': SettingsAuditLogSerializer(many=True),
        'next': serializers.IntegerField(allow_null=True),
    }))
@api_view(['GET'])
@permission_classes([IsAdminOrResponsableTier])
def settings_audit_log(request):
    """Journal des changements de paramètres (qui, quoi, quand).

    Filtres : `?section=...`, `?user=<id>`, `?field=<champ>`,
    `?date_debut=AAAA-MM-JJ`, `?date_fin=AAAA-MM-JJ` (incluses).
    Pagination (APAR32) : `?limit=N` (défaut 100, max 500) + `?offset=N` ;
    `count` = total RÉEL filtré (plus la taille de la page), `next` = offset
    de la page suivante (``None`` en fin de journal). Un `user`/`limit`/
    `offset`/date illisible ⇒ 400, jamais 500.
    Company-scopé. Sections connues (FG18) :
    `profil`, `messages`, `roles`, `utilisateurs`, `automatisations`.
    L'endpoint `sections/` retourne la liste des sections présentes pour
    alimenter le filtre côté UI.
    """
    try:
        limit = min(_entier(request, 'limit', 100, mini=1), 500)
        offset = _entier(request, 'offset', 0)
        user_id = _entier(request, 'user', None)
        date_debut = _date(request, 'date_debut')
        date_fin = _date(request, 'date_fin')
    except (TypeError, ValueError) as exc:
        cle = exc.args[0] if exc.args and exc.args[0] in (
            'limit', 'offset', 'user', 'date_debut', 'date_fin') else None
        return Response(
            {'detail': 'Paramètre de filtre invalide'
                       + (f' : « {cle} ».' if cle else '.')},
            status=status.HTTP_400_BAD_REQUEST)
    company = request.user.company if request.user.company_id else None
    qs = SettingsAuditLog.objects.filter(company=company)
    section = request.GET.get('section')
    if section:
        qs = qs.filter(section=section)
    if user_id is not None:
        qs = qs.filter(user_id=user_id)
    champ = request.GET.get('field')
    if champ:
        qs = qs.filter(field=champ)
    if date_debut:
        qs = qs.filter(timestamp__date__gte=date_debut)
    if date_fin:
        qs = qs.filter(timestamp__date__lte=date_fin)
    total = qs.count()
    page = qs.select_related('user').order_by(
        '-timestamp', '-id')[offset:offset + limit]
    data = SettingsAuditLogSerializer(page, many=True).data
    suivant = offset + limit if offset + limit < total else None
    return Response({'count': total, 'results': data, 'next': suivant})


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


@extend_schema(responses=inline_serializer('JournalAuditSections', {
    'sections': inline_serializer('JournalAuditSection', {
        'value': serializers.CharField(),
        'label': serializers.CharField(),
    }, many=True),
}))
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


@extend_schema(request=None, responses=inline_serializer('PurgeAudit', {
    'audit_deleted': serializers.IntegerField(),
    'settings_deleted': serializers.IntegerField(),
}))
@api_view(['POST'])
@permission_classes([IsAdminRole])
def purge_audit_retention(request):
    """FG26 — purge le journal d'audit de la société au-delà de sa fenêtre de
    rétention (``CompanyProfile.audit_retention_days``). Admin uniquement.

    No-op (0, 0) si la société n'a pas fixé de fenêtre (rétention illimitée).
    APAR3 : plancher légal 365 j, purge journalisée au nom de l'admin ; une
    erreur de suppression remonte (500 journalisé), jamais avalée."""
    from .retention import purge_company_audit
    company = request.user.company if request.user.company_id else None
    if company is None:
        return Response({'detail': 'Aucune société.'}, status=400)
    audit_deleted, settings_deleted = purge_company_audit(
        company, user=request.user)
    return Response({
        'audit_deleted': audit_deleted,
        'settings_deleted': settings_deleted,
    })
