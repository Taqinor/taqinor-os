"""Vues des modèles de message WhatsApp (Paramètres → Messages).

Domaine « Messages & relances ». Extrait de l'ancien ``views.py`` sans aucun
changement d'endpoint ni de comportement (lecture tout rôle, écriture
Administrateur + Responsable promu, mêmes défauts FR/Darija, même audit)."""
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response

from authentication.permissions import IsAdminOrResponsableTier, IsAnyRole
from .models import (
    MESSAGE_TEMPLATE_DEFAULTS,
    MessageTemplate,
    SettingsAuditLog,
)


# Placeholders proposés par clé (aide à la saisie côté UI).
_MESSAGE_PLACEHOLDERS = {
    'devis_unique': ['{civilite}', '{nom}', '{reference}', '{lien}'],
    'devis_multi_entete': ['{civilite}', '{nom}', '{n}'],
    'devis_multi_ligne': ['{reference}', '{lien}'],
    'facture': ['{civilite}', '{nom}', '{reference}', '{lien}'],
    'relance': ['{civilite}', '{nom}', '{reference}', '{lien}'],
}


@api_view(['GET', 'PUT', 'PATCH'])
@permission_classes([IsAnyRole])
def messages_endpoint(request):
    """GET : lecture (tout rôle). PUT/PATCH : enregistrement (Administrateur +
    Responsable promu, jamais le palier limité)."""
    if request.method == 'GET':
        return _messages_list(request)
    if not IsAdminOrResponsableTier().has_permission(request, None):
        return Response(
            {'detail': "Réservé à l'administrateur ou au responsable."},
            status=status.HTTP_403_FORBIDDEN,
        )
    return _messages_save(request)


def _messages_list(request):
    """Tous les modèles de message (FR + Darija), défaut si non personnalisé."""
    company = request.user.company if request.user.company_id else None
    rows = {
        r.cle: r for r in MessageTemplate.objects.filter(company=company)
    } if company else {}
    out = []
    for cle, label in MessageTemplate.Cle.choices:
        row = rows.get(cle)
        default = MESSAGE_TEMPLATE_DEFAULTS.get(cle, '')
        out.append({
            'cle': cle,
            'label': label,
            'corps_fr': (row.corps_fr if row and row.corps_fr else default),
            'corps_darija': (row.corps_darija if row else ''),
            'default_fr': default,
            'placeholders': _MESSAGE_PLACEHOLDERS.get(cle, []),
        })
    return Response(out)


def _messages_save(request):
    """Enregistre un modèle de message pour la société (upsert par clé)."""
    company = request.user.company if request.user.company_id else None
    if company is None:
        return Response(
            {'detail': 'Société requise.'},
            status=status.HTTP_400_BAD_REQUEST,
        )
    cle = request.data.get('cle')
    valid = {c for c, _ in MessageTemplate.Cle.choices}
    if cle not in valid:
        return Response(
            {'detail': 'Clé de message inconnue.'},
            status=status.HTTP_400_BAD_REQUEST,
        )
    obj, _ = MessageTemplate.objects.get_or_create(company=company, cle=cle)
    before_fr, before_darija = obj.corps_fr, obj.corps_darija
    if 'corps_fr' in request.data:
        obj.corps_fr = request.data.get('corps_fr') or ''
    if 'corps_darija' in request.data:
        obj.corps_darija = request.data.get('corps_darija') or ''
    obj.save()
    if obj.corps_fr != before_fr:
        SettingsAuditLog.log_change(
            company=company, user=request.user, section='messages',
            field=cle, field_label=f'Message {cle} (FR)',
            old=before_fr, new=obj.corps_fr,
        )
    if obj.corps_darija != before_darija:
        SettingsAuditLog.log_change(
            company=company, user=request.user, section='messages',
            field=cle, field_label=f'Message {cle} (Darija)',
            old=before_darija, new=obj.corps_darija,
        )
    return Response({
        'cle': obj.cle, 'corps_fr': obj.corps_fr,
        'corps_darija': obj.corps_darija,
    })
